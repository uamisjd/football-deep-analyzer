"""Backfill FotMob: le distinte delle partite passate per gli incroci in panchina (D, `docs/80`).

Perché serve: la riga «incroci in panchina con l'allenatore avversario» (`docs/78` §7) conta le
gare in cui i due allenatori si sono trovati su **panchine opposte**, qualunque coppia di club,
prima di questa partita. L'archivio del collector copre solo la finestra recente (411 gare
finite, tutte della stagione in corso): con otto giornate giocate nessuna coppia si è ancora
incontrata due volte, e la riga infatti resta muta su tutte le 164 panchine
(`audit_panchina.py`: `incroci_panchina_assenti 164`). Questo script scarica le distinte
(`matchDetails`) delle partite **finite delle stagioni precedenti** delle sette leghe e salva:

- le righe ``role="coach"`` in ``lineup`` (chi sedeva in panchina, partita per partita);
- una riga in ``match_storico`` (id, lega, stagione, giornata, data, squadre, gol, stato).

Non tocca ``fixtures``: il resto del sito continua a vedere solo la stagione in corso. L'unico
consumatore dello storico è il calcolo degli incroci in ``analysis.py``, che senza
``match_storico`` si comporta esattamente come prima (tabella assente → DataFrame vuoto).

Uso (nell'ambiente dell'utente, dopo ``fda collect``; richiede rete verso fotmob.com):

    .venv/bin/python scripts/backfill_fotmob.py --riepilogo        # cosa manca, senza scaricare
    .venv/bin/python scripts/backfill_fotmob.py --stagioni 2025/2026
    .venv/bin/python scripts/backfill_fotmob.py --stagioni 2024/2025 --limite 1500
    .venv/bin/python scripts/backfill_fotmob.py --riepilogo        # quanti incroci sono emersi

Poi ``fda build`` e i gate. Il run è **ripartibile**: salta le partite già in ``match_storico``
(o già presenti in ``lineup``), quindi si può spezzare in più sere con ``--limite``. Il budget
``max_requests_per_run`` di ``config/sources.yaml`` (600) vale per il run giornaliero: qui il
tetto è ``--budget`` (default: nessuno), perché un backfill non è un run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from fda.config import leagues as tutte_le_leghe
from fda.config import season, source
from fda.http import HttpClient
from fda.sources.fotmob import FotMobClient, bundle_to_dicts
from fda.store import Store

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "processed"
TABELLA = "match_storico"


def stagioni_precedenti(corrente: str, quante: int) -> list[str]:
    """Le ``quante`` stagioni prima di quella corrente, in formato FotMob («2025/2026»)."""
    inizio = int(str(corrente).split("/")[0])
    return [f"{anno}/{anno + 1}" for anno in range(inizio - 1, inizio - 1 - quante, -1)]


def partite_da_fare(fixtures_stagione: list, gia_fatte: set[int], in_lineup: set[int]) -> list:
    """Partite finite non ancora in archivio, in ordine di data (le più recenti per prime)."""
    out: list = []
    ordinate = sorted(fixtures_stagione,
                      key=lambda f: f.utc_kickoff or pd.Timestamp.min.tz_localize("UTC"),
                      reverse=True)
    for f in ordinate:
        if f.status != "finished" or f.utc_kickoff is None:
            continue
        if f.match_id in gia_fatte or f.match_id in in_lineup:
            continue
        out.append(f)
    return out


def riga_storico(f) -> dict:
    """Una partita dell'archivio storico: quanto basta agli incroci (e a leggerli, un domani)."""
    return {"match_id": int(f.match_id), "league_id": int(f.league_id),
            "stagione": str(f.season), "giornata": f.round,
            "utc_kickoff": f.utc_kickoff, "home_id": int(f.home_id), "home_name": f.home_name,
            "away_id": int(f.away_id), "away_name": f.away_name,
            "home_goals": f.home_goals, "away_goals": f.away_goals, "status": f.status}


