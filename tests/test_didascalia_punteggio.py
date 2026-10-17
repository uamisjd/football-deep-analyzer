"""Didascalia del punteggio coerente con lo stato della gara (docs/41).

**Il difetto, misurato sul sito pubblicato.** Il 19/09/2026 alle 16:03 IT la pagina «Oggi»
mostrava **7 schede su 7** in corso con il punteggio live e la didascalia «calcio d'inizio»
(«Bologna **1–0** calcio d'inizio» con 63 minuti giocati), e l'hero della scheda partita
«**1–0** · calcio d'inizio · 15:00». La didascalia era binaria — `finished` → «finale»,
tutto il resto → «calcio d'inizio» — e nessun invariante di `verify_site` la leggeva: il gate
era verde con 151.316 controlli e il sito pubblicato era fermo su un'etichetta falsa.

Qui: la mappa stato → didascalia, la resa nelle liste e nell'hero su dati raccolti, e il morso
del nuovo invariante `[37]`.
"""

import importlib.util
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from fda.site.analysis import effective_match_state
from fda.site.build import SiteBuilder
from tests.test_site import _seed


def _site_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site_mod", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ogni_stato_ha_la_sua_didascalia():
    """La didascalia dice **che numero è**, non l'orario: un punteggio live non è un kickoff."""
    casi = {
        "finished": "finale", "full_time": "finale", "ft": "finale",
        "live": "in corso", "in_progress": "in corso", "started": "in corso",
        "unverified": "stato da verificare",
        "halftime": "intervallo", "half_time": "intervallo", "paused": "intervallo",
        "postponed": "rinviata", "suspended": "sospesa", "abandoned": "sospesa",
        "cancelled": "annullata", "canceled": "annullata",
        "scheduled": "calcio d'inizio", None: "calcio d'inizio", "": "calcio d'inizio",
    }
    for stato, attesa in casi.items():
        assert SiteBuilder.score_caption(stato) == attesa, stato


def test_stato_e_punteggio_finale_prevalgono_sulla_fotografia_non_finale():
    """Un finale in una delle due tabelle non regredisce a live/scheduled nell'altra."""
    da_dettagli = effective_match_state(
        {"status": "scheduled", "home_goals": None, "away_goals": None},
        {"status": "FT", "home_goals": 4, "away_goals": 0},
    )
    assert da_dettagli == {"status": "finished", "home_goals": 4, "away_goals": 0}

    da_fixture = effective_match_state(
        {"status": "finished", "home_goals": 2, "away_goals": 1},
        {"status": "live", "home_goals": 0, "away_goals": 0},
    )
    assert da_fixture == {"status": "finished", "home_goals": 2, "away_goals": 1}


def test_stato_in_cache_dopo_calcio_d_inizio_diventa_non_verificato():
    """Una pagina statica non deve spacciare stato programmato/live vecchio per dato attuale."""
    now = datetime(2026, 10, 16, 20, 0, tzinfo=UTC)
    def fixture(status: str, elapsed_minutes: int, goals=(0, 0)):
        kickoff = now - timedelta(minutes=elapsed_minutes)
        return {"status": status, "utc_kickoff": kickoff,
                "home_goals": goals[0], "away_goals": goals[1]}

    assert effective_match_state(fixture("scheduled", 29), now=now)["status"] == "scheduled"
    stale = effective_match_state(fixture("scheduled", 31), now=now)
    assert stale == {"status": "unverified", "home_goals": None, "away_goals": None}
    assert effective_match_state(fixture("live", 104), now=now)["status"] == "live"
    stale_live = effective_match_state(fixture("live", 106), now=now)
    assert stale_live == {"status": "unverified", "home_goals": None, "away_goals": None}


