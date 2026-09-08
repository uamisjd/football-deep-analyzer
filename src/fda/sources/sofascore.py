"""Fallback SofaScore per dati pubblicati da FotMob in ritardo.

Usiamo solo gli endpoint pubblici, con cache e rate-limit: calendario del giorno
per collegare una gara ai suoi event id, poi dettagli dell'evento. Il modulo non
sostituisce FotMob e non inventa valori mancanti.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ..http import HttpClient


class SofaScoreClient:
    base_url = "https://www.sofascore.com/api/v1"

    def __init__(self, client: HttpClient | None = None) -> None:
        self.http = client or HttpClient(name="sofascore", rate_limit_s=1.2)

    def scheduled_events(self, day: date) -> list[dict[str, Any]]:
        raw = self.http.get_json(f"{self.base_url}/sport/football/scheduled-events/{day:%Y-%m-%d}", ttl_h=1)
        return raw.get("events") or []

    def event_details(self, event_id: int) -> dict[str, Any]:
        return self.http.get_json(f"{self.base_url}/event/{int(event_id)}", ttl_h=1).get("event") or {}

    def event_lineups(self, event_id: int) -> dict[str, Any]:
        return self.http.get_json(f"{self.base_url}/event/{int(event_id)}/lineups", ttl_h=0.25)

    def event_statistics(self, event_id: int) -> dict[str, Any]:
        return self.http.get_json(f"{self.base_url}/event/{int(event_id)}/statistics", ttl_h=87600)

    def event_incidents(self, event_id: int) -> dict[str, Any]:
        return self.http.get_json(f"{self.base_url}/event/{int(event_id)}/incidents", ttl_h=87600)

    @staticmethod
    def _name(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("name") or value.get("shortName") or "").strip()
        return str(value or "").strip()

    @classmethod
    def match_event(cls, events: list[dict[str, Any]], home: str, away: str,
                    kickoff: datetime | None = None) -> dict[str, Any] | None:
        """Collega una fixture all'evento senza fidarsi solo dei nomi.

        Richiede entrambe le squadre; se esiste il calcio d'inizio sceglie il
        candidato temporalmente più vicino entro 36 ore.
        """
        want_h, want_a = home.casefold(), away.casefold()
        candidates = []
        for event in events:
            eh = cls._name(event.get("homeTeam")).casefold()
            ea = cls._name(event.get("awayTeam")).casefold()
            if not eh or not ea or (want_h not in eh and eh not in want_h) or (want_a not in ea and ea not in want_a):
                continue
            distance = 0.0
            if kickoff and event.get("startTimestamp"):
                distance = abs(float(event["startTimestamp"]) - kickoff.timestamp())
            candidates.append((distance, event))
        return min(candidates, key=lambda x: x[0])[1] if candidates else None

    @staticmethod
    def utc_kickoff(event: dict[str, Any]) -> datetime | None:
        ts = event.get("startTimestamp")
        if ts is None:
            return None
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
