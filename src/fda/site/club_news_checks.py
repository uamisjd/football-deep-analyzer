"""Oracoli di Vita del club: periodo, contabilità e provenienza, non giudizi editoriali.

Non chiamano team_news, i suoi filtri o la sua selezione. La rilevanza resta euristica
ed è protetta da esempi positivi/negativi nei test, non autocertificata da questo audit.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

CARD = re.compile(r'<div class="card" id="notizie">.*?(?=<div class="card"|<footer)', re.DOTALL)
COUNTERS = {
    "esaminate": r"· (\d+) (?:voci esaminate|voce esaminata|titoli esaminati|titolo esaminato)",
    "pubblicate": r"· (\d+) pubblicat[oi]",
    "scartate": r"· (\d+) servizio o cronaca",
    "annunci": r"· (\d+) annunc[oi]",
    "piatti": r"· (\d+) (?:senza un fatto specifico|non sposta)",
    "altre": r"· (\d+) su un'altra squadra",
    "doppioni": r"· (\d+) già raccontat[oi] da un'altra voce",
    "lingua": r"· (\d+) in un'altra lingua",
    "bassa_reputazione": r"· (\d+) fonte a bassa reputazione",
    "oltre": r"· (\d+) oltre (?:i limiti|il limite)",
    "fuori_ambito": r"· (\d+) fuori ambito prima squadra",
    "senza_segnale": r"· (\d+) senza evento o analisi espliciti",
}


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def primary_titles(html: str) -> set[str]:
    """Titoli principali letti dal DOM, indipendenti da attributi/classi extra sui li.

    Non include riserve o letture sul tema: preserva la definizione dei marcatori Clima.
    """
    card = CARD.search(html)
    if card is None:
        return set()
    soup = BeautifulSoup(card.group(), "html.parser")
    return {item.find("a").get_text(strip=True) for item in soup.select("ul.news-list > li")
            if item.find("a") is not None}


def audit_club_life(site: Path, data: Path) -> dict[str, Any]:
    """Rilegge il significato dei numeri e le tuple della fonte; sola lettura."""
    paths = {name: data / f"{name}.parquet" for name in ("fixtures", "news")}
    if not paths["fixtures"].exists():
        return {"counts": {}, "checks": 0, "errors": [], "defects": 0}
    fixtures = pd.read_parquet(paths["fixtures"])
    news = (pd.read_parquet(paths["news"]) if paths["news"].exists() else
            pd.DataFrame(columns=["team_id", "published_at", "title", "source", "url"]))
    dates = pd.to_datetime(news.published_at, utc=True, errors="coerce")
    news = news.assign(_date=dates)
    errors = []
    counts: Counter[str] = Counter()
    checks = 0

    def error(mid: int, kind: str, message: str, team: str = "") -> None:
        errors.append({"match_id": mid, "team": team, "kind": kind, "message": message})

    directory = site / "partite" if (site / "partite").is_dir() else site
    for path in sorted(directory.glob("*.html")):
        html = path.read_text()
        if "Analisi pre-partita" not in html:
            continue
        mid = int(path.stem)
        counts["prematch_pages"] += 1
        card = CARD.search(html)
        checks += 1
        if card is None:
            error(mid, "presence", "sezione Vita del club assente")
            continue
        counts["news_pages"] += 1
        soup = BeautifulSoup(card.group(), "html.parser")
        matches = fixtures[fixtures.match_id.eq(mid)]
        if matches.empty:
            error(mid, "fixture", "calendario della scheda assente")
            continue
        fixture = matches.iloc[0]
        kickoff = pd.to_datetime(fixture.utc_kickoff, utc=True)
        lower = kickoff - pd.Timedelta(days=14)
        period = soup.select_one(".news-window")
        checks += 1
        if period is None:
            error(mid, "period", "periodo assoluto/provvisorietà non dichiarati")
            continue
        try:
            start = pd.to_datetime(period.get("data-window-start"), utc=True, errors="raise")
            end = pd.to_datetime(period.get("data-window-end"), utc=True, errors="raise")
            as_of = pd.to_datetime(period.get("data-as-of"), utc=True, errors="raise")
            if any(pd.isna(x) for x in (start, end, as_of)):
                raise ValueError("data assente")
        except (ValueError, TypeError):
            error(mid, "period", "metadati del periodo non validi")
            continue
        if start != lower or end != kickoff:
            error(mid, "period", "periodo diverso dai quattordici giorni prima della gara")
        phase = "future" if as_of < lower else "open" if as_of < kickoff else "ended"
        expected = {"future": "Settimana non ancora iniziata", "open": "Finestra ancora aperta",
                    "ended": "Finestra terminata"}[phase]
        checks += 1
        if expected not in period.get_text(" ", strip=True):
            error(mid, "coverage", "il messaggio di copertura non rispetta il periodo")
        counts[f"windows_{phase}"] += 1
        sides = soup.select(".news-team")
        checks += 1
        if len(sides) != 2:
            error(mid, "structure", "mancano le due colonne identificabili della rassegna")
            continue
        page_keys: set[str] = set()
        for side, node in zip(("home", "away"), sides, strict=True):
            team, tid = str(fixture[f"{side}_name"]), int(fixture[f"{side}_id"])
            counts["sides"] += 1
            checks += 1
            if node.get("data-team-id") != str(tid):
                error(mid, "attribution", "identità della squadra non coincide col calendario", team)
            header = node.select_one("p.imbuto")
            text = header.get_text(" ", strip=True) if header else ""
            values = {}
            for key, pattern in COUNTERS.items():
                match = re.search(pattern, text)
                values[key] = int(match.group(1)) if match else 0
            primary = node.select("ul.news-list > li")
            reserve = node.select(".news-reserve")
            related = node.select("details.news-related li")
            eligible = news[news.team_id.eq(tid) & news._date.ge(lower) & news._date.le(min(kickoff, as_of))]
            checks += 3
            if values["esaminate"] != len(eligible):
                error(mid, "examined", "voci esaminate diverse dalle righe della fonte nel periodo", team)
            if values["pubblicate"] != len(primary):
                error(mid, "published", "numero pubblicato diverso dall'elenco visibile", team)
            rejected = sum(values[k] for k in values if k not in {"esaminate", "pubblicate"})
            if values["esaminate"] != len(primary) + len(reserve) + len(related) + rejected:
                error(mid, "funnel", "imbuto non chiuso: principali + riserva + letture sul tema + escluse ≠ esaminate", team)
            counts["examined"] += values["esaminate"]
            counts["published"] += len(primary)
            counts["reserve"] += len(reserve)
            counts["related"] += len(related)
            declared_related = re.search(r"· (\d+) lettur[ae] sul tema", text)
            if (int(declared_related.group(1)) if declared_related else 0) != len(related):
                error(mid, "related", "conteggio delle letture sul tema diverso dall'elenco", team)
            counts["empty_sides"] += not (primary or reserve)
            checks += 1
            if len(primary) > 3 or len(reserve) > 2:
                error(mid, "caps", "superati i limiti di tre titoli e due riserve", team)
            topics = [v.get_text(strip=True) for item in primary for v in item.select(".topic")]
            if topics and max(Counter(topics).values()) > 2:
                error(mid, "caps", "superato il limite di due titoli per categoria", team)
            for item in primary + reserve + related:
                link, timestamp, source = item.find("a"), item.find("time"), item.select_one(".news-source")
                checks += 1
                if link is None or timestamp is None or source is None:
                    error(mid, "provenance", "titolo, fonte, data o URL mancanti", team)
                    continue
                title, url = link.get_text(strip=True), str(link.get("href", ""))
                kind = item.get("data-news-kind")
                label = item.select_one(".news-kind")
                expected_kind = {"event": "Evento segnalato", "analysis": "Analisi / dichiarazione"}.get(kind)
                checks += 1
                if expected_kind is None or label is None or label.get_text(strip=True) != expected_kind:
                    error(mid, "kind", "evento segnalato e analisi/dichiarazione non distinguibili", team)
                counts[kind or "kind_missing"] += 1
                stamp = pd.to_datetime(timestamp.get("datetime"), utc=True, errors="coerce")
                checks += 2
                if pd.isna(stamp) or not lower <= stamp <= min(kickoff, as_of):
                    error(mid, "date", "titolo fuori dal periodo o datato nel futuro", team)
                records = eligible[eligible.title.eq(title) & eligible.url.eq(url)
                                   & eligible.source.eq(source.get_text(strip=True)) & eligible._date.eq(stamp)]
                if records.empty:
                    error(mid, "provenance", "tupla titolo/URL/fonte/data non presente nei dati della squadra", team)
                if not url.startswith(("https://", "http://")):
                    error(mid, "url", "link non HTTP(S)", team)
                key = _key(title)
                if key in page_keys:
                    error(mid, "duplicate", "titolo ripetuto tra le due squadre o fra pubblicate e riserve", team)
                page_keys.add(key)
            if "Niente che possa spostare qualcosa" in node.get_text(" ", strip=True):
                error(mid, "claim", "un vuoto di selezione viene dichiarato assenza di fatti importanti", team)
    return {"counts": {k: int(v) for k, v in counts.items()}, "checks": checks,
            "errors": errors, "defects": len(errors)}