def test_build_marca_in_verifica_i_dati_partita_scaduti(tmp_path):
    """Punteggi e stati non aggiornati dopo il kickoff non appaiono come live o in programma."""
    st = _seed(tmp_path)
    match_id = 5749669
    now = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    fx = st.read("fixtures")
    mask = fx.match_id == match_id
    fx.loc[mask, "utc_kickoff"] = now - timedelta(hours=2)
    fx.loc[mask, "status"] = "scheduled"
    fx.loc[mask, "home_goals"] = None
    fx.loc[mask, "away_goals"] = None
    st.write("fixtures", fx)
    mi = st.read("match_info")
    mi.loc[mi.match_id == match_id, "utc_kickoff"] = now - timedelta(hours=2)
    mi.loc[mi.match_id == match_id, "status"] = "scheduled"
    mi.loc[mi.match_id == match_id, "home_goals"] = 0
    mi.loc[mi.match_id == match_id, "away_goals"] = 0
    st.write("match_info", mi)

    out = tmp_path / "sito"
    builder = SiteBuilder(store=st, out_dir=out)
    builder.now = now
    ids = builder.build_indexes(st.read("fixtures"))
    assert match_id in ids
    today = BeautifulSoup((out / "index.html").read_text(encoding="utf-8"), "html.parser")
    card = today.select_one(f'article.match-card[data-match-card] a[href="partite/{match_id}.html"]')
    assert card is not None
    article = card.find_parent("article")
    assert article["data-status"] == "unverified"
    assert article.select_one(".match-score strong").get_text(strip=True) == "vs"
    assert article.select_one(".match-score span").get_text(strip=True) == "stato da verificare"
    assert SiteBuilder._status_bucket("scheduled") == "scheduled"

    builder.build_match_pages({match_id})
    scheda = BeautifulSoup((out / "partite" / f"{match_id}.html").read_text(encoding="utf-8"), "html.parser")
    assert scheda.select_one(".match-hero .result").get_text(strip=True) == "vs"
    assert scheda.select_one(".match-hero .date").get_text(strip=True).startswith("stato non verificato")
    avviso = scheda.select_one('[role="status"]')
    assert avviso is not None and "Nessun punteggio live viene mostrato" in avviso.get_text(" ", strip=True)
    st.close()


def test_lista_risultati_e_scheda_usano_la_stessa_fotografia_finale(tmp_path):
    """Regressione del disaccordo fixture/details: la lista non può contraddire la scheda."""
    st = _seed(tmp_path)
    match_id = 5749669
    fx = st.read("fixtures")
    mask = fx.match_id == match_id
    fx.loc[mask, "utc_kickoff"] = datetime.now(UTC) - timedelta(days=1)
    fx.loc[mask, "status"] = "scheduled"
    fx.loc[mask, "home_goals"] = None
    fx.loc[mask, "away_goals"] = None
    st.write("fixtures", fx)
    mi = st.read("match_info")
    mi.loc[mi.match_id == match_id, "status"] = "finished"
    mi.loc[mi.match_id == match_id, "home_goals"] = 4
    mi.loc[mi.match_id == match_id, "away_goals"] = 0
    st.write("match_info", mi)

    out = tmp_path / "sito"
    builder = SiteBuilder(store=st, out_dir=out)
    ids = builder.build_indexes(st.read("fixtures"))
    assert match_id in ids
    builder.build_match_pages({match_id})

    risultati = BeautifulSoup((out / "risultati.html").read_text(encoding="utf-8"), "html.parser")
    card = risultati.find("a", href=f"partite/{match_id}.html").find_parent("article")
    assert card["data-status"] == "finished"
    assert card.select_one(".match-score strong").get_text(strip=True) == "4–0"
    assert card.select_one(".match-score span").get_text(strip=True) == "finale"

    scheda = BeautifulSoup((out / "partite" / f"{match_id}.html").read_text(encoding="utf-8"), "html.parser")
    assert scheda.select_one(".match-hero .result").get_text(strip=True) == "4–0"
    assert scheda.select_one(".match-hero .date").get_text(strip=True) == "risultato finale"
    st.close()


