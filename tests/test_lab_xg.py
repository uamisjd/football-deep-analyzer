"""Esperimento xG isolato: campione appaiato, assenza di leakage e protocollo invariato."""

import inspect

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from fda.cli import app
from fda.models import lab, lab_xg
from fda.models.calibration import Calibration
from tests.test_xg import training


def sources():
    u = pd.DataFrame({
        "understat_id": [1, 2, 3, 4], "league_slug": ["Serie_A"] * 4,
        "season": [2021, 2026, 2026, 2026], "home_id": [101] * 4, "away_id": [102] * 4,
        "utc_kickoff": pd.to_datetime(["2021-08-01T12:00Z", "2026-10-11T12:00Z",
                                       "2026-10-15T12:00Z", "2026-10-12T13:10Z"], utc=True),
        "is_result": [True, True, False, True], "home_goals": [1, 2, np.nan, 1],
        "away_goals": [0, 1, np.nan, 0], "home_xg": [1.27, 1.35, np.nan, 1.25],
        "away_xg": [0.43, 0.84, np.nan, 0.56],
    })
    h = pd.DataFrame({"league_key": ["NED1", "POR1", "ITA1"],
                      "date": pd.to_datetime(["2024-08-15T00:00Z"] * 3, utc=True),
                      "season": ["2024/2025"] * 3, "home": ["N", "P", "X"],
                      "away": ["N2", "P2", "X2"], "home_goals": [1, 0, 9], "away_goals": [0, 1, 9]})
    return u, h


def test_storia_non_mescola_fonti_ne_aggiunge_gare_future():
    hist = lab_xg.prepare_history(*sources())
    assert len(hist) == 4
    assert (hist.date < lab_xg.CUTOFF).all()
    ita = hist[hist.league_key.eq("ITA1")]
    assert len(ita) == 2 and set(ita.home) == {"understat:101"}
    assert ita.home_xg.tolist() == [1.27, 1.35]
    assert hist[hist.league_key.isin(["NED1", "POR1"])][["home_xg", "away_xg"]].isna().all().all()
    assert set(hist.source) == {"understat", "history"}


@pytest.mark.parametrize("defect", ["id_duplicato", "orario_duplicato", "xg_mancante", "gol_frazionari", "data_mancante"])
def test_preparazione_rifiuta_dati_ambigui(defect):
    u, h = sources()
    if defect == "id_duplicato":
        u.loc[1, "understat_id"] = 1
    elif defect == "orario_duplicato":
        other = u.iloc[[0]].copy()
        other["understat_id"] = 99
        other["utc_kickoff"] += pd.Timedelta(minutes=30)
        u = pd.concat([u, other], ignore_index=True)
    elif defect == "xg_mancante":
        u.loc[0, "home_xg"] = np.nan
    elif defect == "gol_frazionari":
        u.loc[0, "home_goals"] = 1.5
    elif defect == "data_mancante":
        u.loc[0, "utc_kickoff"] = pd.NaT
    with pytest.raises(ValueError):
        lab_xg.prepare_history(u, h)


def test_protocollo_fisso_e_candidato_escluso_dal_set_generico():
    assert (lab_xg.STEP_DAYS, lab_xg.MIN_TRAIN, lab_xg.BOOT_DRAWS, lab_xg.BOOT_SEED) == (90, 800, 2000, 11)
    assert inspect.signature(lab.paired_bootstrap).parameters["seed"].default == lab_xg.BOOT_SEED
    assert (lab_xg.MIN_EVAL, lab_xg.MIN_LEAGUES) == (200, 5)
    assert lab.XG_CANDIDATE.key == "dc_xg"
    assert lab.XG_CANDIDATE.params == {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.7}
    assert lab.XG_CANDIDATE.grid == ()
    assert "dc_xg" not in {c.key for c in lab.CANDIDATES}


@pytest.fixture(scope="module")
def experiment():
    hist = training(360).assign(season=2023)
    baseline = next(c for c in lab.CANDIDATES if c.key == lab.BASELINE)
    rows = lab.walk_forward(hist, (baseline, lab.XG_CANDIDATE), step_days=28, min_train=50,
                            calibration=Calibration(), self_calibrate=True, strict_fits=True)
    expected = lab_xg.eligible_matches(hist, step_days=28, min_train=50)
    return hist, rows, expected


def test_barriere_temporali_e_calibrazione_sui_soli_prefissi(experiment):
    _, rows, expected = experiment
    paired = lab_xg.validate_pairs(rows, expected)
    assert len(paired) == len(expected) and len(rows) == 2 * len(expected)
    assert (rows.train_max < rows.window_start).all()
    assert (rows.window_start <= rows.date).all()
    assert rows.calibration_n.max() > lab.MIN_SELF_CAL
    for (_, _), window in rows.groupby(["candidate", "window_start"]):
        assert window.lambda_scale.nunique() == 1
    assert paired.uses_xg.all() and not paired.uses_xg_ref.any()


def test_xg_e_gol_della_finestra_non_cambiano_la_previsione(experiment):
    hist, original, _ = experiment
    first = original.window_start.min()
    altered = hist.copy()
    mask = altered.date.dt.tz_localize(None) >= first
    altered.loc[mask, ["home_goals", "away_goals", "home_xg", "away_xg"]] = [0, 9, -999, 999]
    baseline = next(c for c in lab.CANDIDATES if c.key == lab.BASELINE)
    rows = lab.walk_forward(altered, (baseline, lab.XG_CANDIDATE), step_days=28, min_train=50,
                            calibration=Calibration(), max_windows=1, strict_fits=True)
    keys = ["candidate", *lab_xg.MATCH_KEYS]
    cols = lab_xg.PROB_COLS + ["lambda_home", "lambda_away", "lambda_scale", "rho"]
    before = original[original.window_start.eq(first)].set_index(keys).sort_index()[cols]
    after = rows.set_index(keys).sort_index()[cols]
    pd.testing.assert_frame_equal(before, after, atol=1e-12, rtol=0)


