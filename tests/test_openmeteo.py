"""Test offline del client Open-Meteo (parser sulla risposta campione)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fda.sources.openmeteo import OpenMeteoClient

FIX = Path(__file__).parent / "fixtures"


class _FakeHttp:
    """Restituisce la risposta campione senza rete."""

    def __init__(self, raw):
        self.raw = raw
        self.stats = type("S", (), {"requests": 1, "cache_hits": 0})()

    def get_json(self, url, params=None, ttl_h=None, extra_headers=None):
        return json.loads(self.raw)


def test_forecast_nearest_hour():
    client = OpenMeteoClient(client=_FakeHttp((FIX / "openmeteo_forecast_sample.json").read_text()))
    # calcio d'inizio 18:45 → l'ora più vicina è 19:00 (21°C, pioggia 60%, "pioggia debole")
    fc = client.forecast(41.93, 12.45, datetime(2026, 9, 9, 18, 45, tzinfo=timezone.utc))
    assert fc["temp_c"] == 21.0
    assert fc["precip_prob"] == 60.0
    assert fc["desc"] == "pioggia debole"
    assert fc["hour"] == "2026-09-09T19:00"


def test_forecast_exact_hour():
    client = OpenMeteoClient(client=_FakeHttp((FIX / "openmeteo_forecast_sample.json").read_text()))
    fc = client.forecast(41.93, 12.45, datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc))
    assert fc["hour"] == "2026-09-09T18:00" and fc["temp_c"] == 22.5


def test_forecast_empty_response():
    class _Empty:
        stats = type("S", (), {"requests": 1, "cache_hits": 0})()

        def get_json(self, *a, **kw):
            return {}

    client = OpenMeteoClient(client=_Empty())
    assert client.forecast(41.93, 12.45, datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)) is None


def test_wmo_translation_and_nearest_index():
    client = OpenMeteoClient(client=_FakeHttp((FIX / "openmeteo_forecast_sample.json").read_text()))
    assert client._nearest_index(["2026-09-09T18:00", "2026-09-09T19:00"],
                                 datetime(2026, 9, 9, 18, 40)) == 1
    assert client._nearest_index([], datetime(2026, 9, 9, 18, 40)) is None
