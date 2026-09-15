"""Analisi avanzate: griglia Dixon-Coles, WP in-play, corsa xG, qualità tiri, scontro."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fda.site.advanced import (
    dixon_coles_grid,
    goals_view,
    grid_1x2,
    probability_steps,
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


def test_style_rows_split_as_quotas_with_declared_sources():
    """La scomposizione xG è pubblicata come quota interna a una sola fonte (docs/20 §4)."""
    pred = {"lambda_home": 1.8, "lambda_away": 1.1}
    home = {"source": "Understat", "played": 4, "xg_pm": 3.45, "xga_pm": 1.2,
            "open_pm": 2.55, "set_pm": 0.25, "split_played": 4}
    away = {"source": "FotMob", "played": 5, "xg_pm": 1.6, "xga_pm": 1.1,
            "open_pm": 1.30, "set_pm": 0.35, "split_played": 5}
    clash = style_rows(home, away, pred)
    by = {r["label"]: r for r in clash["rows"]}
    # nessuna riga invita a sommare due fonti: le quote sommano a 100 per costruzione
    for lado in ("h", "a"):
        assert by["xG da azione manovrata (quota)"][lado] + \
            by["xG da palle inattive (quota)"][lado] == pytest.approx(100.0, abs=0.15)
    assert by["xG da azione manovrata (quota)"]["h"] == pytest.approx(91.1, abs=0.1)
    # le quote non hanno un «migliore»: sono stile, non gradimento — e non portano ▲
    assert by["xG da azione manovrata (quota)"]["best"] is None
    assert by["xG da azione manovrata (quota)"]["suffix"] == "%"
    # ogni riga dichiara la SUA fonte; fonti diverse fra le due colonne sono dette a voce alta
    assert "colonna a sinistra Understat su 4 gare" in (by["xG / gara"]["help"] or "")
    assert "colonna a destra FotMob su 5 gare" in (by["xG / gara"]["help"] or "")
    assert clash["mixed_sources"] is True
    same = style_rows({**home}, {**home, "xg_pm": 2.0}, pred)
    assert same["mixed_sources"] is False
    same_by = {r["label"]: r for r in same["rows"]}
    assert "media stagionale Understat su 4 gare" in (same_by["xG / gara"]["help"] or "")
    assert "due fornitori" not in (same_by["xG / gara"]["help"] or "")
    # i valori assoluti restano nel tooltip, non nella tabella (niente somme spurie)
    assert "2,55" in (by["xG da azione manovrata (quota)"]["help"] or "")


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


def test_goals_view_counts_100_matches_and_20_dots():
    """Istogramma e dotplot devono tornare a occhio: 100 partite e 20 punti, sempre."""
    for lh, la, rho in [(1.69, 1.13, -0.10), (0.7, 0.6, -0.05), (3.2, 2.8, 0.02), (0.0, 0.0, 0.0)]:
        gv = goals_view(lh, la, rho)
        assert sum(b["per100"] for b in gv["bars"]) == 100, f"{lh}+{la}: le barre non sommano 100"
        assert sum(b["p"] for b in gv["bars"]) == pytest.approx(1.0, abs=1e-3)
        assert sum(c["n"] for c in gv["columns"]) == gv["n_dots"] == 20
        assert len(gv["columns"]) == len(gv["bars"])       # assi allineati fra le due viste
        assert 0 <= gv["q10"] <= gv["mediana"] <= gv["q90"] <= gv["cap"] + 1
        # l'intervallo 10°-90° su totali discreti copre sempre più dell'80% (F(q90) ≥ 0,90 e
        # F(q10 − 1) < 0,10) e mai più del 100%: è il numero pubblicato in didascalia, quindi
        # non è un tondo dichiarato a priori ma la massa vera di quella gara
        assert 80.0 < gv["copertura"] <= 100.0, f"{lh}+{la}: copertura {gv['copertura']}%"
        # l'estremo superiore è «7+» quando il percentile cade nella coda: intervallo aperto
        assert (gv["q90_label"] == gv["coda_label"]) == (gv["q90"] == gv["cap"] + 1)
        # nessuna barra oltre il contenitore, e la scala è occupata interamente dalla barra
        # più alta — coda compresa: con λ 3,2+2,8 la massa «7+» supera quella della moda
        altezze = [b["h"] for b in gv["bars"]]
        assert max(altezze) == 1.0 and min(altezze) >= 0.0, f"{lh}+{la}: altezze {altezze}"
        assert max(altezze[:gv["cap"] + 1]) <= altezze[-1] + 1e-9 or gv["bars"][-1]["per100"] <= max(
            b["per100"] for b in gv["bars"][:gv["cap"] + 1])
        assert gv["media"] == pytest.approx(lh + la, abs=0.06)   # la media è quella della griglia
        assert gv["bars"][gv["moda"]]["mode"]
        assert gv["bars"][-1]["tail"] and gv["bars"][-1]["label"] == gv["coda_label"]


def test_goals_view_coda_non_supera_il_contenitore():
    """La barra «7+» usciva dal riquadro: `height:183%` su 5 pagine pubblicate (docs/19 §3.4).

    Causa: la scala era il massimo dei soli totali 0..cap, ma con λ totale 4,7-5,5 la coda ha più
    massa di qualunque singolo totale. La scala ora include la coda, quindi nessuna barra straborda
    e le altezze restano proporzionali alle probabilità (nessun clamp che falserebbe il grafico).
    """
    gv = goals_view(1.84, 3.66)                    # la gara peggiore misurata: 5781741 (NED1)
    coda = gv["bars"][-1]
    assert coda["tail"] and coda["p"] > max(b["p"] for b in gv["bars"][:-1]), "caso non significativo"
    assert coda["h"] == 1.0 and round(coda["h"] * 100) == 100
    assert all(0.0 <= b["h"] <= 1.0 for b in gv["bars"])
    # con la coda come estremità superiore, l'intervallo è aperto e va scritto «7+», non «7»
    assert gv["q90_label"] == gv["coda_label"] == "7+" and gv["q10"] == 3 and gv["mediana"] == 5
    assert gv["copertura"] > 90.0


def test_goals_view_agrees_with_the_published_markets():
    """Le barre derivano dalla stessa griglia dei mercati: Over 1,5/2,5/3,5 devono tornare."""
    from fda.models.dc_grid import GRID_SIZE, probability_grid
    from fda.models.predict import _grid_markets

    lh, la, rho = 1.69, 1.13, -0.10
    gv = goals_view(lh, la, rho)
    # la griglia pubblicata è quella condivisa (11×11): le barre del sito devono tornare con
    # i mercati che la scheda mostra davvero, non con una matrice più corta
    m = _grid_markets(probability_grid(lh, la, rho, size=GRID_SIZE))
    for soglia, key in ((2, "p_over15"), (3, "p_over25"), (4, "p_over35")):
        dalle_barre = sum(b["p"] for b in gv["bars"] if b["g"] >= soglia)
        assert dalle_barre == pytest.approx(m[key], abs=3e-3), key


def test_probability_steps_is_a_real_chain_not_a_reconstruction():
    base = {"dc_p_home": 0.4612, "dc_p_draw": 0.2684, "dc_p_away": 0.2704,
            "elo_p_home": 0.5242, "elo_p_draw": 0.2445, "elo_p_away": 0.2313,
            "blend_p_home": 0.4801, "blend_p_draw": 0.2612, "blend_p_away": 0.2587,
            "w_dc": 0.7, "p_home": 0.4691, "p_draw": 0.2742, "p_away": 0.2567,
            "calibration_version": "grid-cal-1.0", "lambda_scale": 0.94, "calibration_n_fit": 5791}
    # ricetta di produzione (tilt, dal 2026-09-13): la catena ha quattro passi e il passo
    # della griglia inclinata è quello che ha davvero prodotto il vettore salvato in blend_p_*
    steps = probability_steps({**base, "ensemble_mode": "tilt", "tilt": 1.0832})
    assert [s["label"] for s in steps] == ["Modello sui gol (Dixon-Coles)",
                                           "Media pesata con i rating Elo",
                                           "Griglia sulle λ inclinate dall'Elo", "Calibrazione"]
    # il passo 2 è davvero la media pesata dichiarata (ricalcolabile dalla pagina)
    w = base["w_dc"]
    for k, elo in (("p_home", "elo_p_home"), ("p_draw", "elo_p_draw"), ("p_away", "elo_p_away")):
        assert steps[1][k] == pytest.approx(w * steps[0][k] + (1 - w) * base[elo], abs=1e-9)
    # il passo 3 riporta il vettore delle λ inclinate così com'è stato salvato, con la sua misura
    assert steps[2]["p_home"] == pytest.approx(base["blend_p_home"]) and "1,083" in steps[2]["note"]
    assert steps[0]["delta_pp"] is None
    # ogni Δ pubblicato è la differenza fra i valori STAMPATI dei due passi adiacenti
    from fda.site.fmt import pct_triple
    from itertools import pairwise

    for prev_asm, cur in pairwise(steps):
        disp_prev = max(pct_triple((prev_asm["p_home"], prev_asm["p_draw"], prev_asm["p_away"]), 1))
        disp_cur = max(pct_triple((cur["p_home"], cur["p_draw"], cur["p_away"]), 1))
        assert cur["delta_pp"] == pytest.approx(round(disp_cur - disp_prev, 1), abs=1e-9)
    assert steps[3]["top"] == "1" and "5.791" in steps[3]["note"]
    for s in steps:
        assert s["p_home"] + s["p_draw"] + s["p_away"] == pytest.approx(1.0, abs=1e-6)
    # previsione storica (ricetta precedente): il vettore salvato in blend_p_* è dichiarato
    # per quello che era — niente etichetta «media» su un numero che non è una media
    legacy = probability_steps(base)
    assert [s["label"] for s in legacy] == ["Modello sui gol (Dixon-Coles)",
                                            "Media pesata con i rating Elo",
                                            "Media con i rating Elo", "Calibrazione"]
    assert "obiettivo" in legacy[2]["note"]


def test_probability_steps_degrades_when_nothing_is_traced():
    assert probability_steps(None) == [] and probability_steps({}) == []
    # solo il vettore pubblicato: non c'è nessuna catena da mostrare
    assert probability_steps({"p_home": 0.5, "p_draw": 0.26, "p_away": 0.24}) == []
    # passi identici: la "scomposizione" sarebbe rumore
    same = {"dc_p_home": 0.46, "dc_p_draw": 0.27, "dc_p_away": 0.27,
            "p_home": 0.46, "p_draw": 0.27, "p_away": 0.27}
    assert probability_steps(same) == []
    # vettore incoerente (somma 1,05): meglio nessun blocco che un blocco sbagliato
    bad = {"dc_p_home": 0.5, "dc_p_draw": 0.3, "dc_p_away": 0.25,
           "p_home": 0.48, "p_draw": 0.29, "p_away": 0.23}
    assert probability_steps(bad) == []


def test_match_analysis_goals_view(tmp_path):
    """Senza λ la scheda non inventa una distribuzione; con λ la vista è coerente."""
    st = Store(tmp_path / "processed")
    st.upsert("predictions", [
        {"match_id": 1, "lambda_home": 1.7, "lambda_away": 1.1, "dc_rho": -0.06,
         "p_home": 0.47, "p_draw": 0.27, "p_away": 0.26, "made_at": "2026-09-01T12:00:00+00:00"},
        {"match_id": 2, "p_home": 0.4, "p_draw": 0.3, "p_away": 0.3,
         "made_at": "2026-09-01T12:00:00+00:00"},
    ])
    ma = MatchAnalysis(st)
    gv = ma.goals_view(ma.prediction(1))
    assert gv and sum(b["per100"] for b in gv["bars"]) == 100
    assert gv["lambda_home"] == pytest.approx(1.7) and gv["rho"] == pytest.approx(-0.06)
    assert ma.goals_view(ma.prediction(2)) is None      # previsione senza λ → nessun grafico
    assert ma.goals_view(None) is None
    st.close()
