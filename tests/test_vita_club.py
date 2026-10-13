"""Vita del club (docs/96): dati deterministici, conti chiusi e assenze non interpretate."""

from pathlib import Path

import pandas as pd
import pytest

from fda.site import analysis as module
from fda.site.analysis import MatchAnalysis, news_quiet_line, news_title_key
from fda.site.build import SiteBuilder
from fda.site.club_news import title_exclusion, whole_phrase
from fda.store import Store

NOW = pd.Timestamp("2026-10-12T12:00:00Z")
KO = NOW + pd.Timedelta(days=2)
BUCKETS = ("pubblicate", "scartate", "annunci", "piatti", "altre", "doppioni", "lingua",
           "bassa_reputazione", "oltre", "fuori_ambito", "senza_segnale", "correlate")


def seed(tmp_path, rows):
    store = Store(tmp_path / "data")
    store.write("fixtures", pd.DataFrame([{
        "match_id": 1, "utc_kickoff": KO, "league_id": 55, "status": "scheduled",
        "home_id": 1, "home_name": "Inter", "away_id": 2, "away_name": "Roma",
        "home_goals": None, "away_goals": None,
    }]))
    defaults = {"team_id": 1, "published_at": NOW - pd.Timedelta(hours=1), "description": "",
                "source": "ANSA", "url": "https://example.org/article"}
    store.write("news", pd.DataFrame([{**defaults, **r} for r in rows]))
    return store, MatchAnalysis(store)


def news(ma, **kwargs):
    return ma.team_news(1, "Inter", KO, now=NOW, **kwargs)


def assert_closed(nw):
    assert nw["esaminate"] == sum(nw[k] for k in BUCKETS) + len(nw["riserva"])
    assert nw["oltre"] == nw["oltre_categoria"] + nw["oltre_capienza"]


@pytest.mark.parametrize("title,reason", [
    ("Formazioni CDA Navalcarnero - Betis Siviglia: Coppa del Re Calcio", "scartate"),
    ("Statistiche CDA Navalcarnero - Betis Siviglia: Risultati Calcio", "scartate"),
    ("Udinese, Alaba si presenta: qui mi sento già a casa", "annunci"),
    ("Alaba: l'Udinese è la squadra giusta per me", "piatti"),
    ("Torino, Cacciamani orgoglioso della maglia: mi ispiro a Bale", "piatti"),
    ("Torino - Cacciamani: orgoglioso di vestire questa maglia", "piatti"),
    ("Nuovo asse Juve-Bayern: chi è il 2009 che ha sfiorato un record", "piatti"),
    ("Real Madrid-Villarreal LIVE! Cronaca e aggiornamenti in tempo reale", "scartate"),
    ("Napoli, i convocati per il Frosinone: tornano due giocatori", "scartate"),
    ("Atalanta-Venezia, le ultime: Raspadori convocato, recuperi in difesa", "scartate"),
    ("Torino-Udinese, Alaba pronto per l'esordio", "scartate"),
    ("La Nazionale aiuta Abate: Rodriguez è pronto a riprendersi il posto", "scartate"),
    ("Incontro per i media con il tecnico Abate", "annunci"),
    ("Nestor Sensini compie 60 anni: l'Udinese e la famiglia", "annunci"),
    ("APPLAUSI ALLO STADIO DI COMO PER I CAMPIONI DEL MONDO", "annunci"),
    ("Udinese Academy, una nuova alleanza per i giovani talenti", "fuori_ambito"),
    ("Le parole di Alberto Aquilani al termine di Sassuolo-Milan", "piatti"),
    ("Cagliari Juventus, intervista Elia Caprile", "piatti"),
    ("Il Genoa batte la Fiorentina e si vendica sui social", "piatti"),
    ("Serie A: doppio gol, il Napoli stende il Frosinone al Maradona", "piatti"),
])
def test_veti_sui_titoli_misurati(title, reason):
    assert title_exclusion(title) == reason


