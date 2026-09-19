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
import re
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd

from .backoff import sospensione
from .config import DETAIL_WINDOW_DAYS, League, cups, leagues, season_start_year
from .diagnostics import MAX_DETAIL, MAX_DIGEST, detail, digest, shape_of
from .sources.espn import EspnClient
from .sources.espn import to_dicts as espn_dicts
from .sources.fotmob import Fixture, FotMobClient, bundle_to_dicts
from .sources.news import (
    ITALIAN_DIRECT_FEEDS,
    ITALIAN_SEARCH_NAMES,
    NewsClient,
    parse_direct_sports_rss,
    parse_espn_news,
)
from .sources.openmeteo import OpenMeteoClient
from .sources.understat import UnderstatClient
from .sources.understat import to_dicts as us_dicts
from .store import Store
from .teams import canonical

log = logging.getLogger(__name__)

# Orizzonte del meteo previsionale Open-Meteo (giorni futuri coperti come fallback).
WEATHER_HORIZON_DAYS = 7

# Ritenzione dell'archivio notizie, in giorni. È insieme la finestra di accettazione delle
# righe in arrivo e l'età oltre la quale le righe archiviate vengono potate (docs/26 §2 e §8).
# Il valore non è arbitrario: deve coprire le **due** finestre che leggono questa tabella —
# la card «Vita del club» guarda 7 giorni indietro dal calcio d'inizio
# (`MatchAnalysis.NEWS_WINDOW_DAYS`) e il gate `verify_site` [20] ne verifica 12
# (`notizia_in_finestra(..., giorni=12)`) — quindi 14 lascia margine su entrambe.
# Scelto dall'utente il 2026-09-18 al posto di 30. Misurato il 2026-09-18 eseguendo la potatura
# sull'archivio reale (18.705 righe · 4,89 MB · 262 B/riga): toglie 5.028 righe e ne lascia 13.677
# (3,58 MB); a regime, al ritmo degli ultimi 7 giorni (1.531 righe/giorno), 14 giorni valgono
# ~21.400 righe ≈ 5,6 MB e ~28 MB/giorno di history Git, contro le ~45.900 righe ≈ 12,0 MB e
# ~60 MB/giorno dei 30 giorni. Nessuna riga pubblicata si perde: build e verify_site sui dati
# potati danno lo stesso identico risultato (docs/26 §11.1).
NEWS_RETENTION_DAYS = 14

