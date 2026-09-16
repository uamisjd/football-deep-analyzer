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

from ..config import load_sources_config
from ..diagnostics import bump
from ..http import HttpClient

GOOGLE_RSS = "https://news.google.com/rss/search"
ESPN_NEWS = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/news"

# L'header di default del client è `application/json`: su un endpoint RSS è un invito a
# ricevere la pagina sbagliata (avviso, consenso, HTML). Qui si dichiara cosa si vuole.
RSS_ACCEPT = "application/rss+xml, application/xml;q=0.9, */*;q=0.8"


def google_news_params(team_name: str) -> dict[str, str]:
    """Parametri della ricerca RSS per squadra (**non** pre-codificati).

    Difetto misurato il 2026-09-15 (docs/21 §15): la query veniva codificata con
    ``quote()`` e poi passata a ``requests`` in ``params``, che la codificava di nuovo →
    ``q=%2522Ajax%2522%2520calcio``: Google cercava il testo letterale ``%22Ajax%22
    calcio`` e rispondeva un feed **valido con 0 articoli**, senza errore. Da qui il
    sintomo «139 richieste, ok=True, zero righe». La codifica la fa il client HTTP, una
    volta sola.
    """
    return {"q": f'"{team_name}" calcio', "hl": "it", "gl": "IT", "ceid": "IT:it"}


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


