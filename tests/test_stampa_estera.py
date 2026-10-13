"""Test offline della card «stampa in lingua originale» (docs/106).

Nessuna rete: vocabolario, parser RSS e store sintetici. I titoli sono presi da feed reali
del 2026-10-13 (Eredivisie e Liga Portugal), così i test misurano il caso vero e non uno
inventato per farli passare.
"""


from pathlib import Path

import pandas as pd

from fda.config import leagues
from fda.site.analysis import MatchAnalysis, news_quiet_line
from fda.site.estero import TEMI, sintesi_estera
from fda.sources.news import EDITIONS, edition_language, editions_for, parse_rss
from fda.store import Store

KO = lambda s: pd.Timestamp(s, tz="UTC")

NL = {"editions": ["nl"], "lingua": "nl", "label": "olandese"}
PT = {"editions": ["pt"], "lingua": "pt", "label": "portoghese"}

# Titoli veri, dal feed olandese del 2026-10-13 (nessuna modifica).
VERI_NL = [
    ("Mark Smith speelde met Mertens en Chadli en staat nu voor het eerst op eigen benen "
     + "als hoofdtrainer", "panchina"),
    ("Zonneveld openhartig over salaris: 'Dat is niet zo'n heel groot verschil'", "dichiarazione"),
    ("Afgelopen | Sparta Rotterdam - Feyenoord (0-1)", None),
    ("Teruglezen Eredivisie | Vreugde bij PEC na zwaarbevochten zege op Heerenveen", None),
    # il pareggio c'è, ma la notizia del titolo è la dichiarazione: l'ordine di
    # priorità è dichiarato e vince il tema più vicino alla partita
    ("Go Ahead Eagles speelt gelijk tegen Sparta Rotterdam: 'Ik ben teleurgesteld'",
     "dichiarazione"),
]

