"""Corpus storico **surrogato** ricostruito da ``h2h.parquet`` per il lavoro offline.

Perché esiste: dal sandbox dell'agente i mirror di football-data.co.uk non sono raggiungibili
(vedi ``docs/BRIEFING_NUOVA_SESSIONE.md`` §7), quindi lo storico vero non si può scaricare.
La tabella ``h2h`` contiene però i precedenti reali raccolti da FotMob (7.411 gare dal 1999,
con id risolvibili in nomi tramite ``fixtures``): abbastanza per provare **meccanismi**
(coerenza delle griglie, effetto di una calibrazione, confronto fra famiglie di modelli sulle
stesse gare) senza rete.

Limiti, da dichiarare sempre quando si usano questi numeri:
- non è un censimento delle giornate: sono gli incroci fra le coppie di squadre già a
  calendario, quindi un sottoinsieme sbilanciato verso le gare con più precedenti;
- per lega restano poche centinaia di partite per stagione → i fit sono più rumorosi di
  quelli in produzione e il livello dei gol non è confrontabile con quello reale
  (misurato: λ sottostimate del 10% su questo corpus, sovrastimate dell'8,6% su quello vero);
- le competizioni diverse dal campionato (coppe, amichevoli) vengono escluse per nome.

I numeri **autorevoli** restano quelli del run in GitHub Actions sullo storico datahub
completo (``fda lab`` senza ``--history``).

Uso::

    python scripts/corpus_da_h2h.py --out /tmp/corpus_h2h.parquet [--since 2014]
    fda lab --history /tmp/corpus_h2h.parquet --candidates "dc_puro elo mix_50"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fda.store import Store
from fda.teams import canonical

#: nome della competizione FotMob nei precedenti → lega del progetto
LEAGUE_BY_NAME = {
    "Serie A": "ITA1", "Premier League": "ENG1", "LaLiga": "ESP1", "Bundesliga": "GER1",
    "Ligue 1": "FRA1", "Eredivisie": "NED1", "Liga Portugal": "POR1", "Primeira Liga": "POR1",
    "Liga ZON Sagres": "POR1",
}


def build(store: Store | None = None, since: int = 2014) -> pd.DataFrame:
    """Storico surrogato: colonne ``date, league_key, home, away, home_goals, away_goals``."""
    store = store or Store()
    h2h = store.read("h2h")
    fixtures = store.read("fixtures")
    if h2h.empty or fixtures.empty:
        return pd.DataFrame()
    names: dict[int, str] = {}
    for row in fixtures.itertuples(index=False):
        names[int(row.home_id)] = str(row.home_name)
        names[int(row.away_id)] = str(row.away_name)
    df = h2h.copy()
    df["date"] = pd.to_datetime(df["utc"], utc=True)
    df["league_key"] = df["league"].map(LEAGUE_BY_NAME)
    df["home"] = df["home_id"].map(names).map(canonical)
    df["away"] = df["away_id"].map(names).map(canonical)
    df = df.dropna(subset=["league_key", "home", "away", "home_goals", "away_goals"])
    df = df[df["date"].dt.year >= since]
    df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce").astype("Int64")
    df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["home_goals", "away_goals"])
    df["season"] = df["date"].dt.year.astype(str)
    df = df.drop_duplicates(subset=["date", "home", "away", "home_goals", "away_goals"])
    return (df[["date", "season", "league_key", "home", "away", "home_goals", "away_goals"]]
            .sort_values(["league_key", "date"]).reset_index(drop=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Parquet di destinazione")
    ap.add_argument("--since", type=int, default=2014)
    args = ap.parse_args()
    df = build(since=args.since)
    if df.empty:
        raise SystemExit("nessuna riga ricostruita: servono h2h e fixtures nello store")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"{len(df)} gare salvate in {out}")
    print(df.groupby("league_key").agg(n=("date", "size"), prima=("date", "min"),
                                       ultima=("date", "max")).to_string())


if __name__ == "__main__":
    main()
