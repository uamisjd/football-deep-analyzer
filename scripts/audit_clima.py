"""Audit 360° della card «Clima del club» (revisione del 2026-10-11, `docs/81`).

Misura su **tutte** le schede pre-partita di ``site/partite`` che cosa la card propone e
come: i segnali pubblicati per tipo e per tono, quelli che il ricalcolo dai Parquet non
conferma, i segnali mancanti, la fedeltà della nota alle soglie del codice, e tre difetti
strutturali cercati apposta — contatori troncati dalla finestra di forma, ambiguità di
perimetro (campionato vs coppe) e «panchina nuova» senza scadenza.

L'HTML si legge **com'è** e ogni segnale si ricostruisce con strade diverse da quelle del
generatore (mai ``club_mood``): calendario+coppe per riposo/congestione, forma di stagione
intera per le strisce, Understat **e** FotMob (Poisson scritto qui) per xPTS, distinta e
statistiche di stagione per l'infermeria, `lineup`+calendario per la panchina.

Uso: ``.venv/bin/python scripts/audit_clima.py`` (dopo ``fda build``).
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from html import unescape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "partite"
DATA = ROOT / "data" / "processed"
SRC = ROOT / "src" / "fda" / "site" / "analysis.py"

CARD = re.compile(r'<div class="card" id="clima">(.*?)(?=<div class="card"|<footer)', re.DOTALL)
BLOCCO = re.compile(r'<p style="margin:0 0 6px"><b>')
LI = re.compile(r'<li class="mood-(bad|warn|good)"><span class="small">(.*?)</span></li>', re.DOTALL)

SD_XPTS = 1.133          # σ di (punti − xPTS) su una gara-squadra (docs/64 §2.2)
MIN_GARE_XPTS = 3        # sotto le 3 gare nessun verdetto xPTS
MAX_FORMA = 5            # finestra di `MatchAnalysis.form` (default n=5)


def testo(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def striscia(risultati: list[str], valore: str) -> int:
    """Quante volte ``valore`` chiude la sequenza (dall'ultima gara all'indietro)."""
    n = 0
    for r in reversed(risultati):
        if r == valore:
            n += 1
        else:
            break
    return n


def striscia_fino_a(risultati: list[str], diverso: str) -> int:
    """Gare consecutive dall'ultima in cui il risultato **non** è ``diverso``.

    «non vince da N» conta tutte le gare dall'ultima vittoria in poi — pareggi e sconfitte
    mescolati — non solo le une o solo le altre: con ``striscia(N) + striscia(P)`` quattro
    pareggi dopo una sconfitta contavano 4 invece di 5 (bug dell'audit del 2026-10-11, visto
    su Go Ahead Eagles–Sparta Rotterdam). E una striscia non è una somma: ``sum(1 for r in
    reversed(ris) if r != "V")`` senza ``break`` conta tutta la lista.
    """
    n = 0
    for r in reversed(risultati):
        if r != diverso:
            n += 1
        else:
            break
    return n


def poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def xpts_da_xg(lh: float, la: float, k_max: int = 15) -> tuple[float, float]:
    """xPTS attesi della casa e della trasferta dai soli xG (Poisson indipendente).

    Riscrittura dalla definizione di :meth:`MatchAnalysis._poisson_xpts`: qui non si importa
    nulla del generatore, si sommano le masse di probabilità a mano.
    """
    p_draw = sum(poisson_pmf(k, lh) * poisson_pmf(k, la) for k in range(k_max))
    p_home = sum(poisson_pmf(i, lh) * sum(poisson_pmf(j, la) for j in range(i))
                 for i in range(k_max))
    p_away = sum(poisson_pmf(j, la) * sum(poisson_pmf(i, lh) for i in range(j))
                 for j in range(k_max))
    return 3 * p_home + p_draw, 3 * p_away + p_draw


def soglie_codice() -> dict[str, float]:
    """Le soglie della card lette dal codice (parità nota↔codice, non dal generatore)."""
    src = SRC.read_text(encoding="utf-8")
    out: dict[str, float] = {}
    for nome in ("MOOD_LOSS_STREAK", "MOOD_NOWIN", "MOOD_UNBEATEN", "MOOD_DRY",
                 "MOOD_ABSENT_N", "MOOD_ABSENT_STARTERS", "MOOD_ABSENT_CONTRIB",
                 "MOOD_REST_SHORT", "MOOD_REST_VERY_SHORT", "MOOD_CONGEST_DAYS",
                 "MOOD_CONGEST_N"):
        m = re.search(rf"^\s*{nome}\s*=\s*([0-9.]+)", src, re.MULTILINE)
        if m:
            out[nome] = float(m.group(1))
    return out


def main() -> int:
    if not SITE.exists():
        print("nessuna site/partite: esegui prima `fda build`")
        return 1
    from fda.teams import canonical as canon

    fx = pd.read_parquet(DATA / "fixtures.parquet")
    cup = pd.read_parquet(DATA / "cup_fixtures.parquet")
    lu = pd.read_parquet(DATA / "lineup.parquet")
    ps = pd.read_parquet(DATA / "player_stats.parquet")
    mi = pd.read_parquet(DATA / "match_info.parquet")
    us = pd.read_parquet(DATA / "understat_team_matches.parquet")

    for d in (fx, cup, mi):
        if "utc_kickoff" in d.columns:
            d["ko"] = pd.to_datetime(d.utc_kickoff, utc=True, errors="coerce")
        d["home_goals"] = pd.to_numeric(d.get("home_goals"), errors="coerce")
        d["away_goals"] = pd.to_numeric(d.get("away_goals"), errors="coerce")
    for col in ("home_xg", "away_xg"):
        if col in mi.columns:
            mi[col] = pd.to_numeric(mi[col], errors="coerce")
    fx = fx.dropna(subset=["ko"])
    cup = cup.dropna(subset=["ko"])
    us["_nome"] = us.team_name.map(canon)
    us["_data"] = pd.to_datetime(us.date, utc=True, errors="coerce")

    soglie = soglie_codice()

    # statistiche giocatore di stagione: totale per (squadra, nome) — niente cache del generatore
    pnum = ps.assign(num=pd.to_numeric(ps.value, errors="coerce")).dropna(subset=["num"])
    agg = (pnum.groupby(["team_id", "player_name", "key"]).num.sum()
           .unstack("key").reset_index())

    esiti: dict[str, list[str]] = {
        "xpts": [], "infermeria": [], "riposo": [], "congestione": [], "striscia": [],
        "panchina": [], "punteggio_mancante": [], "annotazione": [],
    }
    difetti: dict[str, list[str]] = {
        "troppo_corta": [], "perimetro_coppe_verdetto": [], "panchina_vecchia": [],
        "nota_disallineata": [], "tono_non_dichiarato": [],
    }
    agg_tipi: Counter[str] = Counter()
    agg_toni: Counter[str] = Counter()
    per_lega: Counter[str] = Counter()
    coda_fredda: list[int] = []
    nota_osservata = 0

    for pg in sorted(SITE.glob("*.html")):
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html:
            continue
        m = CARD.search(html)
        if not m:
            esiti["annotazione"].append(f"{pg.stem}: card assente su scheda pre")
            continue
        # split: [0] prefisso della card, [1] blocco casa, [2] blocco trasferta + nota
        blocchi = BLOCCO.split(m.group(1))
        nota = testo(blocchi[-1]) if blocchi else ""
        nota_osservata += 1
        # parità nota ↔ codice: ogni soglia dichiarata deve valere nel codice
        attesi_nota = {
            f"{int(soglie.get('MOOD_LOSS_STREAK', 0))} sconfitte consecutive": "MOOD_LOSS_STREAK",
            f"{int(soglie.get('MOOD_NOWIN', 0))} gare senza vittoria": "MOOD_NOWIN",
            f"{int(soglie.get('MOOD_UNBEATEN', 0))} imbattute": "MOOD_UNBEATEN",
            f"{int(soglie.get('MOOD_DRY', 0))} gare senza gol": "MOOD_DRY",
            f"{int(soglie.get('MOOD_ABSENT_N', 0))} assenti": "MOOD_ABSENT_N",
            f"{int(soglie.get('MOOD_ABSENT_STARTERS', 0))} titolari": "MOOD_ABSENT_STARTERS",
            "0,5 xG+xA/gara": "MOOD_ABSENT_CONTRIB",
            f"{int(soglie.get('MOOD_REST_SHORT', 0))} giorni": "MOOD_REST_SHORT",
            f"{int(soglie.get('MOOD_CONGEST_N', 0))} gare in "
            f"{int(soglie.get('MOOD_CONGEST_DAYS', 0))} giorni": "MOOD_CONGEST_N",
            "1,13": "XPTS_NOISE_SD",
            "3 gare al massimo": "MOOD_COACH_NEW",
        }
        for frase, chiave in attesi_nota.items():
            if frase not in nota:
                difetti["nota_disallineata"].append(f"{pg.stem}: nota senza «{frase}» ({chiave})")
        if not all(x in nota for x in ("rosso", "ambra", "verde")):
            difetti["tono_non_dichiarato"].append(f"{pg.stem}: la nota non spiega i toni")
        if "campionato" not in nota:
            difetti["nota_disallineata"].append(f"{pg.stem}: la nota non dichiara il perimetro")
        righe = LI.findall("".join(blocchi[1:]))
        for _tono, _t in righe:
            agg_toni[_tono] += 1

        mid = int(pg.stem)
        fr = fx[fx.match_id == mid]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        kickoff = pd.Timestamp(fr.ko)
        per_lega[str(fr.get("league_id"))] += 1

        for lato, (tid, tname) in enumerate(((int(fr.home_id), str(fr.home_name)),
                                             (int(fr.away_id), str(fr.away_name)))):
            if len(blocchi) != 3:
                esiti["annotazione"].append(f"{pg.stem}: blocchi = {len(blocchi)}")
                continue
            cell = [testo(t) for _tono, t in LI.findall(blocchi[lato + 1])]

            def trova(prefisso: str, _cell: list[str] = cell) -> str | None:
                for t in _cell:
                    if t.startswith(prefisso):
                        return t
                return None

            # ---------- strisce: forma di stagione intera ----------
            gare = fx[(fx.status == "finished") & (fx.ko < kickoff)
                      & ((fx.home_id == tid) | (fx.away_id == tid))].sort_values("ko")
            ris, gf_lista = [], []
            for r in gare.itertuples(index=False):
                casa = int(r.home_id) == tid
                gf, ga = (r.home_goals, r.away_goals) if casa else (r.away_goals, r.home_goals)
                if pd.isna(gf) or pd.isna(ga):
                    continue
                ris.append("V" if gf > ga else ("N" if gf == ga else "P"))
                gf_lista.append(int(gf))
            lose = striscia(ris, "P")
            nowin = striscia_fino_a(ris, "V")
            unbeaten = striscia_fino_a(ris, "P")
            secco = striscia(["1" if g else "0" for g in gf_lista], "0")

            atteso: list[tuple[str, str]] = []
            if lose >= soglie.get("MOOD_LOSS_STREAK", 3):
                atteso.append(("crisi di risultati",
                               f"crisi di risultati: {lose} sconfitte consecutive in campionato"))
            elif nowin >= soglie.get("MOOD_NOWIN", 4):
                nd = sum(1 for r in ris[len(ris) - nowin:] if r == "N")
                atteso.append(("non vince da", f"non vince da {nowin} gare in campionato ({nd} N, {nowin - nd} P)"))
            elif unbeaten >= soglie.get("MOOD_UNBEATEN", 5):
                atteso.append(("imbattuta da", f"imbattuta da {unbeaten} gare in campionato: clima di fiducia"))
            if secco >= soglie.get("MOOD_DRY", 3):
                atteso.append(("attacco a secco", f"attacco a secco: {secco} gare senza segnare in campionato"))
            for nome, t in atteso:
                agg_tipi[nome] += 1
                if t not in cell:
                    esiti["striscia"].append(f"{pg.stem}|{tname}| atteso «{t}»")
            # troncamento: la finestra di `form()` è 5 gare, la striscia vera può essere più lunga
            for prefisso, vero in (("crisi di risultati:", lose), ("non vince da", nowin),
                                   ("imbattuta da", unbeaten), ("attacco a secco:", secco)):
                t = trova(prefisso)
                if not t:
                    continue
                m_pub = re.search(r"([0-9]+)", t)
                pub = int(m_pub.group(1)) if m_pub else None
                if pub is not None and pub != vero:
                    difetti["troppo_corta"].append(
                        f"{pg.stem}|{tname}| «{t}» (striscia vera {vero})")
            # perimetro: la stessa lettura con le coppe dentro cambierebbe il verdetto?
            cupg = cup[(cup.status == "finished") & (cup.ko < kickoff)
                       & ((cup.home_id == tid) | (cup.away_id == tid))]
            if not cupg.empty:
                tutte = pd.concat([
                    gare[["ko", "home_id", "away_id", "home_goals", "away_goals"]],
                    cupg[["ko", "home_id", "away_id", "home_goals", "away_goals"]],
                ]).sort_values("ko")
                ris2, gf2 = [], []
                for r in tutte.itertuples(index=False):
                    casa = int(r.home_id) == tid
                    gf, ga = (r.home_goals, r.away_goals) if casa else (r.away_goals, r.home_goals)
                    if pd.isna(gf) or pd.isna(ga):
                        continue
                    ris2.append("V" if gf > ga else ("N" if gf == ga else "P"))
                    gf2.append(int(gf))
                lose2, nowin2, unbeaten2 = (striscia(ris2, "P"), striscia_fino_a(ris2, "V"),
                                            striscia_fino_a(ris2, "P"))
                secco2 = striscia(["1" if g else "0" for g in gf2], "0")
                if (lose, nowin, unbeaten, secco) != (lose2, nowin2, unbeaten2, secco2):
                    difetti["perimetro_coppe_verdetto"].append(
                        f"{pg.stem}|{tname}| campionato {(lose, nowin, unbeaten, secco)} "
                        f"vs coppe incluse {(lose2, nowin2, unbeaten2, secco2)}")

            # ---------- riposo e congestione: calendario + coppe ----------
            src = pd.concat([fx, cup], ignore_index=True, sort=False)
            prec = src[(src.status == "finished") & (src.ko < kickoff)
                       & ((src.home_id == tid) | (src.away_id == tid))]
            rest = int((kickoff - prec.ko.max()).total_seconds() // 86400) if not prec.empty else None
            r_rest = trova("riposo corto:")
            if rest is not None and rest <= soglie.get("MOOD_REST_SHORT", 3):
                ultima = prec.loc[prec.ko.idxmax()]
                coppa = str(ultima.get("cup_name") or "").strip()
                atteso = (f"riposo corto: {rest} {'giorno' if rest == 1 else 'giorni'}"
                          + (f", con un turno di {coppa} in mezzo" if coppa and coppa != "nan" else ""))
                agg_tipi["riposo corto"] += 1
                if atteso not in cell:
                    esiti["riposo"].append(f"{pg.stem}|{tname}| atteso «{atteso}»")
            elif r_rest:
                esiti["riposo"].append(f"{pg.stem}|{tname}| pubblicato «{r_rest}» (riposo vero {rest})")
            finestra = src[(src.status == "finished") & (src.ko >= kickoff - pd.Timedelta(days=10))
                           & (src.ko < kickoff)
                           & ((src.home_id == tid) | (src.away_id == tid))]
            r_cong = trova("congestione:")
            if len(finestra) >= soglie.get("MOOD_CONGEST_N", 3):
                agg_tipi["congestione"] += 1
                atteso = f"congestione: {len(finestra)} gare giocate negli ultimi 10 giorni"
                if atteso not in cell:
                    esiti["congestione"].append(f"{pg.stem}|{tname}| atteso «{atteso}»")
            elif r_cong:
                esiti["congestione"].append(f"{pg.stem}|{tname}| pubblicato «{r_cong}» ({len(finestra)} gare)")

            # ---------- infermeria ----------
            unav = lu[(lu.match_id == mid) & (lu.team_id == tid) & (lu.role == "unavailable")
                      & lu.player_id.notna()]
            n_un = len(unav)
            r_inf = trova("infermeria pesante:")
            stats = agg[agg.team_id == tid].set_index("player_name")
            minuti_squadra = float(stats["minutes_played"].sum()) if "minutes_played" in stats else 0.0
            per_giocatore = minuti_squadra / 11 if minuti_squadra else 0.0
            titolari, contrib, contrib_certo = 0, 0.0, 0.0
            for r in unav.itertuples(index=False):
                nome = str(r.player_name)
                if nome not in stats.index or "minutes_played" not in stats:
                    continue
                mins = float(stats.loc[nome, "minutes_played"])
                if pd.isna(mins):
                    continue
                if per_giocatore and mins >= 0.5 * per_giocatore:
                    titolari += 1
                c = 0.0
                for chiave in ("expected_goals", "expected_assists"):
                    if chiave in stats:
                        v = float(stats.loc[nome, chiave] or 0.0)
                        if not pd.isna(v):
                            c += v
                if mins:
                    contrib += round(c / (mins / 90.0), 2) if c else 0.0
                    # sopra i 90 minuti il generatore pubblica il valore grezzo; sotto pubblica
                    # la stima stabilizzata (mai più alta del grezzo), quindi la quota «certa»
                    # è quella dei soli giocatori con minuti sufficienti.
                    if mins >= 90.0:
                        contrib_certo += round(c / (mins / 90.0), 2) if c else 0.0
            soglia_contrib = soglie.get("MOOD_ABSENT_CONTRIB", 0.5)
            if n_un >= soglie.get("MOOD_ABSENT_N", 4) or titolari >= soglie.get("MOOD_ABSENT_STARTERS", 2) \
                    or contrib_certo >= soglia_contrib:
                agg_tipi["infermeria pesante"] += 1
                if r_inf is None:
                    esiti["infermeria"].append(
                        f"{pg.stem}|{tname}| riga assente con n={n_un} titolari={titolari} "
                        f"contrib certo={contrib_certo:.2f}")
                else:
                    mm = re.match(r"infermeria pesante: ([0-9]+) assent", r_inf)
                    if not mm or int(mm.group(1)) != n_un:
                        esiti["infermeria"].append(
                            f"{pg.stem}|{tname}| «{r_inf[:60]}» con n={n_un}")
            elif r_inf and contrib < soglia_contrib:
                esiti["infermeria"].append(
                    f"{pg.stem}|{tname}| pubblicata «{r_inf[:60]}» con n={n_un} "
                    f"titolari={titolari} contrib grezzo={contrib:.2f}")

            # ---------- xPTS: Understat alla vigilia; senza Understat, FotMob via Poisson ----------
            urows = us[(us._nome == canon(tname)) & (us._data < kickoff)]
            diff, banda, fonte = None, None, None
            if len(urows) >= MIN_GARE_XPTS and {"xpts", "pts"} <= set(urows.columns):
                diff = float(urows.pts.sum()) - float(urows.xpts.sum())
                banda = SD_XPTS * math.sqrt(len(urows))
                fonte = "Understat"
            else:
                fin = fx[(fx.status == "finished") & (fx.ko < kickoff)
                         & ((fx.home_id == tid) | (fx.away_id == tid))]
                info = mi[mi.match_id.isin(fin.match_id)]
                info = info.dropna(subset=[c for c in ("home_xg", "away_xg", "home_goals",
                                                       "away_goals") if c in info.columns])
                if not info.empty:
                    tot_x = tot_p = 0.0
                    for r in info.itertuples(index=False):
                        casa = int(r.home_id) == tid
                        xh, xa = float(r.home_xg), float(r.away_xg)
                        xp, xpa = xpts_da_xg(xh, xa)
                        tot_x += xp if casa else xpa
                        hg, ag = int(r.home_goals), int(r.away_goals)
                        signed = hg - ag if casa else ag - hg
                        tot_p += 3 if signed > 0 else 1 if signed == 0 else 0
                    if len(info) >= MIN_GARE_XPTS:
                        diff = tot_p - tot_x
                        banda = SD_XPTS * math.sqrt(len(info))
                        fonte = "FotMob"
            sopra, sotto = trova("rende più di quanto crea"), trova("raccoglie meno punti")
            if diff is not None and banda is not None:
                if diff >= banda:
                    agg_tipi["xpts sopra"] += 1
                    if sopra is None:
                        esiti["xpts"].append(f"{pg.stem}|{tname}| atteso «sopra» "
                                             f"({diff:.2f} ≥ {banda:.2f}, {fonte})")
                elif diff <= -banda:
                    agg_tipi["xpts sotto"] += 1
                    if sotto is None:
                        esiti["xpts"].append(f"{pg.stem}|{tname}| atteso «sotto» "
                                             f"({diff:.2f} ≤ -{banda:.2f}, {fonte})")
                elif sopra or sotto:
                    esiti["xpts"].append(f"{pg.stem}|{tname}| verdetto con diff {diff:.2f} "
                                         f"dentro la banda {banda:.2f} ({fonte})")
            elif sopra or sotto:
                esiti["xpts"].append(f"{pg.stem}|{tname}| verdetto senza campione sufficiente")

            # ---------- panchina ----------
            co = lu[(lu.team_id == tid) & (lu.role == "coach")]
            co = co[co.match_id.isin(fx.match_id)].copy()
            co["ko"] = pd.to_datetime(
                co.match_id.map(fx.drop_duplicates("match_id").set_index("match_id")["ko"]), utc=True)
            co = co[co.ko <= kickoff].sort_values("ko", kind="stable")
            prev, subentro = None, 0
            if not co.empty:
                cur = co.iloc[-1].player_id
                for pid, nm in zip(co.player_id.iloc[::-1], co.player_name.iloc[::-1]):
                    if pid != cur:
                        prev = str(nm)
                        break
                # la permanenza è la sequenza **consecutiva** di panchine con lo stesso id
                # (come ``coach()``): il totale delle righe conterebbe anche un ritorno
                subentro = 0
                for pid in co.player_id.iloc[::-1]:
                    if pid == cur:
                        subentro += 1
                    else:
                        break
            r_coach = trova("panchina nuova:")
            if prev is not None:
                agg_tipi["panchina nuova"] += 1
                coda_fredda.append(subentro)
                if r_coach is None:
                    esiti["panchina"].append(f"{pg.stem}|{tname}| «panchina nuova» attesa")
                elif subentro > 3:
                    difetti["panchina_vecchia"].append(
                        f"{pg.stem}|{tname}| panchina nuova ma {subentro}ª gara dal subentro")
            elif r_coach is not None:
                esiti["panchina"].append(f"{pg.stem}|{tname}| «panchina nuova» senza cambio rilevato")

    print("=== censimento ===")
    print(f"pagine pre-partita con card: {sum(per_lega.values())}")
    print(f"righe totali pubblicate: {sum(agg_toni.values())}")
    print("toni:", dict(agg_toni))
    print("\n=== segnali pubblicati per tipo (ricalcolo indipendente) ===")
    for k in sorted(agg_tipi):
        print(f"{k:22s} {agg_tipi[k]}")
    if coda_fredda:
        s = pd.Series(coda_fredda)
        print(f"\npanchina nuova: gare dal subentro min {s.min()} mediana {int(s.median())} "
              f"75° {int(s.quantile(.75))} max {s.max()} · oltre 3: {(s > 3).sum()}/{len(s)}")
    print("\n=== scostamenti (righe assenti o diverse dal ricalcolo) ===")
    for k, v in esiti.items():
        if v:
            print(f"{k}: {len(v)} — es. {v[:3]}")
    print("\n=== difetti strutturali cercati apposta ===")
    for k, v in difetti.items():
        if k == "tono_non_dichiarato":
            print(f"{k}: {len(v)} pagine" + (f" — es. {v[:1]}" if v else ""))
        else:
            print(f"{k}: {len(v)}" + (f" — es. {v[:3]}" if v else ""))
    print("\n=== pagine per lega ===")
    print(dict(per_lega.most_common()))
    print(f"\nnota letta su {nota_osservata} pagine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
