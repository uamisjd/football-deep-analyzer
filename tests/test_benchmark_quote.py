"""Voce D: misure appaiate sui Parquet già presenti, senza rete né quote inventate."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_quote", Path(__file__).parent.parent / "scripts" / "benchmark_quote.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample():
    dates = pd.to_datetime(["2026-08-01", "2026-08-02", "2026-08-03"], utc=True)
    bt = pd.DataFrame([
        {"league_key": lg, "date": day, "home": home, "away": away,
         "home_goals": hg, "away_goals": ag, "outcome": outcome,
         "p_home": ph, "p_draw": pd_, "p_away": pa, "model_version": "prova"}
        for lg, day, home, away, hg, ag, outcome, ph, pd_, pa in [
            ("ITA1", dates[0], "Internazionale", "Napoli", 2, 0, 0, .4, .3, .3),
            ("NED1", dates[1], "Ajax", "PSV", 0, 1, 2, .2, .5, .3),
            ("POR1", dates[2], "Benfica", "Porto", 1, 1, 1, .3, .4, .3)]])
    history = bt[["league_key", "date", "home", "away", "home_goals", "away_goals"]].copy()
    history.loc[0, "home"] = "Inter"  # alias anche dal lato del backtest, non solo delle quote
    history["date"] += pd.Timedelta(hours=20)  # giorno contro timestamp, stessa gara
    # Margine 11,11%: rimosso → [0,50; 0,25; 0,25] e [0,20; 0,30; 0,50].
    history[["odds_home", "odds_draw", "odds_away"]] = [
        [1.8, 3.6, 3.6], [4.5, 3.0, 1.8], [np.nan, np.nan, np.nan]]
    return bt, history


def test_benchmark_history_metriche_appaiate_alias_date_e_leghe():
    bq = _module()
    bt, history = _sample()
    res = bq.misura(bt, bq.quote_da_history(history), draws=100)
    assert res["n_backtest"] == res["n_agganciate"] == 3 and res["n_valutate"] == 2
    assert res["rps_modello"] == pytest.approx((.225 + .265) / 2)
    assert res["rps_mercato"] == pytest.approx((.15625 + .145) / 2)
    assert res["brier_modello"] == pytest.approx((.54 + .78) / 2)
    assert res["brier_mercato"] == pytest.approx((.375 + .38) / 2)
    assert res["delta"] == pytest.approx(.094375)
    assert res["delta_brier"] == pytest.approx(.2825)
    assert res["ic95"] == res["ic95_brier"] == [None, None]  # <20 gare, non si inventa un IC
    assert res["esclusioni"]["quote_assenti_o_invalide"] == 1
    assert res["versioni_modello"] == {"prova": 2}
    assert res["per_lega"]["POR1"]["n"] == 0 and res["per_lega"]["POR1"]["modello"] is None
    assert len(res["per_lega"]) == 7 and res["leghe_valutate"] == 2
    # L'IC usa differenze sulla stessa gara ed è riproducibile, anche con input disordinati.
    bs, hs = [], []
    for i in range(20):
        bs.append(bt.assign(date=bt.date + pd.Timedelta(days=4*i)))
        hs.append(history.assign(date=history.date + pd.Timedelta(days=4*i)))
    large_bt, large_h = pd.concat(bs), pd.concat(hs)
    first = bq.misura(large_bt, bq.quote_da_history(large_h), draws=100, seed=11)
    shuffled = bq.misura(large_bt.sample(frac=1, random_state=1),
                         bq.quote_da_history(large_h.sample(frac=1, random_state=2)),
                         draws=100, seed=11)
    assert first == shuffled
    assert first["n_valutate"] == 40 and 0 < first["ic95"][0] <= first["ic95"][1]
    assert 0 < first["ic95_brier"][0] <= first["ic95_brier"][1]


def test_benchmark_quote_modello_risultati_invalidi_e_duplicati():
    bq = _module()
    bt, history = _sample()
    for invalid in (0, 1, -1, np.inf, np.nan):
        broken = history.copy()
        broken.loc[0, "odds_home"] = invalid
        res = bq.misura(bt, bq.quote_da_history(broken))
        assert res["n_valutate"] == 1
        assert res["esclusioni"]["quote_assenti_o_invalide"] == 2
    for invalid in ([.8, .7, .1], [np.nan, .2, .8], [-.1, .5, .6]):
        broken = bt.copy()
        broken.loc[0, ["p_home", "p_draw", "p_away"]] = invalid
        res = bq.misura(broken, bq.quote_da_history(history))
        assert res["n_valutate"] == 1
        assert res["esclusioni"]["probabilita_modello_invalide"] == 1
    broken = history.copy()
    broken.loc[0, "home_goals"] = 0
    res = bq.misura(bt, bq.quote_da_history(broken))
    assert res["n_valutate"] == 1
    assert res["esclusioni"]["risultati_assenti_o_discordi"] == 1
    broken = bt.copy()
    broken.loc[0, "outcome"] = 2
    assert bq.misura(broken, bq.quote_da_history(history))["n_valutate"] == 1
    broken = history.copy()
    broken.loc[0, "date"] = pd.NaT
    with pytest.raises(ValueError, match="Chiavi di gara assenti"):
        bq.misura(bt, bq.quote_da_history(broken))
    # Join moltiplicativo vietato: uno stesso risultato non può pesare due volte.
    with pytest.raises(pd.errors.MergeError):
        bq.misura(bt, bq.quote_da_history(pd.concat([history, history.head(1)])))
    with pytest.raises(pd.errors.MergeError):
        bq.misura(pd.concat([bt, bt.head(1)]), bq.quote_da_history(history))


def test_benchmark_senza_quote_e_senza_agganci_non_inventa_zero():
    bq = _module()
    bt, history = _sample()
    without = history.drop(columns=["odds_home", "odds_draw", "odds_away"])
    for source, missing in ((without, 0), (without.head(0), 3)):
        res = bq.misura(bt, bq.quote_da_history(source))
        assert res["n_valutate"] == 0 and res["n_non_agganciate"] == missing
        assert res["leghe_valutate"] == 0 and res["periodo"] is None
        assert res["rps_modello"] is res["brier_mercato"] is res["delta"] is None
        assert res["ic95"] == res["ic95_brier"] == [None, None]
        json.dumps(res, allow_nan=False)  # JSON standard: mai NaN al posto di un dato mancante


def test_benchmark_cli_offline_non_puo_scaricare(tmp_path, monkeypatch, capsys):
    bq = _module()
    bt, history = _sample()
    bt.to_parquet(tmp_path / "backtest.parquet", index=False)
    history.to_parquet(tmp_path / "history.parquet", index=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("la modalità offline non deve chiamare alcuna rete")
    monkeypatch.setattr(bq, "scarica", forbidden)
    from fda.http import HttpClient
    monkeypatch.setattr(HttpClient, "get_bytes", forbidden)
    output = tmp_path / "risultati" / "benchmark.json"
    bq.main(["--offline", "--data", str(tmp_path), "--json", str(output)])
    res = json.loads(output.read_text())
    assert res["n_valutate"] == 2 and "history.parquet" in res["fonte_quote"]
    assert set(res["input_sha256"]) == {"history.parquet", "backtest.parquet"}
    assert all(len(value) == 64 for value in res["input_sha256"].values())
    assert "Brier" in res["convenzioni"] and "brier_mercato" in capsys.readouterr().out
