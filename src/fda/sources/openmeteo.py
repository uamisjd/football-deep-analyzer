"""Meteo previsionale Open-Meteo (gratuito, senza chiave API).

Riempie il vuoto meteo di FotMob sulle partite future: FotMob pubblica il meteo
solo a ridosso della gara (48h), mentre Open-Meteo dà previsioni orarie fino a
16 giorni (licenza CC BY 4.0, ~10.000 richieste/giorno). Viene usato SOLO come
fallback: se FotMob ha già il meteo, quello resta la fonte primaria.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import source
from ..http import HttpClient

# Codice meteo WMO (Open-Meteo `weather_code`) → descrizione italiana breve.
_WMO_IT = {
    0: "sereno", 1: "prevalentemente sereno", 2: "parzialmente nuvoloso", 3: "coperto",
    45: "nebbia", 48: "nebbia con brina",
    51: "pioviggine", 53: "pioviggine", 55: "pioviggine fitta",
    61: "pioggia debole", 63: "pioggia", 65: "pioggia intensa",
    66: "pioggia gelata", 67: "pioggia gelata forte",
    71: "neve debole", 73: "neve", 75: "neve intensa", 77: "nevischio",
    80: "rovesci", 81: "rovesci", 82: "rovesci intensi",
    85: "rovesci di neve", 86: "rovesci di neve intensi",
    95: "temporale", 96: "temporale con grandine", 99: "temporale con grandine forte",
}


class OpenMeteoClient:
    """Previsione oraria nel punto (lat, lon) all'ora del calcio d'inizio."""

    def __init__(self, client: HttpClient | None = None) -> None:
        cfg = source("openmeteo")
        self.base_url: str = cfg["base_url"]
        self.ttl_h: float = float(cfg.get("cache_ttl_h", 3))
        self.http = client or HttpClient(name="openmeteo", rate_limit_s=0.5)

    def forecast(self, lat: float, lon: float, when: datetime) -> dict[str, Any] | None:
        """Previsione all'ora più vicina a `when`: ``{temp_c, precip_prob, desc, code, hour}``."""
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        target = when.astimezone(timezone.utc).replace(tzinfo=None)  # confronto su UTC naive
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "timezone": "UTC", "forecast_days": 16,
        }
        raw = self.http.get_json(self.base_url, params=params, ttl_h=self.ttl_h)
        hourly = (raw or {}).get("hourly") or {}
        times = [t for t in (hourly.get("time") or []) if isinstance(t, str)]
        if not times:
            return None
        idx = self._nearest_index(times, target)
        if idx is None:
            return None

        def _get(arr: list[Any], i: int) -> float | None:
            try:
                v = arr[i]
            except (IndexError, TypeError):
                return None
            return None if v is None else float(v)

        temps = hourly.get("temperature_2m") or []
        precips = hourly.get("precipitation_probability") or []
        codes = hourly.get("weather_code") or []
        code = _get(codes, idx)
        return {"temp_c": _get(temps, idx), "precip_prob": _get(precips, idx),
                "desc": _WMO_IT.get(int(code), None) if code is not None else None,
                "code": int(code) if code is not None else None,
                "hour": times[idx]}

    @staticmethod
    def _nearest_index(times: list[str], target: datetime) -> int | None:
        pts: list[datetime] = []
        for t in times:
            try:
                pts.append(datetime.fromisoformat(t))
            except (ValueError, TypeError):
                continue
        if not pts:
            return None
        diffs = [abs((p - target).total_seconds()) for p in pts]
        return diffs.index(min(diffs))