RSS_NL = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>SC Heerenveen, blessure voor de spits - FeanOnline</title>
<link>https://esempio.nl/1</link><pubDate>Mon, 12 Oct 2026 12:29:00 GMT</pubDate>
<description>brano</description></item>
</channel></rss>"""


def _store(tmp_path, nome, rows):
    st = Store(tmp_path / nome)
    if rows is not None:
        st.write("news", pd.DataFrame(rows))
    return st


def _riga(team_id, quando, titolo, lingua="nl", url=None, fonte="FeanOnline"):
    return {"team_id": team_id, "published_at": KO(quando), "title": titolo,
            "url": url or f"https://esempio.nl/{abs(hash(titolo))}", "source": fonte,
            "description": "", "language": lingua}


# --------------------------------------------------------------------------------------
# Vocabolario (fda.site.estero)
# --------------------------------------------------------------------------------------

def test_titoli_veri_classificati_o_dichiarati_non_classificabili():
    """Il vocabolario è chiuso: se non riconosce, dice di non riconoscere."""
    for titolo, atteso in VERI_NL:
        s = sintesi_estera(titolo, "nl")
        assert (s.chiave if s else None) == atteso, titolo


def test_ogni_tema_ha_almeno_una_espressione_per_lingua():
    for chiave, _etichetta, _nota, lingue in TEMI:
        assert set(lingue) == {"nl", "pt"}, chiave


def test_evidenza_e_una_porzione_del_titolo_originale():
    titolo = "Benfica sofre desfalque importante para o clássico"
    s = sintesi_estera(titolo, "pt")
    assert s is not None and s.chiave == "infortunio"
    assert s.evidenza.lower() in titolo.lower()


def test_priorita_fissa_fra_temi_concorrenti():
    """Un titolo con infortunio E mercato prende il tema più vicino alla partita."""
    s = sintesi_estera("Blessure voor de spits, maar de transfer is rond", "nl")
    assert s is not None and s.chiave == "infortunio"


def test_pagine_di_servizio_escluse_in_entrambe_le_lingue():
    for titolo, lingua in [
        ("Teruglezen Eredivisie | Vreugde bij PEC na zwaarbevochten zege op Heerenveen", "nl"),
        ("SC Heerenveen - Telstar: opstellingen en live updates", "nl"),
        ("Benfica x Porto: onde assistir ao vivo, escalações e palpites", "pt"),
        ("Cinco jogos de hoje: resultados e resumo da jornada", "pt"),
    ]:
        assert sintesi_estera(titolo, lingua) is None, titolo


def test_lingua_non_coperta_o_titolo_vuoto():
    assert sintesi_estera("Some English title about a transfer", "en") is None
    assert sintesi_estera("", "nl") is None
    assert sintesi_estera(None, "nl") is None
    assert sintesi_estera("Transfer nieuws", None) is None


def test_portoghese_classifica_infortunio_e_contratto():
    assert sintesi_estera("Sporting renova contrato com jogador até 2029", "pt").chiave == "contratto"
    assert sintesi_estera("Braga com desfalque para o próximo jogo", "pt").chiave == "infortunio"


# --------------------------------------------------------------------------------------
# Raccolta (edizioni dichiarate)
# --------------------------------------------------------------------------------------

def test_edizioni_per_squadra_sempre_italiana_piu_locali():
    assert editions_for(None) == [EDITIONS["it"]]
    assert editions_for(None, ["nl"]) == [EDITIONS["it"], EDITIONS["nl"]]
    assert editions_for(None, ["xx"]) == [EDITIONS["it"]]      # codice non dichiarato: ignorato
    assert editions_for(None, ["nl", "nl"]) == [EDITIONS["it"], EDITIONS["nl"]]


def test_edition_language_riconosce_le_tre_edizioni():
    assert edition_language(EDITIONS["it"]) == "it"
    assert edition_language(EDITIONS["nl"]) == "nl"
    assert edition_language(EDITIONS["pt"]) == "pt"


def test_parse_rss_scrive_la_lingua_dell_edizione():
    righe = parse_rss(RSS_NL, 1, language="nl")
    assert len(righe) == 1 and righe[0]["language"] == "nl"
    assert righe[0]["title"] == "SC Heerenveen, blessure voor de spits"
    assert righe[0]["source"] == "FeanOnline"
    assert parse_rss(RSS_NL, 1)[0]["language"] == "it"        # default: edizione italiana


def test_configurazione_dichiara_le_edizioni_solo_dove_servono():
    per_chiave = {lg.key: dict(lg.news or {}) for lg in leagues()}
    assert per_chiave["NED1"]["editions"] == ["nl"] and per_chiave["NED1"]["label"] == "olandese"
    assert per_chiave["POR1"]["editions"] == ["pt"]
    for key in ("ITA1", "ENG1", "ESP1", "GER1", "FRA1"):
        assert not per_chiave[key], key


# --------------------------------------------------------------------------------------
# Card (MatchAnalysis.stampa_estera)
# --------------------------------------------------------------------------------------

def test_card_attiva_solo_con_edizione_dichiarata(tmp_path):
    st = _store(tmp_path, "senza_edizioni", [_riga(1, "2026-10-12 10:00", "Blessure bij de spits")])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), {})
    assert out["attiva"] is False and out["voci"] == []
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"),
                                          {"editions": ["nl"], "lingua": "pt", "label": "portoghese"})
    assert out["attiva"] is False   # edizioni dichiarate ma lingua diversa: nessuna card


def test_pubblica_la_voce_della_squadra_con_etichetta_italiana(tmp_path):
    st = _store(tmp_path, "estera_base", [
        _riga(1, "2026-10-12 10:00", "SC Heerenveen, blessure voor de spits"),
        _riga(1, "2026-10-11 10:00", "PSV-huurling schittert bij nieuwe club"),
    ])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL)
    assert out["attiva"] and out["pubblicate"] == 1
    v = out["voci"][0]
    assert v["etichetta"] == "Infortunio" and v["lingua"] == "nl"
    assert v["evidenza"].lower() in v["titolo"].lower()
    assert out["esaminate"] == 2 and out["fuori_ambito"] == 1   # il secondo è del PSV


def test_le_righe_italiane_non_entrano_nella_card_estera(tmp_path):
    st = _store(tmp_path, "estera_ita", [
        _riga(1, "2026-10-12 10:00", "Heerenveen, infortunio per l'attaccante", lingua="it"),
    ])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL)
    assert out["esaminate"] == 0 and out["pubblicate"] == 0


def test_senza_colonna_lingua_l_archivio_e_tutto_italiano(tmp_path):
    """L'archivio scritto prima di docs/106 non ha la colonna: non deve finire qui."""
    st = _store(tmp_path, "estera_no_col", [
        {"team_id": 1, "published_at": KO("2026-10-12 10:00"),
         "title": "SC Heerenveen, blessure voor de spits", "url": "u1", "source": "X",
         "description": ""},
    ])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL)
    assert out["esaminate"] == 0


