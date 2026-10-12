"""Test prospettico γ 1,12 (docs/89): variante, registrazione e valutazione appaiata."""

import pandas as pd

from fda.models import prospettico
from fda.store import Store


def _pred(n=3):
    return pd.DataFrame({
        "match_id": list(range(1, n + 1)), "league_key": ["ITA1"] * n,
        "utc_kickoff": [pd.Timestamp("2027-01-01", tz="UTC")] * n,
        "p_home": [0.5] * n, "p_draw": [0.25] * n, "p_away": [0.25] * n,
        "lambda_home": [1.6] * n, "lambda_away": [1.1] * n, "dc_rho": [-0.04] * n,
    })


def test_gamma_variant_probabilita_valide_e_piu_netta():
    g = prospettico.gamma_variant(1.6, 1.1, -0.04)
    assert abs(g["p_home"] + g["p_draw"] + g["p_away"] - 1) < 1e-9
    # γ > 1 sposta λ a favore del più forte: il favorito (casa) guadagna
    assert g["p_home"] > 0.45 and g["lambda_home"] > 1.6 and g["lambda_away"] < 1.1


def test_record_scrive_due_varianti_per_partita(tmp_path):
    st = Store(tmp_path / "processed")
    assert prospettico.record(st, _pred(3)) == 6
    tab = st.read("prospettico")
    assert set(tab["variant"]) == {prospettico.VARIANT_PROD, prospettico.VARIANT_GAMMA}
    assert len(tab) == 6
    # rilanciare il run non duplica: stessa chiave (partita, variante)
    prospettico.record(st, _pred(3))
    assert len(st.read("prospettico")) == 6
    st.close()


def test_record_rifiuta_previsioni_senza_rho(tmp_path):
    import pytest
    st = Store(tmp_path / "processed")
    with pytest.raises(ValueError):
        prospettico.record(st, _pred(2).drop(columns=["dc_rho"]))
    st.close()


def test_evaluate_appaiato_e_criterio(tmp_path):
    st = Store(tmp_path / "processed")
    prospettico.record(st, _pred(3))
    fx = pd.DataFrame({"match_id": [1, 2, 3], "status": ["finished"] * 3,
                       "home_goals": [2, 0, 1], "away_goals": [0, 0, 1]})
    r = prospettico.evaluate(st, fx)
    assert r["n"] == 3 and r["leagues_better"] in (0, 1)
    assert r["passes"] is False                       # 3 partite << MIN_N
    assert r["lo"] is not None and r["hi"] is not None and r["lo"] <= r["hi"]
    st.close()


def test_evaluate_senza_dati_non_inventa(tmp_path):
    st = Store(tmp_path / "processed")
    r = prospettico.evaluate(st, pd.DataFrame())
    assert r["n"] == 0 and r["passes"] is False and r["delta"] is None
    st.close()