@pytest.mark.parametrize("title", [
    "Inter, il capitano escluso dai convocati per motivi disciplinari",
    "Inter, incontro per i media dopo l'esonero del tecnico",
    "Inter, il dirigente si presenta in procura dopo la denuncia", 
    "Inter Academy: inchiesta della procura sui conti",
    "Gilgeous-Alexander diventa azionista dell'Atlético Madrid",
    "Juventus, sciopero della curva dopo i provvedimenti",
    "Stadio, il tribunale respinge il ricorso del club",
    "Roma, la proprietà smentisce la vendita",
    "Spalletti-Pisacane: lite, quasi rissa e doppio rosso",
])
def test_eventi_specifici_non_cadono_per_la_sola_parola_chiave(title):
    assert title_exclusion(title) is None


def test_versione_piu_recente_e_invarianza_all_ordine(tmp_path):
    title = "Inter, ricorso respinto: la multa resta"
    st, ma = seed(tmp_path, [
        {"title": title, "published_at": NOW - pd.Timedelta(hours=30)},
        {"title": title, "published_at": NOW - pd.Timedelta(hours=2)},
        {"title": "Inter, la proprietà smentisce la vendita", "url": "https://example.org/other"},
    ])
    first = news(ma)
    ma.news_df = ma.news_df.iloc[::-1]
    second = news(ma)
    assert first == second
    chosen = next(n for n in first["notizie"] if n["title"] == title)
    assert chosen["published_at"] == NOW - pd.Timedelta(hours=2)
    assert first["doppioni"] == 1
    assert_closed(first)
    st.close()


def test_una_copia_inammissibile_non_cancella_quella_buona(tmp_path):
    title = "Inter, la proprietà smentisce la vendita del club"
    _, ma = seed(tmp_path, [{"title": title, "published_at": NOW - pd.Timedelta(hours=3)},
                           {"title": title, "published_at": NOW - pd.Timedelta(hours=1), "source": "The Sun"}])
    result = news(ma)
    assert result["pubblicate"] == 1 and result["notizie"][0]["source"] == "ANSA"
    assert result["bassa_reputazione"] == 1
    assert_closed(result)


def many_candidates(tmp_path, monkeypatch):
    rows = [{"title": f"Inter, evento numero {i}", "url": f"https://example.org/{i}",
             "published_at": NOW - pd.Timedelta(hours=i + 1)} for i in range(8)]
    st, ma = seed(tmp_path, rows)
    monkeypatch.setattr(module, "is_italian_news", lambda *a: True)
    from fda.site.club_signals import ClubSignal

    topics = ["societa", "allenatore", "tifo", "stadio"] * 2
    monkeypatch.setattr(module, "club_signal", lambda title: ClubSignal(
        "event", topics[int(title.split()[-1])], "Controllo strutturale", title, title))
    return st, ma


def test_imbuto_include_anche_le_voci_oltre_la_riserva(tmp_path, monkeypatch):
    _, ma = many_candidates(tmp_path, monkeypatch)
    result = news(ma)
    assert result["esaminate"] == 8 and result["pubblicate"] == 3
    assert len(result["riserva"]) == 2 and result["oltre_capienza"] == 3
    assert result["oltre_categoria"] == 0
    assert_closed(result)


def test_condividere_solo_i_titoli_effettivamente_esposti(tmp_path, monkeypatch):
    _, ma = many_candidates(tmp_path, monkeypatch)
    seen = set()
    result = news(ma, seen=seen)
    exposed = {news_title_key(n["title"]) for n in result["notizie"] + result["riserva"]}
    assert seen == exposed and len(seen) == 5
    # Una voce oltre la capienza non è già raccontata nell'altra colonna.
    assert len({news_title_key(t) for t in ma.news_df.title} - seen) == 3


def test_parole_intere_e_altro_club_in_testa(tmp_path):
    assert not whole_phrase("il romanzo di romagnoli", "roma")
    assert whole_phrase("a roma si protesta", "roma")
    assert whole_phrase("i tifosi allatalanta chiedono risposte", "atalanta")
    assert whole_phrase("la protesta dellinter", "inter")
    assert not whole_phrase("un aroma speciale", "roma")
    assert not whole_phrase("uninteressante prospettiva", "inter")
    _, ma = seed(tmp_path, [{"title": "Milan, crisi della squadra: il confronto con l'Inter"}])
    ma._club_tokens = {"milan", "inter", "roma"}
    result = news(ma)
    assert result["pubblicate"] == 0 and result["altre"] == 1
    assert_closed(result)