def test_conta_ogni_esito_dell_imbuto(tmp_path):
    st = _store(tmp_path, "estera_imbuto", [
        _riga(1, "2026-10-12 10:00", "SC Heerenveen, blessure voor de spits", url="u1"),
        _riga(1, "2026-10-12 09:00", "SC Heerenveen - Telstar: opstellingen en live", url="u2"),
        _riga(1, "2026-10-12 08:00", "Advertentie", url="u3"),
        _riga(1, "2026-10-12 07:00", "SC Heerenveen, blessure voor de spits", url="u1"),
        _riga(1, "2026-10-12 06:00", "Code rood in Friesland", url="u4"),
    ])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL)
    assert out["esaminate"] == 5 and out["pubblicate"] == 1
    assert out["doppioni"] == 1            # stesso URL
    assert out["non_classificate"] == 1    # pagina di servizio
    assert out["fuori_ambito"] == 2        # «Advertentie» e «Code rood» non sono la squadra


def test_limite_di_tre_voci_e_due_per_tema(tmp_path):
    righe = []
    for i, titolo in enumerate([
        "SC Heerenveen, blessure voor speler A",
        "SC Heerenveen, blessure voor speler B",
        "SC Heerenveen, blessure voor speler C",     # terzo infortunio: oltre il tema
        "SC Heerenveen haalt een nieuwe spits",     # mercato
        "SC Heerenveen verlengt contract speler D",  # contratto
    ]):
        righe.append(_riga(1, f"2026-10-{12 - i:02d} 10:00", titolo, url=f"u{i}"))
    an = MatchAnalysis(_store(tmp_path, "estera_limiti", righe))
    out = an.stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL)
    assert out["pubblicate"] == 3
    assert sum(1 for v in out["voci"] if v["chiave"] == "infortunio") == 2
    assert out["oltre_tema"] == 1 and out["oltre_capienza"] == 1


def test_finestra_pre_partita_e_voci_vecchie_contate(tmp_path):
    st = _store(tmp_path, "estera_finestra", [
        _riga(1, "2026-09-01 10:00", "SC Heerenveen, blessure voor de spits", url="u1"),
        _riga(1, "2026-10-20 10:00", "SC Heerenveen, blessure voor de spits", url="u2"),
    ])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL,
                                          now=KO("2026-10-14 12:00"))
    assert out["esaminate"] == 0 and out["vecchie"] == 0  # 01/09 è oltre i 45 giorni di orizzonte
    assert out["window_state"] == "open"
    st2 = _store(tmp_path, "estera_finestra2", [
        _riga(1, "2026-10-01 10:00", "SC Heerenveen, blessure voor de spits", url="u1"),
        _riga(1, "2026-10-03 10:00", "SC Heerenveen, blessure voor de spits", url="u2"),
    ])
    out2 = MatchAnalysis(st2).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL,
                                            now=KO("2026-10-14 12:00"))
    assert out2["esaminate"] == 1     # solo la riga del 03/10 è nella finestra dei 14 giorni
    assert out2["vecchie"] == 1       # quella del 01/10 è contata, non nascosta
    assert out2["pubblicate"] == 1


def test_il_gate_di_soggetto_riconosce_giocatori_e_allenatore(tmp_path):
    st = _store(tmp_path, "estera_soggetto", [
        _riga(1, "2026-10-12 10:00", "Blessure voor Zonneveld: out voor de wedstrijd", url="u1"),
    ])
    squad = [{"name": "Zonneveld"}]
    an = MatchAnalysis(st)
    out = an.stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL, squad=squad)
    assert out["pubblicate"] == 1
    out2 = an.stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL, coach="Mark Smith")
    assert out2["pubblicate"] == 0      # né squadra né giocatore né allenatore nel titolo