def test_gara_in_corso_non_dice_calcio_d_inizio(tmp_path):
    """Sulle pagine generate: in corso → «in corso», finita → «finale», da giocare → kickoff."""
    st = _seed(tmp_path)
    now = datetime.now(UTC)
    fx = st.read("fixtures")
    # la gara campione finita diventa **in corso** con il punteggio live (il caso reale del 19/09).
    # Lo stato e il punteggio vanno scritti anche in `match_info`: la scheda partita legge prima
    # quella tabella (`analysis.build`: `_val(info, "status") or f["status"]`).
    # «adesso − 1 ora» attraversa la mezzanotte italiana fra le 22:00 e le 23:00 UTC: la gara
    # finirebbe sul giorno precedente e la pagina «Oggi» — che filtra per data **locale**
    # (`build_indexes`, build.py) — non la conterrebbe più. Il test è saltato un'ora al giorno
    # dal 2026-09-19, quando è stato scritto: il calcio d'inizio resta ~1 ora fa ma non prima
    # della mezzanotte di oggi, così il risultato non dipende dall'ora in cui gira.
    adesso_roma = datetime.now(UTC).astimezone(ZoneInfo("Europe/Rome"))
    mezzanotte_roma = adesso_roma.replace(hour=0, minute=1, second=0, microsecond=0)
    fx.loc[fx.match_id == 5749645, "utc_kickoff"] = max(
        now - timedelta(hours=1), mezzanotte_roma.astimezone(UTC))
    fx.loc[fx.match_id == 5749645, "status"] = "live"
    fx.loc[fx.match_id == 5749645, "home_goals"] = 1
    fx.loc[fx.match_id == 5749645, "away_goals"] = 0
    st.write("fixtures", fx)
    mi = st.read("match_info")
    mi.loc[mi.match_id == 5749645, "status"] = "live"
    mi.loc[mi.match_id == 5749645, "home_goals"] = 1
    mi.loc[mi.match_id == 5749645, "away_goals"] = 0
    st.write("match_info", mi)

    out = tmp_path / "sito"
    builder = SiteBuilder(store=st, out_dir=out)
    builder.build_indexes(st.read("fixtures"))
    builder.build_match_pages({5749645, 5749669})

    lista = (out / "index.html").read_text(encoding="utf-8")
    card = re.search(r'data-status="live".*?<div class="match-score">.*?<span>(.*?)</span>',
                     lista, re.DOTALL)
    assert card, "la gara in corso non è nella pagina «Oggi»"
    assert card.group(1) == "in corso"
    # nessuna card con un punteggio giocato dice ancora «calcio d'inizio»
    for blocco in lista.split('<article class="match-card"')[1:]:
        stato = re.search(r'data-status="(\w+)"', blocco).group(1)
        scritta = re.search(r'<div class="match-score">.*?<span>(.*?)</span>', blocco,
                            re.DOTALL).group(1)
        if stato != "scheduled":
            assert scritta != "calcio d'inizio", (stato, scritta)
        else:
            assert scritta == "calcio d'inizio", "una gara da giocare resta «calcio d'inizio»"

    # l'hero della scheda: il punteggio live dichiara di essere live, l'orario resta leggibile.
    # (Il punteggio dell'hero viene dal contesto della gara, non dalla riga di `fixtures` che
    # questo test ha spostato: qui conta la didascalia, non il valore.)
    live = (out / "partite" / "5749645.html").read_text(encoding="utf-8")
    hero = re.search(r'<span class="result">(.*?)</span><span class="date">(.*?)</span>', live,
                     re.DOTALL)
    assert hero.group(1) != "vs", "una gara in corso ha un punteggio"
    assert hero.group(2).startswith("in corso · calcio d'inizio "), hero.group(2)

    # la gara futura campione non cambia: «vs» e «calcio d'inizio · HH:MM»
    futura = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    hero2 = re.search(r'<span class="result">(.*?)</span><span class="date">(.*?)</span>', futura,
                      re.DOTALL)
    assert hero2.group(1) == "vs"
    assert hero2.group(2).startswith("calcio d'inizio · "), hero2.group(2)
    st.close()


def test_verify_site_ferma_la_didascalia_sbagliata(tmp_path):
    """Morso dell'invariante [37]: il gate vede il difetto che era pubblicato e passa sul corretto."""
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    (site / "partite").mkdir()

    def card(stato: str, punteggio: str, didascalia: str) -> str:
        return (f'<article class="match-card" data-status="{stato}">'
                f'<div class="match-score"><strong>{punteggio}</strong>'
                f'<span>{didascalia}</span></div></article>')

    # il difetto reale: punteggio live con didascalia «calcio d'inizio»
    (site / "index.html").write_text(card("live", "1–0", "calcio d'inizio")
                                     + card("finished", "2–3", "finale")
                                     + card("scheduled", "vs", "calcio d'inizio"),
                                     encoding="utf-8")
    # e lo stesso nell'hero della scheda
    (site / "partite" / "1.html").write_text(
        '<span class="result">1–0</span><span class="date">calcio d\'inizio · 15:00</span>',
        encoding="utf-8")
    fails, checks = vs.check_didascalie_punteggio(site)
    assert checks == 4                       # 3 card + 1 hero
    assert any('didascalia «calcio d\'inizio» su una gara «live»' in f for f in fails), fails
    assert any("hero «1–0» con didascalia" in f for f in fails), fails
    # le due card corrette non sono segnalate
    assert len(fails) == 2, fails

    # stesso sito, didascalie giuste → il gate passa
    (site / "index.html").write_text(card("live", "1–0", "in corso")
                                     + card("finished", "2–3", "finale")
                                     + card("scheduled", "vs", "calcio d'inizio"),
                                     encoding="utf-8")
    (site / "partite" / "1.html").write_text(
        '<span class="result">1–0</span><span class="date">in corso · calcio d\'inizio 15:00</span>',
        encoding="utf-8")
    fails, checks = vs.check_didascalie_punteggio(site)
    assert checks == 4 and fails == []


