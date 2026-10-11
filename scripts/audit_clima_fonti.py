"""Studio di fattibilità del «clima del club»: quanta materia prima esiste davvero.

Serve a `docs/82` (ripensamento della card «Clima del club»). Non è un gate: misura
(1) quante notizie per squadra/lega e quante passano i filtri del sito, (2) la distribuzione
per categoria di `TOPIC_RULES` (panchina, spogliatoio, società, tifo, stadio…), (3) la
copertura del dato `attendance` (mai usato pre-partita) e (4) quante voci restano nella
finestra 7/14 giorni — così una sintesi settimanale ha un senso misurabile o no.

Uso: ``.venv/bin/python scripts/audit_clima_fonti.py``.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

TEMA_CLIMA = ("allenatore", "spogliatoio", "societa", "fuoricampo", "tifo", "stadio")


def main() -> int:
    from fda.config import leagues
    from fda.sources.news import TOPIC_LABELS, classify_news, is_italian_news, news_value

    nd = pd.read_parquet(DATA / "news.parquet")
    nd["published_at"] = pd.to_datetime(nd.published_at, utc=True, errors="coerce")
    # fine della finestra: l'ultima notizia raccolta (non «adesso»: i dati possono essere vecchi)
    fine = nd.published_at.max()
    fx = pd.read_parquet(DATA / "fixtures.parquet")
    chiave = {lg.fotmob_id: lg.key for lg in leagues()}
    fx["lg"] = fx.league_id.map(chiave)
    squadre = (pd.concat([fx[["home_id", "home_name", "lg"]].rename(columns={"home_id": "tid", "home_name": "nome"}),
                          fx[["away_id", "away_name", "lg"]].rename(columns={"away_id": "tid", "away_name": "nome"})])
               .drop_duplicates("tid"))
    print(f"notizie in archivio: {len(nd)} · finestra {nd.published_at.min()} → {fine}")
    print(f"squadre nel calendario: {len(squadre)} · leghe: {sorted(squadre.lg.dropna().unique())}")

    righe = []
    for r in squadre.itertuples(index=False):
        sub = nd[nd.team_id == r.tid]
        b7 = sub[sub.published_at >= fine - pd.Timedelta(days=7)]
        b14 = sub[sub.published_at >= fine - pd.Timedelta(days=14)]
        # filtro lingua (quello del sito) e sostanza
        it7 = sum(1 for t, d in zip(b7.title, b7.description)
                  if is_italian_news(str(t or ""), str(d or "")))
        val7 = sum(1 for t, d in zip(b7.title, b7.description)
                   if news_value(str(t or ""), str(d or "")) is None and is_italian_news(str(t or ""), str(d or "")))
        tema = Counter()
        for t, d in zip(b14.title, b14.description):
            if not is_italian_news(str(t or ""), str(d or "")):
                continue
            k, _p = classify_news(str(t or ""), str(d or ""))
            if k:
                tema[k] += 1
        righe.append({"tid": int(r.tid), "nome": r.nome, "lg": r.lg, "n7": len(b7), "n14": len(b14),
                      "it7": it7, "val7": val7, **{f"t_{k}": v for k, v in tema.items()}})
    tab = pd.DataFrame(righe).fillna(0)
    print(f"\nnotizie per squadra in 7 giorni: mediana {tab.n7.median():.0f} · "
          f"a 0: {(tab.n7 == 0).sum()}/{len(tab)}")
    print(f"di cui in italiano: mediana {tab.it7.median():.0f} · a 0: {(tab.it7 == 0).sum()}/{len(tab)}")
    print("\nper lega (mediana di voci in italiano a 7 giorni · squadre senza voci):")
    for lg, g in tab.groupby("lg"):
        print(f"  {lg:5s} {g.it7.median():5.1f} · senza voci {(g.it7 == 0).sum():3d}/{len(g)}")

    colonne_tema = [c for c in tab.columns if c.startswith("t_")]
    tot = tab[colonne_tema].sum().sort_values(ascending=False)
    print("\ncategorie (finestra 14 giorni, solo italiano):")
    for c, v in tot.items():
        print(f"  {TOPIC_LABELS.get(c[2:], c[2:]):18s} {int(v):5d}")
    clim = [c for c in colonne_tema if c[2:] in TEMA_CLIMA]
    tab["clima14"] = tab[clim].sum(axis=1)
    print(f"\nsquadre con almeno una voce di «clima» (panchina/spogliatoio/società/tifo/stadio/fuori campo) "
          f"in 14 giorni: {(tab.clima14 > 0).sum()}/{len(tab)}")
    print("per lega: " + " · ".join(
        f"{lg} {(g.clima14 > 0).sum()}/{len(g)}" for lg, g in tab.groupby("lg")))

    # ---- attendance ----
    mi = pd.read_parquet(DATA / "match_info.parquet")
    fin = mi[mi.attendance.notna()]
    print(f"\nattendance: {len(fin)}/{len(mi)} righe · "
          f"con capienza: {(fin.stadium_capacity.notna()).sum()}")
    if not fin.empty and "stadium_capacity" in fin.columns:
        ok = fin[fin.stadium_capacity.notna()].copy()
        ok["fill"] = ok.attendance / ok.stadium_capacity.replace(0, pd.NA)
        print("riempimento stadio (spettatori/capienza): media "
              f"{ok.fill.mean():.2f} · mediana {ok.fill.median():.2f} · "
              f"min {ok.fill.min():.2f} · max {ok.fill.max():.2f}")
        gare = pd.read_parquet(DATA / "fixtures.parquet")
        fin2 = ok.drop(columns=[c for c in ("league_id",) if c in ok.columns]) \
            .merge(gare[["match_id", "league_id"]], on="match_id", how="left")
        fin2["lg"] = fin2.league_id.map(chiave)
        print("per lega (riempimento mediano):", {k: round(v, 2) for k, v in fin2.groupby("lg").fill.median().items()})
        # variabilità per squadra: il riempimento è un tratto stabile o si muove?
        gare["lg"] = gare.league_id.map(chiave)
        casa = (fin2.assign(tid=fin2.home_id)
                .groupby(["tid"]).fill.agg(["mean", "std", "count"]))
        casa = casa[casa["count"] >= 3]
        print(f"squadre con 3+ gare in casa misurate: {len(casa)} · "
              f"deviazione standard mediana del riempimento: {casa['std'].median():.3f}")
        # quante squadre si discostano dalla mediana di lega?
        med = fin2.groupby("lg").fill.median().to_dict()
        squadre = fin2.assign(tid=fin2.home_id).merge(
            pd.DataFrame({"lg": list(med), "med_lg": list(med.values())}), on="lg", how="left")
        scarti = squadre.groupby("tid").apply(
            lambda g: (g.fill - g.med_lg).mean(), include_groups=False)
        print(f"squadre con scarto medio dal riempimento di lega > 0,10: "
              f"{(scarti.abs() > 0.10).sum()}/{len(scarti)} · mediana |scarto| {scarti.abs().median():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
