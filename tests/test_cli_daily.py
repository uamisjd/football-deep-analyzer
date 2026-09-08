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
