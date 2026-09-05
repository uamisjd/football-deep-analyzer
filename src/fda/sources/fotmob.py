"""Client FotMob (endpoint non documentati `https://www.fotmob.com/api/data/*`).

Verificati il 5-6 settembre 2026 senza autenticazione. Il client è volutamente sottile:
scarica JSON grezzo (con cache su disco) e lo trasforma in record piatti e stabili.
Se FotMob cambia formato, va aggiornato SOLO questo file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..config import RAW_DIR, season, source
from ..http import HttpClient

log = logging.getLogger(__name__)


def _dt(value: Any) -> datetime | None:
    """Converte 'YYYY-MM-DDTHH:MM:SS(.sss)Z' in datetime UTC."""
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("utcTime")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------
# Record piatti (schema stabile verso il resto del progetto)
# ------------------------------------------------------------------------------------------
@dataclass
class Fixture:
    match_id: int
    league_id: int
    season: str
    round: str | None
    utc_kickoff: datetime | None
    home_id: int
    home_name: str
    away_id: int
    away_name: str
    home_goals: int | None
    away_goals: int | None
    status: str          # scheduled | live | finished | cancelled | postponed
    source: str = "fotmob"


@dataclass
class Shot:
    match_id: int
    shot_id: int
    team_id: int
    player_id: int | None
    player_name: str | None
    minute: int | None
    minute_added: int | None
    period: str | None
    x: float | None
    y: float | None
    xg: float | None
    xgot: float | None
    event_type: str | None     # Goal | AttemptSaved | Miss | Post | ...
    shot_type: str | None      # RightFoot | LeftFoot | Header | ...
    situation: str | None      # RegularPlay | FromCorner | SetPiece | Penalty | FastBreak ...
    is_on_target: bool | None
    is_blocked: bool | None
    is_own_goal: bool | None
    is_inside_box: bool | None
    keeper_id: int | None


@dataclass
class TeamMatchStat:
    match_id: int
    team_id: int
    period: str      # All | FirstHalf | SecondHalf
    key: str
    value: float | None
    text: str | None


@dataclass
class PlayerMatchStat:
    match_id: int
    team_id: int
    player_id: int
    player_name: str
    key: str
    value: float | None
    total: float | None


@dataclass
class LineupPlayer:
    match_id: int
    team_id: int
    player_id: int
    player_name: str
    role: str                 # starter | sub | unavailable | coach
    shirt_number: str | None
    position_id: int | None
    usual_position_id: int | None
    age: int | None
    country: str | None
    market_value_eur: float | None
    rating: float | None
    season_rating: float | None
    is_captain: bool
    unavailability_type: str | None      # injury | suspension | ...
    expected_return: str | None


@dataclass
class MatchInfo:
    match_id: int
    league_id: int
    round: str | None
    utc_kickoff: datetime | None
    home_id: int
    away_id: int
    home_goals: int | None
    away_goals: int | None
    status: str
    coverage_level: str | None
    lineup_type: str | None          # predicted | official | None
    home_formation: str | None
    away_formation: str | None
    home_rating: float | None
    away_rating: float | None
    home_starters_value_eur: float | None
    away_starters_value_eur: float | None
    home_avg_starter_age: float | None
    away_avg_starter_age: float | None
    referee_id: int | None
    referee_name: str | None
    referee_matches: int | None
    referee_yellows_per_match: float | None
    referee_reds_total: int | None
    referee_penalties_total: int | None
    referee_fouls_per_match: float | None
    stadium_name: str | None
    stadium_city: str | None
    stadium_lat: float | None
    stadium_lon: float | None
    stadium_capacity: int | None
    attendance: int | None
    weather_desc: str | None
    weather_temp_c: float | None
    weather_precip_chance: float | None
    weather_wind: float | None
    home_xg: float | None
    away_xg: float | None
    home_xgot: float | None
    away_xgot: float | None
    h2h_home_wins: int | None
    h2h_draws: int | None
    h2h_away_wins: int | None
    fetched_at: datetime | None = None


@dataclass
class MatchBundle:
    """Tutto ciò che si estrae da una chiamata matchDetails."""

    info: MatchInfo
    shots: list[Shot]
    team_stats: list[TeamMatchStat]
    player_stats: list[PlayerMatchStat]
    lineup: list[LineupPlayer]
    events: list[dict[str, Any]]
    momentum: list[dict[str, Any]]
    h2h_matches: list[dict[str, Any]]
    insights: list[dict[str, Any]]


# ------------------------------------------------------------------------------------------
# Client
# ------------------------------------------------------------------------------------------
class FotMobClient:
    def __init__(self, client: HttpClient | None = None, raw_dir: Path | None = None) -> None:
        cfg = source("fotmob")
        self.base_url: str = cfg["base_url"].rstrip("/")
        self.ttl = cfg.get("cache_ttl_h", {})
        self.http = client or HttpClient(
            name="fotmob",
            rate_limit_s=float(cfg.get("rate_limit_s", 1.0)),
            headers=dict(cfg.get("headers", {})),
            max_requests=cfg.get("max_requests_per_run"),
        )
        self.raw_dir = raw_dir or (RAW_DIR / "fotmob")
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    # ---- chiamate grezze ----------------------------------------------------------------
    def _get(self, endpoint: str, params: dict[str, Any], ttl_h: float | None) -> Any:
        return self.http.get_json(f"{self.base_url}/{endpoint}", params=params, ttl_h=ttl_h)

    def fixtures_raw(self, league_id: int, season_str: str | None = None) -> list[dict]:
        data = self._get(
            "fixtures",
            {"id": league_id, "season": season_str or season()},
            ttl_h=self.ttl.get("fixtures", 6),
        )
        return data if isinstance(data, list) else data.get("fixtures", [])

    def league_raw(self, league_id: int) -> dict:
        return self._get("leagues", {"id": league_id}, ttl_h=self.ttl.get("fixtures", 6))

    def match_details_raw(self, match_id: int, finished_hint: bool | None = None) -> dict:
        ttl = self.ttl.get("matchDetails_finished" if finished_hint else "matchDetails_upcoming", 3)
        data = self._get("matchDetails", {"matchId": match_id}, ttl_h=ttl)
        # Se la partita è finita ma era in cache "upcoming", il record verrà riscaricato al
        # prossimo giro grazie al TTL breve; una volta finita si salva con TTL lungo.
        if finished_hint is None and data.get("general", {}).get("finished"):
            self._get("matchDetails", {"matchId": match_id},
                      ttl_h=self.ttl.get("matchDetails_finished", 87600))
        return data

    def team_raw(self, team_id: int) -> dict:
        return self._get("teams", {"id": team_id}, ttl_h=self.ttl.get("teams", 24))

    def player_raw(self, player_id: int) -> dict:
        return self._get("playerData", {"id": player_id}, ttl_h=self.ttl.get("playerData", 168))

    def matches_by_date_raw(self, day: date) -> dict:
        return self._get("matches", {"date": day.strftime("%Y%m%d")}, ttl_h=0.5)

    # ---- parsing ------------------------------------------------------------------------
    @staticmethod
    def _status(st: dict | None) -> str:
        st = st or {}
        if st.get("cancelled"):
            return "cancelled"
        if st.get("finished"):
            return "finished"
        if st.get("started"):
            return "live"
        reason = (st.get("reason") or {}).get("short", "")
        if reason in ("PP", "Postp"):
            return "postponed"
        return "scheduled"

    def parse_fixtures(self, league_id: int, raw: Iterable[dict],
                       season_str: str | None = None) -> list[Fixture]:
        out: list[Fixture] = []
        for m in raw:
            home, away, st = m.get("home", {}), m.get("away", {}), m.get("status", {})
            status = self._status(st)
            hg, ag = home.get("score"), away.get("score")
            if status not in ("finished", "live"):
                hg = ag = None
            out.append(Fixture(
                match_id=int(m["id"]),
                league_id=league_id,
                season=season_str or season(),
                round=str(m.get("round") or (m.get("tournament") or {}).get("round") or "") or None,
                utc_kickoff=_dt(st.get("utcTime")),
                home_id=int(home["id"]), home_name=home.get("name", ""),
                away_id=int(away["id"]), away_name=away.get("name", ""),
                home_goals=None if hg is None else int(hg),
                away_goals=None if ag is None else int(ag),
                status=status,
            ))
        return out

    def parse_match(self, raw: dict) -> MatchBundle:
        g = raw.get("general", {})
        header = raw.get("header", {})
        content = raw.get("content", {}) or {}
        facts = content.get("matchFacts", {}) or {}
        info_box = facts.get("infoBox", {}) or {}
        lineup = content.get("lineup", {}) or {}
        match_id = int(g["matchId"])
        st = header.get("status", {}) or {}
        status = self._status(st)
        teams = header.get("teams", [{}, {}])
        home_id, away_id = int(g["homeTeam"]["id"]), int(g["awayTeam"]["id"])

        # --- arbitro / stadio / meteo -------------------------------------------------
        ref = info_box.get("Referee") or {}
        ref_stats = {s.get("type"): s for s in (ref.get("stats") or [])}
        stadium = info_box.get("Stadium") or {}
        weather = content.get("weather") or {}
        att = info_box.get("Attendance")

        # --- squadre nella formazione ---------------------------------------------------
        lh, la = lineup.get("homeTeam", {}) or {}, lineup.get("awayTeam", {}) or {}

        # --- xG di squadra (da stats All) --------------------------------------------
        team_stats = self._parse_team_stats(match_id, home_id, away_id, content.get("stats"))
        def _stat(team: int, key: str) -> float | None:
            for s in team_stats:
                if s.team_id == team and s.period == "All" and s.key == key:
                    return s.value
            return None

        h2h = (content.get("h2h") or {}).get("summary") or [None, None, None]

        info = MatchInfo(
            match_id=match_id,
            league_id=int(g.get("leagueId") or 0),
            round=str(g.get("matchRound") or "") or None,
            utc_kickoff=_dt(g.get("matchTimeUTCDate")) or _dt(st.get("utcTime")),
            home_id=home_id, away_id=away_id,
            home_goals=teams[0].get("score") if status in ("finished", "live") else None,
            away_goals=teams[1].get("score") if status in ("finished", "live") else None,
            status=status,
            coverage_level=g.get("coverageLevel"),
            lineup_type=lineup.get("lineupType"),
            home_formation=lh.get("formation"), away_formation=la.get("formation"),
            home_rating=_num(lh.get("rating")), away_rating=_num(la.get("rating")),
            home_starters_value_eur=_num(lh.get("totalStarterMarketValue")),
            away_starters_value_eur=_num(la.get("totalStarterMarketValue")),
            home_avg_starter_age=_num(lh.get("averageStarterAge")),
            away_avg_starter_age=_num(la.get("averageStarterAge")),
            referee_id=ref.get("id"), referee_name=ref.get("text"),
            referee_matches=(ref_stats.get("matches") or {}).get("value"),
            referee_yellows_per_match=_num((ref_stats.get("yellowCards") or {}).get("value")),
            referee_reds_total=(ref_stats.get("redCards") or {}).get("value"),
            referee_penalties_total=(ref_stats.get("penalties") or {}).get("value"),
            referee_fouls_per_match=_num((ref_stats.get("fouls") or {}).get("value")),
            stadium_name=stadium.get("name"), stadium_city=stadium.get("city"),
            stadium_lat=_num(stadium.get("lat")), stadium_lon=_num(stadium.get("long")),
            stadium_capacity=stadium.get("capacity"),
            attendance=int(att) if isinstance(att, (int, float)) else None,
            weather_desc=weather.get("description"),
            weather_temp_c=_num(weather.get("temperature")),
            weather_precip_chance=_num(weather.get("precipChance")),
            weather_wind=_num(weather.get("windSpeed")),
            home_xg=_stat(home_id, "expected_goals"), away_xg=_stat(away_id, "expected_goals"),
            home_xgot=_stat(home_id, "expected_goals_on_target"),
            away_xgot=_stat(away_id, "expected_goals_on_target"),
            h2h_home_wins=h2h[0] if len(h2h) > 0 else None,
            h2h_draws=h2h[1] if len(h2h) > 1 else None,
            h2h_away_wins=h2h[2] if len(h2h) > 2 else None,
            fetched_at=datetime.now(timezone.utc),
        )

        return MatchBundle(
            info=info,
            shots=self._parse_shots(match_id, content.get("shotmap")),
            team_stats=team_stats,
            player_stats=self._parse_player_stats(match_id, content.get("playerStats")),
            lineup=self._parse_lineup(match_id, lh, la),
            events=self._parse_events(facts.get("events")),
            momentum=[{"minute": _num(p.get("minute")), "value": _num(p.get("value"))}
                      for p in ((facts.get("momentum") or {}).get("main") or {}).get("data", [])],
            h2h_matches=self._parse_h2h((content.get("h2h") or {}).get("matches")),
            insights=[{"team_id": i.get("teamId"), "player_id": i.get("playerId"),
                       "text": i.get("text")} for i in (facts.get("insights") or [])],
        )

    # ---- sotto-parser -------------------------------------------------------------------
    @staticmethod
    def _parse_shots(match_id: int, shotmap: dict | None) -> list[Shot]:
        shots: list[Shot] = []
        for s in ((shotmap or {}).get("shots") or []):
            shots.append(Shot(
                match_id=match_id, shot_id=int(s.get("id") or 0), team_id=int(s.get("teamId") or 0),
                player_id=s.get("playerId"), player_name=s.get("playerName"),
                minute=s.get("min"), minute_added=s.get("minAdded"), period=s.get("period"),
                x=_num(s.get("x")), y=_num(s.get("y")),
                xg=_num(s.get("expectedGoals")), xgot=_num(s.get("expectedGoalsOnTarget")),
                event_type=s.get("eventType"), shot_type=s.get("shotType"),
                situation=s.get("situation"),
                is_on_target=s.get("isOnTarget"), is_blocked=s.get("isBlocked"),
                is_own_goal=s.get("isOwnGoal"), is_inside_box=s.get("isFromInsideBox"),
                keeper_id=s.get("keeperId"),
            ))
        return shots

    @staticmethod
    def _parse_team_stats(match_id: int, home_id: int, away_id: int,
                          stats: dict | None) -> list[TeamMatchStat]:
        out: list[TeamMatchStat] = []
        periods = ((stats or {}).get("Periods") or {})
        for period, block in periods.items():
            for group in (block or {}).get("stats") or []:
                for s in group.get("stats") or []:
                    if s.get("type") == "title":
                        continue
                    key = s.get("key")
                    vals = s.get("stats") or [None, None]
                    if not key or len(vals) < 2:
                        continue
                    for team_id, v in ((home_id, vals[0]), (away_id, vals[1])):
                        text = None if v is None else str(v)
                        num = _num(str(v).split(" ")[0].replace("%", "")) if v is not None else None
                        out.append(TeamMatchStat(match_id, team_id, period, key, num, text))
        return out

    @staticmethod
    def _parse_player_stats(match_id: int, player_stats: dict | None) -> list[PlayerMatchStat]:
        out: list[PlayerMatchStat] = []
        for pid, p in (player_stats or {}).items():
            team_id = int(p.get("teamId") or 0)
            name = p.get("name", "")
            for group in p.get("stats") or []:
                for _title, item in (group.get("stats") or {}).items():
                    key = item.get("key")
                    stat = item.get("stat") or {}
                    if not key or stat.get("type") == "boolean":
                        continue
                    out.append(PlayerMatchStat(
                        match_id, team_id, int(pid), name, key,
                        _num(stat.get("value")), _num(stat.get("total")),
                    ))
        return out

    @staticmethod
    def _parse_lineup(match_id: int, lh: dict, la: dict) -> list[LineupPlayer]:
        out: list[LineupPlayer] = []
        for team in (lh, la):
            team_id = team.get("id")
            if team_id is None:
                continue
            groups = (("starter", team.get("starters")), ("sub", team.get("subs")),
                      ("unavailable", team.get("unavailable")))
            for role, players in groups:
                for p in players or []:
                    perf = p.get("performance") or {}
                    unav = p.get("unavailability") or {}
                    out.append(LineupPlayer(
                        match_id=match_id, team_id=int(team_id), player_id=int(p["id"]),
                        player_name=p.get("name", ""), role=role,
                        shirt_number=p.get("shirtNumber"), position_id=p.get("positionId"),
                        usual_position_id=p.get("usualPlayingPositionId"), age=p.get("age"),
                        country=p.get("countryCode"), market_value_eur=_num(p.get("marketValue")),
                        rating=_num(perf.get("rating")), season_rating=_num(perf.get("seasonRating")),
                        is_captain=bool(p.get("isCaptain")),
                        unavailability_type=unav.get("type"),
                        expected_return=unav.get("expectedReturn"),
                    ))
            coach = team.get("coach")
            if coach:
                out.append(LineupPlayer(
                    match_id=match_id, team_id=int(team_id), player_id=int(coach["id"]),
                    player_name=coach.get("name", ""), role="coach", shirt_number=None,
                    position_id=None, usual_position_id=None, age=coach.get("age"),
                    country=coach.get("countryCode"), market_value_eur=None, rating=None,
                    season_rating=None, is_captain=False, unavailability_type=None,
                    expected_return=None,
                ))
        return out

    @staticmethod
    def _parse_events(events: dict | None) -> list[dict[str, Any]]:
        out = []
        for e in ((events or {}).get("events") or []):
            typ = e.get("type")
            if typ not in ("Goal", "Card", "Substitution", "AddedTime", "Half"):
                continue
            player = e.get("player") or {}
            out.append({
                "type": typ, "minute": e.get("time"), "minute_added": e.get("overloadTime"),
                "is_home": e.get("isHome"), "player_id": player.get("id"),
                "player_name": player.get("name"), "card": e.get("card"),
                "own_goal": bool(e.get("ownGoal")), "assist_player_id": e.get("assistPlayerId"),
                "home_score": e.get("homeScore"), "away_score": e.get("awayScore"),
                "swap": [(s.get("id"), s.get("name")) for s in (e.get("swap") or [])],
                "goal_description": e.get("goalDescription"),
            })
        return out

    @staticmethod
    def _parse_h2h(matches: list | None) -> list[dict[str, Any]]:
        out = []
        for m in matches or []:
            st = m.get("status") or {}
            if not st.get("finished"):
                continue
            score = (st.get("scoreStr") or "").replace(" ", "").split("-")
            try:
                hg, ag = int(score[0]), int(score[1])
            except (ValueError, IndexError):
                continue
            out.append({
                "utc": _dt(st.get("utcTime")), "league": (m.get("league") or {}).get("name"),
                "home_id": int(m["home"]["id"]), "away_id": int(m["away"]["id"]),
                "home_goals": hg, "away_goals": ag,
            })
        return out

    # ---- salvataggio grezzo (per debug/backfill, mai in chat) --------------------------
    def save_raw(self, name: str, data: Any) -> Path:
        path = self.raw_dir / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path


def bundle_to_dicts(bundle: MatchBundle) -> dict[str, list[dict[str, Any]]]:
    """Converte il bundle in dizionari (pronti per DuckDB/Parquet)."""
    return {
        "match_info": [asdict(bundle.info)],
        "shots": [asdict(s) for s in bundle.shots],
        "team_stats": [asdict(s) for s in bundle.team_stats],
        "player_stats": [asdict(s) for s in bundle.player_stats],
        "lineup": [asdict(p) for p in bundle.lineup],
        "events": [dict(e, match_id=bundle.info.match_id) for e in bundle.events],
        "momentum": [dict(m, match_id=bundle.info.match_id) for m in bundle.momentum],
        "h2h": [dict(m, match_id=bundle.info.match_id) for m in bundle.h2h_matches],
        "insights": [dict(i, match_id=bundle.info.match_id) for i in bundle.insights],
    }
