"""Test di scripts/benchmark_quote.py senza rete (docs/19 §1.1, decisione A)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def _load():
    p = Path(__file__).parent.parent / "scripts" / "benchmark_quote.py"
    spec = importlib.util.spec_from_file_location("benchmark_quote", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bq = _load()


def test_devig_restituisce_probabilita_senza_margine():
    # quote uguali → 1/3 ciascuna
    P = bq.devig([3.0, 3.0, 3.0], [3.0, 3.0, 3.0], [3.0, 3.0, 3.0])
    assert np.allclose(P[0], [1 / 3, 1 / 3, 1 / 3])
    # riga con quota mancante/invalida → NaN, non inventata
    P2 = bq.devig([2.0, 3.5, np.nan], [3.0, 3.0, 3.0], [4.0, 3.2, 4.5])
    assert np.isnan(P2[2]).all() and np.isfinite(P2[:2]).all() and P2.shape == (3, 3)


def test_rps_uguale_a_quella_del_progetto():
    from fda.models.predict import rps as rps_progetto
    P = np.array([[0.5, 0.3, 0.2], [0.1, 0.2, 0.7]])
    o = np.array([[1, 0, 0], [0, 0, 1]])
    # la rps del progetto è già una media: stessa media sulle stesse righe → stesso numero
    assert abs(bq.rps(P, o).mean() - rps_progetto(P.tolist(), [0, 2])) < 1e-12


def test_misura_aggancia_e_misura_su_dati_sintetici():
    """Il Δ è la differenza appaiata fra le due serie; la per-lega è coerente col totale."""
    date = pd.Timestamp("2025-01-20")
    bt = pd.DataFrame({
        "date": [date], "league_key": ["ITA1"], "home": ["Roma"], "away": ["Hellas Verona"],
        "p_home": [0.6], "p_draw": [0.25], "p_away": [0.15],
        "home_goals": [2], "away_goals": [0],
    })
    od = pd.DataFrame({
        "lg": ["ITA1"], "date": [date], "HomeTeam": ["Roma"], "AwayTeam": ["Hellas Verona"],
        "PSCH": [1.5], "PSCD": [4.2], "PSCA": [6.0], "FTHG": [2], "FTAG": [0],
    })
    res = bq.misura(bt, od, draws=200)
    assert res["n_valutate"] == 1
    assert res["leghe_vinte"] in (0, 1)
    assert set(res["per_lega"]) == {"ITA1"}
    riga = res["per_lega"]["ITA1"]
    assert riga["n"] == 1
    # il Δ pubblicato equala modello − mercato ricalcolato (stessa regola di verify_site [3b]);
    # la per-lega è arrotondata a 5 decimali → tolleranza di stampa 2e-5
    assert abs(res["delta"] - (riga["modello"] - riga["mercato"])) < 2e-5


def test_misura_usa_i_nomi_canonici_per_agganciare():
    """Il nome football-data ('Man United') aggancia solo via canonical() → nome FotMob."""
    date = pd.Timestamp("2025-02-01")
    bt = pd.DataFrame({
        "date": [date], "league_key": ["ENG1"], "home": ["Manchester United"], "away": ["Everton"],
        "p_home": [0.55], "p_draw": [0.25], "p_away": [0.2],
        "home_goals": [1], "away_goals": [1],
    })
    od = pd.DataFrame({
        "lg": ["ENG1"], "date": [date], "HomeTeam": ["Man United"], "AwayTeam": ["Everton"],
        "PSCH": [2.0], "PSCD": [3.4], "PSCA": [3.8], "FTHG": [1], "FTAG": [1],
    })
    assert bq.misura(bt, od, draws=200)["n_agganciate"] == 1
