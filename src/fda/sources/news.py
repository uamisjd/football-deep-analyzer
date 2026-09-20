"""Fonti notizie gratuite per la card «Ultime dalle società» (docs/21, P1-5).

Due feed pubblici, già verificati nel catalogo fonti (`docs/02`):

- **Google News RSS** per squadra, in **due edizioni**: quella italiana (``hl=it&gl=IT``),
  che segue tutti i campionati, e quella **locale** del campionato della squadra (es.
  ``hl=es&gl=ES`` per la Liga), che porta il materiale di vita del club che la stampa
  italiana non raccoglie (docs/24 §3.5). Consentito l'uso personale non commerciale, che è
  il perimetro del progetto;
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


#: Edizioni Google News per campionato: il portale adotta rigorosamente la sola
#: edizione italiana (EDIZIONE_IT, ``hl=it&gl=IT``).
#: Come specificato nelle regole di progetto (docs/00_regole_di_lavoro.md regola E,
#: docs/01 §6, docs/BRIEFING_NUOVA_SESSIONE.md), l'interfaccia, i report e tutti i
#: contenuti mostrati all'utente devono essere in lingua italiana. Interrogare edizioni
#: locali estere (es, en, de, fr, nl, pt) produce titoli in lingua straniera che non
#: possono essere pubblicati senza traduzione. La stampa sportiva italiana copre
#: ampiamente anche i club internazionali (Real Madrid, City, PSG, Bayern, ecc.).
GOOGLE_EDITIONS: dict[str, tuple[str, str, str]] = {
    "ITA": ("it", "IT:it", "calcio"),
    "ENG": ("it", "IT:it", "calcio"),
    "ESP": ("it", "IT:it", "calcio"),
    "GER": ("it", "IT:it", "calcio"),
    "FRA": ("it", "IT:it", "calcio"),
    "NED": ("it", "IT:it", "calcio"),
    "POR": ("it", "IT:it", "calcio"),
}
EDIZIONE_IT: tuple[str, str, str] = ("it", "IT:it", "calcio")


def editions_for(country: str | None = None) -> list[tuple[str, str, str]]:
    """Edizioni da interrogare per una squadra: solo quella italiana (hl=it&gl=IT).

    Garantisce che tutto il materiale raccolto sia in lingua italiana, nel pieno rispetto
    delle specifiche del progetto.
    """
    return [EDIZIONE_IT]


import unicodedata


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Termini inequivocabili di lingue straniere (inglese, spagnolo, tedesco, francese,
# olandese, portoghese), normalizzati senza accenti, che non appartengono al lessico dei
# titoli sportivi italiani.
_NON_ITALIAN_TOKENS = frozenset({
    # inglese
    "the", "with", "from", "this", "that", "after", "before", "against",
    "between", "under", "sack", "sacked", "sacks", "boss", "bosses", "signing",
    "signings", "striker", "strikers", "manager", "managers", "fans", "clash",
    "clashes", "speaks", "warning", "warns", "reveals", "target", "targets",
    "deal", "deals", "ahead", "inside", "dressing", "room", "blast", "stars",
    "told", "learn", "fast", "demanded", "demand", "demands", "split", "becoming",
    "like", "meeting", "decision", "penalty", "faces", "call", "revolt", "now",
    "of", "to", "for", "by", "is", "are", "was", "were", "have", "had", "been",
    "at", "on", "as",
    # spagnolo
    "el", "los", "las", "para", "por", "tras", "hacia", "sobre", "pero", "mas",
    "y", "sus", "fichaje", "fichajes", "entrenador", "entrenadores",
    "plantilla", "aficion", "partido", "partidos", "jornada", "jornadas",
    "resumen", "goles", "directo", "donde", "cuando", "horario", "canales",
    "alineaciones", "convocatoria", "banquillo", "vestuario", "reivindica",
    "queja", "lamenta", "polemica", "presupuesto", "desafio", "empate",
    "victoria", "destitucion", "posible", "posibles", "rueda", "prensa",
    "hace", "tantas",
    # tedesco
    "der", "die", "das", "den", "dem", "des", "und", "mit", "fur", "von", "nach",
    "beim", "trainer", "wechsel", "vertrag", "verlangerung", "sieg", "niederlage",
    "spieltag", "aufstellung", "tore", "profis", "gegen", "verlangert", "medien",
    "entschuldigt", "jubel",
    # francese
    "les", "dans", "avec", "pour", "apres", "avant", "entraineur",
    "victoire", "defaite", "joueur", "joueurs", "selection", "billetterie",
    "une", "dette", "liee", "interdit", "interdits", "deplacement",
    # olandese
    "het", "een", "voor", "naar", "speler", "spelers", "wedstrijd", "doelpunt", "eredivisie",
    "veelbesproken", "oud", "bekent", "schuld", "stevige", "grijpt", "deelt", "stadionverboden",
    # portoghese
    "dos", "pelo", "pela", "pelos", "pelas", "derrota", "jogador", "jogadores",
    "vitoria", "treinador", "selecao", "cerebro", "golo", "vai", "estar", "espanhola",
})
_NON_ITALIAN_CHARS = re.compile(r"[¿¡ßœ]")


#: Parole funzionali italiane inequivocabili. Servono quando il rilevatore statistico
#: non ha abbastanza testo (titoli di 3-5 parole, tutti nomi propri) o è in dubbio:
#: in entrambi i casi la presenza di grammatica italiana è l'unica prova disponibile.
_ITALIAN_MARKERS = frozenset({
    # articoli e preposizioni articolate
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    "del", "dello", "della", "dei", "degli", "delle", "al", "allo", "alla", "ai",
    "agli", "alle", "nel", "nello", "nella", "nei", "negli", "nelle", "sul", "sullo",
    "sulla", "sui", "sugli", "sulle", "dal", "dallo", "dalla", "dai", "dagli", "dalle",
    "col", "coi",
    # preposizioni, congiunzioni e avverbi
    "con", "per", "tra", "fra", "dopo", "prima", "mentre", "perche", "perchè", "pero",
    "però", "quindi", "dunque", "contro", "senza", "anche", "come", "quando", "dove",
    "non", "sia", "siano", "essere", "stato", "stata", "stati", "state", "sono",
    "hanno", "aveva", "avevano", "oggi", "domani", "ieri", "ora", "ancora", "tutti",
    "tutte", "tutto", "ogni", "piu", "più", "meno", "molto", "nuovo", "nuova",
    # lessico del calcio all'italiana (assente nelle altre lingue)
    "calcio", "squadra", "partita", "gara", "gare", "gol", "goal", "allenatore",
    "giocatore", "giocatori", "mercato", "stagione", "campionato", "vittoria",
    "sconfitta", "sconfitte", "pareggio", "pareggi", "punti", "minuto", "minuti",
    "casa", "trasferta", "tifosi", "societa", "società", "panchina", "rosa",
    "attaccante", "centrocampista", "portiere", "difensore", "rigore", "rigori",
})

#: Sotto questa soglia di parole il rilevatore statistico non distingue una lingua
#: dall'altra (misurato: «Brighton & Hove Albion vs Arsenal» viene letto come inglese,
#: «Getafe vs Deportivo A Coruña» come spagnolo). In quel caso decide solo la grammatica.
_MIN_PAROLE_LINGUA = 6


def _stima_lingua(testo: str) -> list[tuple[str, float]]:
    """Stime (lingua, probabilità) ordinate per verosimiglianza; lista vuota se non si può.

    ``langdetect`` è una libreria piccola, offline e senza chiavi: lavora sui modelli
    statistici inclusi nel pacchetto, quindi non aggiunge richieste di rete alla
    pipeline e non viola la regola del costo zero. Il seed fisso rende la stima
    **deterministica**: a parità di testo la risposta non cambia fra un run e l'altro
    (senza seed ``langdetect`` usa casualità interna e lo stesso titolo poteva passare
    in un run e cadere in quello dopo).
    """
    try:
        from langdetect import DetectorFactory, LangDetectException, detect_langs
    except ImportError:  # libreria assente: resta il solo veto lessicale
        return []
    try:
        DetectorFactory.seed = 0
        return [(d.lang, float(d.prob)) for d in detect_langs(testo)]
    except (LangDetectException, ValueError):
        return []


def is_italian_news(title: str, description: str = "") -> bool:
    """Verifica che un titolo (e il suo estratto) sia in lingua italiana.

    Regola E di docs/00_regole_di_lavoro.md e docs/01 §6: interfaccia e contenuti del
    portale devono essere rigorosamente in italiano.

    **Perché non basta la lista di parole (misurato il 2026-09-17, docs/25 §2).** Il
    vecchio filtro scartava un titolo solo se conteneva una parola-straniera nota, e
    quindi lasciava passare tutto il resto: sulle **161** voci pubblicate quel giorno
    nelle schede, **61 non erano in italiano** (olandese, tedesco, portoghese,
    francese, spagnolo, inglese) pur non contenendo nessuna parola della lista —
    «Trainerwechsel bei Leverkusen-Gegner», «Petrasso: «Limpámos a nossa imagem»»,
    «Nottingham Forest stadium expansion plans approved». Il portale dichiarava
    «titoli in lingua italiana» pubblicando testo in sei lingue.

    La regola ora è a due stadi, entrambi deterministici:

    1. **veto lessicale** (invariato): caratteri e parole che in un titolo di calcio
       italiano non compaiono (¿ ¡ ß œ, «the», «el», «van de», «des», …);
    2. **rilevamento statistico** su titolo + estratto, con ``langdetect``. Testo
       troppo corto (meno di 6 parole) o dubbio del rilevatore: decide la presenza di
       grammatica italiana, altrimenti si scarta — un titolo di cui non si può
       affermare la lingua non si pubblica.

    Misurato sulle 161 voci pubblicate: i 61 titoli stranieri sono scartati **tutti**,
    i 100 italiani conservati **tutti** (nessun falso scarto). Sul campione di 210
    titoli etichettati per testata la vecchia regola sbagliava 60 volte su 180
    stranieri, la nuova 5 (tutti casi di testate estere che scrivono in italiano).
    """
    if not title:
        return False
    description = description or ""
    if _NON_ITALIAN_CHARS.search(title) or _NON_ITALIAN_CHARS.search(description):
        return False
    clean = _strip_accents(title.lower())
    words = set(re.findall(r"[a-z]+", clean))
    if words & _NON_ITALIAN_TOKENS:
        return False
    testo = f"{title} {description}".strip()
    parole = re.findall(r"[A-Za-zÀ-ÿ']+", testo)
    marcatori = {p.lower().strip("'") for p in parole} & _ITALIAN_MARKERS
    stime = _stima_lingua(testo.lower())
    if not stime:
        # rilevatore non disponibile: resta il veto lessicale, come prima del 2026-09-17
        return True
    if len(parole) < _MIN_PAROLE_LINGUA:
        # troppo poco testo per una statistica: senza grammatica italiana non si pubblica
        return bool(marcatori)
    top_lang, top_prob = stime[0]
    if top_lang == "it":
        return True
    if top_prob < 0.90:
        # il rilevatore è incerto: l'italiano in classifica con grammatica italiana
        # dichiarata (almeno due parole funzionali) vale più di una prima posizione
        # presa per poco (è il caso dei titoli tutti maiuscoli, es. «NAPOLI, LOBOTKA E
        # IL RINNOVO: …», letti come inglese o portoghese).
        it_prob = next((p for lg, p in stime if lg == "it"), 0.0)
        if it_prob >= 0.05 and len(marcatori) >= 2:
            return True
    return False


# Mappa di denominazioni e alias usati dalla stampa sportiva italiana per i club esteri.
# In Italia i giornalisti scrivono "Bayern Monaco" (non "Bayern München"), "Betis Siviglia"
# (non "Real Betis Balompié"), "Athletic Bilbao" (non "Athletic Club"), "Marsiglia"
# (non "Marseille"), "Sporting Lisbona" (non "Sporting CP"), "PSG" (non "Paris Saint-Germain").
ITALIAN_SEARCH_NAMES: dict[str, str] = {
    # Bundesliga
    "Bayern München": '("Bayern Monaco" OR "Bayern")',
    "1. FC Köln": '("Colonia" OR "FC Koln")',
    "VfB Stuttgart": '("Stoccarda" OR "VfB Stuttgart")',
    "Eintracht Frankfurt": '("Eintracht Francoforte" OR "Eintracht")',
    "Werder Bremen": '("Werder Brema" OR "Werder Bremen")',
    "1. FC Union Berlin": '("Union Berlino" OR "Union Berlin")',
    "Hertha BSC": '("Hertha Berlino" OR "Hertha")',
    "Hamburger SV": '("Amburgo" OR "Hamburger SV")',
    "Mainz 05": '("Magonza" OR "Mainz")',
    "FC Augsburg": '("Augusta" OR "Augsburg")',
    "SC Freiburg": '("Friburgo" OR "SC Freiburg")',
    "Borussia Mönchengladbach": '("Borussia Monchengladbach" OR "Gladbach")',
    "Bayer Leverkusen": '("Bayer Leverkusen" OR "Leverkusen")',
    "Borussia Dortmund": '("Borussia Dortmund" OR "BVB")',
    "Schalke 04": '("Schalke 04" OR "Schalke")',
    "VfL Wolfsburg": '"Wolfsburg"',
    "RB Leipzig": '("Lipsia" OR "RB Leipzig")',
    # LaLiga
    "Real Betis": '("Betis Siviglia" OR "Betis")',
    "Athletic Club": '("Athletic Bilbao" OR "Athletic Club")',
    "Atletico Madrid": '("Atletico Madrid" OR "Colchoneros")',
    "Celta Vigo": '("Celta Vigo" OR "Celta")',
    "Deportivo Alaves": '("Alaves" OR "Deportivo Alaves")',
    "Real Sociedad": '("Real Sociedad" OR "Sociedad")',
    "Rayo Vallecano": '"Rayo Vallecano"',
    "Racing Santander": '"Racing Santander"',
    # Ligue 1
    "Marseille": '("Marsiglia" OR "Olympique Marsiglia")',
    "Lyon": '("Lione" OR "Olympique Lione")',
    "Nice": '("Nizza" OR "OGC Nizza")',
    "Paris Saint-Germain": '("PSG" OR "Paris Saint-Germain")',
    "Saint-Étienne": '("Saint-Etienne" OR "St Etienne")',
    # Premier League
    "Wolverhampton Wanderers": '("Wolverhampton" OR "Wolves")',
    "Brighton & Hove Albion": '"Brighton"',
    "West Ham United": '"West Ham"',
    "Newcastle United": '"Newcastle"',
    "Tottenham": '("Tottenham" OR "Spurs")',
    "Manchester United": '("Manchester United" OR "Man United")',
    "Manchester City": '("Manchester City" OR "Man City")',
    "Nottingham Forest": '("Nottingham Forest" OR "Nottingham")',
    # Eredivisie
    "PSV Eindhoven": '("PSV Eindhoven" OR "PSV")',
    "AZ Alkmaar": '("AZ Alkmaar" OR "AZ")',
    "FC Twente": '"Twente"',
    "FC Utrecht": '"Utrecht"',
    "Ajax": '"Ajax"',
    "Feyenoord": '"Feyenoord"',
    # Liga Portugal
    "Sporting CP": '("Sporting Lisbona" OR "Sporting CP")',
    "SL Benfica": '"Benfica"',
    "FC Porto": '"Porto"',
    "SC Braga": '"Braga"',
    "Vitória SC": '("Vitoria Guimaraes" OR "Vitória SC")',
}


def google_news_params(team_name: str, edition: tuple[str, str, str] = EDIZIONE_IT) -> dict[str, str]:
    """Parametri della ricerca RSS per squadra (**non** pre-codificati).

    Usa la denominazione italiana per i club esteri (es. "Bayern Monaco", "Marsiglia",
    "Betis Siviglia") per intercettare i titoli della stampa sportiva italiana.
    """
    hl, ceid, sport = edition
    target = ITALIAN_SEARCH_NAMES.get(team_name, f'"{team_name}"')
    return {"q": f"{target} {sport}", "hl": hl, "gl": ceid.split(":")[0], "ceid": ceid}


#: Feed RSS diretti delle principali testate sportive italiane.
#: Servono a integrare la rassegna di prima mano con articoli verificati in lingua
#: italiana (ANSA per comunicati e giustizia sportiva, Sky Sport e Sportmediaset per
#: retroscena, dichiarazioni e spogliatoio).
ITALIAN_DIRECT_FEEDS: tuple[tuple[str, str], ...] = (
    ("ANSA", "https://www.ansa.it/sito/notizie/sport/calcio/calcio_rss.xml"),
    ("Sky Sport", "https://sport.sky.it/rss/sport_calcio.xml"),
    ("Sportmediaset", "https://www.sportmediaset.mediaset.it/rss/calcio.xml"),
)


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


def parse_direct_sports_rss(
    xml_text: str | bytes,
    team_names: dict[str, int],
    source_name: str,
    diag: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Parse di un feed RSS diretto della stampa sportiva italiana con attribuzione squadra.

    I feed (ANSA, Sky Sport, Sportmediaset) pubblicano il flusso generale del calcio.
    Ogni articolo viene attribuito solo alla squadra di cui parla espressamente nel
    titolo o nell'estratto (usando nomi FotMob, denominazioni italiane e alias comuni).
    """
    if isinstance(xml_text, bytes):
        xml_text = xml_text.decode("utf-8", errors="replace")
    bump(diag, "direct_feed_bytes", len(xml_text))
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        bump(diag, "direct_feed_parse_error")
        return []
    out: list[dict[str, Any]] = []
    sorted_aliases = sorted(
        ((alias, tid) for alias, tid in team_names.items() if len(alias) >= 4),
        key=lambda pair: -len(pair[0]),
    )
    for item in root.iter("item"):
        bump(diag, "direct_feed_items")
        title = clean_text(item.findtext("title"), 200)
        desc = clean_text(item.findtext("description"), 240)
        if not title or not is_italian_news(title, desc):
            continue
        text_blob = f"{title} {desc}".lower()
        matched_tid: int | None = None
        for alias, tid in sorted_aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", text_blob):
                matched_tid = tid
                break
        if matched_tid is None:
            continue
        pub = item.findtext("pubDate") or ""
        try:
            dt = parsedate_to_datetime(pub).astimezone(UTC)
        except (TypeError, ValueError):
            dt = None
        out.append({
            "team_id": int(matched_tid),
            "published_at": dt,
            "title": title,
            "url": (item.findtext("link") or "").strip(),
            "source": source_name,
            "description": desc,
        })
        bump(diag, "direct_feed_attribuiti")
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

    def direct_feed_raw(self, url: str) -> bytes:
        """Scarica un feed RSS diretto della stampa sportiva con cache."""
        return self.http.get_bytes(url, ttl_h=self.ttl_h, extra_headers={"Accept": RSS_ACCEPT})

    def team_rss_raw(self, team_name: str,
                     edition: tuple[str, str, str] = EDIZIONE_IT) -> bytes:
        return self.http.get_bytes(
            GOOGLE_RSS, params=google_news_params(team_name, edition), ttl_h=self.ttl_h,
            extra_headers={"Accept": RSS_ACCEPT})

    def team_news(self, team_id: int, team_name: str,
                  diag: dict[str, Any] | None = None,
                  country: str | None = None) -> list[dict[str, Any]]:
        """Titoli della squadra dall'edizione italiana di Google News.

        Ogni richiesta è contata in ``diag["ricerche"]``: il numero sul report deve
        corrispondere alle richieste vere, non alle squadre.
        """
        out: list[dict[str, Any]] = []
        for edition in editions_for(country):
            bump(diag, "ricerche", 1)
            raw = self.team_rss_raw(team_name, edition)
            out.extend(parse_rss(raw, team_id, diag))
        return out

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
#: Parole di «contratto» che da sole non dicono **chi** firma. In tedesco «Profi-Vertrag für
#: Tim Binder bis 2030» è un contratto da professionista di un giocatore, non un movimento di
#: panchina; la stessa ambiguità vale per `contrat`, `renewal`, `renovación`, `renovaçao`,
#: `manager`. Restano valide quando nel titolo c'è anche una parola di panchina
#: (`COACH_CONTEXT`): misurato il 2026-09-17 sui titoli della seconda edizione — il primo
#: classificatore multilingua le prendeva tutte come «Panchina».
CONTRATTO_GENERICO = frozenset({
    "vertrag", "contrat", "contrato", "contrato hasta", "renewal", "renovación",
    "renovacion", "renovação", "renovacao", "renueva", "manager", "contract",
})

