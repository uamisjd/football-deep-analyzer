"""Sondaggio dei candidati per la card «Clima del club» (revisione 2026-10-11, `docs/81` §9).

Non è un gate: è la misura che precede la decisione (regola B.10). Per ogni candidato:
disponibilità del dato, frequenza sulle 154 celle pre-partita, ridondanza con altre card.

Uso: ``.venv/bin/python scripts/audit_clima_candidati.py`` (dopo ``fda build``).
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from html import unescape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "partite"
DATA = ROOT / "data" / "processed"

CARD_CLIMA = re.compile(r'<div class="card" id="clima">(.*?)(?=<div class="card"|<footer)', re.DOTALL)
CARD_NEWS = re.compile(r'<div class="card" id="notizie">(.*?)(?=<div class="card"|<footer)', re.DOTALL)
BLOCCO = re.compile(r'<p style="margin:0 0 6px"><b>')


def testo(h: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def striscia(ris: list[str], val: str) -> int:
    n = 0
    for r in reversed(ris):
        if r == val:
            n += 1
        else:
            break
    return n


def main() -> int:
    fx = pd.read_parquet(DATA / "fixtures.parquet")
    cup = pd.read_parquet(DATA / "cup_fixtures.parquet")
    lu = pd.read_parquet(DATA / "lineup.parquet")
    ps = pd.read_parquet(DATA / "player_stats.parquet")
    ev = pd.read_parquet(DATA / "events.parquet")
    for d in (fx, cup):
        d["ko"] = pd.to_datetime(d.utc_kickoff, utc=True, errors="coerce")
        d["home_goals"] = pd.to_numeric(d.home_goals, errors="coerce")
        d["away_goals"] = pd.to_numeric(d.away_goals, errors="coerce")
    ev["_ko"] = pd.to_datetime(ev.get("utc_kickoff"), utc=True, errors="coerce") \
        if "utc_kickoff" in ev.columns else pd.NaT
    pnum = ps.assign(num=pd.to_numeric(ps.value, errors="coerce")).dropna(subset=["num"])

    pagine = [p for p in sorted(SITE.glob("*.html"))
              if "Analisi pre-partita" in p.read_text(encoding="utf-8")]
    print(f"schede pre-partita: {len(pagine)}")

    # ---------- A. duplicazione clima ↔ «Da sapere» ----------
    dup = Counter()
    esempi_dup = []
    for p in pagine:
        h = p.read_text(encoding="utf-8")
        mc, mn = CARD_CLIMA.search(h), CARD_NEWS.search(h)
        if not mc or not mn:
            continue
        cl = testo(mc.group(1))
        sapere = testo(mn.group(1))
        fr = fx[fx.match_id == int(p.stem)]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        ko = pd.Timestamp(fr.ko)
        for tid, tn in ((int(fr.home_id), str(fr.home_name)), (int(fr.away_id), str(fr.away_name))):
            gare = fx[(fx.status == "finished") & (fx.ko < ko)
                      & ((fx.home_id == tid) | (fx.away_id == tid))].sort_values("ko")
            ris = []
            for r in gare.itertuples(index=False):
                casa = int(r.home_id) == tid
                a, b = (r.home_goals, r.away_goals) if casa else (r.away_goals, r.home_goals)
                if pd.isna(a) or pd.isna(b):
                    continue
                ris.append("V" if a > b else ("N" if a == b else "P"))
            lose, nowin, unbe = striscia(ris, "P"), None, None
            nowin = 0
            for r in reversed(ris):
                if r != "V":
                    nowin += 1
                else:
                    break
            unbe = 0
            for r in reversed(ris):
                if r != "P":
                    unbe += 1
                else:
                    break
            # la riga clima esiste?
            in_clima = (lose >= 3 and "crisi di risultati" in cl) or \
                       (4 <= nowin < 5 and "non vince da" in cl) or \
                       (5 <= nowin and "non vince da" in cl) or \
                       (unbe >= 5 and "imbattuta da" in cl)
            # la riga «Da sapere» esiste per lo stesso fatto?
            stessa = ((lose >= 3 and "Momento delicato" in sapere)
                      or (nowin >= 5 and "Digiuno di vittorie" in sapere)
                      or (unbe >= 5 and "Striscia positiva" in sapere))
            if in_clima and stessa:
                dup[f"doppia:{tn[:12]}"] += 1
                if len(esempi_dup) < 6:
                    esempi_dup.append(f"{p.stem}|{tn}| perse={lose} nowin={nowin} unbe={unbe} "
                                      f"clima={'sì' if in_clima else 'no'}")
    print(f"\n[A] celle con lo stesso fatto in clima E in «Da sapere»: {sum(dup.values())}")
    for x in esempi_dup:
        print("    ", x)

    # ---------- B. squalifiche dentro «infermeria pesante» ----------
    tipi = Counter()
    soli_sq = []
    for p in pagine:
        mid = int(p.stem)
        fr = fx[fx.match_id == mid]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        for tid, tn in ((int(fr.home_id), str(fr.home_name)), (int(fr.away_id), str(fr.away_name))):
            u = lu[(lu.match_id == mid) & (lu.team_id == tid) & (lu.role == "unavailable")
                   & lu.player_id.notna()]
            for t in u.unavailability_type.dropna():
                tipi[str(t)] += 1
            if len(u) >= 2 and not (u.unavailability_type.astype(str) == "injury").any():
                soli_sq.append(f"{mid}|{tn}| {len(u)} assenti: {sorted(set(u.unavailability_type.astype(str)))}")
    print(f"\n[B] tipi di indisponibilità nel dataset: {dict(tipi)}")
    print(f"    celle con 2+ assenti e nessun infortunio: {len(soli_sq)}")
    for x in soli_sq[:5]:
        print("    ", x)

    # ---------- C. striscia difensiva: gare consecutive subendo 2+ ----------
    for soglia_subiti in (2, 3):
        c = Counter()
        for p in pagine:
            fr = fx[fx.match_id == int(p.stem)]
            if fr.empty:
                continue
            fr = fr.iloc[0]
            ko = pd.Timestamp(fr.ko)
            for tid in (int(fr.home_id), int(fr.away_id)):
                gare = fx[(fx.status == "finished") & (fx.ko < ko)
                          & ((fx.home_id == tid) | (fx.away_id == tid))].sort_values("ko")
                sub = []
                for r in gare.itertuples(index=False):
                    casa = int(r.home_id) == tid
                    sub.append((r.away_goals, r.home_goals)[0] if casa else r.home_goals)
                seq = [1 if (pd.notna(x) and x >= soglia_subiti) else 0 for x in sub]
                n = 0
                for x in reversed(seq):
                    if x:
                        n += 1
                    else:
                        break
                c[f"striscia>={soglia_subiti}"] += int(n >= 3)
        print(f"[C] celle con 3+ gare consecutive subendo {soglia_subiti}+ gol: {c[f'striscia>={soglia_subiti}']}")

    # ---------- D. digiuno del capocannoniere ----------
    righe = []
    for p in pagine:
        mid = int(p.stem)
        fr = fx[fx.match_id == mid]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        ko = pd.Timestamp(fr.ko)
        for tid, tn in ((int(fr.home_id), str(fr.home_name)), (int(fr.away_id), str(fr.away_name))):
            fin = fx[(fx.status == "finished") & (fx.ko < ko)
                          & ((fx.home_id == tid) | (fx.away_id == tid))].sort_values("ko")
            ids = {int(x) for x in fin.match_id}
            psx = pnum[(pnum.team_id == tid) & (pnum.key == "goals") & pnum.match_id.isin(ids)]
            if psx.empty:
                continue
            tot = psx.groupby("player_name").num.sum().sort_values(ascending=False)
            if tot.empty or tot.iloc[0] < 3:
                continue
            bomber = str(tot.index[0])
            suoi = fin[((fin.home_id == tid) | (fin.away_id == tid))]
            gol_seq = []
            for r in suoi.itertuples(index=False):
                g = pnum[(pnum.team_id == tid) & (pnum.match_id == r.match_id)
                         & (pnum.player_name == bomber) & (pnum.key == "goals")]
                gol_seq.append(int(g.num.sum()) if not g.empty else 0)
            dig = 0
            for g in reversed(gol_seq):
                if g == 0:
                    dig += 1
                else:
                    break
            righe.append((dig, tot.iloc[0], bomber, mid, tn, len(fin)))
    d = pd.Series([r[0] for r in righe])
    print(f"\n[D] celle con capocannoniere (>=3 gol) analizzabili: {len(righe)}")
    print(f"    gare di digiuno del capocannoniere: mediana {int(d.median())} · "
          f">=3: {(d >= 3).sum()} · >=4: {(d >= 4).sum()} · >=5: {(d >= 5).sum()}")
    for r in sorted(righe, reverse=True)[:5]:
        print(f"     digiuno {r[0]} gare · {r[1]:.0f} gol stagionali · {r[2]} ({r[4]}, {r[3]})")

    # ---------- E. congestione in arrivo ----------
    src = pd.concat([fx, cup], ignore_index=True, sort=False)
    fut = Counter()
    for p in pagine:
        fr = fx[fx.match_id == int(p.stem)]
        if fr.empty:
            continue
        fr = fr.iloc[0]
        ko = pd.Timestamp(fr.ko)
        for tid in (int(fr.home_id), int(fr.away_id)):
            n = len(src[(src.status == "scheduled") & (src.ko > ko)
                        & (src.ko <= ko + pd.Timedelta(days=7))
                        & ((src.home_id == tid) | (src.away_id == tid))])
            fut[f"gare nei 7gg: {n}"] += 1
    print(f"\n[E] carico in arrivo nei 7 giorni dalla gara: {dict(sorted(fut.items()))}")

    # ---------- F. espulsioni ----------
    if "card" in ev.columns:
        rosse = ev[ev.card.astype(str).str.contains("red", case=False, na=False)]
        print(f"\n[F] eventi con cartellino rosso in archivio: {len(rosse)} (su {len(ev)} eventi)")
        print("    colonne utili:", [c for c in ev.columns if c in ("match_id", "team_id", "is_home", "type", "card")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
