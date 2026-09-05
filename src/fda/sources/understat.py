"""Client Understat (xG, xGA, xPTS, PPDA, deep completions) — 5 grandi leghe dal 2014.

Da dicembre 2025 Understat serve i dati via endpoint JSON che richiedono:
  1) i cookie della homepage (una GET iniziale a https://understat.com),
  2) l'header `X-Requested-With: XMLHttpRequest`.
Questa è la stessa logica di soccerdata (`understat.py`), riscritta qui per evitare la
dipendenza da seleniumbase. Endpoint: /getLeagueData/{slug}/{season}.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from ..config import source
from ..http import HttpClient, SourceError

log = logging.getLogger(__name__)

XHR_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"}


def _f(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    try:
        return None if v is None else int(float(v))
    except (TypeError, ValueError):
        return None


@dataclass
class UnderstatMatch:
    """Una partita con xG di entrambe le squadre (da `dates`)."""

    understat_id: int
    league_slug: str
    season: int
    utc_kickoff: datetime | None
    home_id: int
    home_name: str
    away_id: int
    away_name: str
    home_goals: int | None
    away_goals: int | None
    home_xg: float | None
    away_xg: float | None
    is_result: bool
    forecast_w: float | None      # probabilità Understat (solo pre-partita)
    forecast_d: float | None
    forecast_l: float | None
    source: str = "understat"


@dataclass
class UnderstatTeamMatch:
    """Riga squadra-partita (da `teams[].history`): la base per xPTS, PPDA, deep."""

    league_slug: str
    season: int
    team_id: int
    team_name: str
    date: datetime | None
    is_home: bool
    goals: int | None
    goals_against: int | None
    xg: float | None
    xga: float | None
    npxg: float | None
    npxga: float | None
    npxgd: float | None
    xpts: float | None
    pts: int | None
    ppda: float | None            # att/def: più basso = pressing più intenso
    ppda_allowed: float | None
    deep: int | None
    deep_allowed: int | None
    result: str | None            # w | d | l


@dataclass
class UnderstatPlayerSeason:
    league_slug: str
    season: int
    player_id: int
    player_name: str
    team_name: str
    position: str | None
    matches: int | None
    minutes: int | None
    goals: int | None
    np_goals: int | None
    assists: int | None
    shots: int | None
    key_passes: int | None
    xg: float | None
    np_xg: float | None
    xa: float | None
    xg_chain: float | None
    xg_buildup: float | None
    yellow_cards: int | None
    red_cards: int | None


class UnderstatClient:
    def __init__(self, client: HttpClient | None = None) -> None:
        cfg = source("understat")
        self.base_url: str = cfg["base_url"].rstrip("/")
        self.ttl_h = float((cfg.get("cache_ttl_h") or {}).get("league", 12))
        self.http = client or HttpClient(name="understat",
                                         rate_limit_s=float(cfg.get("rate_limit_s", 2.0)))
        self._cookies_ready = False

    def _ensure_cookies(self) -> None:
        if not self._cookies_ready:
            # Nessuna cache: serve la risposta viva per ottenere i cookie di sessione.
            self.http.get_bytes(self.base_url + "/")
            self._cookies_ready = True

    def league_raw(self, slug: str, season: int) -> dict:
        url = f"{self.base_url}/getLeagueData/{slug}/{season}"
        # Prima prova dalla cache (niente cookie necessari); se manca, prendi i cookie e scarica.
        cached = self.http._read_cache(self.http._cache_path(url, None), self.ttl_h)
        if cached is None:
            self._ensure_cookies()
        data = self.http.get_json(url, ttl_h=self.ttl_h, extra_headers=XHR_HEADERS)
        if not isinstance(data, dict) or "teams" not in data:
            raise SourceError(f"[understat] formato inatteso per {slug}/{season}")
        return data

    # ---- parser ---------------------------------------------------------------------------
    @staticmethod
    def _dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            # Understat usa orari UTC nel formato 'YYYY-MM-DD HH:MM:SS'
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def parse_matches(self, slug: str, season: int, raw: dict) -> list[UnderstatMatch]:
        out: list[UnderstatMatch] = []
        for m in raw.get("dates") or []:
            h, a = m.get("h") or {}, m.get("a") or {}
            goals, xg, fc = m.get("goals") or {}, m.get("xG") or {}, m.get("forecast") or {}
            is_result = bool(m.get("isResult"))
            out.append(UnderstatMatch(
                understat_id=int(m["id"]), league_slug=slug, season=season,
                utc_kickoff=self._dt(m.get("datetime")),
                home_id=int(h["id"]), home_name=h.get("title", ""),
                away_id=int(a["id"]), away_name=a.get("title", ""),
                home_goals=_i(goals.get("h")) if is_result else None,
                away_goals=_i(goals.get("a")) if is_result else None,
                home_xg=_f(xg.get("h")) if is_result else None,
                away_xg=_f(xg.get("a")) if is_result else None,
                is_result=is_result,
                forecast_w=_f(fc.get("w")), forecast_d=_f(fc.get("d")), forecast_l=_f(fc.get("l")),
            ))
        return out

    def parse_team_matches(self, slug: str, season: int, raw: dict) -> list[UnderstatTeamMatch]:
        out: list[UnderstatTeamMatch] = []
        for team in (raw.get("teams") or {}).values():
            tid, tname = int(team["id"]), team.get("title", "")
            for h in team.get("history") or []:
                ppda, ppda_al = h.get("ppda") or {}, h.get("ppda_allowed") or {}
                out.append(UnderstatTeamMatch(
                    league_slug=slug, season=season, team_id=tid, team_name=tname,
                    date=self._dt(h.get("date")), is_home=h.get("h_a") == "h",
                    goals=_i(h.get("scored")), goals_against=_i(h.get("missed")),
                    xg=_f(h.get("xG")), xga=_f(h.get("xGA")),
                    npxg=_f(h.get("npxG")), npxga=_f(h.get("npxGA")), npxgd=_f(h.get("npxGD")),
                    xpts=_f(h.get("xpts")), pts=_i(h.get("pts")),
                    ppda=(_f(ppda.get("att")) / _f(ppda.get("def"))) if _f(ppda.get("def")) else None,
                    ppda_allowed=(_f(ppda_al.get("att")) / _f(ppda_al.get("def")))
                    if _f(ppda_al.get("def")) else None,
                    deep=_i(h.get("deep")), deep_allowed=_i(h.get("deep_allowed")),
                    result=h.get("result"),
                ))
        return out

    def parse_players(self, slug: str, season: int, raw: dict) -> list[UnderstatPlayerSeason]:
        out: list[UnderstatPlayerSeason] = []
        for p in raw.get("players") or []:
            out.append(UnderstatPlayerSeason(
                league_slug=slug, season=season, player_id=int(p["id"]),
                player_name=p.get("player_name", ""), team_name=p.get("team_title", ""),
                position=p.get("position"), matches=_i(p.get("games")), minutes=_i(p.get("time")),
                goals=_i(p.get("goals")), np_goals=_i(p.get("npg")), assists=_i(p.get("assists")),
                shots=_i(p.get("shots")), key_passes=_i(p.get("key_passes")),
                xg=_f(p.get("xG")), np_xg=_f(p.get("npxG")), xa=_f(p.get("xA")),
                xg_chain=_f(p.get("xGChain")), xg_buildup=_f(p.get("xGBuildup")),
                yellow_cards=_i(p.get("yellow_cards")), red_cards=_i(p.get("red_cards")),
            ))
        return out


def team_season_table(team_matches: list[UnderstatTeamMatch]) -> list[dict[str, Any]]:
    """Aggrega le righe squadra-partita in una tabella di stagione (xG, xGA, xPTS vs punti...)."""
    agg: dict[int, dict[str, Any]] = {}
    for r in team_matches:
        t = agg.setdefault(r.team_id, {
            "team_id": r.team_id, "team_name": r.team_name, "league_slug": r.league_slug,
            "season": r.season, "played": 0, "pts": 0, "xpts": 0.0, "goals": 0, "goals_against": 0,
            "xg": 0.0, "xga": 0.0, "npxg": 0.0, "npxga": 0.0, "deep": 0, "deep_allowed": 0,
            "_ppda": [], "_ppda_allowed": [],
        })
        t["played"] += 1
        t["pts"] += r.pts or 0
        t["xpts"] += r.xpts or 0.0
        t["goals"] += r.goals or 0
        t["goals_against"] += r.goals_against or 0
        t["xg"] += r.xg or 0.0
        t["xga"] += r.xga or 0.0
        t["npxg"] += r.npxg or 0.0
        t["npxga"] += r.npxga or 0.0
        t["deep"] += r.deep or 0
        t["deep_allowed"] += r.deep_allowed or 0
        if r.ppda is not None:
            t["_ppda"].append(r.ppda)
        if r.ppda_allowed is not None:
            t["_ppda_allowed"].append(r.ppda_allowed)
    rows = []
    for t in agg.values():
        p = max(t["played"], 1)
        rows.append({
            **{k: v for k, v in t.items() if not k.startswith("_")},
            "xg_per_match": round(t["xg"] / p, 3), "xga_per_match": round(t["xga"] / p, 3),
            "xgd": round(t["xg"] - t["xga"], 3), "npxgd": round(t["npxg"] - t["npxga"], 3),
            "pts_minus_xpts": round(t["pts"] - t["xpts"], 2),
            "ppda": round(sum(t["_ppda"]) / len(t["_ppda"]), 2) if t["_ppda"] else None,
            "ppda_allowed": round(sum(t["_ppda_allowed"]) / len(t["_ppda_allowed"]), 2)
            if t["_ppda_allowed"] else None,
        })
    rows.sort(key=lambda r: (-r["pts"], -r["xgd"]))
    return rows


def to_dicts(rows: list) -> list[dict[str, Any]]:
    return [asdict(r) for r in rows]