@pytest.mark.parametrize("days,state", [(16, "future"), (14, "open"), (2, "open"), (0, "ended"), (-1, "ended")])
def test_stato_temporale_dichiarato_anche_senza_notizie(tmp_path, days, state):
    st = Store(tmp_path / "data")
    result = MatchAnalysis(st).team_news(1, "Inter", NOW + pd.Timedelta(days=days), now=NOW)
    assert result["window_state"] == state and result["esaminate"] == 0
    assert result["window_end"] - result["window_start"] == pd.Timedelta(days=14)
    quiet = news_quiet_line(result, result, "Inter", "Roma")
    assert "nella finestra pre-partita" in quiet["riga"] and "negli ultimi" not in quiet["riga"]


def test_pubblicazione_futura_esclusa_anche_se_prima_del_match(tmp_path):
    _, ma = seed(tmp_path, [
        {"title": "Inter, la proprietà smentisce la vendita"},
        {"title": "Inter, il tecnico rischia l'esonero", "published_at": NOW + pd.Timedelta(minutes=1)},
    ])
    result = news(ma)
    assert result["esaminate"] == 1 and len(result["notizie"]) == 1
    assert all(n["published_at"] <= NOW for n in result["notizie"])
    assert_closed(result)


@pytest.mark.parametrize("raw,phrase", [("confirmed", "ufficiale"), ("predicted", "non confermata"),
                                        ("lastStarting11", "non in quella di questa gara"), (None, "tipo non dichiarato")])
def test_perche_conta_non_promette_un_titolare_confermato(tmp_path, raw, phrase):
    _, ma = seed(tmp_path, [{"title": "Inter, Mario Rossi multato dal club per una frase"}])
    result = news(ma, squad=[{"name": "Mario Rossi", "status": "starter"}], lineup_type=raw)
    assert result["pubblicate"] == 1 and phrase in result["notizie"][0]["why"]


def render_card(tmp_path, st, ma, *, kickoff=KO):
    seen = set()
    h = ma.team_news(1, "Inter", kickoff, now=NOW, seen=seen)
    a = ma.team_news(2, "Roma", kickoff, now=NOW, seen=seen)
    ctx = {"home_id": 1, "home_name": "Inter", "away_id": 2, "away_name": "Roma",
           "home_news": h, "away_news": a, "news_sapere": [],
           "news_quiet": news_quiet_line(h, a, "Inter", "Roma")}
    text = (Path(__file__).parents[1] / "src/fda/site/templates/match.html").read_text()
    start = text.index('  <div class="card" id="notizie">')
    end = text.index('\n  </div>', start) + len('\n  </div>')
    builder = SiteBuilder(store=st, out_dir=tmp_path / "site")
    html = builder.env.from_string(text[start:end]).render(c=ctx)
    directory = tmp_path / "html/partite"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "1.html"
    path.write_text('<h1>Analisi pre-partita</h1>' + html + '<footer></footer>')
    return path


def test_date_assolute_e_incompletezza_nel_template(tmp_path):
    st, ma = seed(tmp_path, [{"title": "Inter, ricorso respinto: la multa resta"}])
    path = render_card(tmp_path, st, ma)
    text = path.read_text()
    assert "Finestra ancora aperta" in text and 'data-window-start=' in text
    assert 'datetime="2026-10-12T11:00:00+00:00"' in text
    assert "Niente che possa spostare qualcosa" not in text
    assert "negli ultimi 7 giorni" not in text
    assert 'class="news-team" data-team-id="1"' in text