def test_ordinamento_per_priorita_del_tema(tmp_path):
    st = _store(tmp_path, "estera_ordine", [
        _riga(1, "2026-10-12 10:00", "SC Heerenveen verlengt contract speler D", url="u1"),
        _riga(1, "2026-10-09 10:00", "SC Heerenveen, blessure voor de spits", url="u2"),
    ])
    out = MatchAnalysis(st).stampa_estera(1, "SC Heerenveen", KO("2026-10-16 18:00"), NL)
    assert [v["chiave"] for v in out["voci"]] == ["infortunio", "contratto"]


def test_card_portoghese(tmp_path):
    st = _store(tmp_path, "estera_pt", [
        {"team_id": 7, "published_at": KO("2026-10-18 10:00"),
         "title": "Braga com desfalque para o jogo", "url": "p1", "source": "Record",
         "description": "", "language": "pt"},
    ])
    out = MatchAnalysis(st).stampa_estera(7, "Braga", KO("2026-10-19 19:00"), PT,
                                          now=KO("2026-10-19 12:00"))
    assert out["pubblicate"] == 1 and out["voci"][0]["etichetta"] == "Infortunio"
    assert out["label"] == "portoghese"


# --------------------------------------------------------------------------------------
# Riga unica della card quando la rassegna italiana è vuota
# --------------------------------------------------------------------------------------

def test_riga_di_quiete_dichiara_anche_la_stampa_estera():
    vuoto = {"notizie": [], "riserva": [], "esaminate": 12, "vecchie": 0, "finestra": 14,
             "lingua": 9, "doppioni": 3}
    base = news_quiet_line(vuoto, vuoto, "SC Heerenveen", "Telstar")
    assert base is not None and "stampa in lingua originale" not in base["riga"]
    con_estera = news_quiet_line(vuoto, vuoto, "SC Heerenveen", "Telstar", estera=2)
    assert "stampa in lingua originale" in con_estera["riga"]
    assert "2 voci" in con_estera["riga"] and con_estera["estera"] == 2


def test_riga_di_quiete_non_compare_se_la_rassegna_italiana_ha_qualcosa():
    pieno = {"notizie": [{"title": "x"}], "riserva": [], "esaminate": 1, "vecchie": 0,
             "finestra": 14}
    assert news_quiet_line(pieno, pieno, "A", "B", estera=3) is None


# --------------------------------------------------------------------------------------
# Misura congelata sui feed reali del 2026-10-13
# --------------------------------------------------------------------------------------

def test_misura_sui_titoli_veri_del_13_10():
    """La resa reale misurata il 2026-10-13, congelata per accorgersi se il vocabolario deriva.

    Prima: 0 voci pubblicabili su 10 schede NED1/POR1 (la stampa italiana non scrive di
    questi club e le voci non italiane in archivio erano pagine di servizio). Dopo: con le
    edizioni locali, ogni club del campione ha almeno una voce pubblicabile.
    """
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "estero_2026-10-13.json"
    dati = json.loads(fixture.read_text())
    an = MatchAnalysis.__new__(MatchAnalysis)      # solo i metodi puri
    vocabolario = {t[1] for t in TEMI}
    attese = {"SC Heerenveen": "nl", "Sparta Rotterdam": "nl", "AZ": "nl", "SC Braga": "pt"}
    for squadra, lingua in attese.items():
        esaminate = pubblicabili = 0
        for titolo, _fonte in dati[lingua]:
            esaminate += 1
            s = sintesi_estera(titolo, lingua)
            if s is None:
                continue
            if not an._estera_soggetto(titolo, squadra, [{"name": "Zonneveld"}], "Mark Smith"):
                continue
            assert s.etichetta in vocabolario
            pubblicabili += 1
        assert esaminate >= 8, squadra
        assert 1 <= pubblicabili <= 4, (squadra, pubblicabili)


# --------------------------------------------------------------------------------------
# La scheda vera (Jinja + template) con una partita di Eredivisie
# --------------------------------------------------------------------------------------

