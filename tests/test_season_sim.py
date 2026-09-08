"""Test offline della simulazione Monte Carlo di stagione (fase 2)."""
import warnings

import numpy as np
import pandas as pd

from fda.models.season_sim import simulate_league


def _synthetic_hist(seed=7):
    """10 squadre, doppio girone andata/ritorno paritario → 90 partite (minimo DC: 50)."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(10)]
    rows = []
    for rd in range(2):
        for i in range(10):
            for j in range(10):
                if i != j and (i + j + rd) % 2 == 0:
                    rows.append({"date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=len(rows)),
                                 "home": teams[i], "away": teams[j],
                                 "home_goals": int(rng.poisson(1.4)), "away_goals": int(rng.poisson(1.1))})
    return pd.DataFrame(rows)


def _bases(teams, extra_team=None):
    pts = {t: 10.0 for t in teams}
    gd = {t: 4 for t in teams}
    pl = {t: 6 for t in teams}
    if extra_team:
        pts[extra_team], gd[extra_team], pl[extra_team] = 2, -3, 3
    return pts, gd, pl


def test_simulate_league_invariants():
    warnings.filterwarnings("ignore")
    hist = _synthetic_hist()
    teams = sorted(set(hist.home))
    rem = pd.DataFrame({"home": ["T1", "T2"], "away": ["T0", "T3"]})
    pts, gd, pl = _bases(teams)
    df = simulate_league(hist, rem, pts, gd, pl, n_sims=300, seed=42, rel_count=3)
    assert len(df) == len(teams)
    # un campione / 4 in top-4 / 3 retrocesse per simulazione (±arrotondamento a 4 decimali)
    assert abs(df.p_title.sum() - 1.0) < 1e-3
    assert abs(df.p_top4.sum() - 4.0) < 1e-3
    assert abs(df.p_rel.sum() - 3.0) < 1e-3
    assert (df.exp_points >= df.points).all()  # i punti non possono diminuire
    assert (df.p_title >= 0).all() and (df.p_title <= 1).all()
    # determinismo con lo stesso seed
    df2 = simulate_league(hist, rem, pts, gd, pl, n_sims=300, seed=42, rel_count=3)
    pd.testing.assert_frame_equal(df.drop(columns=["made_at"]), df2.drop(columns=["made_at"]))


def test_simulate_league_missing_team_neutral():
    """Squadra senza storico DC (es. neopromossa): parametri neutri, nessun crash."""
    warnings.filterwarnings("ignore")
    hist = _synthetic_hist()
    teams = sorted(set(hist.home))
    rem = pd.DataFrame({"home": ["Nuova"], "away": ["T0"]})
    pts, gd, pl = _bases(teams, extra_team="Nuova")
    df = simulate_league(hist, rem, pts, gd, pl, n_sims=200, seed=1, rel_count=3)
    assert "Nuova" in set(df.team)          # simulata comunque, con λ neutre
    assert df.p_title.sum() == 1.0
    assert (df.loc[df.team == "Nuova", "played"] == 3).all()
