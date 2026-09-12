"""Analisi avanzate: griglia Dixon-Coles, WP in-play, corsa xG, qualità tiri, scontro."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fda.site.advanced import (
    dixon_coles_grid,
    grid_1x2,
    score_matrix,
    shot_quality,
    state_probs,
    style_rows,
    wp_path,
    xg_race,
)
from fda.site.analysis import MatchAnalysis
from fda.store import Store


def test_dixon_coles_grid_sums_to_one_and_rho_zero_is_independent():
    g0 = dixon_coles_grid(1.4, 1.1, rho=0.0, max_goals=12)
    assert abs(float(g0.sum()) - 1.0) < 1e-9
    # ρ = 0 → 0-0 = prodotto delle Poisson (salvo rinormalizzazione della coda)
    from scipy.stats import poisson
    p00 = float(poisson.pmf(0, 1.4) * poisson.pmf(0, 1.1))
    assert abs(g0[0, 0] - p00 / float(
        sum(poisson.pmf(i, 1.4) * poisson.pmf(j, 1.1) for i in range(13) for j in range(13))
    )) < 1e-9
    # ρ negativo (tipico) alza 0-0 rispetto a ρ=0
    g_neg = dixon_coles_grid(1.4, 1.1, rho=-0.1, max_goals=12)
    assert g_neg[0, 0] > g0[0, 0]
    ph, pd_, pa = grid_1x2(g0)
    assert abs(ph + pd_ + pa - 1.0) < 1e-9


def test_score_matrix_mode_and_opacity():
    m = score_matrix(2.4, 0.6, rho=0.0, cap=5)
    assert m["mode"] == "2-0" or m["mode_i"] >= m["mode_j"]
    assert m["cells"][0][0]["i"] == 0 and m["cells"][0][0]["p"] > 0
    assert 0.12 <= m["cells"][0][0]["op"] <= 1.0
    assert sum(1 for row in m["cells"] for c in row if c["mode"]) == 1
    assert m["p_tail"] >= 0


def test_state_probs_full_time_and_kickoff():
    # a 90' il risultato è già scritto
    assert state_probs(2, 0, 1.5, 1.2, 90) == (1.0, 0.0, 0.0)
    assert state_probs(1, 1, 1.5, 1.2, 90) == (0.0, 1.0, 0.0)
    assert state_probs(0, 3, 1.5, 1.2, 95) == (0.0, 0.0, 1.0)
    # al calcio d'inizio, 2-0 casa favorita → P(1) > P(2)
    ph, pd_, pa = state_probs(0, 0, 2.0, 0.8, 0.0, rho=0.0)
    assert ph > pa and abs(ph + pd_ + pa - 1.0) < 1e-6
    # 2-0 al 89' è quasi chiuso
    ph89, _, _ = state_probs(2, 0, 1.5, 1.5, 89.0)
    assert ph89 > 0.97


def test_wp_path_own_goal_and_order():
    """`home` è la squadra **a cui il gol è attribuito**: FotMob ha già contato gli autogol.

    Verificato su 226 partite finite (22 con autogol): usare `isHome` tal quale riproduce il
    risultato finale 225/226 e 22/22 sui casi con autogol; ribaltarlo sugli autogol dà 0/22.
    """
    goals = [
        {"minute": 10, "home": True, "own_goal": False, "player": "A"},
        {"minute": 40, "home": True, "own_goal": True, "player": "B"},   # autogol di B → gol casa
        {"minute": 70, "home": False, "own_goal": False, "player": "C"},
    ]
    path = wp_path(goals, 1.5, 1.2, rho=0.0)
    assert path[0]["hg"] == 0 and path[0]["ag"] == 0 and path[0]["event"] is None
    assert path[1]["hg"] == 1 and path[1]["ag"] == 0 and path[1]["event"] == "goal"
    assert path[2]["hg"] == 2 and path[2]["ag"] == 0
    assert path[2]["scorer_home"] is True      # nessun ribaltamento: l'autogol vale per la casa
    assert path[3]["hg"] == 2 and path[3]["ag"] == 1
    assert path[3]["scorer_home"] is False
    assert "x" in path[0] and "y_h" in path[0]


def test_xg_race_cumulative_excludes_own_goals():
    shots = pd.DataFrame([
        {"team_id": 1, "minute": 10, "minute_added": None, "xg": 0.4, "event_type": "Goal",
         "player_name": "A", "is_own_goal": False},
        {"team_id": 2, "minute": 20, "minute_added": None, "xg": 0.3, "event_type": "Miss",
         "player_name": "B", "is_own_goal": False},
        {"team_id": 1, "minute": 30, "minute_added": None, "xg": 0.9, "event_type": "Goal",
         "player_name": "C", "is_own_goal": True},  # escluso
    ])
    race = xg_race(shots, 1, 2)
    assert race["n"] == 2
    assert race["home_xg"] == 0.4
    assert race["away_xg"] == 0.3
    assert len(race["goals"]) == 1 and race["goals"][0]["player"] == "A"
    assert race["poly_h"] and race["poly_a"]
    assert xg_race(pd.DataFrame(), 1, 2) is None


def test_shot_quality_buckets_and_finishing():
    shots = pd.DataFrame([
        {"team_id": 1, "xg": 0.20, "xgot": 0.30, "event_type": "Goal", "situation": "RegularPlay",
         "is_own_goal": False, "is_inside_box": True, "is_on_target": True,
         "player_name": "A", "minute": 12},
        {"team_id": 1, "xg": 0.10, "xgot": 0.00, "event_type": "Miss", "situation": "FromCorner",
         "is_own_goal": False, "is_inside_box": True, "is_on_target": False,
         "player_name": "B", "minute": 40},
        {"team_id": 1, "xg": 0.76, "xgot": 0.80, "event_type": "Goal", "situation": "Penalty",
         "is_own_goal": False, "is_inside_box": True, "is_on_target": True,
         "player_name": "C", "minute": 70},
        {"team_id": 2, "xg": 0.50, "xgot": 0.40, "event_type": "Miss", "situation": "RegularPlay",
         "is_own_goal": False, "is_inside_box": False, "is_on_target": True,
         "player_name": "D", "minute": 8},
    ])
    q = shot_quality(shots, 1)
    assert q["n"] == 3 and abs(q["xg"] - 1.06) < 1e-9
    assert q["open"]["n"] == 1 and q["set"]["n"] == 1 and q["pen"]["n"] == 1
    assert q["goals"] == 2
    assert q["best"]["situation"] == "rigore"
    assert q["over_xg"] == 2 - q["xg"]
    assert shot_quality(shots, 99) is None


def test_style_rows_degrades_without_style():
    pred = {"lambda_home": 1.8, "lambda_away": 1.1, "dc_attack_home": 0.4,
            "dc_attack_away": 0.1, "dc_defence_home": -0.2, "dc_defence_away": 0.3}
    clash = style_rows(None, None, pred)
    labels = [r["label"] for r in clash["rows"]]
    assert "Gol attesi (λ)" in labels and "Attacco DC" in labels
    assert style_rows(None, None, None) is None
    # PPDA: più basso = meglio (pressing)
    styled = style_rows({"ppda": 8.0, "xg_pm": 1.5}, {"ppda": 14.0, "xg_pm": 1.1}, pred)
    by = {r["label"]: r for r in styled["rows"]}
    assert by["PPDA (↓ = più pressing)"]["best"] == "h"
    assert by["xG / gara"]["best"] == "h"


def test_match_analysis_score_matrix_and_wp(tmp_path):
    st = Store(tmp_path / "processed")
    st.upsert("predictions", [
        {"match_id": 1, "lambda_home": 2.0, "lambda_away": 0.9, "dc_rho": -0.05,
         "p_home": 0.6, "p_draw": 0.22, "p_away": 0.18, "made_at": "2026-09-01T12:00:00+00:00"},
    ])
    st.upsert("events", [
        # home_score/away_score di FotMob = punteggio **prima** del gol (verificato 226/226)
        {"match_id": 1, "type": "Goal", "minute": 15, "minute_added": None, "is_home": True,
         "player_name": "X", "own_goal": False, "home_score": 0, "away_score": 0},
    ])
    ma = MatchAnalysis(st)
    pred = ma.prediction(1)
    m = ma.score_matrix(pred)
    assert m and m["cells"][0][0]["p"] > 0
    wp = ma.match_wp(pred, ma.timeline(1))
    assert wp and len(wp["points"]) == 2 and wp["poly_h"]
    assert ma.match_wp(None, []) is None
    assert ma.score_matrix(None) is None
    st.close()


def _synthetic_hist(n_teams: int = 12, seed: int = 7) -> pd.DataFrame:
    """Storico sintetico (264 partite) per i test che richiedono un fit Dixon-Coles."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    rows = []
    for i, h in enumerate(teams):
        for a in teams[i + 1:]:
            for _ in range(4):
                rows.append({"date": pd.Timestamp("2024-08-01") + pd.Timedelta(days=int(rng.integers(0, 300))),
                             "home": h, "away": a,
                             "home_goals": int(rng.poisson(1.4)), "away_goals": int(rng.poisson(1.1))})
    return pd.DataFrame(rows)