def test_la_scheda_rende_il_blocco_fuori_dalla_tendina(tmp_path):
    """End-to-end: la card compare nella scheda, con lingua e titolo originali.

    La partita è di Eredivisie (league_id 57) e la rassegna italiana è vuota: è il caso
    vero del 2026-10-13. Il blocco estero deve stare **fuori** dalla tendina di metodo,
    altrimenti resterebbe invisibile proprio dove serve.
    """
    from fda.site.build import SiteBuilder

    ko = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=3)
    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame([{
        "match_id": 900001, "league_id": 57, "season": "2026/2027", "round": "9",
        "utc_kickoff": ko, "home_id": 1, "home_name": "SC Heerenveen",
        "away_id": 2, "away_name": "Telstar", "home_goals": None, "away_goals": None,
        "status": "scheduled", "source": "test"}]))
    st.write("match_info", pd.DataFrame([{"match_id": 900001, "status": "scheduled"}]))
    # la voce è archiviata prima di adesso e dentro la finestra pre-partita
    quando = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=2)
    st.write("news", pd.DataFrame([
        {"team_id": 1, "published_at": quando, "language": "nl",
         "title": "SC Heerenveen, blessure voor de spits", "url": "https://esempio.nl/1",
         "source": "FeanOnline", "description": ""},
        {"team_id": 1, "published_at": quando - pd.Timedelta(hours=1), "language": "nl",
         "title": "SC Heerenveen - Telstar: opstellingen en live", "url": "https://esempio.nl/2",
         "source": "VoetbalPrimeur", "description": ""},
        {"team_id": 1, "published_at": quando - pd.Timedelta(hours=2), "language": "it",
         "title": "Heerenveen, il ds parla del mercato", "url": "https://esempio.it/1",
         "source": "Gazzetta", "description": ""},
    ]))
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({900001})
    html = (out / "partite" / "900001.html").read_text(encoding="utf-8")

    assert "stampa in lingua originale" in html
    assert "FeanOnline" in html and "SC Heerenveen, blessure voor de spits" in html
    assert 'lang="nl"' in html and "olandese" in html
    assert "Infortunio" in html and "riconosciuto da" in html
    # lista con classe propria: gli oracoli di «Vita del club» selezionano `ul.news-list`
    assert 'class="news-estera-list"' in html
    # la pagina di servizio non compare: non è pubblicabile in nessuna lingua
    assert "opstellingen en live" not in html
    # il blocco è visibile, non chiuso nella tendina del metodo
    assert html.index("stampa in lingua originale") < html.index('<details class="news-more"')
    # la riga unica della card dice che la stampa locale ha qualcosa da mostrare
    assert "Nella stampa in lingua originale" in html


# --------------------------------------------------------------------------------------
# L'oracolo [50]: il difetto del primo run in produzione (docs/106 §6) non deve tornare
# --------------------------------------------------------------------------------------

def _checker():
    """Carica `scripts/verify_site.py` come modulo, senza eseguirne il main."""
    import importlib.util

    p = Path(__file__).resolve().parents[1] / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site_estera", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pagina_con_due_squadre(tmp_path, monkeypatch):
    """Scheda di Eredivisie con voci in lingua originale su **entrambe** le squadre.

    È la forma che il 13/10 ha fatto fallire il `daily` #267: la prima stesura dell'oracolo
    ritagliava i riquadri con un'espressione regolare e il blocco della prima squadra si
    portava dietro anche il secondo.
    """
    from fda.site.build import SiteBuilder

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    ko = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=3)
    quando = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=3)
    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame([{
        "match_id": 900002, "league_id": 57, "season": "2026/2027", "round": "9",
        "utc_kickoff": ko, "home_id": 8614, "home_name": "Sparta Rotterdam",
        "away_id": 8525, "away_name": "Willem II", "home_goals": None, "away_goals": None,
        "status": "scheduled", "source": "test"}]))
    st.write("match_info", pd.DataFrame([{"match_id": 900002, "status": "scheduled"}]))
    def voce(tid, titolo, url):
        return {"team_id": tid, "published_at": quando, "title": titolo, "url": url,
                "source": "Testata NL", "description": "", "language": "nl"}

    righe = [voce(8614, "Sparta Rotterdam, blessure voor de spits", "u1"),
             voce(8614, "Sparta Rotterdam verlengt contract speler A", "u2"),
             voce(8614, "Sparta Rotterdam haalt een nieuwe spits", "u3"),
             voce(8525, "Willem II, blessure voor de doelman", "u4"),
             voce(8525, "Willem II verlengt contract speler B", "u5")]
    st.write("news", pd.DataFrame(righe))
    site = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=site).build_match_pages({900002})
    return site, tmp_path / "processed"


