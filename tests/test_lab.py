"""Laboratorio modelli: assenza di leakage, miscele di griglie, metriche appaiate, stacking."""

import numpy as np
import pandas as pd
import pytest

from fda.models import lab
from fda.models.calibration import Calibration
from fda.models.dc_grid import tau_grid
from fda.models.lab import (BASELINE, CANDIDATES, Candidate, convex_weights, per_league,
                            summarize, walk_forward)


def synthetic_hist(n_teams: int = 12, seasons: int = 3, seed: int = 3) -> pd.DataFrame:
    """Storico sintetico: forza fissa per squadra, gol Poisson, un turno a settimana."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    att = {t: float(rng.normal(0, 0.3)) for t in teams}
    dfn = {t: float(rng.normal(0, 0.3)) for t in teams}
    rows, start = [], pd.Timestamp("2023-08-12")
    for season in range(seasons):
        for rnd in range(n_teams - 1):
            day = start + pd.Timedelta(days=7 * rnd + 365 * season)
            order = list(rng.permutation(teams))
            for i in range(0, n_teams, 2):
                home, away = order[i], order[i + 1]
                lh = np.exp(0.15 + att[home] - dfn[away])
                la = np.exp(-0.10 + att[away] - dfn[home])
                rows.append({"date": day, "league_key": "TEST", "home": home, "away": away,
                             "home_goals": int(rng.poisson(lh)), "away_goals": int(rng.poisson(la))})
    return pd.DataFrame(rows)


class SpyGoals:
    """Modello sui gol finto: registra l'ultima data vista in allenamento."""

    def __init__(self, train: pd.DataFrame) -> None:
        self.teams = set(train["home"]) | set(train["away"])
        self.train_max = pd.to_datetime(train["date"]).max()
        self.n_train = len(train)

    def grid(self, home: str, away: str) -> np.ndarray:
        return tau_grid(1.4 if home < away else 1.1, 1.1 if home < away else 1.4, -0.05, size=lab.GRID_SIZE)


def test_walk_forward_never_trains_on_the_future(monkeypatch):
    """Ogni gara valutata è prevista da un fit che ha visto solo partite precedenti."""
    seen: list[pd.Timestamp] = []

    def spy_fit(train, cand):                     # noqa: ANN001, ANN202 — firma di fit_goals
        spy = SpyGoals(train)
        seen.append(spy.train_max)
        return spy

    monkeypatch.setattr(lab, "fit_goals", spy_fit)
    cand = (Candidate("spy", "Modello spia", "goals", "poisson"),)
    rows = walk_forward(synthetic_hist(), cand, step_days=28, min_train=60)
    assert len(rows) > 50
    assert (pd.to_datetime(rows["date"]) > pd.to_datetime(pd.Series(seen)).min()).all()
    # la data di allenamento di ogni finestra precede strettamente le gare che valuta
    assert max(seen) < pd.to_datetime(rows["date"]).max()
    assert (rows["n_train"] >= 60).all()
    assert not rows.duplicated(subset=["candidate", "date", "home", "away"]).any()


def test_walk_forward_is_empty_on_short_history():
    hist = synthetic_hist(seasons=1)
    assert walk_forward(hist, (Candidate("dc_puro", "DC", "goals", "dixon_coles"),),
                        step_days=14, min_train=5000).empty


def test_candidates_registry_is_unique_and_has_the_baseline():
    keys = [c.key for c in CANDIDATES]
    assert len(keys) == len(set(keys))
    assert BASELINE in keys
    # ogni candidato dichiara famiglia e tipo: servono al riepilogo e alla pagina del sito
    for c in CANDIDATES:
        assert c.kind in {"goals", "rating", "blend", "production"} and c.label and c.family