# Errori di fonte che degradano senza bloccare il run: la fonte primaria copre il dato.
#
# ``news direct`` (i feed RSS della stampa italiana) entra il 2026-09-19 con una misura, non
# per comodità. Il feed di Sportmediaset risponde con una pagina HTML vuota (verificato:
# ``<!doctype html><html><head></head><body></body></html>``) e su *Stato fonti* la riga
# ``news:NEWS`` era **ERRORE** a ogni run — ma l'archivio dice che i feed diretti sono un
# canale ridondante: su 16.337 notizie, Sportmediaset ne ha 205 e arrivano **tutte** da
# Google News (0 dal feed diretto, l'ultima il 19/09 alle 12:02 UTC); Sky Sport 392, tutte da
# Google News; ANSA 377, di cui 94 dal feed diretto. Un feed diretto morto quindi non toglie
# una notizia, e marcarlo ERRORE faceva due danni: la riga restava rossa per settimane (il
# 404 è dichiarato aperto dal 17/09, `docs/25` §5.2) e un guasto **vero** di Google News non
# si sarebbe più distinto da quel rosso permanente. Come per ESPN, il degrado coperto da
# un'altra fonte è AVVISO: il motivo resta pubblicato, l'allarme torna a significare qualcosa.
_WARN_NON_BLOCCANTE = ("espn standings", "espn news", "espn scoreboard", "news direct")

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
    # --- diagnostica per fonte (docs/21 §15): una fonte «OK» con 0 righe deve spiegarsi ---
    # row_counts: righe salvate nella tabella della fonte (None = non applicabile)
    # details:    frase breve in italiano coi numeri dell'imbuto, pubblicata in `stato.html`
    # digests:    firma tecnica (soli nomi di campo visti), salvata nel Parquet e nel log
    row_counts: dict[str, int | None] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)
    digests: dict[str, str] = field(default_factory=dict)
    #: chiave della riga → prefisso con cui si riconosce il suo errore in `errors` (una fonte con
    #: più fasi — ESPN classifica/scoreboard — ha una riga per fase e una sola fase può rompersi).
    error_prefix: dict[str, str] = field(default_factory=dict)

    def note(self, source: str, *, rows: int | None = None, detail_text: str = "",
             digest_text: str = "") -> None:
        """Registra la diagnostica di una fonte (troncata ai tetti di `fda.diagnostics`)."""
        if rows is not None:
            self.row_counts[source] = int(rows)
        if detail_text:
            self.details[source] = detail_text[:MAX_DETAIL]
        if digest_text:
            self.digests[source] = digest_text[:MAX_DIGEST]

    def as_status_rows(self) -> list[dict[str, Any]]:
        out = []
        for src, n in self.requests.items():
            # L'errore si cerca col prefisso della **fase** di quella riga, non con quello della
            # fonte: `startswith("espn")` avrebbe attribuito l'errore dello scoreboard alla riga
            # della classifica (e viceversa) appena una delle due andava bene e l'altra no.
            prefisso = self.error_prefix.get(src, src)
            errori = [e for e in self.errors if e.startswith(prefisso)]
            err = errori[0] if errori else None
            # Fonti il cui 403 è un degrado noto e già coperto da un'altra fonte: vengono
            # registrate come AVVISO, non come errore bloccante (ESPN standings 403 cronico,
            # coperto dalla classifica FotMob; ESPN news 403, coperto da Google News; ESPN
            # scoreboard 403 su 7/7 leghe — misurato nel run `35131980208`, docs/23 §5 — con
            # gli eventi del giorno già coperti da FotMob; `news direct`, i feed RSS della
            # stampa italiana, coperti da Google News — misura in testa a questo modulo).
            #
            # **Tutti** gli errori della fase devono essere non bloccanti, non solo il primo:
            # con `err.startswith(...)` bastava un feed diretto morto a mascherare da AVVISO
            # un guasto vero della stessa fonte capitato nello stesso run, e l'esito dipendeva
            # dall'ordine in cui le fasi avevano scritto in `errors`.
            warn = bool(errori) and all(e.startswith(_WARN_NON_BLOCCANTE) for e in errori)
            out.append({"run_at": self.run_at, "source": f"{src}:{self.league}", "requests": n,
                        "ok": err is None, "warn": warn, "error": err,
                        "rows": self.row_counts.get(src), "detail": self.details.get(src, ""),
                        "digest": self.digests.get(src, "")})
        return out


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
    future_days: int = DETAIL_WINDOW_DAYS,
    max_matches: int = 40,
    max_backfill: int = 40,
    max_refresh: int = 6,
    fotmob: FotMobClient | None = None,
    understat: UnderstatClient | None = None,
    espn: EspnClient | None = None,
    openmeteo: OpenMeteoClient | None = None,
    today: date | None = None,
) -> CollectReport:
    now = datetime.now(UTC)
    today = today or now.date()
    report = CollectReport(league=lg.key, run_at=now)
    fm = fotmob or FotMobClient()
    uc = understat or UnderstatClient()
    ec = espn or EspnClient()
    om = openmeteo            # None = passo meteo disattivato (es. test offline senza rete)
    # Contatori di partenza: `source_status` deve registrare le richieste **della fase**,
    # non il totale cumulativo del client condiviso (difetto misurato il 2026-09-15:
    # `fotmob:POR1` 129 includeva anche le richieste di NED1, `transfers:TRANSFERS` 263
    # tutte quelle delle fasi precedenti → il numero per fase non era ricostruibile).
    req0 = {"fotmob": fm.http.mark(), "understat": uc.http.mark(),
            "espn": ec.http.mark(),
            "openmeteo": om.http.mark() if om is not None else 0}

    # 1) calendario -------------------------------------------------------------------------
    fixtures = _safe("fotmob", lambda: fm.parse_fixtures(lg.fotmob_id, fm.fixtures_raw(lg.fotmob_id)), report)
    if fixtures:
        report.fixtures = store.upsert("fixtures", [asdict(f) for f in fixtures])

        # 2) dettagli partite nella finestra ----------------------------------------------
        lo = datetime.combine(today - timedelta(days=past_days), datetime.min.time(), UTC)
        hi = datetime.combine(today + timedelta(days=future_days), datetime.max.time(), UTC)
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
    def _standings() -> int:
        rows = ec.parse_standings(lg.espn_code, ec.standings_raw(lg.espn_code))
        return store.upsert("espn_standings", espn_dicts(rows))

    def _scoreboards() -> int:
        total = 0
        for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
            events, stats = ec.parse_scoreboard(lg.espn_code, ec.scoreboard_raw(lg.espn_code, d))
            total += store.upsert("espn_events", espn_dicts(events))
            store.upsert("espn_team_stats", espn_dicts(stats))
        return total

    # Backoff (docs/19 P1.9): se la classifica ESPN ha fallito negli ultimi BACKOFF_FAILS run
    # la richiesta non parte — il 403 cronico costava 7 richieste a run e 7 righe di avviso
    # identiche nella pagina *Stato fonti*.
    sospesa = sospensione(store, f"espn:{lg.key}", "espn standings")
    espn_standings_rows = 0
    espn_inizio = ec.http.mark()
    if sospesa:
        report.errors.append(f"espn standings: {sospesa}")
    else:
        espn_standings_rows = _safe("espn standings", _standings, report) or 0
    espn_dopo_standings = ec.http.mark()
    # Lo scoreboard ha la **sua** serie e la **sua** sospensione (docs/23 §5). Fino al run
    # `35131980208` (2026-09-16 18:09 UTC) era l'unica fase ESPN fuori dal backoff perché lo si
    # dichiarava «attivo, risponde»: misurato su una riga propria per la prima volta, risponde
    # **403 su 7/7 leghe** — 7 richieste a run (35 al giorno) per 0 righe, e nel repository non
    # è mai esistita una tabella `espn_events`/`espn_team_stats`. Stesso costo senza dato che
    # P1.9 aveva tolto alla classifica, stessa regola: la chiave è `espn scoreboard:<lega>`.
    sospesa_scoreboard = sospensione(store, f"espn scoreboard:{lg.key}", "espn scoreboard")
    if sospesa_scoreboard:
        report.errors.append(f"espn scoreboard: {sospesa_scoreboard}")
    else:
        report.espn_events = _safe("espn scoreboard", _scoreboards, report) or 0
    espn_fine = ec.http.mark()

    # 5) meteo previsionale Open-Meteo (fallback: riempie il vuoto FotMob sui futuri) ------
    weather_reason = "passo non attivo"

    def _weather() -> int:
        nonlocal weather_reason
        if om is None:
            weather_reason = "passo non attivo"
            return 0
        if not fixtures:
            weather_reason = "calendario non disponibile"
            return 0
        horizon = today + timedelta(days=WEATHER_HORIZON_DAYS)
        upcoming = [f for f in fixtures
                    if f.status == "scheduled" and f.utc_kickoff
                    and today <= f.utc_kickoff.date() <= horizon]
        if not upcoming:
            weather_reason = f"nessuna gara nei prossimi {WEATHER_HORIZON_DAYS} giorni"
            return 0
        mi = store.read("match_info")
        if mi.empty or not {"stadium_lat", "stadium_lon", "weather_desc"}.issubset(mi.columns):
            weather_reason = "dettagli partita non ancora raccolti"
            return 0
        coords = mi.set_index("match_id")[["stadium_lat", "stadium_lon", "weather_desc"]]
        rows = []
        # perché una gara non finisce nella tabella: conta il motivo, non solo il totale
        skipped_fotmob = skipped_coords = skipped_forecast = 0
        for f in upcoming:
            if f.match_id not in coords.index:
                skipped_coords += 1
                continue
            lat, lon, fotmob_weather = coords.loc[f.match_id]
            if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                skipped_coords += 1
                continue
            # FotMob resta la fonte primaria: se ha già il meteo non serve il fallback
            if isinstance(fotmob_weather, str) and fotmob_weather.strip():
                skipped_fotmob += 1
                continue
            fc = om.forecast(float(lat), float(lon), f.utc_kickoff)
            if not fc:
                skipped_forecast += 1
                continue
            rows.append({"match_id": f.match_id, "lat": float(lat), "lon": float(lon),
                         "hour": fc.get("hour"), "temp_c": fc.get("temp_c"),
                         "precip_prob": fc.get("precip_prob"), "code": fc.get("code"),
                         "desc": fc.get("desc"), "fetched_at": now})
        if not rows:
            weather_reason = (f"nessuna previsione utile su {len(upcoming)} gare future "
                              f"(meteo FotMob {skipped_fotmob} · coordinate {skipped_coords} · "
                              f"previsione assente {skipped_forecast})")
            return 0
        weather_reason = f"{len(rows)} gare senza meteo FotMob"
        return store.upsert("weather_forecast", rows)

    weather_rows = _safe("openmeteo forecast", _weather, report) or 0

    used = {"fotmob": fm, "understat": uc}
    if om is not None:
        used["openmeteo"] = om
    report.requests = {}
    for src, client in used.items():
        # Understat non copre NED1/POR1 (has_understat=False): una riga «OK, 0 richieste»
        # direbbe che la fonte è stata interrogata con successo, il che è falso (docs/19 §2.1).
        if src == "understat" and not lg.has_understat:
            continue
        report.requests[src] = client.http.mark() - req0[src]
    # ESPN: **due** contatori, uno per fase (docs/23 §3). Prima la riga «espn:ITA1» contava il
    # totale del client, quindi includeva le richieste dello scoreboard — che allora non era
    # governato dal backoff (oggi lo è, docs/23 §5): la riga della classifica risultava
    # «SOSPESA ma con 1 richiesta» e il verificatore non poteva più distinguere un backoff
    # attivo da un backoff che non esiste (run 35129006426).
    # La chiave della classifica resta «espn» perché è l'identità su cui cammina lo storico di
    # `backoff.state()` (`f"espn:{lg.key}"`): cambiarla azzererebbe la serie dei fallimenti.
    report.requests["espn"] = espn_dopo_standings - espn_inizio
    report.requests["espn scoreboard"] = espn_fine - espn_dopo_standings
    # alla riga «espn» (classifica) va attribuito l'errore della classifica, non quello dello
    # scoreboard: `startswith("espn")` li prende entrambi e conterebbe l'ordine di chiamata
    report.error_prefix["espn"] = "espn standings"
    report.note("fotmob", rows=report.fixtures,
                detail_text=detail(f"calendario {report.fixtures}",
                                   f"partite {report.matches_fetched}",
                                   f"backfill {report.matches_backfilled}",
                                   f"classifica di lega {report.standings}"))
    report.note("understat", rows=report.understat_rows,
                detail_text=("lega non coperta da Understat" if not lg.has_understat else
                             detail(f"righe raccolte {report.understat_rows}",
                                    "riserva: la classifica primaria è FotMob")))
    report.note("espn", rows=espn_standings_rows,
                detail_text=detail(f"classifica {espn_standings_rows}",
                                   "riserva: la classifica primaria è FotMob" if not espn_standings_rows else "",
                                   "eventi del giorno: riga a parte"))
    report.note("espn scoreboard", rows=report.espn_events,
                detail_text=detail(
                    f"eventi del giorno {report.espn_events}",
                    "fase a parte: ha il suo backoff, serie distinta dalla classifica"))
    report.note("openmeteo", rows=weather_rows, detail_text=weather_reason)
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
    now = datetime.now(UTC)
    report = CollectReport(league="CUPS", run_at=now)
    fm = fotmob or FotMobClient()
    fm0 = fm.http.mark()
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
    report.requests = {"fotmob": fm.http.mark() - fm0}
    report.note("fotmob", rows=report.fixtures,
                detail_text=detail(f"coppe {len(cups())}",
                                   f"gare di calendario {report.fixtures}"))
    store.upsert("source_status", report.as_status_rows())
    return report


