"""Fit xG continuo: oracolo analitico, gradiente, cutoff e ripiego esattamente neutro."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fda.models import xg
from fda.models.predict import DixonColesModel


def training(n=120):
    rng = np.random.default_rng(41)
    rows = []
    for i in range(n // 2):
        order = rng.permutation(["A", "B", "C", "D"])
        for j in (0, 2):
            rows.append({"date": pd.Timestamp("2023-08-01", tz="UTC") + pd.Timedelta(days=i),
                         "league_key": "ITA1", "home": order[j], "away": order[j + 1],
                         "home_goals": int(rng.poisson(1.75)), "away_goals": int(rng.poisson(1.25)),
                         "home_xg": 1.75, "away_xg": 1.25})
    return pd.DataFrame(rows)


def test_gradiente_confrontato_con_differenze_finite():
    theta = np.array([0.2, -0.1, 0.1, -0.2, 0.1, 0.3, -0.1, 0.2, 0.15])
    args = (np.array([0, 1, 2, 3, 0]), np.array([1, 2, 3, 0, 2]),
            np.array([1.25, 0.32, 2.74, 1.39, 0.05]), np.array([0.75, 1.18, 0.46, 2.3, 1.63]),
            np.array([0.5, 0.7, 0.8, 0.9, 1.0]))
    _, gradient = xg._poisson_loss(theta, *args)
    numerical = []
    for i in range(len(theta)):
        plus, minus = theta.copy(), theta.copy()
        plus[i] += 1e-6
        minus[i] -= 1e-6
        numerical.append((xg._poisson_loss(plus, *args)[0] - xg._poisson_loss(minus, *args)[0]) / 2e-6)
    np.testing.assert_allclose(gradient, numerical, atol=1e-8, rtol=1e-6)
    assert abs(gradient[:4].sum()) < 1e-12


def test_fit_non_tronca_gli_xg_soluzione_analitica():
    hist = training()
    fitted = xg.fit_fractional_poisson(hist, np.ones(len(hist)), rho=-0.05)
    p = fitted.get_params()
    lh = np.exp(p["attack_A"] + p["defence_B"] + p["home_advantage"])
    la = np.exp(p["attack_B"] + p["defence_A"])
    np.testing.assert_allclose([lh, la], [1.75, 1.25], atol=1e-7, rtol=0)
    assert p["rho"] == -0.05
    assert abs(sum(p[f"attack_{t}"] for t in "ABCD")) < 1e-12


def test_xg_usa_rho_sui_gol_dello_stesso_prefisso():
    hist = training()
    base = DixonColesModel().fit(hist)
    model = xg.XGDixonColesModel().fit(hist)
    assert model.uses_xg and model.n_matches == len(hist)
    assert model.team_weight == base.team_weight
    assert model.model.get_params()["rho"] == pytest.approx(base.model.get_params()["rho"], abs=1e-10)
    p = model.predict("A", "B")
    assert sum(p[c] for c in ["p_home", "p_draw", "p_away"]) == pytest.approx(1.0)


@pytest.mark.parametrize("league", ["NED1", "POR1"])
def test_fallback_identico_senza_xg_inventati(league):
    hist = training().drop(columns=xg.XG_COLUMNS).assign(league_key=league)
    base = DixonColesModel().fit(hist).predict("A", "B")
    model = xg.XGDixonColesModel().fit(hist)
    got = model.predict("A", "B")
    assert not model.uses_xg
    for key in ["p_home", "p_draw", "p_away", "lambda_home", "lambda_away", "dc_rho"]:
        assert got[key] == pytest.approx(base[key], abs=1e-12, rel=0)


def test_cutoff_esclude_anche_la_gara_al_confine():
    hist = training()
    cutoff = hist.date.iloc[80]
    before = hist[hist.date < cutoff]
    expected = xg.XGDixonColesModel().fit(before)
    corrupted_future = hist.copy()
    corrupted_future.loc[corrupted_future.date >= cutoff, "home_xg"] = -999
    fitted = xg.XGDixonColesModel().fit(corrupted_future, as_of=cutoff)
    assert fitted.n_matches == len(before) == 80
    for key, value in expected.model.get_params().items():
        assert fitted.model.get_params()[key] == pytest.approx(value, abs=1e-10)


@pytest.mark.parametrize("column,value", [
    ("home_xg", np.nan), ("away_xg", np.inf), ("home_xg", -1.0),
    ("home_goals", 1.5), ("away_goals", -1.0), ("date", pd.NaT),
])
def test_fit_rifiuta_dati_invalidi(column, value):
    hist = training()
    if column.endswith("goals"):
        hist[column] = hist[column].astype(float)
    hist.loc[0, column] = value
    with pytest.raises(ValueError):
        xg.XGDixonColesModel().fit(hist)


def test_xg_mancanti_in_lega_coperta_non_diventano_gol():
    with pytest.raises(ValueError, match="mancano le colonne"):
        xg.XGDixonColesModel().fit(training().drop(columns=xg.XG_COLUMNS))


def test_fit_su_piu_leghe_e_fallback_con_xg_sono_rifiutati():
    hist = training()
    hist.loc[0, "league_key"] = "ESP1"
    with pytest.raises(ValueError, match="un solo campionato"):
        xg.XGDixonColesModel().fit(hist)
    with pytest.raises(ValueError, match="inattesi"):
        xg.XGDixonColesModel().fit(training().assign(league_key="NED1"))


def test_mancata_convergenza_non_produce_previsioni(monkeypatch):
    monkeypatch.setattr(xg, "minimize", lambda *a, **k: SimpleNamespace(success=False, message="stop"))
    hist = training()
    with pytest.raises(ValueError, match="non convergente"):
        xg.fit_fractional_poisson(hist, np.ones(len(hist)), rho=0.0)