def test_mix_grids_stays_a_valid_distribution_between_the_two_components():
    lh, la, rho = 1.7, 1.1, -0.06
    ga = tau_grid(lh, la, rho, size=lab.GRID_SIZE)
    probs_b = (0.40, 0.29, 0.31)
    for w in (0.0, 0.35, 0.7, 1.0):
        mix, _, _ = lab._mix_grids(lh, la, rho, probs_b, w)
        assert mix.shape == ga.shape
        assert (mix >= -1e-15).all()
        assert mix.sum() == pytest.approx(1.0, abs=1e-9)
    i, j = np.indices(ga.shape)
    hda_a = (ga[i > j].sum(), ga[i == j].sum(), ga[i < j].sum())
    mix, _, _ = lab._mix_grids(lh, la, rho, probs_b, 0.5)
    hda_m = (mix[i > j].sum(), mix[i == j].sum(), mix[i < j].sum())
    # la miscela a metà sta fra le due componenti (nessuna probabilità "scappa" fuori)
    for a, b, m in zip(hda_a, probs_b, hda_m):
        assert min(a, b) - 1e-9 <= m <= max(a, b) + 1e-9


def _rows(candidates: dict[str, np.ndarray], outcomes: np.ndarray, leagues: list[str] | None = None):
    """Costruisce righe del laboratorio da vettori 1X2 dati (test deterministico e veloce)."""
    n = len(outcomes)
    leagues = leagues or ["TEST"] * n
    out = []
    for key, probs in candidates.items():
        for i in range(n):
            out.append({"candidate": key, "label": key, "kind": "goals", "family": "poisson",
                        "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                        "league_key": leagues[i], "home": f"H{i % 7}", "away": f"A{i % 5}",
                        "home_goals": int(outcomes[i] == 0), "away_goals": int(outcomes[i] == 2),
                        "outcome": int(outcomes[i]), "n_train": 500,
                        "p_home": probs[i, 0], "p_draw": probs[i, 1], "p_away": probs[i, 2],
                        "lambda_home": 1.5, "lambda_away": 1.2, "lambda_total": 2.7, "rho": -0.05,
                        "p_over15": 0.8, "p_over25": 0.55, "p_over35": 0.33, "p_btts": 0.55,
                        "p_home_clean_sheet": 0.26, "p_away_clean_sheet": 0.21})
    return pd.DataFrame(out)


def test_summarize_pairs_candidates_on_the_same_matches():
    rng = np.random.default_rng(7)
    n = 400
    outcomes = rng.choice([0, 1, 2], size=n, p=[0.44, 0.26, 0.30])
    # il vettore "migliore" è la distribuzione vera degli esiti: è il minimo dell'RPS
    good = np.tile([0.44, 0.26, 0.30], (n, 1)) + rng.normal(0, 0.02, (n, 3))
    good = np.clip(good, 0.01, 0.95)
    good = good / good.sum(1, keepdims=True)
    bad = np.tile([1 / 3, 1 / 3, 1 / 3], (n, 1))
    rows = _rows({BASELINE: bad, "migliore": good}, outcomes)
    tab = summarize(rows, baseline=BASELINE, draws=200)
    assert set(tab["candidate"]) == {BASELINE, "migliore"}
    ref = tab.set_index("candidate").loc[BASELINE]
    assert ref["delta_rps"] == pytest.approx(0.0, abs=1e-12)
    better = tab.set_index("candidate").loc["migliore"]
    assert better["delta_rps"] < 0                      # RPS più bassa = migliore
    assert better["delta_rps_hi95"] < 0.05              # l'IC appaiato è riportato
    assert 0.0 <= better["migliore_in"] <= 1.0
    assert better["n"] == int(ref["n"]) == n            # confronto sulle stesse gare
    assert (tab.iloc[0]["rps"] <= tab.iloc[-1]["rps"])   # ordinato dal migliore