#: Parole che dicono che si parla della panchina (o di chi la occupa).
COACH_CONTEXT = re.compile(
    r"trainer|coach|allenatore|mister|entrenador|t[eé]cnico|entra[iî]neur|treinador|"
    r"tecnico|panchina|banquillo|banqueta|destituci|esonero|esonerat|sacked|entlassung|"
    r"rescis|dimission|despido|cese", re.IGNORECASE)

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
    # formazioni e squadre non prime: «così in campo», l'Under 23, la Primavera, il
    # femminile. Sono pagine vere, ma non riguardano la prima squadra di questa partita:
    # misurate il 2026-09-17 (Sambenedettese-Atalanta U23 pubblicata come «Società»).
    r"così in campo|ecco le formazioni|le scelte di|\bU\d\d\b|primavera|giovanili|"
    r"\bserie c\b|"
    r"\bunder \d\d\b|femminile|women'?s|"
    # stessa famiglia in lingua locale (docs/24 §3.5): con la seconda query il feed porta
    # titoli spagnoli, inglesi, tedeschi, francesi, olandesi e portoghesi; senza queste voci
    # le pagine di servizio straniere entrerebbero in card come se fossero notizie.
    r"cómo ver|como ver|dónde ver|donde ver|a qué hora|en directo|directo:|previa y|"
    r"posibles alineaciones|alineaci[oó]n(?:es)? probable|once probable|posible once|"
    r"pron[oó]stico|cuotas|apuestas|resultado final|resumen|cr[oó]nica|highlights|"
    r"how to watch|where to watch|live (?:stream|blog|updates)|team news|"
    r"predicted (?:line-?up|xi)|line-?ups|odds|betting|match (?:preview|pack)|"
    r"wo (?:sehen|läuft)|übertragung|live-?ticker|voraussichtliche aufstellung|"
    r"aufstellungen|quoten|wett-?tipps|spielvorschau|anpfiff|"
    r"où voir|quelle chaîne|en direct|compositions? probables?|pronostics?|cotes|avant-?match|"
    r"waar te zien|opstelling|voorspelling|voorbeschouwing|"
    r"onde assistir|escala[cç][aã]o|prov[aá]vel|palpites|pr[eé]via|"
    # cronaca di una gara già giocata: il titolo porta il risultato («2-1», «3-0»). Il
    # portale pubblica forma, risultati e lettura post-partita dai propri dati: la
    # cronaca di una testata aggiunge rumore, non informazione (docs/24 §3.2).
    r"\b\d{1,2}\s*[-–]\s*\d{1,2}\b", re.IGNORECASE)

