"""Test offline della simulazione Monte Carlo di stagione (fase 2)."""
import warnings

import numpy as np
import pandas as pd
import pytest

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


def test_rel_counts_include_playoffs():
    """POR1 (2 dirette + playoff), NED1 (2 dirette + playoff) e FRA1 (barrage) = 3 posti a rischio."""
    from fda.models.season_sim import REL_COUNTS
    assert REL_COUNTS["POR1"] == 3   # prima era 2: mancava la 16ª al playoff
    assert REL_COUNTS["NED1"] == 3 and REL_COUNTS["FRA1"] == 3
    assert REL_COUNTS["ITA1"] == 3


def test_persist_history_is_a_per_league_snapshot(tmp_path):
    """Lo storico di allenamento salvato: uno snapshot per lega, riproducibile offline."""
    from fda.models.season_sim import persist_history
    from fda.store import Store

    st = Store(tmp_path / "processed")
    hist = _synthetic_hist()
    assert persist_history(st, hist, "TEST") == len(hist)
    saved = st.read("history")
    assert len(saved) == len(hist) and set(saved["league_key"]) == {"TEST"}
    assert set(saved.columns) >= {"league_key", "date", "home", "away", "home_goals", "away_goals"}
    # un secondo run della stessa lega sostituisce lo snapshot, non lo duplica
    assert persist_history(st, hist.head(40), "TEST") == 40
    assert len(st.read("history")) == 40
    # un'altra lega si aggiunge: il laboratorio lavora su tutti i campionati insieme
    other = hist.copy()
    other["home"] = other["home"] + "B"
    other["away"] = other["away"] + "B"
    persist_history(st, other, "ALTRO")
    both = st.read("history")
    assert set(both["league_key"]) == {"TEST", "ALTRO"} and len(both) == 40 + len(hist)
    # store assente o storico vuoto: nessun errore, nessuna scrittura
    assert persist_history(None, hist, "TEST") == 0
    assert persist_history(st, hist.head(0), "TEST") == 0
    st.close()


def test_match_grid_uses_the_published_calibration():
    """Le proiezioni di stagione usano la stessa calibrazione delle schede partita."""
    import warnings

    from fda.models.calibration import Calibration
    from fda.models.season_sim import _match_grid
    from fda.models.predict import DixonColesModel, EloModel

    warnings.filterwarnings("ignore")
    hist = _synthetic_hist()
    dc = DixonColesModel().fit(hist)
    elo = EloModel().fit(hist)
    neutral = (1.35, 1.10)
    raw, lh0, la0 = _match_grid(dc, elo, "T0", "T1", 0.7, neutral)
    cal = Calibration(lambda_scale=0.94, rho_shift=-0.04)
    adj, lh1, la1 = _match_grid(dc, elo, "T0", "T1", 0.7, neutral, calibration=cal)
    assert lh1 == pytest.approx(lh0 * 0.94, abs=1e-9) and la1 == pytest.approx(la0 * 0.94, abs=1e-9)
    assert raw.sum() == pytest.approx(1.0, abs=1e-9) and adj.sum() == pytest.approx(1.0, abs=1e-9)
    # meno gol attesi → più massa sul pareggio: è l'effetto cercato, non un arrotondamento
    i, j = np.indices(adj.shape)
    assert adj[i == j].sum() > raw[i == j].sum()
    # squadra senza storico DC: λ neutre, la calibrazione non inventa nulla
    neut, lm, la = _match_grid(dc, elo, "MaiVista", "T1", 0.7, neutral, calibration=cal)
    assert (lm, la) == neutral and neut.sum() == pytest.approx(1.0, abs=1e-9)


def test_simulate_league_accepts_calibration():
    """La simulazione completa gira anche con la calibrazione attiva (stesse invarianti)."""
    import warnings

    from fda.models.calibration import Calibration

    warnings.filterwarnings("ignore")
    hist = _synthetic_hist()
    teams = sorted(set(hist.home))
    rem = pd.DataFrame({"home": ["T1", "T2"], "away": ["T0", "T3"]})
    pts, gd, pl = _bases(teams)
    df = simulate_league(hist, rem, pts, gd, pl, n_sims=200, seed=11, rel_count=3,
                         calibration=Calibration(lambda_scale=0.94, rho_shift=-0.04))
    assert len(df) == len(teams)
    assert abs(df.p_title.sum() - 1.0) < 1e-3
    assert (df.exp_points >= df.points).all()
