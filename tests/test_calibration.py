"""Calibrazione della griglia: coerenza, soglia minima, recupero di un bias noto, store."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fda.models.calibration import (
    BRIER_WEIGHT,
    FIT_WINDOW_DAYS,
    LAMBDA_SCALE_GRID,
    MIN_ROWS,
    SCALE_BOUNDS,
    Calibration,
    evaluate,
    fit,
    from_store,
    moment_scale,
)
from fda.models.dc_grid import (
    GRID_SIZE,
    grid_markets_many,
    probability_grid,
    tau_grid,
    tau_grid_many,
)
from fda.models.predict import _grid_markets, calibrated_prediction, wilson_interval
from fda.store import Store


def sample_backtest(n: int = 2400, scale_true: float = 1.0, seed: int = 5) -> pd.DataFrame:
    """Backtest sintetico in cui le λ pubblicate sono ``scale_true`` volte quelle reali.

    Con ``scale_true = 1/0.94`` riproduciamo il difetto misurato sul backtest di produzione
    (λ gonfiate dell'~6-9% e pareggio sottostimato): la calibrazione deve ritrovare ≈0,94.
    """
    rng = np.random.default_rng(seed)
    lh_true = rng.uniform(0.8, 2.4, n)
    la_true = rng.uniform(0.6, 2.0, n)
    rho = np.full(n, -0.06)
    hg = rng.poisson(lh_true)
    ag = rng.poisson(la_true)
    dates = pd.Timestamp("2024-01-06") + pd.to_timedelta(np.sort(rng.integers(0, 900, n)), unit="D")
    return pd.DataFrame({
        "date": dates, "league_key": "TEST", "home": [f"H{i % 20}" for i in range(n)],
        "away": [f"A{i % 17}" for i in range(n)], "home_goals": hg, "away_goals": ag,
        "lambda_home": lh_true * scale_true, "lambda_away": la_true * scale_true, "dc_rho": rho,
    })


def test_tau_grid_many_matches_scalar():
    """La versione vettorizzata è la stessa τ della scalare (una sola implementazione)."""
    lh = np.array([1.6, 0.4, 2.9, 1e-9])
    la = np.array([1.1, 1.9, 0.2, 1.3])
    rho = np.array([-0.08, 0.0, 0.04, -0.5])
    vec = tau_grid_many(lh, la, rho, size=11)
    for i in range(len(lh)):
        scal = tau_grid(float(lh[i]), float(la[i]), float(rho[i]), size=11)
        assert np.allclose(vec[i], scal, atol=1e-14), f"riga {i} diversa"
        assert abs(vec[i].sum() - 1.0) < 1e-12


def test_grid_markets_many_matches_probability_grid():
    """I mercati vettorizzati coincidono con quelli di penaltyblog usati in produzione."""
    for lh, la, rho in ((1.7, 1.2, -0.07), (0.9, 2.3, 0.02), (1.4, 1.4, 0.0)):
        m = grid_markets_many(tau_grid_many(np.array([lh]), np.array([la]), np.array([rho]), size=11))
        ref = _grid_markets(probability_grid(lh, la, rho, size=11))
        assert m["p_home"][0] == pytest.approx(ref["p_home"], abs=1e-9)
        assert m["p_draw"][0] == pytest.approx(ref["p_draw"], abs=1e-9)
        assert m["p_over25"][0] == pytest.approx(ref["p_over25"], abs=1e-9)
        assert m["p_btts"][0] == pytest.approx(ref["p_btts"], abs=1e-9)
        assert m["p_home_clean_sheet"][0] == pytest.approx(ref["p_home_clean_sheet"], abs=1e-9)
        # λ effettiva = media della matrice (non il parametro grezzo) e resta vicina a λ_home+λ_away
        assert m["lambda_total"][0] == pytest.approx(lh + la, abs=0.05)


def test_apply_calibration_scales_and_clamps_rho():
    cal = Calibration(lambda_scale=0.94, rho_shift=-0.30)     # ρ fuori da ogni bound
    lh, la, rho = cal.apply(1.8, 1.2, -0.05)
    assert lh == pytest.approx(1.8 * 0.94)
    assert la == pytest.approx(1.2 * 0.94)
    assert rho >= max(-1 / lh, -1 / la) and rho <= min(1.0, 1 / (lh * la))
    # la griglia resta una distribuzione valida anche con ρ estrema
    g = tau_grid(lh, la, rho, size=11)
    assert (g >= 0).all() and g.sum() == pytest.approx(1.0, abs=1e-12)


def test_identity_calibration_changes_nothing():
    cal = Calibration()
    assert cal.is_identity
    assert cal.apply(1.5, 1.0, -0.04) == pytest.approx((1.5, 1.0, -0.04))


def test_fit_below_threshold_returns_identity():
    df = sample_backtest(n=MIN_ROWS - 1)
    cal = fit(df)
    assert cal.is_identity and cal.n_fit == len(df)
    assert "soglia" in cal.corpus


def test_fit_recovers_a_known_lambda_bias():
    """λ gonfiate di 1/0,94: la calibrazione deve ritrovare ≈0,94 e ridurre il bias."""
    df = sample_backtest(n=3000, scale_true=1 / 0.94)
    before = evaluate(df, Calibration())
    cal = fit(df)
    assert cal.estimator == "momenti"
    assert abs(cal.lambda_scale - 0.94) < 0.02, f"atteso ≈0,94, ottenuto {cal.lambda_scale}"
    after = evaluate(df, cal)
    assert before["bias_lambda"] > 0.15
    assert abs(after["bias_lambda"]) < abs(before["bias_lambda"]) / 2
    # il pareggio resta calibrato (nei dati sintetici i gol sono Poisson indipendenti: ρ vero = 0)
    assert abs(after["pareggio_previsto"] - after["pareggio_osservato"]) < 0.02
    assert after["brier_mercati"] <= before["brier_mercati"] + 1e-9
    # le metriche walk-forward sono registrate (guadagno onesto, non in-sample)
    assert cal.metrics["holdout_n"] > 0
    assert cal.metrics["holdout_brier_dopo"] <= cal.metrics["holdout_brier_prima"] + 1e-9


BACKTEST_REALE = Path(__file__).resolve().parents[1] / "data" / "processed" / "backtest.parquet"


@pytest.mark.skipif(not BACKTEST_REALE.exists(), reason="backtest di produzione non presente")
def test_fit_on_production_backtest_fixes_the_measured_bias():
    """Sul backtest vero (5.811 gare fuori campione) la calibrazione corregge il bias residuo.

    Con la ricetta a gol attesi invariati (tilt, promossa il 2026-09-13) il difetto storico ha
    **cambiato segno**: la griglia grezza ora *sottostima* i gol (bias −0,133) invece di
    sovrastimarli (+0,240 con la ricetta precedente, che gonfiava le λ invertendo l'1X2
    mediato), e il pareggio grezzo è già centrato (25,7% contro 25,6% osservato). La
    calibrazione resta giustificata: dimezza il bias residuo e migliora il Brier dei mercati,
    con il guadagno valutato walk-forward (regola B8).
    """
    df = pd.read_parquet(BACKTEST_REALE)
    before = evaluate(df, Calibration())
    cal = fit(df)
    after = evaluate(df, cal)
    assert abs(before["bias_lambda"]) > 0.10, "il bias misurato sul backtest è cambiato: rileggere docs/15"
    assert abs(after["bias_lambda"]) < abs(before["bias_lambda"]) / 2
    # il pareggio resta dentro l'intervallo di Wilson 95% dell'osservato, prima e dopo
    n = int(before["n"])
    k = round(before["pareggio_osservato"] * n)
    lo, hi = wilson_interval(k, n)
    assert lo <= before["pareggio_previsto"] <= hi
    assert lo <= after["pareggio_previsto"] <= hi
    assert after["brier_mercati"] < before["brier_mercati"]
    assert cal.metrics["holdout_brier_dopo"] < cal.metrics["holdout_brier_prima"]
    # l'1X2 non deve peggiorare oltre il rumore: la calibrazione non nasce per quello
    assert cal.metrics["holdout_rps_delta"] < 0.001


def test_evaluate_reports_the_same_markets_as_the_site():
    df = sample_backtest(n=200)
    out = evaluate(df, Calibration())
    for key in ("rps", "logloss", "brier_1x2", "brier_mercati", "hit", "lambda_media",
                "gol_osservati", "bias_lambda", "pareggio_previsto", "pareggio_osservato"):
        assert key in out and np.isfinite(out[key])
    for key in ("brier_p_over25", "brier_p_btts", "brier_p_home_clean_sheet"):
        assert key in out
    assert 0.0 <= out["hit"] <= 1.0 and out["rps"] > 0


def test_calibrated_prediction_is_coherent_with_the_grid():
    """Dopo la calibrazione, 1X2/doppia chance/mercati derivano tutti dalla stessa matrice."""
    out = {"p_home": 0.48, "p_draw": 0.26, "p_away": 0.26, "lambda_home": 1.9, "lambda_away": 1.4,
           "dc_rho": -0.07, "p_1x": 0.74, "p_12": 0.74, "p_x2": 0.52, "p_over25": 0.60,
           "p_over15": 0.82, "p_over35": 0.38, "p_btts": 0.58, "p_home_clean_sheet": 0.24,
           "p_away_clean_sheet": 0.18, "top_scores": {"1-1": 0.12}, "model": "ensemble"}
    cal = Calibration(lambda_scale=0.94, rho_shift=-0.04)
    res = calibrated_prediction(out, cal)
    lh, la, rho = cal.apply(1.9, 1.4, -0.07)
    # la griglia è quella condivisa (11×11): la calibrazione stima i parametri su quella
    # superficie, quindi pubblicare da una 10×10 ottimizzerebbe una cosa e ne mostrerebbe un'altra
    ref = _grid_markets(probability_grid(lh, la, rho, size=GRID_SIZE))
    assert res["p_home"] == pytest.approx(ref["p_home"], abs=1e-9)
    assert res["p_draw"] == pytest.approx(ref["p_draw"], abs=1e-9)
    assert res["p_away"] == pytest.approx(ref["p_away"], abs=1e-9)
    assert res["p_home"] + res["p_draw"] + res["p_away"] == pytest.approx(1.0, abs=1e-9)
    assert res["p_1x"] == pytest.approx(res["p_home"] + res["p_draw"], abs=1e-9)
    assert res["p_over25"] == pytest.approx(ref["p_over25"], abs=1e-9)
    assert res["lambda_home"] == pytest.approx(lh) and res["dc_rho"] == pytest.approx(rho)
    # trasparenza: il vettore prima della calibrazione resta leggibile
    assert res["blend_p_home"] == pytest.approx(0.48)
    assert res["lambda_home_raw"] == pytest.approx(1.9) and res["rho_raw"] == pytest.approx(-0.07)


def test_identity_calibration_keeps_raw_columns_only():
    out = {"p_home": 0.5, "p_draw": 0.25, "p_away": 0.25, "lambda_home": 1.5, "lambda_away": 1.0,
           "dc_rho": -0.05}
    res = calibrated_prediction(out, Calibration())
    assert res["p_home"] == 0.5 and "blend_p_home" not in res
    assert res["lambda_home_raw"] == 1.5


def test_calibration_roundtrip_through_the_store(tmp_path):
    store = Store(base_dir=tmp_path)
    cal = fit(sample_backtest(n=2600, scale_true=1 / 0.96))
    store.upsert("calibration", [cal.as_row()])
    back = from_store(store)
    assert back.lambda_scale == pytest.approx(cal.lambda_scale, abs=1e-6)
    assert back.rho_shift == pytest.approx(cal.rho_shift, abs=1e-6)
    assert back.window_days == cal.window_days and back.estimator == cal.estimator
    assert back.n_fit == cal.n_fit and back.version == cal.version
    assert back.metrics["holdout_brier_dopo"] == pytest.approx(cal.metrics["holdout_brier_dopo"], abs=1e-6)
    store.close()


def test_from_store_without_table_is_identity(tmp_path):
    store = Store(base_dir=tmp_path)
    assert from_store(store).is_identity
    store.close()


def test_objective_weights_both_scores():
    """L'obiettivo dichiarato combina RPS e Brier dei mercati: il peso è pubblico e non nullo."""
    assert BRIER_WEIGHT > 0
    df = sample_backtest(n=400)
    out = evaluate(df, Calibration())
    assert out["obiettivo"] == pytest.approx(out["rps"] + BRIER_WEIGHT * out["brier_mercati"], abs=1e-9)


FIX = Path(__file__).parent / "fixtures"


def _serie_a_history() -> pd.DataFrame:
    """Storico reale della Serie A 2025/26 (fixture del repo): usato per l'integrazione."""
    from fda.config import league
    from fda.sources.history import HistoryClient
    from fda.teams import canonical

    raw = pd.read_csv(FIX / "datahub_serie_a_2526.csv")
    df = HistoryClient._normalize(raw, league("ITA1"), 2025)
    df["home"] = df["home"].map(canonical)
    df["away"] = df["away"].map(canonical)
    return df


def test_predict_matches_publishes_the_calibrated_grid():
    """`fda predict` con calibrazione: λ scalate, 1X2 coerente con la matrice, traccia dei grezzi."""
    from fda.models.predict import predict_matches

    hist = _serie_a_history()
    fixtures = pd.DataFrame({"match_id": list(range(10)), "league_key": "ITA1",
                             "utc_kickoff": pd.Timestamp("2026-09-20 18:00", tz="UTC"),
                             "home": hist["home"].head(10).tolist(),
                             "away": hist["away"].head(10).tolist()})
    raw, _, _ = predict_matches(hist, fixtures)
    cal = Calibration(lambda_scale=0.94, rho_shift=-0.04, n_fit=5000)
    adj, _, _ = predict_matches(hist, fixtures, calibration=cal)

    assert (adj["calibration_version"] == cal.version).all()
    assert (raw["calibration_version"] == "identity").all()
    assert np.allclose(adj["lambda_home"], raw["lambda_home"] * 0.94, atol=1e-9)
    assert np.allclose(adj["lambda_home_raw"], raw["lambda_home"], atol=1e-9)
    assert np.allclose(adj["p_home"] + adj["p_draw"] + adj["p_away"], 1.0, atol=1e-9)
    assert np.allclose(adj["p_1x"], adj["p_home"] + adj["p_draw"], atol=1e-9)
    # coerenza con la matrice: l'1X2 pubblicato è quello della griglia calibrata
    for row in adj.itertuples(index=False):
        ref = _grid_markets(probability_grid(row.lambda_home, row.lambda_away, row.dc_rho,
                                                 size=GRID_SIZE))
        assert row.p_home == pytest.approx(ref["p_home"], abs=1e-9)
        assert row.p_over25 == pytest.approx(ref["p_over25"], abs=1e-9)
    # la λ più bassa alza la massa del pareggio: è l'effetto cercato, non un arrotondamento
    assert adj["p_draw"].mean() > raw["p_draw"].mean()


def test_moment_scale_reproduces_the_observed_goals():
    """Il moltiplicatore a momenti riproduce la media dei gol: è la sua definizione."""
    rng = np.random.default_rng(17)
    n = 4000
    lh_true, la_true = rng.uniform(0.9, 2.2, n), rng.uniform(0.7, 1.9, n)
    goals = rng.poisson(lh_true) + rng.poisson(la_true)
    m = moment_scale(lh_true * 1.12, la_true * 1.12, goals)     # λ gonfiate del 12%
    assert m == pytest.approx(1 / 1.12, abs=0.01)
    assert (lh_true * 1.12 * m + la_true * 1.12 * m).mean() == pytest.approx(goals.mean(), abs=1e-9)
    # λ degenerate: nessuna correzione invece di un rapporto assurdo
    assert moment_scale(np.zeros(10), np.zeros(10), goals[:10]) == 1.0
    # limiti di sicurezza: un modello che dichiara il triplo dei gol non si "calibra"
    assert moment_scale(lh_true * 3, la_true * 3, goals) == 0.85


def test_fit_follows_the_recent_regime_when_the_bias_drifts():
    """Il bias delle λ non è stazionario: la finestra recente deve pesare più dello storico."""
    rng = np.random.default_rng(23)
    frames = []
    # prima metà senza bias, seconda metà con λ gonfiate del 25%
    for i, (days, scale_true) in enumerate(((0, 1.0), (900, 1.12))):
        n = 1600
        lh, la = rng.uniform(0.9, 2.1, n), rng.uniform(0.7, 1.8, n)
        dates = (pd.Timestamp("2023-01-01") + pd.Timedelta(days=days)
                 + pd.to_timedelta(np.sort(rng.integers(0, 800, n)), unit="D"))
        frames.append(pd.DataFrame({
            "date": dates, "league_key": "TEST", "home": [f"H{j % 18}" for j in range(n)],
            "away": [f"A{j % 15}" for j in range(n)],
            "home_goals": rng.poisson(lh), "away_goals": rng.poisson(la),
            "lambda_home": lh * scale_true, "lambda_away": la * scale_true,
            "dc_rho": np.full(n, -0.05)}))
    df = pd.concat(frames, ignore_index=True)
    tutta = fit(df, window_days=None)
    recente = fit(df, window_days=FIT_WINDOW_DAYS)
    assert tutta.lambda_scale > recente.lambda_scale + 0.03, (tutta.lambda_scale, recente.lambda_scale)
    assert recente.lambda_scale == pytest.approx(1 / 1.12, abs=0.02)
    assert recente.metrics["stima_n"] < len(df)
    # la finestra è dichiarata nella traccia, non nascosta
    assert str(FIT_WINDOW_DAYS) in recente.corpus and recente.window_days == FIT_WINDOW_DAYS
    # sui dati più recenti il bias residuo è minore con la stima finestrata
    tail = df[df["date"] >= df["date"].max() - pd.Timedelta(days=365)]
    assert abs(evaluate(tail, recente)["bias_lambda"]) < abs(evaluate(tail, tutta)["bias_lambda"])


def test_fit_records_the_score_grid_choice_for_comparison():
    """La calibrazione pubblicata dice anche quale moltiplicatore avrebbe scelto il punteggio."""
    cal = fit(sample_backtest(n=2600, scale_true=1 / 0.96))
    assert "confronto_scale_griglia" in cal.metrics
    assert 0.90 <= cal.metrics["confronto_scale_griglia"] <= 1.03
    assert "holdout_bias_lambda_prima" in cal.metrics and "holdout_bias_lambda_dopo" in cal.metrics
    assert abs(cal.metrics["holdout_bias_lambda_dopo"]) < abs(cal.metrics["holdout_bias_lambda_prima"])


def test_n_fit_dichiara_le_gare_usate_per_la_stima_non_il_campione():
    """La scheda scrive «stimata su N gare fuori campione»: N deve essere la finestra di stima.

    Con la finestra a 730 giorni i due numeri divergono (misurato sul backtest reale: 4.743 gare
    di stima su 5.791 di campione) e dichiarare il campione sarebbe una precisione falsa.
    """
    cal = fit(sample_backtest(n=3000, scale_true=1 / 0.94))
    assert cal.n_fit == int(cal.metrics["stima_n"])
    assert cal.n_fit <= int(cal.metrics["campione_n"])
    # il corpus dichiara entrambi i numeri: il campione valutato e la finestra di stima
    assert "gare fuori campione" in cal.corpus
    assert f"ultimi {FIT_WINDOW_DAYS} giorni" in cal.corpus
    assert f"{int(cal.metrics['campione_n'])} gare" in cal.corpus
    assert f"stimati su {cal.n_fit} gare" in cal.corpus
    assert cal.estimator == "momenti" and cal.window_days == FIT_WINDOW_DAYS


# --- P1.12: il claim pubblicato sul moltiplicatore dice il vero (docs/19 §1.7) ------------


def test_dominio_del_moltiplicatore_e_quello_dei_bounds_con_lo_stimatore_dei_momenti():
    """Lo stimatore in produzione è continuo: l'intervallo esplorato sono i bounds.

    L'audit `docs/19` §1.7 sospettava un claim «più forte dei dati» perché il valore
    pubblicato (λ×1,0401) è **fuori** da ``LAMBDA_SCALE_GRID`` (0,90…1,02). Misurato qui:
    non è un difetto, è che la griglia **non sceglie** il valore in produzione — lo sceglie
    :func:`moment_scale`, limitato da ``SCALE_BOUNDS``. Il claim deve dire questo.
    """
    cal = Calibration(lambda_scale=1.0401, estimator="momenti")
    assert cal.scale_domain == (SCALE_BOUNDS[0], SCALE_BOUNDS[1])
    # il valore realmente pubblicato è dentro il dominio dichiarato: nessun claim fuori misura
    assert cal.scale_domain[0] <= cal.lambda_scale <= cal.scale_domain[1]
    # ...e sarebbe stato fuori dal dominio della griglia, che infatti non è quello usato
    assert not (min(LAMBDA_SCALE_GRID) <= cal.lambda_scale <= max(LAMBDA_SCALE_GRID))


def test_il_claim_non_dichiara_una_griglia_quando_lo_stimatore_e_dei_momenti():
    """Niente «scelto su griglia» se la griglia non ha scelto nulla (claim ridotto, P1.12)."""
    claim = Calibration(lambda_scale=1.0401, estimator="momenti").scale_claim
    assert "momenti" in claim
    assert "0,85" in claim and "1,05" in claim      # virgola decimale italiana (regola 00 §E)
    assert "griglia" not in claim
    # e col vero stimatore a griglia il claim cambia, dichiarando la griglia reale
    claim_grid = Calibration(lambda_scale=1.02, estimator="griglia").scale_claim
    assert "griglia" in claim_grid and "0,90" in claim_grid and "1,02" in claim_grid


def test_lo_store_registra_il_dominio_esplorato_del_moltiplicatore():
    """`docs/19` §1.7 chiede di documentare l'intervallo esplorato nello store."""
    row = Calibration(lambda_scale=1.0401, estimator="momenti").as_row()
    assert row["scale_grid_min"] == SCALE_BOUNDS[0]
    assert row["scale_grid_max"] == SCALE_BOUNDS[1]
    assert row["scale_grid_min"] <= row["lambda_scale"] <= row["scale_grid_max"]


def test_il_fit_reale_resta_dentro_il_dominio_che_dichiara():
    """Invariante di sicurezza: il parametro pubblicato non esce mai dal dominio dichiarato."""
    cal = fit(sample_backtest(n=2600, scale_true=1 / 0.94))
    lo, hi = cal.scale_domain
    assert lo <= cal.lambda_scale <= hi
    assert cal.as_row()["scale_grid_max"] == hi
