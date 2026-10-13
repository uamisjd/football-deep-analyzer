"""Verifica offline del backfill Understat (docs/91), senza rete né scritture.

Conta le gare FINITE (non il calendario futuro), verifica la completezza dei cinque
campionati e incrocia ogni gara con i due lati in understat_team_matches. Il calendario
atteso vale per le stagioni 2021–2025: non va esteso a nuovi formati senza revisione.
Uso: python scripts/audit_understat_storico.py [--data data/processed]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEASONS = (2021, 2022, 2023, 2024, 2025)
LEAGUES = ("EPL", "La_Liga", "Serie_A", "Bundesliga", "Ligue_1")
KEYS = ["league_slug", "season", "team_id", "date"]
VALUES = ["goals", "goals_against", "xg", "xga"]


def audit(matches: pd.DataFrame, teams: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Conteggi per stagione/lega e difetti; non importa parser né funzioni del modello."""
    problems: list[str] = []
    counts = pd.DataFrame(0, index=SEASONS, columns=LEAGUES)
    match_cols = {"understat_id", "league_slug", "season", "utc_kickoff", "is_result",
                  "home_id", "away_id", "home_goals", "away_goals", "home_xg", "away_xg"}
    for name, df, required in (("partite", matches, match_cols),
                                ("lati", teams, set(KEYS + VALUES + ["is_home"]))):
        missing = required - set(df.columns)
        if missing:
            problems.append(f"{name}: colonne mancanti {sorted(missing)}")
    if problems:
        return counts, problems

    m = matches[matches["season"].isin(SEASONS)].copy()
    t = teams[teams["season"].isin(SEASONS)].copy()
    if m["understat_id"].duplicated().any():
        problems.append("partite: ID Understat duplicati")
    if not m["is_result"].eq(True).all():
        problems.append("storico: presenti gare non finite")
    m = m[m["is_result"].eq(True)]
    counts = m.groupby(["season", "league_slug"]).size().unstack(fill_value=0)
    counts = counts.reindex(index=SEASONS, columns=LEAGUES, fill_value=0).fillna(0).astype(int)
    for season in SEASONS:
        for league in LEAGUES:
            n_teams = 18 if league == "Bundesliga" or (league == "Ligue_1" and season >= 2023) else 20
            expected = n_teams * (n_teams - 1)
            if counts.loc[season, league] != expected:
                problems.append(f"{season}/{league}: {counts.loc[season, league]} finite, attese {expected}")
    if not set(m["league_slug"]).issubset(LEAGUES) or not set(t["league_slug"]).issubset(LEAGUES):
        problems.append("storico: campionati fuori perimetro")
    v = m[["home_goals", "away_goals", "home_xg", "away_xg"]].apply(pd.to_numeric, errors="coerce")
    if not (np.isfinite(v).all().all() and v.ge(0).all().all()):
        problems.append("partite: gol/xG mancanti, non finiti o negativi")
    goals = v[["home_goals", "away_goals"]]
    if not goals.eq(goals.round()).all().all():
        problems.append("partite: gol non interi")

    sides = []
    for side, other in (("home", "away"), ("away", "home")):
        one = m[["league_slug", "season", f"{side}_id", "utc_kickoff", f"{side}_goals",
                 f"{other}_goals", f"{side}_xg", f"{other}_xg"]].copy()
        one.columns = KEYS + VALUES
        one["is_home"] = side == "home"
        sides.append(one)
    expected_sides = pd.concat(sides, ignore_index=True)
    for name, frame in (("partite", expected_sides), ("lati", t)):
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        if frame[KEYS].isna().any().any():
            problems.append(f"{name}: chiavi mancanti o date non valide")
        if frame.duplicated(KEYS).any():
            problems.append(f"{name}: chiavi lato-squadra duplicate")
    # Con chiavi ambigue non inventiamo un abbinamento many-to-many.
    if expected_sides.duplicated(KEYS).any() or t.duplicated(KEYS).any():
        return counts, problems
    joined = expected_sides.merge(t, on=KEYS, how="outer", suffixes=("_m", "_t"),
                                  indicator=True, validate="one_to_one")
    unmatched = int(joined["_merge"].ne("both").sum())
    if unmatched:
        problems.append(f"incrocio partite/lati: {unmatched} righe senza corrispondenza")
    both = joined[joined["_merge"].eq("both")]
    for col in VALUES + ["is_home"]:
        a = pd.to_numeric(both[f"{col}_m"], errors="coerce").to_numpy(float)
        b = pd.to_numeric(both[f"{col}_t"], errors="coerce").to_numpy(float)
        n = int((~np.isclose(a, b, atol=1e-6, rtol=0)).sum())
        if n:
            problems.append(f"incrocio {col}: {n} differenze oltre 1e-6")
    return counts, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    def read(name: str) -> pd.DataFrame:
        path = args.data / f"{name}.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()

    counts, problems = audit(read("understat_matches"), read("understat_team_matches"))
    print("Understat 2021–2025: gare finite per stagione iniziale (2021 = 2021/22)")
    print(counts.assign(totale=counts.sum(axis=1)).to_string())
    print(f"Totale: {counts.to_numpy().sum()} gare · difetti: {len(problems)}")
    for message in problems[:10]:
        print(f"  - {message}")
    if len(problems) > 10:
        print(f"  … altri {len(problems) - 10} difetti")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
