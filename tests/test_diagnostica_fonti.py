"""Test offline della diagnostica delle fonti a zero righe (docs/21 §15).

Coprono tre cose nate da un caso reale (2026-09-15: `news` 139 richieste e `transfers` 132
payload, entrambe «OK», zero righe salvate e nessuna spiegazione leggibile):

1. il difetto dimostrato della query Google News **doppio-codificata** (feed valido ma
   vuoto, nessun errore) — qui c'è la regressione con `requests.PreparedRequest`;
2. l'imbuto: feed vuoto, corpo non-RSS e payload JSON di forma ignota non sono più
   indistinguibili, e la firma dello schema espone **solo nomi di campo**, mai valori;
3. i contatori sono **della fase**, non il cumulativo del client condiviso (era il motivo
   per cui `transfers:TRANSFERS` 263 non significava «263 richieste di quella fase»).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone

import pandas as pd
import requests

from fda.collect import CollectReport, collect_news, collect_transfers
from fda.config import league
from fda.diagnostics import MAX_DETAIL, MAX_DIGEST, bump, digest, key_names, shape_of
from fda.sources.fotmob import FotMobClient
from fda.sources.news import (ESPN_NEWS, GOOGLE_RSS, google_news_params,
                               parse_espn_news, parse_rss)
from fda.store import Store

RSS_VUOTO = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
             '<title>"Squadra" calcio</title><link>https://news.google.com/</link>'
             '</channel></rss>')
RSS_UNO = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
           '<item><title>La squadra cambia modulo - Corriere dello Sport</title>'
           '<link>https://esempio.invalid/a</link>'
           '<pubDate>Mon, 14 Sep 2026 18:05:00 GMT</pubDate>'
           '<description>Testo &lt;b&gt;breve&lt;/b&gt;.</description></item>'
           '</channel></rss>')
PAGINA_HTML = "<!doctype html><html><body><h1>Prima di continuare</h1></body></html>"


# ---- 1) il difetto dimostrato: una sola codifica della query --------------------------------
def test_query_google_news_codificata_una_volta_sola():
    params = google_news_params("Ajax")
    assert params["q"] == '"Ajax" calcio'          # non pre-codificata
    url = requests.Request("GET", GOOGLE_RSS, params=params).prepare().url
    assert "q=%22Ajax%22+calcio" in url or "q=%22Ajax%22%20calcio" in url
    assert "%2522" not in url                      # doppia codifica = ricerca del testo letterale


# ---- 2) imbuto dei parse ---------------------------------------------------------------------
def test_parse_rss_feed_valido_ma_vuoto():
    diag: dict = {}
    assert parse_rss(RSS_VUOTO, 7, diag) == []
    # feed valido ma senza articoli: «item 0» e zero corpi non-RSS, cioè una diagnosi
    assert diag["items"] == 0 and diag["parse_error"] == 0 and diag["bytes"] > 0


def test_parse_rss_corpo_non_rss():
    diag: dict = {}
    assert parse_rss(PAGINA_HTML, 7, diag) == []
    assert diag["parse_error"] == 1 and diag["bytes"] > 0


def test_parse_rss_feed_con_articolo():
    diag: dict = {}
    rows = parse_rss(RSS_UNO, 7, diag)
    assert len(rows) == 1 and diag["items"] == 1
    assert rows[0]["source"] == "Corriere dello Sport"     # testata separata dal titolo
    assert rows[0]["published_at"].year == 2026


def test_parse_espn_news_conta_articoli_e_attribuiti():
    diag: dict = {}
    payload = {"articles": [{"headline": "Roma, out il capitano", "description": ""},
                            {"headline": "Notizia di lega senza squadre", "description": ""}]}
    rows = parse_espn_news(payload, {"Roma": 1}, diag)
    assert len(rows) == 1 and diag["espn_articoli"] == 2 and diag["espn_attribuiti"] == 1


# ---- 3) firma dello schema: solo nomi, mai valori --------------------------------------------
def test_shape_of_espone_solo_nomi_di_campo():
    firma = shape_of({"playerName": "Segreto Rossi", "fee": {"amount": 45000000}})
    assert "playerName" in firma and "fee" in firma
    assert "Segreto" not in firma and "Rossi" not in firma and "45000000" not in firma
    assert shape_of(["a", "b", "c"]) == "lista(3)"
    assert shape_of(None) == "NoneType"
    # dal 2026-09-16 (docs/21 §17) gli spazi singoli fra parole sono ammessi: la sezione
    # transfers di FotMob usa chiavi come «Players in»/«Players out»
    assert key_names({"chiave con spazi": 1, "ok_key": 2}) == ["chiave con spazi", "ok_key"]
    # …ma il resto della whitelist non cambia: niente spazi doppi, davanti/dietro,
    # simboli, testo con punteggiatura o nomi oltre il tetto di lunghezza
    assert key_names({"doppio  spazio": 1, " davanti": 2, "simboli!": 3, "punto.": 4,
                      "a" * 41: 5}) == []


def test_digest_e_detail_hanno_un_tetto():
    assert len(digest("x" * 500)) <= MAX_DIGEST
    assert len(CollectReport(league="X", run_at=datetime.now(timezone.utc)).details) == 0


# ---- 4) righe + motivo in source_status ------------------------------------------------------
def test_as_status_rows_porta_righe_motivo_e_firma():
    rep = CollectReport(league="NEWS", run_at=datetime.now(timezone.utc))
    rep.requests = {"news": 3, "espn": 1}
    rep.errors = ["espn news ITA1: SourceError: HTTP 403"]
    rep.note("news", rows=0, detail_text="f" * 300, digest_text="g" * 300)
    rows = {r["source"]: r for r in rep.as_status_rows()}
    assert rows["news:NEWS"]["rows"] == 0
    assert len(rows["news:NEWS"]["detail"]) <= MAX_DETAIL
    assert len(rows["news:NEWS"]["digest"]) <= MAX_DIGEST
    # un 403 sulle notizie ESPN è un degrado coperto da Google News, non un errore bloccante
    assert rows["espn:NEWS"]["warn"] is True and rows["espn:NEWS"]["ok"] is False


# ---- 5) i collettori: imbuto pubblicato e contatori per fase ---------------------------------
class _Stats:
    def __init__(self, start: int = 0) -> None:
        self.requests = start
        self.cache_hits = 0


class _FakeHttp:
    def __init__(self, payload: bytes, start: int = 0) -> None:
        self.stats = _Stats(start)
        self.payload = payload
        self.calls: list[dict] = []

    def mark(self) -> int:
        # stesso contratto di HttpClient.mark(): istantanea per i delta per lega/fase
        return self.stats.requests

    def get_bytes(self, url, params=None, ttl_h=None, extra_headers=None):
        self.stats.requests += 1
        self.calls.append({"url": url, "params": params, "headers": extra_headers})
        return self.payload


class _FakeNews:
    """Client notizie finto: feed valido ma **vuoto**, come la ricerca doppio-codificata."""

    def __init__(self, start: int = 0) -> None:
        self.http = _FakeHttp(RSS_VUOTO.encode(), start=start)

    def team_news(self, team_id, team_name, diag=None, country=None):
        # ``country`` esiste nella firma del client vero (edizione locale, docs/24 §3.5):
        # il finto risponde lo stesso feed perché qui interessa la contabilità.
        raw = self.http.get_bytes(GOOGLE_RSS, params=google_news_params(team_name), ttl_h=12.0,
                                  extra_headers={"Accept": "application/rss+xml"})
        return parse_rss(raw, team_id, diag)

    def league_news_raw(self, espn_code, http=None):
        client = http or self.http
        return json.loads(client.get_bytes(ESPN_NEWS.format(code=espn_code), ttl_h=12.0))

    def direct_feed_raw(self, url: str) -> bytes:
        """Feed RSS diretti della stampa italiana (ANSA, Sky Sport, Sportmediaset).

        Senza questo metodo il collettore sollevava ``AttributeError`` su ognuno dei tre
        feed a ogni test: ``_safe`` lo catturava, quindi la suite restava verde mentre il
        ramo dei feed diretti non veniva **mai** esercitato e tre errori finti finivano
        negli errori del report (trovato il 2026-09-17, docs/26 §5).
        """
        return self.http.get_bytes(url, ttl_h=12.0, extra_headers={"Accept": "application/rss+xml"})


class _FakeEspn:
    def __init__(self, start: int = 0) -> None:
        self.http = _FakeHttp(b'{"articles": []}', start=start)


def _store_con_fixtures(tmp_path) -> Store:
    st = Store(tmp_path / "processed")
    ita1 = league("ITA1")
    st.write("fixtures", pd.DataFrame([
        {"league_id": ita1.fotmob_id, "home_id": 1, "home_name": "Roma", "away_id": 2,
         "away_name": "Inter", "utc_kickoff": pd.Timestamp("2026-09-20 18:00", tz="UTC"),
         "status": "scheduled"},
        {"league_id": ita1.fotmob_id, "home_id": 3, "home_name": "Torino", "away_id": 4,
         "away_name": "Como", "utc_kickoff": pd.Timestamp("2026-09-20 20:45", tz="UTC"),
         "status": "scheduled"},
    ]))
    return st


def test_collect_news_pubblica_imbuto_e_contatori_separati(tmp_path):
    st = _store_con_fixtures(tmp_path)
    nc, ec = _FakeNews(start=50), _FakeEspn(start=100)     # client già usati: contano i delta
    report = collect_news(st, keys=["ITA1"], news=nc, espn=ec)
    stato = st.read("source_status")
    riga = stato[stato.source == "news:NEWS"].iloc[0]
    assert riga["rows"] == 0
    assert "articoli 0" in riga["detail"]                  # il motivo, in pagina
    assert "item 0" in riga["digest"] and "rss:" in riga["digest"]
    assert "in finestra 0" in riga["detail"]
    # le richieste ESPN non finiscono più nel contatore delle notizie. Il totale è 5:
    # 2 ricerche Google (una per squadra) + 3 feed diretti (ANSA, Sky Sport, Sportmediaset)
    assert report.requests == {"news": 5, "espn": 1}
    # il ramo dei feed diretti è esercitato davvero: nessun AttributeError fra gli errori
    assert not [e for e in report.errors if e.startswith("news direct")], report.errors
    riga_espn = stato[stato.source == "espn:NEWS"].iloc[0]
    assert riga_espn["rows"] == 0 and "articoli di lega 0" in riga_espn["detail"]
    st.close()


def test_parse_transfers_registra_la_firma_su_forma_ignota():
    payload = {"details": {}, "transfers": {"data": [{"name": "Tizio"}]}, "squad": []}
    diag: dict = {}
    assert FotMobClient.parse_transfers(payload, 1, "Roma", "ITA1", diag) == []
    assert diag["sezione"] == "dict" and diag["campi_sezione"] == "data"
    assert diag["top"] == "dict(3): details,transfers,squad"   # dove sta la sezione, per davvero


class _FakeFotMobMercato:
    """Client FotMob finto: payload con la sezione `transfers` in forma non riconosciuta."""

    def __init__(self, start: int = 90) -> None:
        self.requests = start
        self.http = type("H", (), {"stats": self, "mark": lambda s: self.requests})()

    def team_raw(self, team_id: int) -> dict:
        self.requests += 1
        return {"details": {}, "transfers": {"data": [{"name": "Tizio"}]}, "squad": []}


def test_collect_transfers_imbuto_e_contatori_per_fase(tmp_path):
    st = Store(tmp_path / "mercato")
    st.write("fotmob_standings", pd.DataFrame([
        {"league_code": "ITA1", "team_id": 1, "team_name": "Roma", "rank": 1},
        {"league_code": "ITA1", "team_id": 2, "team_name": "Inter", "rank": 2},
    ]))
    report = collect_transfers(st, fotmob=_FakeFotMobMercato(start=90))
    riga = st.read("source_status").query("source == 'transfers:TRANSFERS'").iloc[0]
    assert riga["rows"] == 0
    assert "payload letti 2" in riga["detail"] and "sezione dict in 2" in riga["detail"]
    assert "transfers" in riga["digest"] and "campi data" in riga["digest"]
    # 90 richieste erano di altre fasi: qui se ne contano solo le 2 di questa
    assert report.requests == {"transfers": 2}
    st.close()


def test_bump_su_none_non_solleva():
    bump(None, "x")          # i parser restano chiamabili senza diagnostica


def test_la_firma_non_contiene_mai_valori_dall_endpoint_vero():
    """Il caso reale: il valore è un nome di giocatore, la firma deve contenere solo campi."""
    vero = {"transfers": {"incoming": [{"name": "Kylian Mbappé", "from": {"name": "PSG"}}],
                          "outgoing": []}}
    firma = shape_of(vero["transfers"])
    diag: dict = {}
    assert len(FotMobClient.parse_transfers(vero, 1, "Real Madrid", "ESP1", diag)) == 1
    assert diag["sezione"] == "dict/in-out" and "incoming" in diag["campi_sezione"]
    for valore in ("Mbappé", "PSG", "Real Madrid"):
        assert valore not in firma and valore not in diag["campi_sezione"]


def test_parse_rss_conta_le_date_illeggibili_nel_collettore(tmp_path):
    """Una data illeggibile non pubblica la riga (finestra 7 giorni) ma viene contata."""
    rss = RSS_UNO.replace("Mon, 14 Sep 2026 18:05:00 GMT", "data non leggibile")
    st = _store_con_fixtures(tmp_path)
    nc = _FakeNews()
    nc.http.payload = rss.encode()
    collect_news(st, keys=["ITA1"], news=nc, espn=_FakeEspn())
    riga = st.read("source_status").query("source == 'news:NEWS'").iloc[0]
    assert "senza data 2" in riga["detail"] and riga["rows"] == 0
    st.close()


def test_collect_news_pota_l_archivio_oltre_la_finestra(tmp_path):
    """La potatura che la docstring di ``collect_news`` prometteva senza implementarla.

    Caso reale trovato il 2026-09-17 (docs/26 §2): ``window_days`` filtrava solo le righe
    **in arrivo**, così ``news.parquet`` cresceva a ogni run — 18.705 righe / 4,9 MB e
    +1.562 righe/giorno misurate sui dati del repo, cioè il limite GitHub di 100 MB per
    singolo file in ~230 giorni, con 5 run al giorno che ne riscrivono il blob in history.

    Tre comportamenti da tenere distinti: la riga oltre la finestra si pota, quella dentro
    resta, e una riga **senza data** non si butta (non si elimina un dato solo perché non
    se ne conosce l'età). Il conteggio finisce nell'imbuto di *Stato fonti*.
    """
    st = _store_con_fixtures(tmp_path)

    def iso(giorni: int) -> str:
        return (datetime.now(UTC) - timedelta(days=giorni)).isoformat()

    st.write("news", pd.DataFrame([
        {"team_id": 1, "published_at": iso(90), "title": "Vecchia", "url": "u/90",
         "source": "s", "description": ""},
        {"team_id": 1, "published_at": iso(5), "title": "Fresca", "url": "u/5",
         "source": "s", "description": ""},
        {"team_id": 1, "published_at": None, "title": "Senza data", "url": "u/nd",
         "source": "s", "description": ""},
    ]))
    collect_news(st, keys=["ITA1"], news=_FakeNews(), espn=_FakeEspn(), window_days=30)

    assert set(st.read("news")["title"]) == {"Fresca", "Senza data"}
    riga = st.read("source_status").query("source == 'news:NEWS'").iloc[0]
    assert "potate 1" in riga["detail"], riga["detail"]
    st.close()


def test_collect_news_non_pota_se_non_ce_nulla_di_vecchio(tmp_path):
    """Nessuna potatura inutile: l'archivio in finestra non viene riscritto."""
    st = _store_con_fixtures(tmp_path)
    recente = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    st.write("news", pd.DataFrame([
        {"team_id": 1, "published_at": recente, "title": "Fresca", "url": "u/2",
         "source": "s", "description": ""},
    ]))
    prima = st.path("news").read_bytes()
    collect_news(st, keys=["ITA1"], news=_FakeNews(), espn=_FakeEspn(), window_days=30)
    assert set(st.read("news")["title"]) == {"Fresca"}
    assert st.path("news").read_bytes() == prima, "riscrittura senza motivo (diff Git inutile)"
    assert "potate 0" in st.read("source_status").query("source == 'news:NEWS'").iloc[0]["detail"]
    st.close()


def test_la_ritenzione_delle_notizie_copre_le_finestre_di_lettura():
    """``NEWS_RETENTION_DAYS`` non è un numero libero: sta **sopra** chi legge la tabella.

    Due finestre leggono ``news``: la card «Vita del club» guarda 7 giorni indietro dal
    calcio d'inizio e il gate ``verify_site`` [20] ne verifica 12. Una ritenzione sotto
    quelle soglie farebbe sparire righe che il sito pubblica o che il gate ricalcola, e
    il difetto si vedrebbe solo in produzione. Scelta dell'utente 2026-09-18 (docs/26 §8).
    """
    import inspect

    from fda.collect import NEWS_RETENTION_DAYS, collect_news
    from fda.site.analysis import MatchAnalysis

    assert NEWS_RETENTION_DAYS >= 12, "sotto i 12 giorni il gate verify_site [20] perde righe"
    assert NEWS_RETENTION_DAYS >= MatchAnalysis.NEWS_WINDOW_DAYS, "sotto i 7 giorni la card si svuota"
    default = inspect.signature(collect_news).parameters["window_days"].default
    assert default == NEWS_RETENTION_DAYS, "il default deve essere la costante, non un numero a mano"
