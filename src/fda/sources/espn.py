"""Client ESPN (API pubbliche non documentate di site.api.espn.com) — la "spina dorsale" di riserva.

Endpoint verificati il 5-6 settembre 2026 senza autenticazione:
  /apis/site/v2/sports/soccer/{code}/scoreboard?dates=YYYYMMDD
  /apis/site/v2/sports/soccer/{code}/summary?event={id}
  /apis/v2/sports/soccer/{code}/standings
  /apis/site/v2/sports/soccer/{code}/teams
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from typing import Any

from ..config import source
from ..http import HttpClient

log = logging.getLogger(__name__)


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _f(v: Any) -> float | None:
    try:
        return None if v in (None, "") else float(str(v).replace("%", ""))
    except (TypeError, ValueError):
        return None


@dataclass
class EspnEvent:
    espn_id: int
    league_code: str
    utc_kickoff: datetime | None
    home_id: int
    home_name: str
    away_id: int
    away_name: str
    home_goals: int | None
    away_goals: int | None
    status: str                 # scheduled | live | finished | postponed | cancelled
    status_detail: str | None
    venue: str | None
    city: str | None
    attendance: int | None
    home_form: str | None       # es. "WDLWW"
    away_form: str | None
    source: str = "espn"


@dataclass
class EspnTeamStat:
    espn_event_id: int
    team_id: int
    key: str
    value: float | None


@dataclass
class EspnStandingRow:
    league_code: str
    team_id: int
    team_name: str
    rank: int | None
    played: int | None
    wins: int | None
    draws: int | None
    losses: int | None
    goals_for: int | None
    goals_against: int | None
    goal_diff: int | None
    points: int | None
    note: str | None


class EspnClient:
    STATUS_MAP = {
        "STATUS_SCHEDULED": "scheduled",
        "STATUS_IN_PROGRESS": "live",
        "STATUS_HALFTIME": "live",
        "STATUS_FIRST_HALF": "live",
        "STATUS_SECOND_HALF": "live",
        "STATUS_FULL_TIME": "finished",
        "STATUS_FINAL": "finished",
        "STATUS_FINAL_PEN": "finished",
        "STATUS_FINAL_AET": "finished",
        "STATUS_POSTPONED": "postponed",
        "STATUS_CANCELED": "cancelled",
        "STATUS_ABANDONED": "cancelled",
    }

    def __init__(self, client: HttpClient | None = None) -> None:
        cfg = source("espn")
        self.base_url: str = cfg["base_url"].rstrip("/")
        self.ttl = cfg.get("cache_ttl_h", {})
        self.http = client or HttpClient(name="espn", rate_limit_s=float(cfg.get("rate_limit_s", 0.5)))

    # ---- grezzo -----------------------------------------------------------------------------
    def scoreboard_raw(self, league_code: str, day: date | None = None) -> dict:
        params = {"dates": day.strftime("%Y%m%d")} if day else None
        return self.http.get_json(f"{self.base_url}/site/v2/sports/soccer/{league_code}/scoreboard",
                                  params=params, ttl_h=self.ttl.get("scoreboard", 1))

    def summary_raw(self, league_code: str, event_id: int, finished: bool = False) -> dict:
        ttl = self.ttl.get("summary_finished", 87600) if finished else 1
        return self.http.get_json(f"{self.base_url}/site/v2/sports/soccer/{league_code}/summary",
                                  params={"event": event_id}, ttl_h=ttl)

    def standings_raw(self, league_code: str) -> dict:
        return self.http.get_json(f"{self.base_url}/v2/sports/soccer/{league_code}/standings",
                                  ttl_h=self.ttl.get("standings", 6))

    def teams_raw(self, league_code: str) -> dict:
        return self.http.get_json(f"{self.base_url}/site/v2/sports/soccer/{league_code}/teams",
                                  ttl_h=24)

    # ---- parser -----------------------------------------------------------------------------
    def parse_scoreboard(self, league_code: str, raw: dict) -> tuple[list[EspnEvent], list[EspnTeamStat]]:
        events: list[EspnEvent] = []
        stats: list[EspnTeamStat] = []
        for ev in raw.get("events") or []:
            comp = (ev.get("competitions") or [{}])[0]
            st_type = ((comp.get("status") or {}).get("type") or {})
            status = self.STATUS_MAP.get(st_type.get("name", ""), "live" if st_type.get("state") == "in" else
                                         "finished" if st_type.get("completed") else "scheduled")
            sides = {c.get("homeAway"): c for c in comp.get("competitors") or []}
            home, away = sides.get("home", {}), sides.get("away", {})
            venue = comp.get("venue") or {}
            eid = int(ev["id"])

            def _score(c: dict) -> int | None:
                if status not in ("finished", "live"):
                    return None
                try:
                    return int(float(c.get("score")))
                except (TypeError, ValueError):
                    return None

            events.append(EspnEvent(
                espn_id=eid, league_code=league_code, utc_kickoff=_dt(comp.get("date") or ev.get("date")),
                home_id=int(home.get("id", 0)), home_name=(home.get("team") or {}).get("displayName", ""),
                away_id=int(away.get("id", 0)), away_name=(away.get("team") or {}).get("displayName", ""),
                home_goals=_score(home), away_goals=_score(away), status=status,
                status_detail=st_type.get("shortDetail"),
                venue=venue.get("fullName"), city=(venue.get("address") or {}).get("city"),
                attendance=comp.get("attendance") or None,
                home_form=home.get("form"), away_form=away.get("form"),
            ))
            for c in (home, away):
                for s in c.get("statistics") or []:
                    if s.get("name") and s.get("name") != "appearances":
                        stats.append(EspnTeamStat(eid, int(c.get("id", 0)), s["name"], _f(s.get("displayValue"))))
        return events, stats

    def parse_standings(self, league_code: str, raw: dict) -> list[EspnStandingRow]:
        rows: list[EspnStandingRow] = []
        # Struttura: children[0].standings.entries[] (a volte direttamente standings.entries)
        blocks = raw.get("children") or [raw]
        for block in blocks:
            for e in ((block.get("standings") or {}).get("entries") or []):
                team = e.get("team") or {}
                st = {s.get("name"): s for s in e.get("stats") or []}

                def _v(name: str) -> int | None:
                    v = (st.get(name) or {}).get("value")
                    return None if v is None else int(v)

                rows.append(EspnStandingRow(
                    league_code=league_code, team_id=int(team.get("id", 0)),
                    team_name=team.get("displayName", ""), rank=_v("rank"),
                    played=_v("gamesPlayed"), wins=_v("wins"), draws=_v("ties"), losses=_v("losses"),
                    goals_for=_v("pointsFor"), goals_against=_v("pointsAgainst"),
                    goal_diff=_v("pointDifferential"), points=_v("points"),
                    note=((e.get("note") or {}).get("description")),
                ))
        rows.sort(key=lambda r: (r.rank is None, r.rank or 0))
        return rows

    def parse_summary_boxscore(self, event_id: int, raw: dict) -> list[EspnTeamStat]:
        out: list[EspnTeamStat] = []
        for t in ((raw.get("boxscore") or {}).get("teams") or []):
            tid = int((t.get("team") or {}).get("id", 0))
            for s in t.get("statistics") or []:
                if s.get("name"):
                    out.append(EspnTeamStat(event_id, tid, s["name"], _f(s.get("displayValue"))))
        return out

    @staticmethod
    def parse_summary_officials(raw: dict) -> list[str]:
        """Nomi degli arbitri (gameInfo.officials) se presenti."""
        officials = ((raw.get("gameInfo") or {}).get("officials")) or []
        return [o.get("displayName") or o.get("fullName") for o in officials if isinstance(o, dict)]


def to_dicts(rows: list) -> list[dict[str, Any]]:
    return [asdict(r) for r in rows]
