"""Test prospettico γ 1,12 (docs/89): registrazione pre-partita e confronto appaiato."""

import numpy as np
import pandas as pd
import pytest

from fda.models import prospettico
from fda.store import Store

NOW = pd.Timestamp("2026-10-12T12:00:00Z")
KICKOFF = NOW + pd.Timedelta(hours=1)


def _pred(n=3):
    return pd.DataFrame({
        "match_id": list(range(1, n + 1)), "league_key": ["ITA1"] * n,
        "utc_kickoff": [KICKOFF] * n,
        "p_home": [0.5] * n, "p_draw": [0.25] * n, "p_away": [0.25] * n,
        "lambda_home": [1.6] * n, "lambda_away": [1.1] * n, "dc_rho": [-0.04] * n,
    })


def _finished(n=3):
    return pd.DataFrame({"match_id": list(range(1, n + 1)), "status": ["finished"] * n,
                         "home_goals": [2] * n, "away_goals": [0] * n,
                         "utc_kickoff": [KICKOFF] * n})


def test_gamma_variant_probabilita_valide_e_piu_netta():
    g = prospettico.gamma_variant(1.6, 1.1, -0.04)
    assert abs(g["p_home"] + g["p_draw"] + g["p_away"] - 1) < 1e-9
    # γ > 1 sposta λ a favore del più forte: il favorito (casa) guadagna
    assert g["p_home"] > 0.45 and g["lambda_home"] > 1.6 and g["lambda_away"] < 1.1


def test_record_scrive_due_varianti_per_partita(tmp_path):
    st = Store(tmp_path / "processed")
    assert prospettico.record(st, _pred(3), now=NOW) == 6
    tab = st.read("prospettico")
    assert set(tab["variant"]) == {prospettico.VARIANT_PROD, prospettico.VARIANT_GAMMA}
    assert len(tab) == 6
    # rilanciare il run non duplica: stessa chiave (partita, variante)
    prospettico.record(st, _pred(3), now=NOW)
    assert len(st.read("prospettico")) == 6
    st.close()


def test_record_rifiuta_previsioni_senza_rho(tmp_path):
    st = Store(tmp_path / "processed")
    with pytest.raises(ValueError, match="dc_rho"):
        prospettico.record(st, _pred(2).drop(columns=["dc_rho"]), now=NOW)
    st.close()


def test_record_solo_future_non_al_fischio_ne_senza_data(tmp_path):
    st = Store(tmp_path / "processed")
    p = _pred(4)
    p["utc_kickoff"] = [NOW - pd.Timedelta(seconds=1), NOW, pd.NaT, KICKOFF]
    assert prospettico.record(st, p, now=NOW) == 2
    tab = st.read("prospettico")
    assert set(tab.match_id) == {4}
    assert (tab.made_at < tab.utc_kickoff).all()
    assert prospettico.record(st, p, now=KICKOFF) == 0
    pd.testing.assert_frame_equal(st.read("prospettico"), tab)


def test_record_aggiorna_prima_del_fischio_ma_non_scongela_rinvii(tmp_path):
    st = Store(tmp_path / "processed")
    p = _pred(1)
    prospettico.record(st, p, now=NOW)
    p["p_home"], p["p_draw"], p["p_away"] = 0.6, 0.2, 0.2
    updated_at = NOW + pd.Timedelta(minutes=10)
    assert prospettico.record(st, p, now=updated_at) == 2
    frozen = st.read("prospettico")
    assert frozen.made_at.eq(updated_at).all()
    assert frozen.loc[frozen.variant.eq("prod"), "p_home"].iloc[0] == 0.6
    before = st.path("prospettico").read_bytes()
    # Anche se l'input sposta il kickoff in avanti, la coppia ha già raggiunto il suo
    # kickoff archiviato: non riapriamo il test dopo avere osservato una parte di gara.
    p["utc_kickoff"] = KICKOFF + pd.Timedelta(days=1)
    assert prospettico.record(st, p, now=KICKOFF) == 0
    assert st.path("prospettico").read_bytes() == before


@pytest.mark.parametrize("column,value", [
    ("dc_rho", np.nan), ("dc_rho", np.inf), ("lambda_home", 0.0),
    ("lambda_away", -1.0), ("lambda_home", np.nan), ("p_home", -0.1),
    ("p_draw", np.nan), ("p_away", 1.0),
])
def test_record_rifiuta_valori_invalidi_senza_scrivere(tmp_path, column, value):
    st = Store(tmp_path / "processed")
    p = _pred(1)
    p[column] = value
    with pytest.raises(ValueError, match="non valid"):
        prospettico.record(st, p, now=NOW)
    assert st.read("prospettico").empty