# Annuncio o logistica: fresco, pertinente, spesso pieno di nomi propri — e inutile. La
# conferenza stampa della vigilia, il nuovo sponsor, i lavori allo stadio, gli orari e i
# parcheggi non cambiano nulla di questa partita: la card li **conta** e li lascia fuori,
# così il numero stampato è riconciliabile (docs/24 §3.5).
ANNUNCIO_NEWS = re.compile(
    r"rueda de prensa|conferencia de prensa|comparecencia|press conference|"
    r"pressekonferenz|conf[eé]rence de presse|persconferentie|coletiva de imprensa|"
    r"conferenza stampa|presentaci[oó]n|presentazione|acto oficial|watch party|"
    r"patrocinad|patrocinio|sponsor|nuevo patrocinador|obras|lavori allo stadio|"
    r"remodelaci[oó]n|climatiz|accesos|aparcamiento|precios|entradas|abonos|tickets|"
    r"horario|a qué hora|new balance arena|"
    r"premio|galard[oó]n|homenaje|cumplea[ñn]os|aniversario|"
    r"fichaje estrella|camiseta|maglia celebrativa|"
    r"^\s*(?:comunicato del club|nota del club|comunicato ufficiale)\s*$", re.IGNORECASE)

# Il gate della card: un fatto entra solo se può **spostare qualcosa** — una frizione, una
# decisione, un vincolo, una protesta, un numero che dice quanto la società può spendere.
# È la correzione chiesta dall'utente il 2026-09-16 («con queste notizie non ci faccio
# nulla»): freschezza e pertinenza sono necessarie ma non sufficienti (docs/24 §3.5).
CONSEGUENZA_NEWS = re.compile(
    # frizione, crisi, decisione (spagnolo: la lingua della seconda query per la Liga)
    r"queja|lamenta|malestar|tensi[oó]n|enfado|mosqueo|crisis|dimisi|destituci|despido|"
    r"ultim[aá]tum|presiona|protesta|manifestaci[oó]n|concentraci[oó]n|huelga|"
    r"amenaza|insulto|abucheo|pol[eé]mica|arremete|critica|estalla|se revuelve|"
    r"carga contra|plantilla corta|plantilla muy corta|rosa corta|sin extremos|"
    r"no tiene extremos|se queda cort[ao]|peligra su puesto|en la cuerda floja|"
    r"se le acaba el cr[eé]dito|desmiente|denuncia|renuncia|se planta|"
    r"sanci[oó]n|multa|expediente|deuda|concurso|insolvencia|bloqueo|veto|"
    r"l[ií]mite salarial|tope salarial|presupuesto|balance|d[eé]ficit|super[aá]vit|"
    r"rechaza|rechaz|exige|recurso|sentencia|licencia|comunicado|defiende|defensa|"
    r"respalda|renueva|renovaci[oó]n|acuerdo|firma|ampliaci[oó]n|recorte|"
    r"congelaci[oó]n|limitaci[oó]n|reducci[oó]n|"
    # italiano (il feed italiano resta quello di partenza)
    r"esonero|esonerat\w*|dimissioni|crisi|protesta|contestazion|striscione|multa|debit|ricorso|"
    r"sfuriata|sgridat\w*|daspo|saluti romani|multipropriet\w*|sfogo|ammonizion\w*|"
    r"sentenza|rinnovo|accordo|firma|limite|tetto|bilancio|comunicato|difende|"
    r"minacce|insulti|braccio di ferro|attacca|smentisce|nega|inchiesta|indagine|"
    r"vendita|acquisizione|accusa|polemica|rischia la panchina|in bilico|ultimatum|"
    r"panchina a rischio|diffida|tribunale|esposto|bacchetta|scarica|"
    # inglese (parole intere: «row» non deve pescare «grow»)
    r"\b(?:complaint|slams?|blasts?|fury|feud|ultimatum|sack(?:ed)?|resign(?:ed|s|ing)?|"
    r"threat|abuse|protest|strike|ban(?:ned|s)?|fine[sd]?|debt|sanction(?:ed|s)?|"
    r"demand(?:s|ed)?|reject(?:s|ed)?|accuse(?:s|d)?|criticis\w*|anger|outburst|"
    r"budget|salary cap|short squad|short of players|backlash|blast)\b|"
    # tedesco, francese, olandese, portoghese
    r"beschwerde|kritik|vertrag|verl[aä]ngerung|streik|schulden|"
    r"plainte|critique|gr[eè]ve|protestation|dette|"
    r"beklag|kritiek|schuld|"
    r"queixa|cr[ií]tica|protesto|greve|d[ií]vida|"
    # fuori dal campo: la grana personale di un tesserato pesa su chi scende in campo, e la
    # stampa locale ne parla per giorni (voce «Fuori dal campo» di TOPIC_RULES)
    r"incidente|alcoltest|tasso alcolemico|stupefacenti|tossicolog\w*|patente ritirata|"
    r"arresto|arrestat\w*|"
    r"querela|denunciat\w*|"
    r"detenido|imputado|juicio|accidente de tr[aá]fico|"
    r"\b(?:arrested|charged with|drink-?driving)\b", re.IGNORECASE)