def test_oracolo_50_passa_con_voci_su_entrambe_le_squadre(tmp_path, monkeypatch):
    """Il caso che il 13/10 ha reso rosso il `daily` #267: voci su tutte e due le squadre."""
    site, data = _pagina_con_due_squadre(tmp_path, monkeypatch)
    fails, checks = _checker().check_stampa_estera(site, data)
    assert fails == [], fails
    assert checks >= 8      # due riquadri, cinque voci e le loro righe di fonte


def test_oracolo_50_vede_i_difetti_veri(tmp_path, monkeypatch):
    """L'oracolo non è uno specchio: se la pagina mente, deve dirlo.

    Tre manomissioni, una per tipo di controllo: il conteggio dichiarato, il titolo
    (che deve esistere in archivio) e la lingua dichiarata.
    """
    site, data = _pagina_con_due_squadre(tmp_path, monkeypatch)
    pg = site / "partite" / "900002.html"
    originale = pg.read_text(encoding="utf-8")
    vs = _checker()

    pg.write_text(originale.replace(": 3 voci su", ": 9 voci su"), encoding="utf-8")
    fails, _ = vs.check_stampa_estera(site, data)
    assert any("dichiara 9 voci e ne rende 3" in f for f in fails), fails

    pg.write_text(originale.replace("Sparta Rotterdam, blessure voor de spits",
                                    "Sparta Rotterdam, blessure voor de spitsen"), encoding="utf-8")
    fails, _ = vs.check_stampa_estera(site, data)
    assert any("non presente in archivio" in f for f in fails), fails

    pg.write_text(originale.replace("lingua originale: olandese", "lingua originale: inglese"),
                  encoding="utf-8")
    fails, _ = vs.check_stampa_estera(site, data)
    assert any("lingua dichiarata" in f or "non dichiarata" in f for f in fails), fails

    # un riquadro in meno (una sola squadra): la pagina promette una copertura che non ha
    pg.write_text(originale[:originale.index('<div class="news-estera" data-team-id="8525"')]
                  + originale[originale.index("</div>\n    </div>",
                                              originale.index('data-team-id="8525"')):],
                  encoding="utf-8")
    fails, _ = vs.check_stampa_estera(site, data)
    assert any("invece di 2" in f for f in fails), fails

    pg.write_text(originale, encoding="utf-8")


def test_oracolo_50_con_una_squadra_vuota_e_l_altra_piena(tmp_path, monkeypatch):
    """Il caso più frequente in produzione («squadra 8464 dichiara 0 voci e ne rende 3»):

    il riquadro di una squadra è vuoto, quello dell'altra ha le voci. Con la cattura a
    espressione regolare i tre titoli finivano attribuiti alla squadra vuota.
    """
    from fda.site.build import SiteBuilder

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    ko = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=3)
    quando = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=3)
    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame([{
        "match_id": 900003, "league_id": 57, "season": "2026/2027", "round": "9",
        "utc_kickoff": ko, "home_id": 8464, "home_name": "Fortuna Sittard",
        "away_id": 8674, "away_name": "NEC", "home_goals": None, "away_goals": None,
        "status": "scheduled", "source": "test"}]))
    st.write("match_info", pd.DataFrame([{"match_id": 900003, "status": "scheduled"}]))
    st.write("news", pd.DataFrame([
        {"team_id": 8674, "published_at": quando, "title": "NEC haalt een nieuwe spits",
         "url": "n1", "source": "Testata NL", "description": "", "language": "nl"},
        {"team_id": 8674, "published_at": quando, "title": "NEC verlengt contract speler C",
         "url": "n2", "source": "Testata NL", "description": "", "language": "nl"},
        {"team_id": 8674, "published_at": quando, "title": "NEC, blessure voor de doelman",
         "url": "n3", "source": "Testata NL", "description": "", "language": "nl"},
    ]))
    site = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=site).build_match_pages({900003})
    fails, checks = _checker().check_stampa_estera(site, tmp_path / "processed")
    assert fails == [], fails
    assert checks >= 5      # due riquadri + le tre voci del NEC