def test_evaluate_appaiato_e_criterio(tmp_path):
    st = Store(tmp_path / "processed")
    prospettico.record(st, _pred(3), now=NOW)
    fx = _finished(3)
    fx["home_goals"], fx["away_goals"] = [2, 0, 1], [0, 0, 1]
    r = prospettico.evaluate(st, fx)
    assert r["n"] == 3 and r["leagues_better"] in (0, 1)
    assert r["passes"] is False                       # 3 partite << MIN_N
    assert r["lo"] is not None and r["hi"] is not None and r["lo"] <= r["hi"]
    st.close()


@pytest.mark.parametrize("defect", [
    "postuma", "al_fischio", "senza_data", "snapshot_diversi", "kickoff_diversi",
    "probabilita_nan", "probabilita_fuori_range", "probabilita_non_normalizzate",
    "duplicato", "coppia_incompleta", "lega_diversa", "calendario_anticipato",
])
def test_evaluate_esclude_coppie_non_valide(tmp_path, defect):
    st = Store(tmp_path / "processed")
    prospettico.record(st, _pred(2), now=NOW)
    tab = st.read("prospettico")
    one = tab.match_id.eq(1)
    gamma = one & tab.variant.eq("gamma_112")
    fx = _finished(2)
    if defect in {"postuma", "al_fischio", "senza_data"}:
        tab.loc[one, "made_at"] = {
            "postuma": KICKOFF + pd.Timedelta(seconds=1),
            "al_fischio": KICKOFF, "senza_data": pd.NaT,
        }[defect]
    elif defect == "snapshot_diversi":
        tab.loc[gamma, "made_at"] = NOW + pd.Timedelta(minutes=1)
    elif defect == "kickoff_diversi":
        tab.loc[gamma, "utc_kickoff"] = KICKOFF + pd.Timedelta(minutes=1)
    elif defect == "probabilita_nan":
        tab.loc[gamma, "p_home"] = np.nan
    elif defect == "probabilita_fuori_range":
        tab.loc[gamma, ["p_home", "p_draw", "p_away"]] = [-0.1, 0.5, 0.6]
    elif defect == "probabilita_non_normalizzate":
        tab.loc[gamma, "p_home"] = 0.9
    elif defect == "duplicato":
        tab = pd.concat([tab, tab[gamma]], ignore_index=True)
    elif defect == "coppia_incompleta":
        tab = tab[~gamma]
    elif defect == "lega_diversa":
        tab.loc[gamma, "league_key"] = "ENG1"
    elif defect == "calendario_anticipato":
        fx.loc[fx.match_id.eq(1), "utc_kickoff"] = NOW
    st.write("prospettico", tab)
    r = prospettico.evaluate(st, fx)
    assert r["n"] == 1                   # resta soltanto la gara 2, valida e appaiata
    assert r["passes"] is False


@pytest.mark.parametrize("n,better,passes", [
    (199, 7, False), (200, 4, False), (200, 5, True), (200, 0, False),
])
def test_soglie_preregistrate_non_cambiano(tmp_path, n, better, passes):
    st = Store(tmp_path / "processed")
    rows = []
    leagues = ["ITA1", "ENG1", "ESP1", "GER1", "FRA1", "NED1", "POR1"]
    for i in range(n):
        for variant in ("prod", "gamma_112"):
            ph = 0.4 if variant == "prod" or i % 7 >= better else 0.7
            rows.append({"match_id": i + 1, "league_key": leagues[i % 7], "variant": variant,
                         "utc_kickoff": KICKOFF, "made_at": NOW,
                         "p_home": ph, "p_draw": 0.2, "p_away": 0.8 - ph})
    st.write("prospettico", pd.DataFrame(rows))
    r = prospettico.evaluate(st, _finished(n))
    assert (prospettico.MIN_N, prospettico.MIN_LEAGUES, prospettico.N_BOOT) == (200, 5, 2000)
    assert r["n"] == n and r["leagues_better"] == better and r["n_leagues"] == 7
    assert r["hi"] < 0 if better else r["hi"] == 0
    assert r["passes"] is passes


def test_evaluate_senza_dati_non_inventa(tmp_path):
    st = Store(tmp_path / "processed")
    r = prospettico.evaluate(st, pd.DataFrame())
    assert r["n"] == 0 and r["passes"] is False and r["delta"] is None
    st.close()