def test_verify_site_ferma_la_discordanza_fra_card_e_scheda(tmp_path):
    """Il nuovo gate [51] intercetta stati o punteggi diversi attraversando un link."""
    vs = _site_module()
    site = tmp_path / "site"
    (site / "partite").mkdir(parents=True)
    (site / "index.html").write_text(
        '<article class="match-card" data-status="finished">'
        '<a href="partite/1.html">Apri</a>'
        '<div class="match-score"><strong>4–0</strong><span>finale</span></div></article>',
        encoding="utf-8",
    )
    detail = site / "partite" / "1.html"
    detail.write_text(
        '<div class="match-hero"><span class="result">4–0</span>'
        '<span class="date">risultato finale</span></div>', encoding="utf-8")
    fails, checks = vs.check_match_state_parity(site)
    assert checks == 1 and fails == []

    detail.write_text(
        '<div class="match-hero"><span class="result">0–0</span>'
        '<span class="date">calcio d\'inizio · 15:00</span></div>', encoding="utf-8")
    fails, checks = vs.check_match_state_parity(site)
    assert checks == 1
    assert any("card «finished» ma scheda «scheduled»" in f for f in fails), fails
    assert any("card «4–0» ma hero «0–0»" in f for f in fails), fails


def test_percentile_ids_ordine_dichiarato_su_ogni_hash_seed():
    """`docs/40` §5.1: l'ordine delle card «Percentili di lega» non dipende più dal processo.

    Con il `set` due build **dello stesso codice** davano 2.074 schede giocatore su 3.748 in
    sequenza diversa (misurato); qui la stessa chiamata è eseguita in quattro processi con
    `PYTHONHASHSEED` diversi e l'ordine deve essere identico e uguale a quello dichiarato.
    """
    from fda.site.players import PCT_EXTRA, RADAR, percentile_ids

    codice = ("from fda.site.players import percentile_ids;"
              "print('|'.join(f'{p}:' + ','.join(percentile_ids(p)) for p in (0, 1, 2, 3)))")
    uscite = set()
    for seed in ("0", "1", "2", "7"):
        # l'ambiente del test resta intatto (in CI l'interprete può dipendere da variabili sue):
        # cambia solo il seed dell'hash, che è ciò che prima spostava l'ordine
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True,
                              env=env, check=True, cwd=str(Path(__file__).resolve().parents[1]))
        uscite.add(proc.stdout.strip())
    assert len(uscite) == 1, f"l'ordine cambia con l'hash seed: {uscite}"
    for pos in (0, 1, 2, 3):
        assert percentile_ids(pos) == [s for s, _ in RADAR[pos]] + PCT_EXTRA[pos]


def test_scala_della_barra_tollera_il_doppio_arrotondamento():
    """Il 2026-09-19 il run giornaliero si è fermato su 22 pagine: la scala stampata con una
    cifra («2,0») veniva confrontata col percentile grezzo (2,0503) con tolleranza 0,05,
    mentre il generatore arrotonda a due cifre **prima** di stampare (issue #65)."""
    mod = _site_module()
    casi_ok = [(2.0, 2.0503), (2.1, 2.0503), (3.4, 3.38), (2.0, 2.0), (2.5, 2.5)]
    casi_ko = [(2.5, 2.0503), (2.0, 3.1), (3.9, 3.38)]
    for pubblicato, percentile in casi_ok:
        assert mod._scala_ok(pubblicato, percentile), (pubblicato, percentile)
    for pubblicato, percentile in casi_ko:
        assert not mod._scala_ok(pubblicato, percentile), (pubblicato, percentile)