@pytest.mark.parametrize("defect", ["manca_riga", "duplicato", "probabilita", "futuro", "calibrazione", "fallback"])
def test_validazione_rifiuta_un_confronto_falsato(experiment, defect):
    _, original, expected = experiment
    rows = original.copy()
    if defect == "manca_riga":
        rows = rows.iloc[1:]
    elif defect == "duplicato":
        rows = pd.concat([rows, rows.iloc[[0]]], ignore_index=True)
    elif defect == "probabilita":
        rows.loc[0, "p_home"] = np.nan
    elif defect == "futuro":
        rows.loc[0, "train_max"] = rows.loc[0, "date"]
    elif defect == "calibrazione":
        rows.loc[0, "calibration_n"] += 1
    elif defect == "fallback":
        rows.loc[rows.candidate.eq("dc_xg"), "uses_xg"] = False
    with pytest.raises(ValueError):
        lab_xg.validate_pairs(rows, expected)


def test_squadre_mai_viste_escluse_per_entrambi():
    hist = training(80)
    hist.loc[70, "home"] = "NEOPROMOSSA"
    expected = lab_xg.eligible_matches(hist, step_days=20, min_train=50)
    baseline = next(c for c in lab.CANDIDATES if c.key == lab.BASELINE)
    rows = lab.walk_forward(hist, (baseline, lab.XG_CANDIDATE), step_days=20, min_train=50,
                            calibration=Calibration(), strict_fits=True)
    assert len(expected) == 29 and "NEOPROMOSSA" not in set(expected.home)
    assert len(lab_xg.validate_pairs(rows, expected)) == 29


def test_fallback_walk_forward_appaiato_e_neutro():
    hist = training(80).drop(columns=["home_xg", "away_xg"]).assign(league_key="NED1", season=2023)
    expected = lab_xg.eligible_matches(hist, step_days=20, min_train=50)
    baseline = next(c for c in lab.CANDIDATES if c.key == lab.BASELINE)
    rows = lab.walk_forward(hist, (baseline, lab.XG_CANDIDATE), step_days=20, min_train=50,
                            calibration=Calibration(), strict_fits=True)
    paired = lab_xg.validate_pairs(rows, expected)
    assert len(paired) == 30 and not paired.uses_xg.any()
    report = lab_xg.report_results(hist, rows, paired)
    assert report["n_xg"] == 0 and report["n_fallback"] == 30
    assert report["per_league"][0]["delta_rps"] == 0
    assert report["leagues_better"] == 0 and report["passes"] is False


def test_fit_fallito_interrompe_solo_in_modalita_strict(monkeypatch):
    def fail(*args):
        raise ValueError("fit deliberatamente fallito")

    monkeypatch.setattr(lab, "_fit_candidate", fail)
    with pytest.raises(ValueError, match="deliberatamente"):
        lab.walk_forward(training(), (lab.XG_CANDIDATE,), min_train=50, max_windows=1, strict_fits=True)
    assert lab.walk_forward(training(), (lab.XG_CANDIDATE,), min_train=50, max_windows=1).empty


@pytest.mark.parametrize("n,n_xg,hi,better,passes", [
    (199, 199, -0.01, 5, False), (200, 199, -0.01, 5, False),
    (200, 200, 0.0, 5, False), (200, 200, -0.01, 4, False),
    (200, 200, -0.01, 5, True), (1000, 0, -0.01, 7, False), (200, 200, np.nan, 5, False),
])
def test_promozione_senza_scorciatoie(n, n_xg, hi, better, passes):
    assert lab_xg.promotion(n, n_xg, hi, better) is passes


def test_rps_indipendente_e_riepilogo_coerenti(experiment):
    hist, rows, expected = experiment
    paired = lab_xg.validate_pairs(rows, expected)
    report = lab_xg.report_results(hist, rows, paired)
    assert report["n"] == len(expected) == report["n_xg"]
    assert report["n_fallback"] == 0
    assert report["promoted"] is False and report["passes"] is False  # un solo campionato sintetico
    assert report["leagues_required"] == 7


def test_output_in_produzione_e_snapshot_diversi_sono_rifiutati(tmp_path):
    data = tmp_path / "processed"
    data.mkdir()
    with pytest.raises(ValueError, match="produzione"):
        lab_xg.run(data, data)
    with pytest.raises(ValueError, match="produzione"):
        lab_xg.run(data, data / "nested")
    for name in lab_xg.INPUT_HASHES:
        (data / name).write_bytes(b"snapshot sbagliato")
    with pytest.raises(ValueError, match="snapshot diverso"):
        lab_xg.run(data, tmp_path / "experiment")
    assert not (tmp_path / "experiment").exists()


def test_cli_offline_dichiara_errori_senza_finto_successo(tmp_path):
    result = CliRunner().invoke(app, ["lab-xg", "--data", str(tmp_path / "assente")])
    assert result.exit_code == 1 and "interrotto" in result.output
    help_result = CliRunner().invoke(app, ["lab-xg", "--help"])
    assert help_result.exit_code == 0 and "promozione" in help_result.output