def collect_news(store: Store, keys: list[str] | None = None,
                 news: NewsClient | None = None,
                 fotmob: FotMobClient | None = None,
                 espn: EspnClient | None = None,
                 window_days: int = NEWS_RETENTION_DAYS) -> CollectReport:
    """Notizie per squadra (docs/21, P1-5): Google News RSS + ESPN news di lega.

    Una o due richieste RSS per squadra della stagione (cache 12 h: i run successivi allo
    stesso giorno non ridownloadano): l'edizione italiana e, per i campionati stranieri,
    l'edizione locale — è quella che porta il materiale di vita del club che la stampa
    italiana non raccoglie (docs/24 §3.5). Più una JSON ESPN per campionato. Le righe
    vecchie oltre ``window_days`` vengono potate **dall'archivio**, non solo scartate in
    arrivo: senza quel passo il Parquet cresceva senza limite (docs/26 §2). Fonte isolata
    come le altre: se Google non è raggiungibile il run continua e ``source_status`` mostra
    l'avviso; la card degrada a segnaposto onesto.
    """
    now = datetime.now(UTC)
    report = CollectReport(league="NEWS", run_at=now)
    nc = news or NewsClient()
    ec = espn or EspnClient()
    nc0, ec0 = nc.http.mark(), ec.http.mark()
    fx = store.read("fixtures")
    if fx.empty:
        report.errors.append("news: fixtures vuote, salto")
        report.note("news", rows=0, detail_text="calendario non disponibile, raccolta saltata")
        report.note("espn", rows=0, detail_text="calendario non disponibile, raccolta saltata")
        store.upsert("source_status", report.as_status_rows())
        return report
    teams = fx.drop_duplicates("home_id")[["home_id", "home_name", "league_id"]]
    rows: list[dict[str, Any]] = []
    # imbuto delle notizie (docs/21 §15): byte letti, articoli visti, corpi non-RSS,
    # articoli senza titolo, articoli ESPN visti e attribuiti a una squadra. Le ricerche
    # sono contate dal client (una o due per squadra secondo il campionato, docs/24 §3.5)
    diag: dict[str, Any] = {}
    paesi = {int(lg.fotmob_id): lg.country for lg in leagues()}
    for tid, name, lid in teams.itertuples(index=False):
        paese = paesi.get(int(lid))          # edizione locale del campionato (docs/24 §3.5)
        items = _safe(f"news rss {name}",
                      lambda t=tid, n=name, c=paese:
                          nc.team_news(int(t), str(n), diag, country=c), report)
        if items:
            rows.extend(items)
    # ESPN news di lega: passa dal client ESPN (contabilità separata) e attribuisce ogni
    # articolo alla squadra che cita, mai a tutte
    espn_shape = ""
    # Backoff (docs/19 P1.9): le notizie ESPN sono 403 su tutte le 7 leghe da 20+ run; la
    # fonte primaria della card è Google News. Sospesa, torna a essere sondata ogni
    # BACKOFF_PROBE_RUNS run senza perdere il rientro quando ESPN riapre.
    sospesa_news = sospensione(store, "espn:NEWS", "espn news")
    if sospesa_news:
        report.errors.append(f"espn news: {sospesa_news}")
    else:
        for lg in leagues(keys):
            payload = _safe(f"espn news {lg.key}",
                            lambda c=lg.espn_code: nc.league_news_raw(c, http=ec.http), report)
            if not payload:
                continue
            if not espn_shape:
                espn_shape = shape_of(payload)   # firma: solo nomi di campo (docs/21 §15)
            ids = {}
            for r in fx[fx.league_id == lg.fotmob_id][["home_id", "home_name"]].drop_duplicates().itertuples(index=False):
                ids[canonical(str(r.home_name))] = int(r.home_id)
            rows.extend(parse_espn_news(payload, ids, diag))
    # Feed RSS diretti della stampa sportiva italiana (ANSA, Sky Sport, Sportmediaset)
    # Aggiungono rassegna di prima mano in lingua italiana (100% gratuita e verificata)
    name_map: dict[str, int] = {}
    for tid, name, _lid in teams.itertuples(index=False):
        name_map[str(name).lower()] = int(tid)
        if str(name) in ITALIAN_SEARCH_NAMES:
            for part in re.findall(r'"([^"]+)"', ITALIAN_SEARCH_NAMES[str(name)]):
                name_map[part.lower()] = int(tid)
    for source_name, feed_url in ITALIAN_DIRECT_FEEDS:
        feed_xml = _safe(f"news direct {source_name}",
                         lambda u=feed_url: nc.direct_feed_raw(u), report)
        if feed_xml:
            direct_items = parse_direct_sports_rss(feed_xml, name_map, source_name, diag)
            if direct_items:
                rows.extend(direct_items)
    cut = now - timedelta(days=window_days)
    fresh: list[dict[str, Any]] = []
    senza_data = fuori_finestra = 0
    for r in rows:
        pa = r.get("published_at")
        if pa is None:
            # la card promette una finestra di 12 giorni: senza data la promessa non è
            # verificabile → la riga non si pubblica, ma il motivo viene contato
            senza_data += 1
            continue
        ts = pd.Timestamp(pa)
        if ts.tzinfo is None:
            ts = ts.tz_localize(UTC)
        if ts >= cut:
            fresh.append(r)
        else:
            fuori_finestra += 1
    stored = store.upsert("news", fresh) if fresh else 0
    # Potatura dell'archivio. La docstring di questa funzione la promette dal 2026-09-12
    # («le righe vecchie oltre ``window_days`` vengono potate») ma il passo non era
    # implementato: ``cut`` filtrava solo le righe **in arrivo**, così ``news.parquet``
    # cresceva a ogni run senza limite. Misurato il 2026-09-17 su dati reali: 18.705 righe
    # / 4,9 MB e +1.562 righe/giorno (0,41 MB/giorno) → il limite GitHub di 100 MB per
    # singolo file arrivava in ~230 giorni, con 5 run al giorno che ne riscrivono il blob
    # nella storia del repository. ``window_days`` (vedi ``NEWS_RETENTION_DAYS``) copre le
    # due finestre che leggono la tabella — 7 giorni la card, 12 il gate — e il numero di
    # righe potate è dichiarato nell'imbuto di *Stato fonti* invece di restare invisibile.
    potate = 0
    archivio = store.read("news")
    if not archivio.empty and "published_at" in archivio.columns:
        eta = pd.to_datetime(archivio["published_at"], utc=True, errors="coerce")
        # NaT (riga senza data) non è «più vecchia di cut»: resta, non si butta un dato
        # solo perché non se ne conosce l'età
        tieni = archivio[~(eta < cut)]
        potate = int(len(archivio) - len(tieni))
        if potate:
            store.write("news", tieni)
    report.requests = {"news": nc.http.mark() - nc0,
                       "espn": ec.http.mark() - ec0}
    report.note("news", rows=stored,
                detail_text=detail(f"ricerche {diag.get('ricerche', 0)}",
                                   f"articoli {diag.get('items', 0)}",
                                   f"corpi non RSS {diag.get('parse_error', 0)}",
                                   f"in finestra {len(fresh)}", f"fuori finestra {fuori_finestra}",
                                   f"senza data {senza_data}", f"salvate {stored}",
                                   f"potate {potate}"),
                digest_text=digest(f"rss: byte {diag.get('bytes', 0)}",
                                   f"item {diag.get('items', 0)}",
                                   f"parse_error {diag.get('parse_error', 0)}",
                                   f"senza_titolo {diag.get('senza_titolo', 0)}"))
    report.note("espn", rows=int(diag.get("espn_attribuiti", 0)),
                detail_text=detail(f"articoli di lega {diag.get('espn_articoli', 0)}",
                                   f"attribuiti a una squadra {diag.get('espn_attribuiti', 0)}"),
                digest_text=digest(f"espn: {espn_shape}" if espn_shape else "",
                                   f"articoli {diag.get('espn_articoli', 0)}",
                                   f"attribuiti {diag.get('espn_attribuiti', 0)}",
                                   f"payload non JSON {diag.get('espn_payload_non_json', 0)}"))
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
    now = datetime.now(UTC)
    report = CollectReport(league="TRANSFERS", run_at=now)
    fm = fotmob or FotMobClient()
    fm0 = fm.http.mark()
    st = store.read("fotmob_standings")
    if st.empty or "team_id" not in st.columns:
        report.errors.append("transfers: classifica vuota, salto")
        report.note("transfers", rows=0, detail_text="classifica non disponibile, raccolta saltata")
        store.upsert("source_status", report.as_status_rows())
        return report
    rows: list[dict[str, Any]] = []
    n_teams = 0
    voci = 0
    rinnovi = 0
    voci_mercato = 0
    sezioni: dict[str, int] = {}
    firma = ""
    for r in st[["league_code", "team_id", "team_name"]].drop_duplicates("team_id").itertuples(index=False):
        raw = _safe(f"transfers {r.team_name}", lambda t=int(r.team_id): fm.team_raw(t), report)
        if raw is None:
            continue
        n_teams += 1
        diag: dict[str, Any] = {}
        rows.extend(FotMobClient.parse_transfers(raw, int(r.team_id), str(r.team_name),
                                                 str(r.league_code), diag))
        voci += int(diag.get("voci", 0))
        rinnovi += int(diag.get("rinnovi", 0))
        voci_mercato += int(diag.get("voci_mercato", 0))
        sez = str(diag.get("sezione", "?"))
        sezioni[sez] = sezioni.get(sez, 0) + 1
        if not firma:
            # firma dello schema del primo payload: solo nomi di campo, mai valori.
            # Da docs/21 §17 include anche i campi di `data` e della prima voce, così
            # un'eventuale nuova forma si legge dal Parquet senza aspettare i log.
            firma = digest(f"top {diag.get('top', '?')}",
                           f"sezione {sez} campi {diag.get('campi_sezione') or '—'}",
                           f"campi data {diag.get('campi_data')}" if diag.get("campi_data") else "",
                           f"campi voce {diag.get('campi_voce')}" if diag.get("campi_voce") else "")
    stored = store.upsert("transfers", rows) if rows else 0
    log.info("transfers: %d righe da %d squadre (voci viste %d; rinnovi %d; voci di mercato %d; sezioni %s)",
             stored, n_teams, voci, rinnovi, voci_mercato, sezioni)
    report.requests = {"transfers": fm.http.mark() - fm0}
    report.note("transfers", rows=stored,
                detail_text=detail(f"payload letti {n_teams}", f"voci viste {voci}",
                                   f"salvate {stored}",
                                   f"rinnovi {rinnovi}" if rinnovi else "",
                                   f"voci di mercato {voci_mercato}" if voci_mercato else "",
                                   "sezione " + ", ".join(f"{k} in {v}" for k, v in
                                                          sorted(sezioni.items(), key=lambda kv: -kv[1])[:3])
                                   if sezioni else ""),
                digest_text=firma)
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
