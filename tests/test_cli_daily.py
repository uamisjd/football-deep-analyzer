"""Regressione: daily→collect deve ricevere interi, non oggetti typer.Option.

Bug reale (run daily 2026-09-08 16:07 UTC): daily_cmd chiamava collect_cmd()
senza max_backfill → il default restava typer.Option → TypeError su
old[:max_backfill] alla prima lega senza Understat (NED1).
"""
import warnings

import pandas as pd

import fda.collect as collect_mod
import fda.site.build as site_build_mod
import fda.store as store_mod
from fda.cli import daily_cmd
from fda.collect import CollectReport


class FakeStore:
    def read(self, table): return pd.DataFrame()
    def summary(self): return pd.DataFrame([{"table": "fixtures", "rows": 0}])
    def close(self): pass


class FakeBuilder:
    def __init__(self, *a, **k): pass
    def build(self): return {"matches": 0}


def test_daily_passes_int_limits_to_collect(tmp_path, monkeypatch):
    warnings.filterwarnings("ignore")
    captured = {}

    def fake_collect_all(keys=None, store=None, **kw):
        captured.update(kw)
        from datetime import UTC, datetime
        return [CollectReport(league="ITA1", run_at=datetime.now(UTC))]

    monkeypatch.setattr(collect_mod, "collect_all", fake_collect_all)
    monkeypatch.setattr(store_mod, "Store", FakeStore)
    monkeypatch.setattr(site_build_mod, "SiteBuilder", FakeBuilder)
    monkeypatch.setattr(site_build_mod, "SITE_DIR", tmp_path)
    daily_cmd(league_keys=["ITA1"], skip_predict=True)
    assert isinstance(captured["max_backfill"], int), \
        f"max_backfill non è un intero: {type(captured['max_backfill'])}"
    assert captured["max_backfill"] == 40
    assert isinstance(captured["max_matches"], int)


def test_daily_passes_ints_to_calibrate(tmp_path, monkeypatch):
    """Stesso bug, altro comando (docs/48 §5): daily→calibrate deve ricevere interi.

    Riprodotto il 2026-09-20: ``calibrate_cmd()`` senza argomenti riceveva ``typer.Option`` →
    ``TypeError: '<' not supported between instances of 'int' and 'OptionInfo'`` dentro
    ``fit``, catturato dal ``try`` del daily → «calibrate fallito» e calibrazione mai
    risalvata dal 13/09 (``calibration.parquet`` fermo, ``backtest.parquet`` aggiornato).
    """
    import fda.cli as cli_mod
    import fda.models.calibration as cal_mod
    import fda.models.season_sim as sim_mod

    warnings.filterwarnings("ignore")
    captured = {}

    class StoreConBacktest(FakeStore):
        def read(self, table):
            if table == "backtest":
                return pd.DataFrame([{"p_home": 0.4, "p_draw": 0.3, "p_away": 0.3}])
            return pd.DataFrame()

        def upsert(self, table, rows):
            captured["salvato"] = table
            return 1

    def fake_fit(bt, folds, min_rows):
        captured["folds"], captured["min_rows"] = folds, min_rows
        return cal_mod.Calibration()

    def fake_collect_all(keys=None, store=None, **kw):
        from datetime import UTC, datetime
        return [CollectReport(league="ITA1", run_at=datetime.now(UTC))]

    monkeypatch.setattr(collect_mod, "collect_all", fake_collect_all)
    monkeypatch.setattr(store_mod, "Store", StoreConBacktest)
    monkeypatch.setattr(site_build_mod, "SiteBuilder", FakeBuilder)
    monkeypatch.setattr(site_build_mod, "SITE_DIR", tmp_path)
    monkeypatch.setattr(cal_mod, "fit", fake_fit)
    # gli altri passi del daily non sono sotto test: no-op
    monkeypatch.setattr(cli_mod, "predict_cmd", lambda **kw: None)
    monkeypatch.setattr(cli_mod, "backtest_cmd", lambda **kw: None)
    monkeypatch.setattr(cli_mod, "mercati_monitor_cmd", lambda **kw: None)
    monkeypatch.setattr(sim_mod, "simulate_all", lambda *a, **kw: pd.DataFrame())
    daily_cmd(league_keys=["ITA1"], skip_predict=False)
    assert isinstance(captured.get("folds"), int) and isinstance(captured.get("min_rows"), int), \
        f"calibrate non ha ricevuto interi: {captured}"
    assert captured["min_rows"] == 1200 and captured["folds"] == 6
    # dry_run deve essere False (non un OptionInfo truthy): la calibrazione va salvata
    assert captured.get("salvato") == "calibration"
