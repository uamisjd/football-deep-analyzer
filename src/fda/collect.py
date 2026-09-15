"""Orchestrazione della raccolta dati (il cuore del run giornaliero).

Per ogni campionato:
  1. calendario stagionale (FotMob fixtures) → tabella `fixtures`
  2. dettagli delle partite nella finestra [oggi-past_days, oggi+future_days]:
     finite → una sola volta (poi cache lunga); future → ad ogni run (formazioni/indisponibili/meteo)
     2b. solo per le leghe senza Understat: backfill dei dettagli di tutte le finite di
     stagione (ognuna una sola volta) → xG di stagione FotMob completo
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

import pandas as pd

from .config import League, cups, leagues, season_start_year
from .sources.espn import EspnClient, to_dicts as espn_dicts
from .sources.fotmob import Fixture, FotMobClient, bundle_to_dicts
from .sources.news import NewsClient, parse_espn_news
from .sources.openmeteo import OpenMeteoClient
from .sources.understat import UnderstatClient, to_dicts as us_dicts
from .store import Store
from .teams import canonical

log = logging.getLogger(__name__)

# Orizzonte del meteo previsionale Open-Meteo (giorni futuri coperti come fallback).
WEATHER_HORIZON_DAYS = 7

# Versione dello snapshot per-partita. Va incrementata quando cambia il modo in cui le
# tabelle per-partita vengono salvate: le partite finite salvate con una versione più
# vecchia vengono riscaricate una volta (poche per run, vedi `max_refresh`).
#   2 (2026-09-12): tabelle per-partita salvate come snapshot completi (replace_by match_id),
#                   chiave `lineup` senza ruolo → formazioni e sostituzioni complete.
COLLECT_SNAPSHOT = 2


@dataclass
class CollectReport:
    league: str
    run_at: datetime
    fixtures: int = 0
    matches_fetched: int = 0
    matches_skipped: int = 0
    matches_backfilled: int = 0
    matches_refreshed: int = 0
    standings: int = 0
    understat_rows: int = 0
    espn_events: int = 0
    errors: list[str] = field(default_factory=list)
    requests: dict[str, int] = field(default_factory=dict)

    def as_status_rows(self) -> list[dict[str, Any]]:
        rows = []
        for src, n in self.requests.items():
            err = next((e for e in self.errors if e.startswith(src)), None)
            # ESPN standings risponde 403 cronico: è coperto dalla classifica FotMob (fonte
            # primaria), quindi viene registrato come AVVISO e non come errore bloccante.
            warn = err is not None and err.startswith("espn standings")
            rows.append({"run_at": self.run_at, "source": f"{src}:{self.league}", "requests": n,
                         "ok": err is None, "warn": warn, "error": err})
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
    max_backfill: int = 40,
    max_refresh: int = 6,
    fotmob: FotMobClient | None = None,
    understat: UnderstatClient | None = None,
    espn: EspnClient | None = None,
    openmeteo: OpenMeteoClient | None = None,
    today: date | None = None,
) -> CollectReport:
    now = datetime.now(timezone.utc)
    today = today or now.date()
    report = CollectReport(league=lg.key, run_at=now)
    fm = fotmob or FotMobClient()
    uc = understat or UnderstatClient()
    ec = espn or EspnClient()
    om = openmeteo            # None = passo meteo disattivato (es. test offline senza rete)

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
            done = existing["status"] == "finished"
            if "snapshot_version" in existing.columns:
                ver = pd.to_numeric(existing["snapshot_version"], errors="coerce").fillna(0)
                done = done & (ver >= COLLECT_SNAPSHOT)
            already = set(existing.loc[done, "match_id"].astype(int))
        def _fetch(f: Fixture) -> bool:
            """Scarica e salva i dettagli di una partita. Ritorna True se salvata."""
            raw = _safe(f"fotmob match {f.match_id}",
                        lambda: fm.match_details_raw(f.match_id, finished_hint=f.status == "finished"),
                        report)
            if not raw:
                return False
            bundle = _safe(f"fotmob parse {f.match_id}", lambda: fm.parse_match(raw), report)
            if not bundle:
                return False

            def _save() -> bool:
                for table, rows in bundle_to_dicts(bundle).items():
                    if table == "match_info":
                        # marca lo snapshot: le partite finite salvate con una versione
                        # precedente vengono riscaricate una volta (vedi `already`)
                        rows = [{**r, "snapshot_version": COLLECT_SNAPSHOT} for r in rows]
                    # tabelle per-partita = snapshot completi: sostituzione, non fusione
                    store.upsert(table, rows, replace_by="match_id")
                return True

            # anche il salvataggio è isolato: una partita con righe anomale non deve
            # uccidere il run (regressione: run daily 2026-09-08 14:31 UTC morto su NED1)
            return _safe(f"fotmob save {f.match_id}", _save, report) is not None

        window.sort(key=lambda f: f.utc_kickoff)
        for f in window[:max_matches]:
            if f.status == "finished" and f.match_id in already:
                report.matches_skipped += 1
                continue
            if _fetch(f):
                report.matches_fetched += 1

        # 2b) backfill finite di stagione (TUTTE le leghe: parità 7/7 per le schede    --
        # giocatore, fase 3 — docs/07). Ogni finita si scarica una sola volta (poi è in
        # `already`); le più recenti prima.
        past = [f for f in fixtures
                if f.status == "finished" and f.utc_kickoff and f.utc_kickoff < lo]
        past.sort(key=lambda f: f.utc_kickoff, reverse=True)
        old = [f for f in past if f.match_id not in already]        # mai scaricate
        stale = [f for f in past if f.match_id in already]          # snapshot da rinfrescare
        for f in old[:max_backfill]:
            if _fetch(f):
                report.matches_backfilled += 1
        # Rinfresco delle partite finite salvate prima dello snapshot corrente: recupera
        # formazioni e sostituzioni complete. Tetto piccolo e separato dal backfill per
        # restare dentro il budget FotMob (600 richieste/run, ~500 già usate).
        for f in stale[:max_refresh]:
            if _fetch(f):
                report.matches_refreshed += 1

    # 2c) tabella di lega (FotMob `leagues`: fonte primaria delle classifiche) ----------------
    def _table() -> int:
        rows = fm.parse_league_table(lg.key, fm.league_raw(lg.fotmob_id))
        if not rows:
            raise ValueError("tabella vuota o formato inatteso")
        return store.upsert("fotmob_standings", [asdict(r) for r in rows])

    report.standings = _safe("fotmob standings", _table, report) or 0

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

    # 5) meteo previsionale Open-Meteo (fallback: riempie il vuoto FotMob sui futuri) ------
    def _weather() -> int:
        if om is None or not fixtures:
            return 0
        horizon = today + timedelta(days=WEATHER_HORIZON_DAYS)
        upcoming = [f for f in fixtures
                    if f.status == "scheduled" and f.utc_kickoff
                    and today <= f.utc_kickoff.date() <= horizon]
        if not upcoming:
            return 0
        mi = store.read("match_info")
        if mi.empty or not {"stadium_lat", "stadium_lon", "weather_desc"}.issubset(mi.columns):
            return 0
        coords = mi.set_index("match_id")[["stadium_lat", "stadium_lon", "weather_desc"]]
        rows = []
        for f in upcoming:
            if f.match_id not in coords.index:
                continue
            lat, lon, fotmob_weather = coords.loc[f.match_id]
            if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                continue
            # FotMob resta la fonte primaria: se ha già il meteo non serve il fallback
            if isinstance(fotmob_weather, str) and fotmob_weather.strip():
                continue
            fc = om.forecast(float(lat), float(lon), f.utc_kickoff)
            if not fc:
                continue
            rows.append({"match_id": f.match_id, "lat": float(lat), "lon": float(lon),
                         "hour": fc.get("hour"), "temp_c": fc.get("temp_c"),
                         "precip_prob": fc.get("precip_prob"), "code": fc.get("code"),
                         "desc": fc.get("desc"), "fetched_at": now})
        return store.upsert("weather_forecast", rows) if rows else 0

    _safe("openmeteo forecast", _weather, report)

    report.requests = {"fotmob": fm.http.stats.requests, "understat": uc.http.stats.requests,
                       "espn": ec.http.stats.requests}
    if om is not None:
        report.requests["openmeteo"] = om.http.stats.requests
    store.upsert("source_status", report.as_status_rows())
    return report


def collect_cups(store: Store, fotmob: FotMobClient | None = None) -> CollectReport:
    """Calendario delle coppe europee (docs/21, P1-4): una richiesta per coppa per run.

    Perché esiste: ``rest_days`` contava solo le gare di campionato, quindi una squadra
    in campo il martedì di Champions mostrava «6 giorni di riposo» nella scheda del
    sabato. Con il calendario coppe in ``cup_fixtures`` il riposo e la congestione sono
    quelli veri. Le coppe restano fuori da modelli e schede proprie (perimetro deciso):
    qui si raccoglie solo il calendario.
    """
    now = datetime.now(timezone.utc)
    report = CollectReport(league="CUPS", run_at=now)
    fm = fotmob or FotMobClient()
    rows: list[dict[str, Any]] = []
    for cp in cups():
        fx = _safe(f"fotmob cups {cp.key}",
                   lambda c=cp: fm.parse_fixtures(c.fotmob_id, fm.fixtures_raw(c.fotmob_id)),
                   report)
        if not fx:
            continue
        for f in fx:
            if f.status == "cancelled":
                continue
            d = asdict(f)
            d["league_key"] = cp.key
            d["cup_name"] = cp.name
            rows.append(d)
    if rows:
        store.upsert("cup_fixtures", rows)
        report.fixtures = len(rows)
    report.requests = {"fotmob": fm.http.stats.requests}
    store.upsert("source_status", report.as_status_rows())
    return report


def collect_news(store: Store, keys: list[str] | None = None,
                 news: NewsClient | None = None,
                 fotmob: FotMobClient | None = None,
                 espn: EspnClient | None = None,
                 window_days: int = 30) -> CollectReport:
    """Notizie per squadra (docs/21, P1-5): Google News RSS + ESPN news di lega.

    Una richiesta RSS per squadra della stagione (cache 12 h: i run successivi allo
    stesso giorno non ridownloadano) + una JSON ESPN per campionato. Le righe vecchie
    oltre ``window_days`` vengono potate: la card legge 12 giorni, il resto è peso morto
    nel Parquet. Fonte isolata come le altre: se Google non è raggiungibile il run
    continua e ``source_status`` mostra l'avviso; la card degrada a segnaposto onesto.
    """
    now = datetime.now(timezone.utc)
    report = CollectReport(league="NEWS", run_at=now)
    nc = news or NewsClient()
    fx = store.read("fixtures")
    if fx.empty:
        report.errors.append("news: fixtures vuote, salto")
        store.upsert("source_status", report.as_status_rows())
        return report
    teams = fx.drop_duplicates("home_id")[["home_id", "home_name"]]
    rows: list[dict[str, Any]] = []
    for tid, name in teams.itertuples(index=False):
        items = _safe(f"news rss {name}", lambda t=tid, n=name: nc.team_news(int(t), str(n)), report)
        if items:
            rows.extend(items)
    # ESPN news di lega: attribuisce ogni articolo alla squadra che cita (mai a tutte)
    ec = espn or EspnClient()
    for lg in leagues(keys):
        payload = _safe(f"espn news {lg.key}", lambda c=lg.espn_code: nc.league_news_raw(c), report)
        if not payload:
            continue
        ids = {}
        for r in fx[fx.league_id == lg.fotmob_id][["home_id", "home_name"]].drop_duplicates().itertuples(index=False):
            ids[canonical(str(r.home_name))] = int(r.home_id)
        rows.extend(parse_espn_news(payload, ids))
    cut = now - timedelta(days=window_days)
    fresh = []
    for r in rows:
        pa = r.get("published_at")
        if pa is None:
            continue
        ts = pd.Timestamp(pa)
        if ts.tzinfo is None:
            ts = ts.tz_localize(timezone.utc)
        if ts >= cut:
            fresh.append(r)
    if fresh:
        store.upsert("news", fresh)
    report.requests = {"news": nc.http.stats.requests, "espn": ec.http.stats.requests}
    store.upsert("source_status", report.as_status_rows())
    return report


def collect_transfers(store: Store, fotmob: FotMobClient | None = None) -> CollectReport:
    """Trasferimenti per squadra dall'endpoint FotMob `teams` (docs/21, P2-7).

    Una richiesta per squadra della classifica (cache 24 h: la finestra si muove piano,
    e la stessa squadra ricompare in più run senza riscaricare). Fonte isolata come le
    altre: se `teams` non è raggiungibile il run continua e ``source_status`` mostra
    l'avviso; la card «Mercato» degrada ad assenza (segnaposto onesto). Lo schema della
    sezione `transfers` non è documentato: se le righe raccolte sono zero il conteggio
    nel log di Actions lo rende visibile al primo run (mai dati inventati).
    """
    now = datetime.now(timezone.utc)
    report = CollectReport(league="TRANSFERS", run_at=now)
    fm = fotmob or FotMobClient()
    st = store.read("fotmob_standings")
    if st.empty or "team_id" not in st.columns:
        report.errors.append("transfers: classifica vuota, salto")
        store.upsert("source_status", report.as_status_rows())
        return report
    rows: list[dict[str, Any]] = []
    n_teams = 0
    for r in st[["league_code", "team_id", "team_name"]].drop_duplicates("team_id").itertuples(index=False):
        raw = _safe(f"transfers {r.team_name}", lambda t=int(r.team_id): fm.team_raw(t), report)
        if raw is None:
            continue
        n_teams += 1
        rows.extend(FotMobClient.parse_transfers(raw, int(r.team_id), str(r.team_name), str(r.league_code)))
    if rows:
        store.upsert("transfers", rows)
    # i conteggi restano nel log di run (salvato come artifact da Actions): la tabella
    # CLI ha colonne calendario/partite che qui non c'entrano, e source_status — come
    # per le notizie — registra richieste ed esito, non volumi.
    log.info("transfers: %d righe da %d squadre", len(rows), n_teams)
    report.requests = {"transfers": fm.http.stats.requests}
    store.upsert("source_status", report.as_status_rows())
    return report


def collect_all(keys: list[str] | None = None, store: Store | None = None,
                with_cups: bool = True, with_news: bool = True,
                with_transfers: bool = True,
                **kw: Any) -> list[CollectReport]:
    store = store or Store()
    fm, uc, ec, om = FotMobClient(), UnderstatClient(), EspnClient(), OpenMeteoClient()
    reports = []
    for lg in leagues(keys):
        log.info("== %s ==", lg.name)
        reports.append(collect_league(lg, store, fotmob=fm, understat=uc, espn=ec, openmeteo=om, **kw))
    if with_cups:
        log.info("== coppe (calendario) ==")
        reports.append(collect_cups(store, fotmob=fm))
    if with_news:
        log.info("== notizie squadre ==")
        reports.append(collect_news(store, keys=keys, news=NewsClient(), fotmob=fm, espn=ec))
    if with_transfers:
        log.info("== mercato (trasferimenti) ==")
        reports.append(collect_transfers(store, fotmob=fm))
    return reports