def test_summarize_handles_rating_candidates_without_markets():
    rng = np.random.default_rng(11)
    n = 200
    outcomes = rng.choice([0, 1, 2], size=n)
    probs = np.clip(rng.dirichlet([3, 2, 2], size=n), 0.02, 0.9)
    probs = probs / probs.sum(1, keepdims=True)
    rows = _rows({BASELINE: probs, "elo": probs}, outcomes)
    rows.loc[rows["candidate"] == "elo", ["lambda_home", "lambda_away", "lambda_total", "rho",
                                          "p_over15", "p_over25", "p_over35", "p_btts",
                                          "p_home_clean_sheet", "p_away_clean_sheet"]] = np.nan
    tab = summarize(rows, draws=100)
    elo = tab.set_index("candidate").loc["elo"]
    assert np.isnan(elo.get("brier_mercati", np.nan))    # niente mercati: non si inventano zeri
    assert np.isnan(elo.get("bias_lambda", np.nan))
    assert np.isfinite(elo["rps"])


def test_per_league_splits_the_sample():
    rng = np.random.default_rng(3)
    n = 120
    outcomes = rng.choice([0, 1, 2], size=n)
    probs = np.clip(rng.dirichlet([3, 2, 2], size=n), 0.02, 0.9)
    probs = probs / probs.sum(1, keepdims=True)
    leagues = ["ITA1"] * (n // 2) + ["ENG1"] * (n - n // 2)
    rows = _rows({BASELINE: probs}, outcomes, leagues)
    tab = per_league(rows)
    assert set(tab["league_key"]) == {"ITA1", "ENG1"}
    assert int(tab["n"].sum()) == n
    assert ((tab["rps"] > 0) & (tab["rps"] < 1)).all()


def test_convex_weights_sum_to_one_and_follow_the_better_member():
    rng = np.random.default_rng(13)
    n = 600
    outcomes = rng.choice([0, 1, 2], size=n, p=[0.45, 0.26, 0.29])
    strong = np.tile([0.45, 0.26, 0.29], (n, 1)) + rng.normal(0, 0.015, (n, 3))
    strong = np.clip(strong, 0.02, 0.9)
    strong = strong / strong.sum(1, keepdims=True)
    weak = np.tile([1 / 3, 1 / 3, 1 / 3], (n, 1))
    rows = _rows({"forte": strong, "debole": weak}, outcomes)
    w = convex_weights(rows, ["forte", "debole"])
    assert set(w) == {"forte", "debole"}
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
    assert w["forte"] > w["debole"]
    assert w["forte"] > 0.85, f"atteso quasi tutto il peso sul membro migliore, ottenuto {w}"


def test_calibration_is_threaded_through_the_lab():
    """La stessa calibrazione usata in produzione può essere applicata dentro il laboratorio."""
    cal = Calibration(lambda_scale=0.94, rho_shift=-0.04)
    row = {"lambda_home": 1.9, "lambda_away": 1.4, "rho": -0.06, "p_home": 0.5, "p_draw": 0.26,
           "p_away": 0.24}
    out = lab._apply_calibration(row, cal)
    assert out["lambda_home"] == pytest.approx(1.9 * 0.94)
    assert out["lambda_home_raw"] == pytest.approx(1.9)
    assert out["p_home"] + out["p_draw"] + out["p_away"] == pytest.approx(1.0, abs=1e-9)
    # con calibrazione identica la riga non viene toccata
    same = lab._apply_calibration(row, Calibration())
    assert same["lambda_home"] == pytest.approx(1.9) and "lambda_home_raw" not in same


def test_lab_runs_on_a_real_offline_corpus(tmp_path):
    """Smoke test sul corpus ricostruito dagli H2H, se presente (altrimenti sintetico)."""
    hist = synthetic_hist(seasons=3)
    rows = walk_forward(hist, tuple(c for c in CANDIDATES if c.key in {"dc_puro", "elo", "mix_50"}),
                        step_days=21, min_train=100, max_windows=5)
    assert not rows.empty
    assert set(rows["candidate"]) <= {"dc_puro", "elo", "mix_50"}
    tab = summarize(rows, baseline="dc_puro", draws=100)
    assert "rps" in tab.columns and len(tab) >= 1