@pytest.mark.parametrize("defect", ["count", "date", "title", "url", "source", "window", "coverage"])
def test_oracolo_vede_le_mutazioni_senza_chiamare_team_news(tmp_path, monkeypatch, defect):
    from bs4 import BeautifulSoup

    from fda.site.club_news_checks import audit_club_life

    st, ma = seed(tmp_path, [{"title": "Inter, ricorso respinto: la multa resta"}])
    path = render_card(tmp_path, st, ma)
    assert audit_club_life(path.parents[1], st.base_dir)["defects"] == 0
    soup = BeautifulSoup(path.read_text(), "html.parser")
    card = soup.find(id="notizie")
    if defect == "count":
        head = card.select_one(".news-team .imbuto")
        text = head.get_text(" ", strip=True).replace("1 voce esaminata", "2 voci esaminate")
        head.clear()
        head.append(text)
    elif defect == "date":
        card.select_one("li time")["datetime"] = (KO + pd.Timedelta(minutes=1)).isoformat()
    elif defect == "title":
        card.select_one("li a").string = "Un titolo inventato"
    elif defect == "url":
        card.select_one("li a")["href"] = "https://example.org/altro"
    elif defect == "source":
        card.select_one("li .news-source").string = "Un'altra testata"
    elif defect == "window":
        card.select_one(".news-window")["data-window-start"] = KO.isoformat()
    else:
        card.select_one(".news-window").clear()
        card.select_one(".news-window").append("Settimana non ancora iniziata")
    path.write_text(str(soup))
    monkeypatch.setattr(MatchAnalysis, "team_news", lambda *a, **k: pytest.fail("oracolo accoppiato"))
    assert audit_club_life(path.parents[1], st.base_dir)["defects"] > 0


def test_sezione_e_indice_restano_anche_senza_notizie_o_da_sapere(tmp_path, monkeypatch):
    from tests.test_site import _seed

    st = _seed(tmp_path)
    builder = SiteBuilder(store=st, out_dir=tmp_path / "site")
    builder.analysis.news_df = pd.DataFrame()
    monkeypatch.setattr(builder.analysis, "news_sapere", lambda *a, **k: [])
    builder.build_match_pages({5749669})
    html = (tmp_path / "site/partite/5749669.html").read_text()
    assert 'id="notizie"' in html and 'href="#notizie"' in html
    assert "Nessuna voce raccolta" in html


def test_settimana_futura_non_diventa_silenzio_della_stampa(tmp_path):
    st, ma = seed(tmp_path, [{"title": "Inter, ricorso respinto: la multa resta"}])
    path = render_card(tmp_path, st, ma, kickoff=NOW + pd.Timedelta(days=16))
    text = path.read_text()
    assert "Settimana non ancora iniziata" in text
    assert "il vuoto non indica assenza di notizie importanti" in text


def test_nomi_brevi_e_prefissi_condivisi_non_scartano_la_squadra_corrente(tmp_path):
    """Club con nome di 3-4 lettere (Lens, PSG, Ajax, Roma) e prefissi condivisi (Real, Borussia)."""
    _, ma = seed(tmp_path, [
        {"title": "Lens, ufficiale: il capitano rinnova fino al 2029", "url": "u1"},
        {"title": "Real Sociedad, svolta Alguacil: la rimonta rilancia la squadra", "url": "u2"},
    ])
    res_lens = ma.team_news(1, "Lens", KO, opponent="Nizza", now=NOW)
    assert res_lens["pubblicate"] >= 1
    res_soc = ma.team_news(1, "Real Sociedad", KO, opponent="Valencia", now=NOW)
    assert res_soc["pubblicate"] >= 1


def test_dati_di_contesto_aperti_per_default_sulla_scheda(tmp_path):
    st, ma = seed(tmp_path, [{"title": "Inter, ricorso respinto: la multa resta"}])
    seen = set()
    h = ma.team_news(1, "Inter", KO, now=NOW, seen=seen)
    a = ma.team_news(2, "Roma", KO, now=NOW, seen=seen)
    ctx = {"home_id": 1, "home_name": "Inter", "away_id": 2, "away_name": "Roma",
           "home_news": h, "away_news": a,
           "news_sapere": [{"tag": "Squalifica", "testo": "Mario Rossi salta la gara."}],
           "news_quiet": news_quiet_line(h, a, "Inter", "Roma")}
    text = (Path(__file__).parents[1] / "src/fda/site/templates/match.html").read_text()
    start = text.index('  <div class="card" id="notizie">')
    end = text.index('\n  </div>', start) + len('\n  </div>')
    builder = SiteBuilder(store=st, out_dir=tmp_path / "site")
    html = builder.env.from_string(text[start:end]).render(c=ctx)
    assert '<details class="news-context" open>' in html