def test_dixon_coles_grid_uses_the_fitted_model_tau():
    """La τ del sito deve essere quella del modello addestrato, non quella dell'helper.

    Regressione (verificata a 2,8e-17): ``create_dixon_coles_grid`` di penaltyblog applica i
    fattori 1+λρ e 1+μρ a celle invertite rispetto a ``DixonColesGoalModel.predict`` — ~1 pp
    di differenza sull'1X2, cioè una pagina incoerente con la propria matrice punteggi.
    """
    from fda.models.predict import DixonColesModel

    m = DixonColesModel(shrink_prior=0.0).fit(_synthetic_hist())
    for home, away in (("T0", "T5"), ("T3", "T11"), ("T7", "T2")):
        d = m.predict(home, away)
        ref = np.asarray(m.model.predict(home, away, max_goals=10).grid)
        mine = dixon_coles_grid(d["lambda_home"], d["lambda_away"], rho=d["dc_rho"], max_goals=9)
        assert mine.shape == ref.shape
        assert np.abs(mine - ref).max() < 1e-12
        # e i mercati della griglia condivisa coincidono con quelli del modello
        assert abs(grid_1x2(mine)[0] - float(np.asarray(m.model.predict(home, away, max_goals=10).home_draw_away)[0])) < 1e-12
