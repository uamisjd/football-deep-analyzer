"""Fonti notizie gratuite per la card «Ultime dalle società» (docs/21, P1-5).

Due feed pubblici, già verificati nel catalogo fonti (`docs/02`):

- **Google News RSS** per squadra (``hl=it&gl=IT``): titoli, link, testata e data in
  italiano; consentito l'uso personale non commerciale, che è il perimetro del progetto;
- **ESPN news** per campionato (JSON pubblico), come riserva e controllo incrociato.

Nessuna chiave a pagamento, nessuna pagina protetta: solo feed pubblici, con rate limit e
cache come le altre fonti (`http.HttpClient`). I testi vengono pubblicati **come raccolti**
(titolo + brano breve + testata + data + link): il portale non riscrive le notizie, le
seleziona e le attribuisce. La selezione per squadra vive in `site/analysis.team_news`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import quote

from ..config import load_sources_config
from ..http import HttpClient

GOOGLE_RSS = "https://news.google.com/rss/search"
ESPN_NEWS = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/news"

# Parole chiave di contesto «interno» usate per ordinare le notizie di una squadra:
# una notizia che le cita vale più di una cronaca generica (docs/21: niente contenuti
# uguali per tutte le squadre).
KEYWORDS = ("esonero", "esonerato", "dimissioni", "crisi", "infermeria", "infortunio",
            "vigilia", "convocati", "conferenza", "panchina", "mercato", "acquisto",
            "cessione", "squalifica", "deferimento", "penalizzazione", "presidente",
            "proprietà", "contestazione", "ritiro")


def clean_text(value: str | None, limit: int = 240) -> str:
    """Da markup/rss a testo piano: niente tag, entità risolte, spazi collassati."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def parse_rss(xml_text: str | bytes, team_id: int) -> list[dict[str, Any]]:
    """Parse di un feed RSS di Google News in righe pronte per la tabella ``news``.

    Il titolo di Google News è «Titolo - Testata»: la testata viene separata e tenuta in
    ``source`` (è l'attribuzione che la card mostra). Date RFC-822 → UTC; date illeggibili
    → ``None`` (la riga resta ma la card ordina per rilevanza, mai per data inventata).
    """
    if isinstance(xml_text, bytes):
        xml_text = xml_text.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = clean_text(item.findtext("title"), 200)
        if not title:
            continue
        source = "Google News"
        head, sep, tail = title.rpartition(" - ")
        if sep and 0 < len(tail) <= 40 and head:
            title, source = head, tail.strip()
        pub = item.findtext("pubDate") or ""
        try:
            dt = parsedate_to_datetime(pub).astimezone(UTC)
        except (TypeError, ValueError):
            dt = None
        out.append({
            "team_id": int(team_id),
            "published_at": dt,
            "title": title,
            "url": (item.findtext("link") or "").strip(),
            "source": source,
            "description": clean_text(item.findtext("description")),
        })
    return out


def parse_espn_news(payload: Any, team_ids: dict[str, int]) -> list[dict[str, Any]]:
    """Parse del JSON notizie ESPN: gli articoli citano una squadra nel header/description.

    ``team_ids`` mappa nome canonical → id: l'articolo viene attribuito alla squadra che
    cita, mai a tutte (una notizia generica di lega senza squadra riconoscibile si scarta).
    """
    if not isinstance(payload, dict):
        return []
    out: list[dict[str, Any]] = []
    for art in payload.get("articles", []) or []:
        head = clean_text(art.get("headline"), 200)
        desc = clean_text(art.get("description"), 240)
        blob = f"{head} {desc}".lower()
        for name, tid in team_ids.items():
            if name and name.lower() in blob:
                pub = art.get("published") or art.get("lastModified")
                try:
                    from datetime import datetime as _dt
                    dt = _dt.fromisoformat(str(pub))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                except (TypeError, ValueError):
                    dt = None
                out.append({"team_id": int(tid), "published_at": dt, "title": head,
                            "url": (art.get("links", {}).get("web", {}).get("href")
                                    if isinstance(art.get("links"), dict) else "") or "",
                            "source": "ESPN", "description": desc})
                break
    return out


class NewsClient:
    """Client delle fonti notizie (cache 12 h per squadra, rate limit da sources.yaml)."""

    def __init__(self, client: HttpClient | None = None, ttl_h: float | None = None) -> None:
        cfg = load_sources_config().get("news", {}) or {}
        self.http = client or HttpClient(
            name="news",
            rate_limit_s=float(cfg.get("rate_limit_s", 1.0)),
            max_requests=cfg.get("max_requests_per_run"))
        self.ttl_h = ttl_h if ttl_h is not None else float(cfg.get("cache_ttl_h", 12.0))

    def team_rss_raw(self, team_name: str) -> bytes:
        q = quote(f'"{team_name}" calcio')
        return self.http.get_bytes(
            GOOGLE_RSS, params={"q": q, "hl": "it", "gl": "IT", "ceid": "IT:it"},
            ttl_h=self.ttl_h)

    def team_news(self, team_id: int, team_name: str) -> list[dict[str, Any]]:
        raw = self.team_rss_raw(team_name)
        return parse_rss(raw, team_id)

    def league_news_raw(self, espn_code: str) -> Any:
        import json
        raw = self.http.get_bytes(ESPN_NEWS.format(code=espn_code), ttl_h=self.ttl_h)
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None


def keyword_score(text: str) -> int:
    """Quante parole chiave di contesto «interno» cita un testo (per l'ordinamento)."""
    low = text.lower()
    return sum(1 for k in KEYWORDS if k in low)