def backfill(client: FotMobClient, store: Store, leghe: list, stagioni: list[str], *,
             limite: int | None = None, tutti_i_ruoli: bool = False, flush: int = 50,
             dry_run: bool = False, log=print) -> dict:
    """Scarica le distinte delle partite finite delle ``stagioni`` e le salva in Parquet.

    Ritorna un riepilogo con i contatori del run: è il contratto usato dai test offline
    (client finto) e dalla stampa finale.
    """
    lineup_vivo = store.read("lineup")
    in_lineup = (set(lineup_vivo["match_id"].astype(int)) if not lineup_vivo.empty
                 else set())
    storico = store.read(TABELLA)
    gia_fatte = set(storico["match_id"].astype(int)) if not storico.empty else set()

    rep = {"stagioni": list(stagioni), "partite_candidate": 0, "partite_saltate": 0,
           "partite_fatte": 0, "righe_coach": 0, "senza_coach": 0, "errori": 0,
           "richieste": 0, "cache": 0, "interrotto": False, "client": client}
    righe_storico: list[dict] = []
    righe_lineup: list[dict] = []
    fatte_in_questo_run = 0

    def scarica(f) -> bool:
        """Una partita: distinta → righe coach + riga storica. False se la richiesta fallisce."""
        try:
            raw = client.match_details_raw(int(f.match_id), finished_hint=True)
        except Exception as exc:  # noqa: BLE001 — rete rotta o budget: si registra e si va avanti
            rep["errori"] += 1
            log(f"    ! {f.match_id}: {exc}")
            return False
        bundle = client.parse_match(raw)
        tabelle = bundle_to_dicts(bundle)
        righe = tabelle.get("lineup") or []
        if not tutti_i_ruoli:
            righe = [r for r in righe if r.get("role") == "coach"]
        righe_lineup.extend(righe)
        rep["righe_coach"] += len(righe)
        rep["senza_coach"] += int(not righe)
        # la riga storica viene dai dati del **calendario** (gol e stato definitivi), non dal
        # dettaglio: se un dettaglio arrivasse senza punteggio, la partita resta leggibile
        righe_storico.append(riga_storico(f))
        return True

    def scrivi() -> None:
        nonlocal righe_lineup, righe_storico
        if not righe_lineup and not righe_storico:
            return
        if righe_lineup:
            store.upsert("lineup", righe_lineup, replace_by="match_id")
        if righe_storico:
            store.upsert(TABELLA, righe_storico)
        righe_lineup, righe_storico = [], []

    for lg in leghe:
        if rep["interrotto"]:
            break
        for stag in stagioni:
            try:
                fixtures = client.parse_fixtures(lg.fotmob_id, client.fixtures_raw(lg.fotmob_id, stag),
                                                 season_str=stag)
            except Exception as exc:  # noqa: BLE001 — una stagione illeggibile non ferma il resto
                rep["errori"] += 1
                log(f"  {lg.key} {stag}: calendario non disponibile ({exc})")
                continue
            finite = [f for f in fixtures if f.status == "finished" and f.utc_kickoff is not None]
            da_fare = partite_da_fare(fixtures, gia_fatte, in_lineup)
            rep["partite_candidate"] += len(da_fare)
            rep["partite_saltate"] += len(finite) - len(da_fare)
            log(f"  {lg.key} {stag}: {len(finite)} gare finite · {len(da_fare)} da scaricare "
                f"({len(finite) - len(da_fare)} già in archivio)")
            if dry_run:
                continue
            for f in da_fare:
                if limite is not None and fatte_in_questo_run >= limite:
                    rep["interrotto"] = True
                    break
                if not scarica(f):
                    if rep["errori"] > 20:
                        rep["interrotto"] = True
                        break
                    continue
                gia_fatte.add(int(f.match_id))
                fatte_in_questo_run += 1
                rep["partite_fatte"] += 1
                if rep["partite_fatte"] % flush == 0:
                    scrivi()
                    log(f"    … {rep['partite_fatte']} partite salvate")
            scrivi()
            if rep["interrotto"]:
                break
        if rep["interrotto"]:
            break
    scrivi()
    rep["richieste"] = client.http.stats.requests
    rep["cache"] = client.http.stats.cache_hits
    return rep