def parse_rss(xml_text: str | bytes, team_id: int,
              diag: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Parse di un feed RSS di Google News in righe pronte per la tabella ``news``.

    Il titolo di Google News è «Titolo - Testata»: la testata viene separata e tenuta in
    ``source`` (è l'attribuzione che la card mostra). Date RFC-822 → UTC; una data
    illeggibile resta ``None`` e viene contata dall'imbuto del collettore, che scarta la
    riga (la card promette una finestra di 12 giorni: senza data la promessa non è
    verificabile, quindi non si pubblica).

    ``diag`` è l'imbuto di ``fda.diagnostics``: somma byte letti, articoli visti e corpi
    non-RSS incontrati. Un feed vuoto e una pagina HTML danno **entrambi** zero righe ma
    non sono la stessa cosa, e prima del 2026-09-15 erano indistinguibili (docs/21 §15).
    """
    if isinstance(xml_text, bytes):
        xml_text = xml_text.decode("utf-8", errors="replace")
    bump(diag, "bytes", len(xml_text))
    bump(diag, "items", 0)          # «item 0» è una diagnosi, non un'assenza di dato
    bump(diag, "parse_error", 0)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        bump(diag, "parse_error")
        return []
    out: list[dict[str, Any]] = []
    for item in root.iter("item"):
        bump(diag, "items")
        title = clean_text(item.findtext("title"), 200)
        if not title:
            bump(diag, "senza_titolo")
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


def parse_espn_news(payload: Any, team_ids: dict[str, int],
                    diag: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Parse del JSON notizie ESPN: gli articoli citano una squadra nel header/description.

    ``team_ids`` mappa nome canonical → id: l'articolo viene attribuito alla squadra che
    cita, mai a tutte (una notizia generica di lega senza squadra riconoscibile si scarta).
    ``diag`` conta articoli visti e articoli attribuiti: con zero righe la differenza tra
    «la fonte non ha articoli» e «nessun articolo cita una squadra» è la diagnosi.
    """
    if not isinstance(payload, dict):
        bump(diag, "espn_payload_non_json")
        return []
    out: list[dict[str, Any]] = []
    for art in payload.get("articles", []) or []:
        bump(diag, "espn_articoli")
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
                bump(diag, "espn_attribuiti")
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
        return self.http.get_bytes(
            GOOGLE_RSS, params=google_news_params(team_name), ttl_h=self.ttl_h,
            extra_headers={"Accept": RSS_ACCEPT})

    def team_news(self, team_id: int, team_name: str,
                  diag: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raw = self.team_rss_raw(team_name)
        return parse_rss(raw, team_id, diag)

    def league_news_raw(self, espn_code: str, http: HttpClient | None = None) -> Any:
        """Notizie di lega ESPN. ``http`` permette di farle contare al client ESPN.

        Serve alla contabilità (docs/21 §15): prima queste richieste passavano dal client
        ``news`` (139 = 132 ricerche per squadra + 7 ESPN) mentre l'errore 403 finiva sulla
        riga ``espn:NEWS``: due righe che raccontavano una cosa sola, nessuna delle due vera.
        """
        import json
        client = http or self.http
        raw = client.get_bytes(ESPN_NEWS.format(code=espn_code), ttl_h=self.ttl_h)
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None


def keyword_score(text: str) -> int:
    """Quante parole chiave di contesto «interno» cita un testo (per l'ordinamento)."""
    low = text.lower()
    return sum(1 for k in KEYWORDS if k in low)


# ---------------------------------------------------------------------------------------
# Classificazione delle notizie (docs/24). La card «Ultime dalle società» pubblicava i
# titoli grezzi ordinati per parole chiave: misurato sul sito pubblicato il 2026-09-16,
# le prime 4 notizie di una squadra erano per il 38% dirette/pronostici/streaming e la
# voce più recente mostrata era vecchia di 10 giorni, perché a parità di punteggio
# l'ordinamento era per data **crescente** (`sort` senza `reverse` su una chiave negata).
#
# Qui vivono le due competenze che la card deve avere e che il feed non garantisce:
#
# 1. `JUNK_NEWS` riconosce ciò che **non è informazione**: dirette, dove vederla,
#    pronostici, probabili formazioni, pagelle, video, riepiloghi di giornata. Non è
#    censura editoriale: sono pagine che il portale non può né usare né migliorare, e
#    occupavano 2.598 titoli su 6.877 (37,8%).
# 2. `classify_news` assegna a un titolo **una** categoria con un peso, e scarta ciò che
#    non dice nulla di utile su come arriva la squadra. Le categorie sono le domande che
#    un analista si fa prima della gara: chi manca, chi è squalificato, chi siede in
#    panchina, che aria tira in società, che cosa si muove sul mercato.
#
# Deterministico e senza rete: si prova su tabelle sintetiche e si misura sui Parquet
# committati (docs/24 §2).
# ---------------------------------------------------------------------------------------

# Ciò che non è informazione per questa card. Le voci sono misurate: ognuna compare nei
# 6.877 titoli raccolti; la quota dell'insieme è 37,8% (docs/24 §2.1).
JUNK_NEWS = re.compile(
    r"risultati in diretta|in diretta|diretta tv|diretta streaming|live ?stream|streaming|"
    r"su dazn|dove veder|come veder|quando gioca|orario|quando (?:si )?gioca|"
    r"probabili formazioni|formazioni ufficiali|le formazioni|formazione ufficiale|"
    r"pronostico|pronostici|quote|scommess|odds|pagell|highlights|video|"
    r"testa a testa|altre partite|video correlati|tabellino|segui la partita|live calcio|"
    r"gol e highlights|anticipo|posticipo|fischio d'inizio|calcio d'inizio|diretta gol|"
    r"risultato finale|marcatori|la partita in (?:tv|diretta)|tv:|in streaming|"
    r"i risultati di|i risultati della|risultati e classifica|la classifica|il calendario|"
    r"migliori scommesse|consigli per le scommesse|preview|"
    # biglietti, prevendite e merchandising: pagine di servizio della testata, non notizie
    # sulla squadra. Misurato sul sito pubblicato il 2026-09-16: 27 voci su 162 pubblicate
    # erano «Come acquistare i biglietti per X-Y» — la card dichiarava di escluderle e non
    # lo faceva (docs/24 §3.3).
    r"bigliett|abbonament|prevendita|figurin|magliett|merchandis|souvenir|"
    r"come acquistare|come ottenere|informazioni sulla partita|parcheggi|"
    r"store ufficiale|shop ufficiale|album ufficial|"
    # cronaca di una gara già giocata: il titolo porta il risultato («2-1», «3-0»). Il
    # portale pubblica forma, risultati e lettura post-partita dai propri dati: la
    # cronaca di una testata aggiunge rumore, non informazione (docs/24 §3.2).
    r"\b\d{1,2}\s*[-–]\s*\d{1,2}\b", re.IGNORECASE)

# (chiave, etichetta, peso, espressione). L'ordine è l'ordine di priorità: vince la prima
# che trova, così «squalificato per infortunio» non diventa due categorie. Pesi: le tre
# voci che cambiano la formazione o la panchina valgono 5, la società 4, il mercato 3
# (spesso è già nella card «Mercato»), il resto 2.
TOPIC_RULES: tuple[tuple[str, str, int, re.Pattern[str]], ...] = (
    ("squalifiche", "Squalifiche", 5, re.compile(
        r"squalific\w*|diffidat\w*|turno di stop|stop di \d+ (?:giornat|turn)|"
        r"giudice sportivo|salta(?:r[àa])? (?:la|il|le|i) (?:prossim|gara|partita|turno)|"
        r"espulsion\w*|cartellin\w* ross|non sarà della partita", re.IGNORECASE)),
    ("infortuni", "Infortuni", 5, re.compile(
        r"infortun\w*|indisponibil\w*|lesion\w*|distorsion\w*|distrazion\w*|"
        r"elongazion\w*|stirament\w*|trauma|frattur\w*|operat(?:o|a|i|e) (?:al|alla|a)|"
        r"problema (?:muscolare|fisico|al)|risentimento|affaticament\w*|"
        r"si ferma|out \d+|fuori \d+ (?:settiman|mes)|stop di (?:circa )?\d+|"
        r"non ci sarà|salta (?:la|il|le|i) |a parte|differenziat\w*|"
        r"condizioni (?:da valutare|non ottimali)|in dubbio|ballottaggio|"
        r"recupero lampo|rientro|rientra|tornerà|torna in gruppo|a disposizione|"
        r"leave the|infermeria", re.IGNORECASE)),
    ("allenatore", "Allenatore", 5, re.compile(
        r"esonero|esonerat\w*|nuovo allenatore|nuovo tecnico|nuovo mister|"
        r"dimissioni|si è dimesso|si dimette|panchina (?:a|di|in bilico)|"
        r"rischia la panchina|accordo (?:con|per) il (?:nuovo )?tecnic|"
        r"sostitu(?:ire|to) (?:il|sul) (?:tecnico|allenatore|mister)|"
        r"vice allenatore|traghettatore|contratto (?:fino al|al 20\d\d)", re.IGNORECASE)),
    ("societa", "Società", 4, re.compile(
        r"propriet\w*|president\w*|amministratore|debit\w*|penalizzazion\w*|"
        r"deferiment\w*|inchiesta|plusvalenz\w*|bilancio|assemblea|cda|falliment\w*|"
        r"contestazion\w*|protesta dei tifosi|crisi (?:societaria|di risultati|interna)|"
        r"commissario|congedo", re.IGNORECASE)),
    ("mercato", "Mercato", 3, re.compile(
        r"ufficial\w*|ha firmato|firma(?:to)? (?:con|per|un)|colpo|acquist\w*|"
        r"cedut\w*|cessione|prestito|rinnov\w*|trattativa|offerta|addio|saluta|"
        r"biennale|triennale|fino al 20\d\d|mercato|svincol\w*|parametro zero", re.IGNORECASE)),
    ("squadra", "Squadra", 2, re.compile(
        r"convocat\w*|nazionale|esordio|record|primato|imbattibilit\w*|"
        r"serie (?:utile|positiva|negativa)|capitano|ritiro|"
        r"infortunio (?:in|con la) nazionale", re.IGNORECASE)),
    ("dichiarazioni", "Dichiarazioni", 2, re.compile(
        r"dichiarazion\w*|conferenza stampa|intervista|a microfoni|parla il|ha detto|"
        r"le parole di|frasi|il messaggio di|social", re.IGNORECASE)),
    # coda leggera: colore di società. Pesa 1, quindi si vede solo quando non c'è nulla di
    # meglio (l'ordinamento della card è per peso) — evita la card vuota senza riempirla di
    # comunicati su maglie e sponsor quando c'è un infortunio da leggere.
    ("club", "Club", 1, re.compile(
        r"premio|festa|celebr\w*|anniversario|iniziativa|solidariet\w*|maglia|sponsor|"
        r"stadio|tifosi|academy|settore giovanile|prim\w* squadra|museo", re.IGNORECASE)),
)

TOPIC_LABELS: dict[str, str] = {key: label for key, label, _, _ in TOPIC_RULES}
TOPIC_WEIGHTS: dict[str, int] = {key: w for key, _, w, _ in TOPIC_RULES}


def strip_credit(text: str | None, source: str | None = None) -> str:
    """Brano senza la testata: il nome del giornale non è contenuto della notizia.

    Difetto misurato il 2026-09-16 (docs/24 §3): la descrizione di Google News è «titolo +
    testata», quindi classificando titolo+brano la categoria la decideva la testata — un
    pezzo di cronaca ripreso da TUTTOmercatoWEB risultava «Mercato», e lo stesso valeva
    per Calciomercato o «Sportmediaset». Qui si toglie il credito prima di leggere.
    """
    out = str(text or "")
    for token in (source, "Google News", "ESPN"):
        if token and isinstance(token, str):
            out = re.sub(re.escape(token), " ", out, flags=re.IGNORECASE)
    return out


def classify_news(title: str | None, description: str | None = "",
                  source: str | None = None) -> tuple[str | None, str]:
    """Categoria della notizia e parola che l'ha determinata; ``(None, "")`` se non è utile.

    Il testo esaminato è titolo + brano **senza il nome della testata** (vedi
    :func:`strip_credit`): il brano allarga la copertura senza introdurre testo nostro né
    far decidere la categoria a chi ha pubblicato il pezzo.
    L'ordine di ``TOPIC_RULES`` è l'ordine di priorità. Il ritorno include la prova (la
    parola trovata) perché la card possa dire **perché** quella notizia è lì, e perché i
    test possano fissare il comportamento senza indovinare.
    """
    text = f"{title or ''} {strip_credit(description, source)}"
    if not text.strip():
        return None, ""
    if JUNK_NEWS.search(text):
        return None, ""
    for key, _label, _w, rx in TOPIC_RULES:
        m = rx.search(text)
        if m:
            return key, m.group(0).lower()
    return None, ""


def meaningful_news(title: str | None, description: str | None = "",
                    source: str | None = None) -> bool:
    """La notizia è pubblicabile nella card «Ultime dalle società»?"""
    return classify_news(title, description, source)[0] is not None
