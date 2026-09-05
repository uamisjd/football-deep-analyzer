"""Orchestrazione della raccolta dati (il cuore del run giornaliero).

Per ogni campionato:
  1. calendario stagionale (FotMob fixtures) → tabella `fixtures`
  2. dettagli delle partite nella finestra [oggi-past_days, oggi+future_days]:
     finite → una sola volta (poi cache lunga); future → ad ogni run (formazioni/indisponibili/meteo)
  3. Understat (se coperto) → xG/xPTS/PPDA di stagione
  4. ESPN → classifica + partite del giorno (riserva e controllo incrociato)
Ogni fonte è isolata: se una fallisce, le altre continuano e l'esito finisce in `source_status`.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from .config import League, leagues, season_start_year
from .sources.espn import EspnClient, to_dicts as espn_dicts
from .sources.fotmob import FotMobClient, bundle_to_dicts
from .sources.understat import UnderstatClient, to_dicts as us_dicts
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class CollectReport:
    league: str
    run_at: datetime
    fixtures: int = 0
    matches_fetched: int = 0
    matches_skipped: int = 0
    understat_rows: int = 0
    espn_events: int = 0
    errors: list[str] = field(default_factory=list)
    requests: dict[str, int] = field(default_factory=dict)

    def as_status_rows(self) -> list[dict[str, Any]]:
        rows = []
        for src, n in self.requests.items():
            err = next((e for e in self.errors if e.startswith(src)), None)
            rows.append({"run_at": self.run_at, "source": f"{src}:{self.league}", "requests": n,
                         "ok": err is None, "error": err})
        return rows


def _safe(step: str, fn: Callable[[], Any], report: CollectReport) -> Any:
    try:
        return fn()
    except Exception as exc:  # una fonte rotta non deve fermare il run
        msg = f"{step}: {type(exc).__name__}: {exc}"
        report.errors.append(msg)
        log.error("%s\n%s", msg, traceback.format_exc(limit=3))
        return None


def collect_league(
    lg: League,
    store: Store,
    past_days: int = 3,
    future_days: int = 3,
    max_matches: int = 40,
    fotmob: FotMobClient | None = None,
    understat: UnderstatClient | None = None,
    espn: EspnClient | None = None,
    today: date | None = None,
) -> CollectReport:
    now = datetime.now(timezone.utc)
    today = today or now.date()
    report = CollectReport(league=lg.key, run_at=now)
    fm = fotmob or FotMobClient()
    uc = understat or UnderstatClient()
    ec = espn or EspnClient()

    # 1) calendario -------------------------------------------------------------------------
    fixtures = _safe("fotmob", lambda: fm.parse_fixtures(lg.fotmob_id, fm.fixtures_raw(lg.fotmob_id)), report)
    if fixtures:
        report.fixtures = store.upsert("fixtures", [asdict(f) for f in fixtures])

        # 2) dettagli partite nella finestra ----------------------------------------------
        lo = datetime.combine(today - timedelta(days=past_days), datetime.min.time(), timezone.utc)
        hi = datetime.combine(today + timedelta(days=future_days), datetime.max.time(), timezone.utc)
        window = [f for f in fixtures if f.utc_kickoff and lo <= f.utc_kickoff <= hi
                  and f.status != "cancelled"]
        already = set()
        existing = store.read("match_info")
        if not existing.empty and "status" in existing.columns:
            already = set(existing.loc[existing["status"] == "finished", "match_id"].astype(int))
        window.sort(key=lambda f: f.utc_kickoff)
        for f in window[:max_matches]:
            if f.status == "finished" and f.match_id in already:
                report.matches_skipped += 1
                continue
            raw = _safe(f"fotmob match {f.match_id}",
                        lambda f=f: fm.match_details_raw(f.match_id, finished_hint=f.status == "finished"),
                        report)
            if not raw:
                continue
            bundle = _safe(f"fotmob parse {f.match_id}", lambda raw=raw: fm.parse_match(raw), report)
            if not bundle:
                continue
            for table, rows in bundle_to_dicts(bundle).items():
                store.upsert(table, rows)
            report.matches_fetched += 1

    # 3) Understat --------------------------------------------------------------------------
    if lg.has_understat:
        def _understat() -> int:
            yr = season_start_year()
            raw = uc.league_raw(lg.understat_slug, yr)
            n = store.upsert("understat_matches", us_dicts(uc.parse_matches(lg.understat_slug, yr, raw)))
            n += store.upsert("understat_team_matches",
                              us_dicts(uc.parse_team_matches(lg.understat_slug, yr, raw)))
            n += store.upsert("understat_players", us_dicts(uc.parse_players(lg.understat_slug, yr, raw)))
            return n
        report.understat_rows = _safe("understat", _understat, report) or 0

    # 4) ESPN -------------------------------------------------------------------------------
    # Standings e scoreboard sono indipendenti: un 403 sulla classifica non deve impedire
    # di usare gli eventi giornalieri (la fonte resta comunque segnalata in source_status).
    def _standings() -> None:
        rows = ec.parse_standings(lg.espn_code, ec.standings_raw(lg.espn_code))
        store.upsert("espn_standings", espn_dicts(rows))

    def _scoreboards() -> int:
        total = 0
        for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
            events, stats = ec.parse_scoreboard(lg.espn_code, ec.scoreboard_raw(lg.espn_code, d))
            total += store.upsert("espn_events", espn_dicts(events))
            store.upsert("espn_team_stats", espn_dicts(stats))
        return total

    _safe("espn standings", _standings, report)
    report.espn_events = _safe("espn scoreboard", _scoreboards, report) or 0

    report.requests = {"fotmob": fm.http.stats.requests, "understat": uc.http.stats.requests,
                       "espn": ec.http.stats.requests}
    store.upsert("source_status", report.as_status_rows())
    return report


def collect_all(keys: list[str] | None = None, store: Store | None = None, **kw: Any) -> list[CollectReport]:
    store = store or Store()
    fm, uc, ec = FotMobClient(), UnderstatClient(), EspnClient()   # client condivisi: rate limit unico
    reports = []
    for lg in leagues(keys):
        log.info("== %s ==", lg.name)
        reports.append(collect_league(lg, store, fotmob=fm, understat=uc, espn=ec, **kw))
    return reports