def riepilogo_incroci(store: Store, log=print) -> dict:
    """Quante panchine hanno davvero un incrocio, con lo storico ora in archivio.

    È la risposta alla domanda «basta così?»: per ogni gara in programma con una previsione,
    conta le coppie di allenatori che hanno già condiviso il campo su panchine opposte. Se
    resta a zero, le stagioni scaricate non coprono le carriere degli allenatori attuali.
    """
    storico = store.read(TABELLA)
    lineup = store.read("lineup")
    fixture = store.read("fixtures")
    if storico.empty or lineup.empty:
        log("  nessuno storico in archivio: niente da riepilogare")
        return {"panchine": 0, "con_incrocio": 0}
    media = pd.concat([fixture[["match_id", "utc_kickoff"]], storico[["match_id", "utc_kickoff"]]],
                      ignore_index=True).dropna().drop_duplicates("match_id").set_index("match_id")
    co = lineup[lineup.role == "coach"].copy()
    co["ko"] = co.match_id.map(media["utc_kickoff"])
    co = co.dropna(subset=["ko"])
    panchine = 0
    con = 0
    for f in fixture[fixture.status == "scheduled"].itertuples(index=False):
        kick = pd.Timestamp(f.utc_kickoff)
        for lato in ("home", "away"):
            tid = f.home_id if lato == "home" else f.away_id
            suo = co[(co.team_id == tid) & (co.ko < kick)] if not co.empty else co
            if suo.empty:
                continue
            cur = suo.iloc[-1].player_id
            opp = co[(co.team_id == (f.away_id if lato == "home" else f.home_id))
                     & (co.ko < kick)]
            if opp.empty:
                continue
            oid = opp.iloc[-1].player_id
            panchine += 1
            miei = set(suo[suo.player_id == cur].match_id)
            suoi = set(opp[opp.player_id == oid].match_id)
            if miei & suoi:
                con += 1
    log(f"  panchine in programma: {panchine} · con almeno un incrocio nello storico: {con}")
    return {"panchine": panchine, "con_incrocio": con}


def main(argv: list[str] | None = None) -> int:
    cfg = source("fotmob")
    ap = argparse.ArgumentParser(description="Backfill FotMob per gli incroci in panchina (docs/80)")
    ap.add_argument("--leghe", default="", help="chiavi separate da virgola (default: tutte)")
    ap.add_argument("--stagioni", default="", help="es. «2024/2025,2025/2026» (default: le 2 precedenti)")
    ap.add_argument("--quante-stagioni", type=int, default=2, help="quante stagioni, se --stagioni è vuoto")
    ap.add_argument("--limite", type=int, default=None, help="partite da scaricare in questo run")
    ap.add_argument("--budget", type=int, default=0, help="tetto di richieste (0 = nessuno)")
    ap.add_argument("--rate", type=float, default=float(cfg.get("rate_limit_s", 1.0)),
                    help="pausa fra le richieste (default: da config/sources.yaml)")
    ap.add_argument("--tutti-i-ruoli", action="store_true",
                    help="salva l'intero lineup, non solo gli allenatori")
    ap.add_argument("--dry-run", action="store_true", help="conta le partite, non scarica")
    ap.add_argument("--riepilogo", action="store_true",
                    help="solo il riepilogo degli incroci, senza scaricare")
    ap.add_argument("--data", default=str(DEFAULT_DATA), help="cartella dei Parquet")
    ap.add_argument("--flush", type=int, default=50, help="scrive su disco ogni N partite")
    args = ap.parse_args(argv)

    store = Store(Path(args.data))
    if args.riepilogo:
        riepilogo_incroci(store)
        return 0
    chiavi = [k.strip() for k in args.leghe.split(",") if k.strip()]
    leghe = tutte_le_leghe(chiavi or None)
    stagioni = ([s.strip() for s in args.stagioni.split(",") if s.strip()]
                or stagioni_precedenti(season(), args.quante_stagioni))
    print(f"stagioni: {', '.join(stagioni)} · leghe: {', '.join(lg.key for lg in leghe)}")
    http = HttpClient(name="fotmob", rate_limit_s=args.rate,
                      headers=dict(cfg.get("headers", {})),
                      max_requests=args.budget or None)
    client = FotMobClient(client=http)
    rep = backfill(client, store, leghe, stagioni, limite=args.limite,
                   tutti_i_ruoli=args.tutti_i_ruoli, flush=args.flush, dry_run=args.dry_run)
    print(f"\npartite da scaricare: {rep['partite_candidate']} "
          f"(già in archivio: {rep['partite_saltate']})"
          + ("  [dry-run: nessuna richiesta]" if args.dry_run else ""))
    if not args.dry_run:
        print(f"partite salvate: {rep['partite_fatte']} · righe coach: {rep['righe_coach']} "
              f"· dettagli senza allenatore: {rep['senza_coach']} · errori: {rep['errori']}")
        print(f"richieste: {rep['richieste']} (cache: {rep['cache']})")
        if rep["interrotto"]:
            print("run interrotto dal --limite: rilanciare con lo stesso comando per continuare")
        print()
        riepilogo_incroci(store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
