"""Audit 360° delle card dell'area clima (revisione del 2026-10-11, `docs/81`; `docs/82`).

Dall'11/10/2026 (`docs/82` §5, opzione A) l'area è divisa in due card: **«Stato della
squadra»** (ex «Clima del club»: forma, disponibilità, calendario) e **«Clima del club»**
(la settimana secondo la stampa e la pressione da aspettative). Questo script le misura
entrambe.

Sulla card «Stato della squadra»: i segnali pubblicati per tipo e per tono, quelli che il
ricalcolo dai Parquet non conferma, i segnali mancanti, la fedeltà della nota alle soglie del
codice, e tre difetti strutturali cercati apposta — contatori troncati dalla finestra di
forma, ambiguità di perimetro (campionato vs coppe) e «panchina nuova» senza scadenza.

Sulla card «Clima del club»: le righe della settimana (calda / in tensione / tranquilla /
vuoto dichiarato), quelle delle aspettative (sotto e sopra), e ogni dislivello fra pagina e
ricalcolo — conteggi per tema, soglia delle 3 voci, rango per valore dei titolari contro
classifica, frase del vuoto presente se e solo se il conteggio è zero.

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

CARD = re.compile(r'<div class="card" id="stato-squadra">(.*?)(?=<div class="card"|<footer)',
                  re.DOTALL)
CARD_CLIMA = re.compile(r'<div class="card" id="clima">(.*?)(?=<div class="card"|<footer)',
                        re.DOTALL)
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
    ev = pd.read_parquet(DATA / "events.parquet")
    ndf = pd.read_parquet(DATA / "news.parquet")
    fm = pd.read_parquet(DATA / "fotmob_standings.parquet")
    us["_nome"] = us.team_name.map(canon)
    us["_data"] = pd.to_datetime(us.date, utc=True, errors="coerce")

    soglie = soglie_codice()

    # statistiche giocatore di stagione: totale per (squadra, nome) — niente cache del generatore
    pnum = ps.assign(num=pd.to_numeric(ps.value, errors="coerce")).dropna(subset=["num"])
    agg = (pnum.groupby(["team_id", "player_name", "key"]).num.sum()
           .unstack("key").reset_index())

    esiti: dict[str, list[str]] = {
        "xpts": [], "infermeria": [], "riposo": [], "congestione": [], "striscia": [],
        "panchina": [], "ultima_gara": [], "punteggio_mancante": [], "annotazione": [],
    }
    difetti: dict[str, list[str]] = {
        "troppo_corta": [], "perimetro_coppe_verdetto": [], "panchina_vecchia": [],
        "nota_disallineata": [], "tono_non_dichiarato": [],
        "clima_nota_disallineata": [], "clima_dislivello": [],
        "clima_elenco_disallineato": [],
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
            r_inf = next((t for t in cell
                          if t.startswith(("infermeria pesante", "assenze pesanti"))), None)
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
                    mm = re.match(r"(?:infermeria pesante|assenze pesanti): ([0-9]+) assent", r_inf)
                    if not mm or int(mm.group(1)) != n_un:
                        esiti["infermeria"].append(
                            f"{pg.stem}|{tname}| «{r_inf[:60]}» con n={n_un}")
                    # «infermeria» solo con i soli infortuni (docs/81 §10)
                    _soli_inf = (all(str(t).strip().lower() == "injury"
                                     for t in unav.unavailability_type.dropna())
                                 if n_un else True)
                    attesa_et = "infermeria pesante" if _soli_inf else "assenze pesanti"
                    if not r_inf.startswith(attesa_et):
                        esiti["infermeria"].append(
                            f"{pg.stem}|{tname}| etichetta «{r_inf[:40]}» invece di «{attesa_et}»")
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

            # ---------- ultima gara di campionato: sconfitta pesante e espulsione ----------
            ug = fx[(fx.status == "finished") & (fx.ko < kickoff)
                    & ((fx.home_id == tid) | (fx.away_id == tid))]
            if not ug.empty:
                u = ug.loc[ug.ko.idxmax()]
                casa = int(u.home_id) == tid
                gf, ga = (u.home_goals, u.away_goals) if casa else (u.away_goals, u.home_goals)
                r_pes = trova("sconfitta pesante nell'ultima gara di campionato:")
                if pd.notna(gf) and pd.notna(ga) and (int(ga) - int(gf)) >= 3:
                    agg_tipi["sconfitta pesante"] += 1
                    atteso_pes = (f"sconfitta pesante nell'ultima gara di campionato: "
                                  f"{int(gf)}-{int(ga)}")
                    if atteso_pes not in cell:
                        esiti["ultima_gara"].append(f"{pg.stem}|{tname}| atteso «{atteso_pes}»")
                elif r_pes:
                    esiti["ultima_gara"].append(f"{pg.stem}|{tname}| pubblicata «{r_pes[:50]}»")
                r_esp = trova("espulsione nell'ultima gara di campionato")
                miei = []
                if not ev.empty and {"match_id", "card", "is_home"} <= set(ev.columns):
                    miei = [r for r in ev[(ev.match_id == int(u.match_id))
                                          & ev.card.astype(str).str.lower().isin(("red", "yellowred"))
                                          & ev.is_home.notna()
                                          & (ev.is_home.astype(bool) == casa)].itertuples(index=False)]
                if miei:
                    agg_tipi["espulsione"] += 1
                    if r_esp is None:
                        esiti["ultima_gara"].append(f"{pg.stem}|{tname}| espulsione attesa e assente")
                elif r_esp:
                    esiti["ultima_gara"].append(f"{pg.stem}|{tname}| pubblicata «{r_esp[:50]}»")

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

    # ---- card «Clima del club» (`docs/82` §5): settimana della stampa + aspettative ----------
    from fda.sources.news import TOPIC_LABELS as _TL
    from fda.sources.news import TOPIC_WEIGHTS as _TW
    from fda.sources.news import classify_news as _cl
    from fda.sources.news import club_nel_titolo as _cnt
    from fda.sources.news import fatto_grave as _fg
    from fda.sources.news import is_italian_news as _it
    from fda.sources.news import is_low_reputation as _lr
    from fda.sources.news import soggetto_tokens as _sg
    _temi = ("allenatore", "spogliatoio", "societa", "tifo", "stadio", "fuoricampo")
    _press = ("allenatore", "spogliatoio", "societa", "tifo")
    _ord = {k: i for i, k in enumerate(_temi)}
    _pa = pd.to_datetime(ndf.published_at, utc=True, errors="coerce") if not ndf.empty else None
    for _c in ("home_starters_value_eur", "away_starters_value_eur"):
        if _c in mi.columns:
            mi[_c] = pd.to_numeric(mi[_c], errors="coerce")

    _tl = lambda t: re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

    def _attesi_clima(tid: int, tname: str, ko: pd.Timestamp, pubblicate: set[str],
                      ) -> tuple[list[tuple[str, str]], int, list[dict], dict | None]:
        """Righe attese (testo, tono), numero di voci e gruppi elencati: la specifica dei Parquet.

        Dal 2026-10-11 (`docs/82` §9) la card pubblica anche l'elenco: una voce per titolo
        (chiave riscritta qui), le più recenti fino al tetto di 24, marcate quelle che
        «Vita del club» racconta sulla stessa pagina.
        """
        att: list[tuple[str, str]] = []
        if ndf.empty:
            return att, 0, []
        sub = ndf[(ndf.team_id == tid) & (_pa >= ko - pd.Timedelta(days=7)) & (_pa <= ko)].copy()
        sub["_pa"] = _pa.loc[sub.index]
        sub = sub.dropna(subset=["_pa"]).sort_values("_pa", ascending=False, kind="stable")
        voci_righe: list[dict] = []
        viste: set[str] = set()
        _sogg = _sg(tname)
        for r in sub.itertuples(index=False):
            titolo = str(getattr(r, "title", "") or "").strip()
            if not titolo:
                continue
            desc = getattr(r, "description", None)
            desc = "" if desc is None or pd.isna(desc) else str(desc)
            if not _it(titolo, desc):
                continue
            if _lr(getattr(r, "source", None)):
                continue
            chiave, _p = _cl(titolo, "", getattr(r, "source", None))
            if chiave not in _temi:
                continue
            # gate di soggetto: il club **nel titolo** (anche «Juve», «Colonia»)
            if not _cnt(titolo, _sogg):
                continue
            tk = _tl(titolo)
            if not tk or tk in viste:
                continue
            viste.add(tk)
            voci_righe.append({"key": chiave, "title": titolo,
                               "url": str(getattr(r, "url", "") or ""),
                               "in_vita": tk in pubblicate})
        conta: Counter[str] = Counter(v["key"] for v in voci_righe)
        voci = len(voci_righe)
        pressione = sum(conta[k] for k in _press)
        temi = sorted(conta, key=lambda k: (-conta[k], _ord[k]))
        elencate = voci_righe[:24]
        per_tema: dict[str, list[dict]] = {}
        for v in elencate:
            per_tema.setdefault(v["key"], []).append(v)
        gruppi = [{"key": k, "label": _TL.get(k, k), "n": int(conta[k]),
                   "voci": per_tema.get(k, [])} for k in temi]

        def det(chiavi: list[str]) -> str:
            return " · ".join(f"{_TL.get(k, k).lower()} {conta[k]}" for k in chiavi)

        det_press = det([k for k in temi if k in _press])
        if pressione >= 3:
            testo_atteso = (f"settimana calda: {pressione} voci di pressione in 7 giorni "
                            f"({det_press})")
            att.append((testo_atteso, "bad"))
        elif pressione:
            testo_atteso = (f"pressione in settimana: {pressione} "
                            f"{'voce' if pressione == 1 else 'voci'} ({det_press})")
            att.append((testo_atteso, "warn"))
        elif voci:
            testo_atteso = (f"settimana tranquilla: {voci} {'voce' if voci == 1 else 'voci'}, "
                            f"nessuna di pressione ({det(temi)})")
            att.append((testo_atteso, "good"))
        riga = fm[fm.team_name.map(canon) == canon(tname)] if not fm.empty else fm
        if not riga.empty and pd.notna(riga.iloc[0].get("rank")) and not mi.empty:
            fin = fx[(fx.status == "finished") & (fx.ko < ko)]
            info = mi[mi.match_id.isin({int(x) for x in fin.match_id})]
            valori: dict[int, list[float]] = {}
            for r in info.itertuples(index=False):
                for t, col in ((int(r.home_id), "home_starters_value_eur"),
                               (int(r.away_id), "away_starters_value_eur")):
                    v = getattr(r, col, None)
                    if v is None or pd.isna(v) or float(v) <= 0:
                        continue
                    valori.setdefault(t, []).append(float(v))
            medie = {t: float(pd.Series(v).median()) for t, v in valori.items() if len(v) >= 3}
            lega = fm[fm.league_code == riga.iloc[0]["league_code"]].drop_duplicates("team_id")
            in_lega = sorted({int(t) for t in lega.team_id} & set(medie))
            if tid in medie and len(in_lega) >= 8:
                rango = sorted(in_lega, key=lambda t: (-medie[t], t)).index(tid) + 1
                pos = int(riga.iloc[0]["rank"])
                if pos - rango >= 5:
                    testo_atteso = (f"pressione da aspettative: rosa da {rango}ª per valore dei "
                                    f"titolari, in classifica {pos}ª")
                    att.append((testo_atteso, "warn"))
                elif rango - pos >= 5:
                    testo_atteso = (f"sopra le attese: in classifica {pos}ª con una rosa da "
                                    f"{rango}ª per valore dei titolari")
                    att.append((testo_atteso, "good"))
        fatto = None
        if voci_righe:
            def _peso(v: dict) -> int:
                return _TW.get(v["key"], 1) + (3 if _fg(v["title"]) else 0)
            # solo se il tema pesa almeno 4 o c'è un fatto grave (CLIMA_FATTO_MIN)
            pesanti = [v for v in voci_righe if _peso(v) >= 4]
            fatto = max(pesanti, key=_peso) if pesanti else None
        return att, voci, gruppi, fatto

    clima_toni: Counter[str] = Counter()
    clima_tipi: Counter[str] = Counter()
    clima_pagine = 0
    clima_vuoto = 0
    clima_lati = 0
    clima_scarti = 0
    clima_elencate = 0
    clima_in_vita = 0
    for pg in sorted(SITE.glob("*.html")):
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html:
            continue
        m2 = CARD_CLIMA.search(html)
        if not m2:
            difetti["clima_dislivello"].append(f"{pg.stem}: card «Clima del club» assente")
            continue
        clima_pagine += 1
        nota2 = testo(m2.group(1))
        for frase, chiave in (("7 giorni", "CLIMA_SETTIMANA"),
                              ("3 voci di pressione", "CLIMA_CALDA_N"),
                              ("almeno 5 posizioni", "CLIMA_VALORE_DELTA"),
                              ("il tema si vede nel titolo", "pertinenza"),
                              ("il club si vede nel titolo", "soggetto"),
                              ("avversario di passaggio", "soggetto"),
                              ("bassa reputazione", "fonti"),
                              ("fatto della settimana", "fatto"),
                              ("esce solo se il tema pesa", "CLIMA_FATTO_MIN"),
                              ("fra virgolette è la frase di qualcun altro", "fatto grave"),
                              ("valore dei titolari", "CLIMA_VALORE_MIN"),
                              ("stampa", "lingua")):
            if frase not in nota2:
                difetti["clima_nota_disallineata"].append(f"{pg.stem}: nota senza «{frase}» ({chiave})")
        from fda.site.club_news_checks import primary_titles

        pubblicate = {_tl(x) for x in primary_titles(html)}
        fr = fx[fx.match_id == int(pg.stem)]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        blocchi2 = BLOCCO.split(m2.group(1))
        if len(blocchi2) != 3:
            difetti["clima_dislivello"].append(f"{pg.stem}: struttura inattesa ({len(blocchi2)})")
            continue
        for parte in blocchi2[1:]:
            tname = testo(parte.split("</b>", 1)[0])
            tid = int(fr.home_id) if tname == str(fr.home_name) else int(fr.away_id)
            attesi, voci, gruppi, fatto = _attesi_clima(tid, tname, pd.Timestamp(fr.ko),
                                                        pubblicate)
            righe = [(unescape(t), tone) for tone, t in LI.findall(parte)]
            clima_lati += 1
            for testo_atteso, tono in attesi:
                clima_toni[tono] += 1
                if testo_atteso.startswith("settimana calda"):
                    clima_tipi["settimana calda"] += 1
                elif testo_atteso.startswith("pressione in settimana"):
                    clima_tipi["pressione in settimana"] += 1
                elif testo_atteso.startswith("settimana tranquilla"):
                    clima_tipi["settimana tranquilla"] += 1
                elif testo_atteso.startswith("pressione da aspettative"):
                    clima_tipi["aspettative sotto"] += 1
                elif testo_atteso.startswith("sopra le attese"):
                    clima_tipi["aspettative sopra"] += 1
                if (testo_atteso, tono) not in righe:
                    difetti["clima_dislivello"].append(
                        f"{pg.stem}|{tname}| attesa assente «{testo_atteso[:60]}»")
                    clima_scarti += 1
            for testo_pagina, tono in righe:
                if (testo_pagina, tono) not in attesi:
                    difetti["clima_dislivello"].append(
                        f"{pg.stem}|{tname}| riga non giustificata «{testo_pagina[:60]}»")
                    clima_scarti += 1
            if (voci == 0) != ("Nessuna voce di clima raccolta dalla stampa italiana" in parte):
                difetti["clima_dislivello"].append(
                    f"{pg.stem}|{tname}| vuoto dichiarato incoerente ({voci} voci)")
            if voci == 0:
                clima_vuoto += 1
            # il fatto della settimana: la voce più pesante (tema + fatto grave), o niente
            fatto_pag = re.search(
                r'<p class="small" style="margin:6px 0 0"><b>Il fatto della settimana:</b>\s*'
                r'<a href="([^"]+)"[^>]*>(.*?)</a>', parte, re.DOTALL)
            if (fatto is None) != (fatto_pag is None):
                difetti["clima_elenco_disallineato"].append(
                    f"{pg.stem}|{tname}| fatto della settimana "
                    f"{'assente' if fatto else 'presente'} contro l'atteso")
            elif fatto_pag is not None and (fatto_pag.group(1) != fatto["url"]
                                            or unescape(fatto_pag.group(2)) != fatto["title"]):
                difetti["clima_elenco_disallineato"].append(
                    f"{pg.stem}|{tname}| fatto «{unescape(fatto_pag.group(2))[:50]}» "
                    f"invece di «{fatto['title'][:50]}»")
            # l'elenco delle voci contate (`docs/82` §9): sommario, gruppi, item, marcatori
            elencate = sum(len(g["voci"]) for g in gruppi)
            in_vita = sum(1 for g in gruppi for v in g["voci"] if v["in_vita"])
            somm = re.search(r"<summary>(.*?)</summary>", parte, re.DOTALL)
            testo_somm = testo(somm.group(1)) if somm else ""
            if (elencate > 0) != bool(somm):
                difetti["clima_elenco_disallineato"].append(
                    f"{pg.stem}|{tname}| tendina {'assente' if elencate else 'presente'} "
                    f"({elencate} voci elencate)")
            elif somm:
                clima_elencate += elencate
                clima_in_vita += in_vita
                atteso_somm = (
                    f"Le {elencate} voci più recenti di {voci} contate" if voci > elencate
                    else "Una voce contata" if voci == 1
                    else f"Le {voci} voci contate")
                if atteso_somm not in testo_somm:
                    difetti["clima_elenco_disallineato"].append(
                        f"{pg.stem}|{tname}| sommario «{testo_somm[:60]}» "
                        f"invece di «{atteso_somm}»")
                if in_vita:
                    atteso_marc = ("già raccontata in «Vita del club»" if voci == 1
                                   else "una già raccontata in «Vita del club»" if in_vita == 1
                                   else f"{in_vita} già raccontate in «Vita del club»")
                    if atteso_marc not in testo_somm:
                        difetti["clima_elenco_disallineato"].append(
                            f"{pg.stem}|{tname}| sommario senza i marcatori ({in_vita})")
                gr_pag = re.findall(
                    r'<p class="small" style="margin:8px 0 4px"><b>(.*?) \((\d+)\)</b></p>\s*'
                    r'<ul class="news-list">(.*?)</ul>', parte, re.DOTALL)
                if len(gr_pag) != len(gruppi):
                    difetti["clima_elenco_disallineato"].append(
                        f"{pg.stem}|{tname}| gruppi {len(gr_pag)} in pagina contro "
                        f"{len(gruppi)} attesi")
                else:
                    for (lab, n, ul), att_g in zip(gr_pag, gruppi):
                        if unescape(lab) != att_g["label"] or int(n) != att_g["n"]:
                            difetti["clima_elenco_disallineato"].append(
                                f"{pg.stem}|{tname}| gruppo «{lab} ({n})» invece di "
                                f"«{att_g['label']} ({att_g['n']})»")
                        items = re.findall(
                            r'<li><span class="small"><a href="([^"]+)"[^>]*>(.*?)</a> '
                            r'<span class="mut">(.*?)</span></span></li>', ul, re.DOTALL)
                        if [unescape(t) for _u, t, _r in items] \
                                != [v["title"] for v in att_g["voci"]]:
                            difetti["clima_elenco_disallineato"].append(
                                f"{pg.stem}|{tname}| voci elencate di «{att_g['label']}» "
                                f"non corrispondenti ({len(items)} in pagina)")
                        for (u, _t, meta), v in zip(items, att_g["voci"]):
                            if u != v["url"] or (("anche in «Vita del club»" in unescape(meta))
                                                 != v["in_vita"]):
                                difetti["clima_elenco_disallineato"].append(
                                    f"{pg.stem}|{tname}| voce «{v['title'][:40]}» "
                                    f"con link o marcatore diversi")
                if voci > elencate:
                    atteso_coda = ("E un'altra voce della settimana, non elencata."
                                   if voci - elencate == 1
                                   else f"E altre {voci - elencate} voci della settimana, "
                                        f"non elencate.")
                    if atteso_coda not in testo(parte):
                        difetti["clima_elenco_disallineato"].append(
                            f"{pg.stem}|{tname}| resto oltre il tetto non dichiarato "
                            f"({voci - elencate} voci)")

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
    print("\n=== clima del club (docs/82 §5): settimana e aspettative ===")
    print(f"pagine con la card: {clima_pagine} · lati-squadra misurati: {clima_lati}")
    print(f"righe pubblicate: {sum(clima_toni.values())} · toni: {dict(clima_toni)}")
    print("tipo:", dict(clima_tipi))
    print(f"lati con vuoto dichiarato della stampa: {clima_vuoto} · scostamenti: {clima_scarti}")
    print(f"voci elencate nelle tendine: {clima_elencate} · marcate «anche in «Vita del club»»: "
          f"{clima_in_vita}")

    print("\n=== pagine per lega ===")
    print(dict(per_lega.most_common()))
    print(f"\nnota letta su {nota_osservata} pagine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