# (chiave, etichetta, peso, espressione). L'ordine è l'ordine di priorità: vince la prima
# che trova, così «squalificato per infortunio» non diventa due categorie. Pesi: panchina,
# spogliatoio e società valgono 5 (sono le voci che cambiano qualcosa), stadio/tifo/mercato
# 3, il resto 2 o 1. Con la seconda query il testo può essere in lingua locale: ogni regola
# porta le alternative spagnole, inglesi, tedesche, francesi, olandesi e portoghesi
# (docs/24 §3.5).
TOPIC_RULES: tuple[tuple[str, str, int, re.Pattern[str]], ...] = (
    ("squalifiche", "Squalifiche", 5, re.compile(
        r"squalific\w*|diffidat\w*|turno di stop|stop di \d+ (?:giornat|turn)|"
        r"giudice sportivo|salta(?:r[àa])? (?:la|il|le|i) (?:prossim|gara|partita|turno)|"
        r"espulsion\w*|cartellin\w* ross|non sarà della partita|"
        r"sancionad\w*|sanci[oó]n de partidos|suspensi[oó]n de partidos|tarjeta roja|"
        r"expulsi[oó]n|no jugar[aá]|baja por sanci[oó]n|apercibid\w*|"
        r"suspension|suspended|red card|misses the|banned|"
        r"sperre|rotes karte|carton rouge|schorsing|suspens[aã]o|cart[aã]o vermelho",
        re.IGNORECASE)),
    ("infortuni", "Infortuni", 5, re.compile(
        r"infortun\w*|indisponibil\w*|lesion\w*|distorsion\w*|distrazion\w*|"
        r"elongazion\w*|stirament\w*|trauma|frattur\w*|lussazion\w*|ricadut\w*|"
        r"rottura (?:del|di) (?:legament|crociat)|legamento crociato|frattura composta|"
        r"operat(?:o|a|i|e)\b|si è operato|intervento (?:chirurgico|riuscito)|"
        r"sala operatoria|problema (?:muscolare|fisico|al|alla)|risentimento|affaticament\w*|"
        r"si ferma|out \d+|fuori \d+ (?:settiman|mes|giorn)|stop di (?:circa )?\d+|"
        r"non ci sarà|salta (?:la|il|le|i) |a parte|differenziat\w*|"
        r"condizioni (?:da valutare|non ottimali)|in dubbio|ballottaggio|"
        r"recupero lampo|rientro|rientra|tornerà|torna in gruppo|a disposizione|"
        r"lesi[oó]n|lesionad\w*|bajas?|duda|parte m[eé]dico|enfermer[ií]a|"
        r"se pierde|tocado|molestias|isquio|rotura|esguince|recuperaci[oó]n|"
        r"injury|injured|out for|hamstring|fitness|"
        r"verletzt|verletzung|ausfall|f[aä]llt aus|"
        r"blessure|bless[eé]|forfait|incertain|geblesseerd|desfalque|"
        r"leave the|infermeria", re.IGNORECASE)),
    # Panchina: non solo l'esonero consumato, anche il ciclo che finisce e il contratto che
    # pesa. È la voce che l'utente ha chiesto per prima («allenatore a rischio esonero»).
    ("allenatore", "Panchina", 5, re.compile(
        r"esonero|esonerat\w*|nuovo allenatore|nuovo tecnico|nuovo mister|"
        r"dimissioni|si è dimesso|si dimette|panchina (?:a|di|in bilico|a rischio)|"
        r"rischia la panchina|panchina (?:traballante|in discussione|in soffitta)|"
        r"accordo (?:con|per) il (?:nuovo )?tecnic|"
        r"sostitu(?:ire|to) (?:il|sul) (?:tecnico|allenatore|mister)|"
        r"vice allenatore|traghettatore|contratto (?:fino al|al 20\d\d|in scadenza)|"
        r"ultimo anno di contratto|cambio (?:di )?panchina|fine (?:annunciata|del ciclo)|"
        r"ciclo (?:finito|chiuso)|addio (?:al|del) (?:club|tecnico|mister)|"
        r"separazione|rescissione|futuro (?:di|del) (?:mister|tecnico|allenatore)|"
        r"crisi (?:nera|tecnica|di risultati)|"
        r"entrenador|t[eé]cnico|banquillo|destituci|despido|cese|"
        r"renueva|renovaci[oó]n|contrato hasta|futuro de|presi[oó]n|"
        r"manager|head coach|sacked|renewal|vertrag|entlassung|"
        r"entra[iî]neur|\bcontrat\b|treinador|renova[cç][aã]o|trainer", re.IGNORECASE)),
    # Spogliatoio: il gruppo che scricchiola — o che si compatta. Qui l'evidenza sono le
    # parole del malessere, non il nome del club.
    ("spogliatoio", "Spogliatoio", 5, re.compile(
        r"vestuario|spogliatoio|dressing room|kabine|vestiaire|vesti[aá]rio|"
        r"malestar|tensi[oó]n|enfado|rega[ñn]ina|rifa|pique|lite|litigi\w*|\bclima\b|"
        r"gruppo (?:squadra|spaccato|diviso|unit[oa])|team spirit|friction|dressing|"
        r"ammutinamento|malumore|malcontento|insoddisfazion\w*|incomprension\w*|"
        r"frizion\w*|rottura (?:dei rapporti|con (?:il|la|lo) )|faccia a faccia|chiarimento|"
        r"discussione (?:accesa|nello spogliatoio)|rapporti? (?:tesi|difficili)|"
        r"clima (?:teso|pesante|non sereno)|"
        r"critica la plantilla|se vuelve a quejar|se queja de la plantilla|"
        r"no tiene extremos|sin extremos|\b[uú]nico equipo\b|plantilla corta|"
        r"plantilla muy corta|se queda cort|sin refuerzos|sin fichajes|"
        r"berlusconi|ammutinamento", re.IGNORECASE)),
    # Società: proprietà, giustizia sportiva e ordinaria, soldi, organizzazione. Qui entra
    # anche il vocabolario italiano che nella prima stesura mancava («indagine», «minacce»,
    # «sentenza», «perquisizioni»): era il motivo per cui le voci più succose del feed
    # italiano restavano fuori categoria e finivano contate come «servizio» (misurato il
    # 2026-09-17 su 1467 titoli: 587 senza categoria, fra cui l'inchiesta su Lotito/Lazio,
    # la sentenza Udinese e il caso Maldini).
    ("societa", "Società", 5, re.compile(
        r"propriet\w*|president\w*|amministratore|debit\w*|penalizzazion\w*|"
        r"deferiment\w*|inchiesta|indagine|indagat\w*|plusvalenz\w*|assemblea|cda|"
        r"bilancio (?:d'esercizio|consolidato|societario|economico|finanziario)|"
        r"falliment\w*|commissariament\w*|tribunale|processo|sentenza|udienza|"
        r"perquisizion\w*|sequestr\w*|procura|avviso di garanzia|condann\w*|assoluzion\w*|"
        r"truffa|riciclaggio|falso in bilancio|evasion\w*|pignorament\w*|risarciment\w*|"
        r"minacce|minacciat\w*|pressioni|intimidazion\w*|ricatt\w*|estorsion\w*|esposto|"
        r"contestazion\w*|protesta dei tifosi|crisi (?:societaria|di risultati|interna)|"
        r"commissario|congedo|vendita (?:del|della|dello) (?:club|società|pacchetto)|"
        r"cessione (?:del|della) (?:club|società)|nuovi (?:soci|proprietari|investitori)|"
        r"azionist\w*|quote|cedere|trattativa per la (?:vendita|cessione)|organigramma|"
        r"direttore sportivo|fair play finanziario|vertenz\w*|"
        r"directiva|consejo de administraci[oó]n|junta|accionistas|propiedad|"
        r"propietario|l[ií]mite salarial|limite salariale|tetto ingaggi|monte ingaggi|tope salarial|licencia|urbanismo|"
        r"sentencia|recurso|multa|san[cç][aã]o|deuda|presupuesto|fundaci[oó]n|"
        r"board|ownership|salary cap|takeover|investigation|lawsuit|"
        r"vorstand|schulden|gehaltsobergrenze|conseil|direction|dette|licence|"
        r"bestuur|schuld|diretoria|d[ií]vida", re.IGNORECASE)),
    # Fuori dal campo: la grana personale di un tesserato (incidenti, guai giudiziari). Non
    # è la partita, ma pesa su chi la gioca — e la stampa locale ne parla per giorni.
    ("fuoricampo", "Fuori dal campo", 4, re.compile(
        # «incidente» da solo non basta: in spagnolo e in italiano è anche l'episodio
        # qualsiasi. Pescato il 2026-09-17 sui titoli della seconda edizione: «Pellegrini
        # difende Ez Abde dopo l'incidente della maglia di Ceuta» finiva fra i guai
        # giudiziari. Ora serve la forma che indica un fatto di strada o di salute.
        r"incidente (?:stradale|d'?auto|automobilistico|mortale|in (?:auto|moto|scooter|macchina|bici))|"
        r"incidente[^.:;]{0,40}(?:stradale|auto|moto|macchina|alcol|tossicolog)|"
        r"etilometro|alcoltest|positivo (?:ad|al|a) (?:alcol|alcool|stupefacenti|drog)|"
        r"tossicolog\w*|"
        r"alcoltest|tasso alcolemico|stupefacenti|patente ritirata|arrestat\w*|arresto|denunciat\w*|querela|"
        r"indagato|colluttazione|rissa|"
        r"detenido|imputado|juicio|condena|accidente de tr[aá]fico|"
        r"arrested|charged with|drink-?driving|court date", re.IGNORECASE)),
    ("tifo", "Tifoseria", 3, re.compile(
        r"afici[oó]n|aficionad\w*|abonados|socios|pe[ñn]a|ultras|supporters|tifosi|"
        r"fans|grada|protesta|manifestaci[oó]n|corteo|banderas|ambientazo|"
        r"hinchas|seguidores|tifo|curva|striscion\w*|contestazione dei tifosi|"
        r"fischi|fischiato|delusione dei tifosi|assemblea dei tifosi|sostenitori|"
        r"divieto di trasferta|daspo|questura|ordine pubblico|tessera del tifoso|"
        r"anh[aä]nger|claque|aanhang", re.IGNORECASE)),
    ("stadio", "Stadio e città", 3, re.compile(
        r"estadio|stadium|stadion|stadio|stade|est[aá]dio|obras|remodelaci[oó]n|"
        r"vecinos|barrio|aparcamiento|accesos|climatiz|ruido|c[eé]sped|"
        r"manto erboso|campo (?:pesante|inagibile)|stadio (?:chiuso|inagibile|nuovo)|"
        r"impianto (?:sportivo|chiuso)|centro sportivo|sede (?:nuova|della società)|"
        r"pitch|terreno di gioco|city council|ayuntamiento", re.IGNORECASE)),
    ("mercato", "Mercato", 3, re.compile(
        r"ufficial\w*|ha firmato|firma(?:to)? (?:con|per|un)|colpo|acquist\w*|"
        r"cedut\w*|cessione|prestito|rinnov\w*|trattativa|offerta|addio|saluta|"
        r"biennale|triennale|fino al 20\d\d|mercato|svincol\w*|parametro zero|"
        r"fichaje|traspaso|cesi[oó]n|mercado|signing|transfer|deal|"
        r"verpflichtung|transfert|contrata[cç][aã]o", re.IGNORECASE)),
    ("squadra", "Squadra", 2, re.compile(
        r"convocat\w*|nazionale|esordio|record|primato|imbattibilit\w*|"
        r"serie (?:utile|positiva|negativa)|capitano|ritiro|"
        r"infortunio (?:in|con la) nazionale|"
        r"convocatoria|selecci[oó]n|internacional|r[eé]cord|racha|capit[aá]n|"
        r"squad|national team|unbeaten|kader|nationalmannschaft|"
        r"s[eé]lection|selectie|sele[cç][aã]o", re.IGNORECASE)),
    ("dichiarazioni", "Dichiarazioni", 2, re.compile(
        r"dichiarazion\w*|conferenza stampa|intervista|a microfoni|parla il|ha detto|"
        r"le parole di|frasi|il messaggio di|social|«|»|"
        r"declaracion\w*|dijo|asegur[oó]|se[ñn]al[oó]|explic[oó]|afirm[oó]|palabras|"
        r"quotes|said|spoke|says|erkl[aä]rt|d[eé]clare|aldus|disse", re.IGNORECASE)),
    # coda leggera: colore di società, settore giovanile e iniziative. Pesa 1, quindi si vede
    # solo quando non c'è nulla di meglio (l'ordinamento della card è per punteggio) — evita
    # la card vuota senza riempirla di comunicati quando c'è un fatto che sposta qualcosa.
    ("club", "Club", 1, re.compile(
        r"premio|festa|celebr\w*|anniversario|iniziativa|solidariet\w*|maglia|sponsor|"
        r"tifosi|academy|settore giovanile|prim\w* squadra|museo|cantera|filial|"
        r"primavera|under \d+|u\d\d|"
        r"academia|celebraci[oó]n|camiseta|solidaridad|"
        r"trophy|anniversary|jubil[aä]um|troph[eé]e|jubileu", re.IGNORECASE)),
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
        if not m:
            continue
        prova = m.group(0).lower()
        if key == "allenatore" and prova in CONTRATTO_GENERICO \
                and not COACH_CONTEXT.search(text):
            continue      # un contratto senza panchina nel titolo non è un fatto di panchina
        return key, prova
    return None, ""


def meaningful_news(title: str | None, description: str | None = "",
                    source: str | None = None) -> bool:
    """La notizia è pubblicabile nella card «Ultime dalle società»?"""
    return classify_news(title, description, source)[0] is not None


PIATTO_NEWS = re.compile(
    r"il punto sulla giornata|il punto sul campionato|il punto di giornata|"
    r"il quadro della giornata|panoramica della giornata|la rassegna stampa di oggi|"
    r"un punto m[aá]s|un punto e a capo",
    re.IGNORECASE,
)



# ---- reputazione fonte (P2 audit §18 + quality 2026-09-20: alzare soglia gossip) ----
LOW_REPUTATION_PATTERN = re.compile(
    r"fantacalcio|calciomercato|tuttomercato|scommess|pronostic|the sun|daily star|"
    r"leggo\.it|superscommess|barcauniversal|madridista|onlyfans|clickbait|"
    r"juvefc|sempreinter|sempremilan|toro news|toronews|napolicalcio|calcio\.com|"
    r"diretta|sofascore|futbol24|yahoo|fotmob|sportbible|sospronostics|"
    r"instagram|tiktok|facebook|youtube|twitter|x\.com|dagospia|novella|gossip|trash|"
    r"the\s+sun",
    re.IGNORECASE,
)

LOW_REPUTATION_EXACT = frozenset({
    "diretta",
    "sofascore",
    "futbol24",
    "yahoo",
    "yahoo finanzas",
    "yahoo sports",
    "top scommesse",
    "fantacalcio",
    "calciomercato",
    "tuttomercatoweb",
    "calciomercato.com",
    "tuttomercatoweb.com",
    "fantacalcio.it",
    "leggo.it",
    "superscommesse",
    "sospronostics",
    "the sun",
    "daily star",
    "sportbible",
    "sempreinter",
    "sempremilan",
    "toro news",
    "toronews.net",
    "napolicalcionews.it",
    "calcio.com",
    "fotmob",
})

def is_low_reputation(source: str | None) -> bool:
    """Fonte a bassa reputazione per la card news (P2): scommesse, fantacalcio, gossip, aggregatori live."""
    if not source:
        return False
    s = str(source).strip()
    if not s:
        return False
    low = s.lower()
    if low in LOW_REPUTATION_EXACT:
        return True
    if LOW_REPUTATION_PATTERN.search(s):
        return True
    # aggregatori generici senza redazione
    if low in {"diretta", "sofascore", "futbol24", "yahoo", "fotmob"}:
        return True
    return False



def news_value(title: str | None, description: str | None = "",
               source: str | None = None) -> str | None:
    """Il fatto può **spostare qualcosa** o dare sostanza di club? ``None`` se sì, altrimenti il motivo.

    Gate editoriale della card:
    - ``"annuncio"`` — conferenza stampa di mera logistica, presentazione sponsor, lavori allo
      stadio, orari e biglietti;
    - ``"piatto"`` — rassegna stampa generica, punto sul campionato privo di eventi specifici
      o testo vuoto;
    - ``None`` — il titolo ha valore informativo ed entra in card.

    Il testo esaminato è titolo + brano senza la testata (vedi :func:`strip_credit`).
    """
    text = f"{title or ''} {strip_credit(description, source)}"
    clean = _strip_accents(text.lower()).strip()
    if not clean:
        return "piatto"
    if ANNUNCIO_NEWS.search(text):
        return "annuncio"
    if PIATTO_NEWS.search(text) or PIATTO_NEWS.search(clean):
        return "piatto"
    return None
