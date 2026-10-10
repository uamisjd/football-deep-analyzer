import importlib.util
import re
from pathlib import Path

import pandas as pd


def _load():
    p = Path(__file__).parent.parent / "scripts" / "verify_standings.py"
    spec = importlib.util.spec_from_file_location("verify_standings", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vs = _load()

COLS = ["league_code", "team_id", "team_name", "rank", "played", "wins", "draws",
        "losses", "goals_for", "goals_against", "goal_diff", "points"]


def test_check_table_ok():
    df = pd.DataFrame([("ITA1", 1, "A", 1, 3, 3, 0, 0, 8, 2, 6, 9),
                       ("ITA1", 2, "B", 2, 3, 1, 1, 1, 4, 4, 0, 4)], columns=COLS)
    assert vs.check_table(df, 2) == ([], [])


def test_check_table_problems():
    df = pd.DataFrame([("ITA1", 1, "A", 1, 3, 3, 0, 0, 8, 2, 6, 9)], columns=COLS)
    problems, _ = vs.check_table(df, 2)
    assert any("invece di 2" in p for p in problems)


def test_check_table_points_warning():
    df = pd.DataFrame([("ITA1", 1, "A", 1, 3, 3, 0, 0, 8, 2, 6, 6),   # 6 pt invece di 9?
                       ("ITA1", 2, "B", 2, 3, 1, 1, 1, 4, 4, 0, 4)], columns=COLS)
    problems, warnings = vs.check_table(df, 2)
    assert problems == [] and any("3V+N" in w for w in warnings)


def test_finished_coverage():
    fx = pd.DataFrame([{"league_id": 57, "status": "finished"},
                       {"league_id": 57, "status": "finished"},
                       {"league_id": 57, "status": "scheduled"},
                       {"league_id": 55, "status": "finished"}])
    mi = pd.DataFrame([{"league_id": 57, "status": "finished", "home_xg": 1.2},
                       {"league_id": 55, "status": "finished", "home_xg": None}])
    assert vs.finished_coverage(fx, mi) == {57: (2, 1), 55: (1, 0)}


def _site_module():
    p = Path(__file__).parent.parent / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_verify_site_stato_fonti_senza_motivo(tmp_path):
    """[28] Una fonte «OK» con 0 righe deve dichiarare il motivo (docs/21 §15).

    Il caso reale: `news:NEWS` e `transfers:TRANSFERS` rispondevano OK con zero righe
    salvate e dalla pagina non si capiva perché. Il controllo pretende l'imbuto; un errore
    o un avviso non lo richiedono (il motivo è già il testo dell'errore).
    """
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()

    def row(fonte: str, righe: str, esito: str) -> str:
        return (f'<tr><td>{fonte}</td><td class="mut">15/09 22:35</td><td class="r">139</td>'
                f'<td class="r">{righe}</td><td>{esito}</td></tr>')

    (site / "stato.html").write_text("<table>"
        + row("news:NEWS", "0", '<span class="pill V">OK</span>')
        + row("transfers:TRANSFERS", "0", '<span class="pill V">OK</span> <span class="small mut">'
                                           '0 righe · payload letti 132 · sezione assente in 132</span>')
        + row("fotmob:ITA1", "132", '<span class="pill V">OK</span> <span class="small mut">calendario 132</span>')
        + row("espn:NEWS", "0", '<span class="pill N">AVVISO</span> <span class="small mut">HTTP 403</span>')
        + "</table>", encoding="utf-8")
    fails, checks = vs.check_status(site)
    assert checks == 4
    assert len(fails) == 1 and "news:NEWS" in fails[0]


def test_verify_site_content_checks(tmp_path):
    """Il verificatore del sito trova i difetti che l'audit 2026-09-12 ha corretto."""
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    (site / "ok.html").write_text(
        '<a href="altra.html">link</a><p>1 gara · 2 pareggi · xG 1,69 · spettatori 67.598</p>', encoding="utf-8")
    (site / "altra.html").write_text("<p>ok</p>", encoding="utf-8")
    fails, pages = vs.check_pages(site)
    assert pages == 2 and fails == []        # i separatori di migliaia non sono decimali col punto

    (site / "rotta.html").write_text(
        '<a href="mancante.html">x</a><p>1 gare · nan · 1.69 · RegularPlay · clean sheet</p>'
        # le sei forme dell'hotfix concordanza (docs/40): il gate deve fermarle tutte, anche
        # dentro un attributo pronunciato dal lettore di schermo
        '<p>1 assenti · 1 titolari · 1 giocatori · 1 partite · 1 giorni · 1 gara finita</p>'
        '<span aria-label="nelle ultime 1 partite">forma</span>', encoding="utf-8")
    fails, pages = vs.check_pages(site)
    kinds = {f.split(": ", 1)[1] for f in fails if f.startswith("rotta.html")}
    assert pages == 3
    assert any("collegamento interno mancante" in k for k in kinds)
    assert any("concordanza '1 gare'" in k for k in kinds)
    assert any("concordanza '1 assenti'" in k for k in kinds)
    assert any("concordanza '1 titolari'" in k for k in kinds)
    assert any("concordanza '1 giocatori'" in k for k in kinds)
    assert any("concordanza '1 giorni'" in k for k in kinds)
    # «1 partite» sia nel testo sia nell'aria-label (gli attributi sono una dimensione presidiata)
    assert any("concordanza '1 partite'" in k for k in kinds)
    assert any("concordanza in attributo '1 partite'" in k for k in kinds)
    # il singolare corretto non è un problema: «1 gara finita» passa
    assert not any("'1 gara finita'" in k for k in kinds)
    assert any("residuo 'nan'" in k for k in kinds)
    assert any("decimale col punto '1.69'" in k for k in kinds)
    assert any("inglese" in k for k in kinds)


def test_verify_site_concordanza_numero_articolo_nome(tmp_path):
    """«2 i titoli», mai: l'articolo fra numero e nome schermava il gate (docs/53 §6.2).

    Caso reale del 07/10/2026: la card «Vita del club» pubblicava «2 i titoli più
    vecchi guardati» (17 schede) e «1 i titolo più vecchio guardato» (3 schede). Il
    ramo «1 + plurale» non mordeva perché fra «1» e il nome c'era l'articolo «i».
    """
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    # struttura vera della card: l'imbuto è testo nostro (ricontrollato), i titoli
    # della stampa restano citazioni verbatim (escluse: «1 gare» lì dentro non morde)
    (site / "ok.html").write_text(
        '<div id="notizie">'
        '<p class="small mut imbuto">(2 titoli più vecchi guardati, oltre la finestra)</p>'
        '<p class="small mut imbuto">(1 titolo più vecchio guardato, oltre la finestra)</p>'
        '<ul class="news-list"><li><a href="https://esempio.invalid/x">1 gare strane</a></li></ul>'
        "</div>", encoding="utf-8")
    fails, pages = vs.check_pages(site)
    assert pages == 1 and fails == [], fails
    (site / "rotta.html").write_text(
        '<div id="notizie">'
        '<p class="small mut imbuto">(2 i titoli più vecchi guardati, oltre la finestra)</p>'
        "</div>", encoding="utf-8")
    fails, pages = vs.check_pages(site)
    kinds = {f.split(": ", 1)[1] for f in fails if f.startswith("rotta.html")}
    assert any("concordanza '2 i titoli'" in k for k in kinds), kinds


def test_verify_site_accepts_existing_fragment_and_decimal_plural(tmp_path):
    """Le ancore della jump nav sono link validi; 3,1 gialli non è una concordanza errata."""
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    (site / "match.html").write_text(
        '<nav><a href="#contesto">Dati e contesto</a></nav>'
        '<p id="contesto">Arbitro · 3,1 gialli/gara</p>', encoding="utf-8")
    fails, pages = vs.check_pages(site)
    assert pages == 1 and fails == []

    (site / "broken.html").write_text('<a href="#missing">no</a>', encoding="utf-8")
    fails, _ = vs.check_pages(site)
    assert any("ancora interna mancante #missing" in f for f in fails)


def test_verify_site_notizie_verbatim_escluse_dai_controlli(tmp_path):
    """La card «Ultime dalle società» pubblica titoli e brani delle testate verbatim
    (docs/21 P1-5, scelto anche nel footer della card): «Sofascore 8.9», «13.09.2026»
    o un «Monday» nel titolo sono parole della stampa, non numeri nostri — i controlli
    su decimali/inglese/residui valgono per il testo del sito, fuori dalla card."""
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    (site / "match.html").write_text(
        '<div class="card" id="notizie"><h2>Ultime dalle società</h2>'
        '<p style="margin:0 0 6px"><b>Milan</b> <span class="small mut">· 1 notizia verificata</span></p>'
        '<ul class="news-list"><li>'
        '<a href="https://news.google.com/x" rel="noopener noreferrer nofollow">'
        "Valutazione Sofascore 8.9 e Monday Night</a>"
        '<br><span class="small mut">quote 13.09.2026</span></li></ul></div>'
        "<p>xG 1,69 · 2 gare</p>", encoding="utf-8")
    fails, pages = vs.check_pages(site)
    assert pages == 1 and fails == []          # dentro la card: citazione, non si tocca

    (site / "fuori.html").write_text(
        '<div class="card" id="notizie"></div><p>1.69 · nan · Monday</p>', encoding="utf-8")
    fails, _ = vs.check_pages(site)
    kinds = {f.split(": ", 1)[1] for f in fails if f.startswith("fuori.html")}
    assert any("decimale col punto" in k for k in kinds)     # fuori dalla card si continua a mordere
    assert any("residuo" in k for k in kinds)
    assert any("inglese" in k for k in kinds)


def test_verify_site_barre_1x2(tmp_path):
    """[11a] Il verificatore prende le barre che non chiudono 100 o contraddicono le etichette."""
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    ok = (
        '<div class="bar" role="img" aria-label="Probabilità: vittoria Casa 41 per cento, '
        'pareggio 40 per cento, vittoria Ospite 19 per cento" style="height:30px">'
        '<span class="h" style="width:41%">1 · 41%</span>'
        '<span class="d" style="width:40%">X · 40%</span>'
        '<span class="a" style="width:19%">2 · 19%</span></div>'
        '<div class="bar" role="img" aria-label="passo: 61,3 per cento, 24,2 per cento, '
        '14,5 per cento"><span class="h" style="width:61.3%">1 · 61,3%</span>'
        '<span class="d" style="width:24.2%">X · 24,2%</span>'
        '<span class="a" style="width:14.5%">2 · 14,5%</span></div>'
        '<div class="mini-probability"><div class="bar" role="img" aria-label="Probabilità: 1 41%, '
        'pareggio 40%, 2 19%"><span class="h" style="width:41%"></span>'
        '<span class="d" style="width:40%"></span><span class="a" style="width:19%"></span></div>'
        '<div class="prob-labels"><span class="is-fav">1 41%</span><span>X 40%</span>'
        '<span>2 19%</span></div></div>'
        '<header><div class="bar"><span class="h"><span class="ca">Calcio</span></span></div></header>')
    (site / "scheda.html").write_text(ok, encoding="utf-8")
    fails, checks = vs.check_bars(site)
    assert fails == [] and checks >= 5, (fails, checks)   # il wordmark dell'header non entra

    rotta = (
        '<div class="bar" style="height:30px"><span class="h" style="width:40%">1 · 40%</span>'
        '<span class="d" style="width:40%">X · 40%</span>'
        '<span class="a" style="width:19%">2 · 19%</span></div>'                      # 99%, no aria
        '<div class="bar" role="img" aria-label="Probabilità: 41 per cento, 40 per cento, '
        '19 per cento"><span class="h" style="width:42%">1 · 41%</span>'                # etichetta≠larghezza
        '<span class="d" style="width:40%">X · 40%</span>'
        '<span class="a" style="width:19%">2 · 19%</span></div>'
        '<div class="prob-labels"><span>1 41%</span><span class="is-fav">X 40%</span>'
        '<span>2 19%</span></div>')                                                    # favorito ≠ massimo
    (site / "rotta.html").write_text(rotta, encoding="utf-8")
    fails, _ = vs.check_bars(site)
    assert any("rotta.html: barra 1X2 larga 99%" in f for f in fails)
    assert any("rotta.html: barra 1X2 senza aria-label" in f for f in fails)
    assert any("rotta.html: etichetta 41% ma larghezza 42%" in f for f in fails)
    assert any("rotta.html: aria-label [41.0, 40.0, 19.0] != larghezze [42.0, 40.0, 19.0]" in f for f in fails)
    assert any("rotta.html: favorito evidenziato ma non è il massimo" in f for f in fails)
    assert not [f for f in fails if f.startswith("scheda.html")]


def test_notizia_in_finestra_duplicati_stesso_url():
    """[20] Lo stesso (url, team_id) raccolto due volte con published_at diversi.

    Caso reale 2026-09-16 (5868080.html, Villarreal): il feed ripubblica lo stesso link
    prima a 07:00 poi a 01:21 del giorno dopo; per una gara al 20/09 la finestra inizia
    alle 16:30 dell'8/9 — la riga vecchia è fuori, quella stampata dal build dentro.
    Il verificatore non deve guardare solo ``iloc[0]``.
    """
    vs = _site_module()
    kickoff = pd.Timestamp("2026-09-20 16:30:00+00:00")
    righe = pd.DataFrame({
        "published_at": ["2026-09-08 07:00:00+00:00",   # fuori finestra, era il falso positivo
                         "2026-09-09 01:21:44+00:00"],  # dentro finestra, quella stampata
        "title": ["t", "t"],
    })
    assert vs.notizia_in_finestra(righe, kickoff) is True

    # tutte fuori → resta un difetto vero e deve fallire
    solo_vecchie = pd.DataFrame({
        "published_at": ["2026-08-29 19:03:25+00:00", "2026-09-08 07:00:00+00:00"],
        "title": ["t", "t"],
    })
    assert vs.notizia_in_finestra(solo_vecchie, kickoff) is False

    # righe senza data: ignorate, non valide per default
    senza_data = pd.DataFrame({"published_at": [pd.NaT], "title": ["t"]})
    assert vs.notizia_in_finestra(senza_data, kickoff) is False


def test_verify_site_sospensione_deve_dire_motivo_e_non_chiamare(tmp_path):
    """[28] esteso (docs/19 P1.9): una fonte SOSPESA deve dichiarare N run e il ritentativo.

    Il difetto che il controllo previene non è estetico: se una riga dicesse «sospeso» senza
    dire perché, la pagina *Stato fonti* tornerebbe a nascondere il guasto — e se una fonte
    sospesa continuasse a fare richieste, il backoff non risparmierebbe nulla.
    """
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    ok = ("<tr><td>openmeteo:ITA1</td><td class=\"mut\">16/09 15:05</td><td class=\"r\">0</td>"
          "<td class=\"r\">0</td><td><span class=\"pill V\">OK</span> <span class=\"small mut\">"
          "0 righe · nessuna previsione utile su 10 gare future (meteo FotMob 10)</span></td></tr>")
    sospeso = ("<tr><td>espn:ITA1</td><td class=\"mut\">16/09 15:05</td><td class=\"r\">0</td>"
               "<td class=\"r\">0</td><td><span class=\"pill S\">SOSPESO</span> <span class=\"small mut\">"
               "espn standings: sospeso dopo 20 run falliti consecutivi (espn standings); "
               "nuovo tentativo fra 4 run</span></td></tr>")
    (site / "stato.html").write_text(f"<table>{ok}{sospeso}</table>", encoding="utf-8")
    fails, checks = vs.check_status(site)
    assert fails == [] and checks == 2

    # sospeso senza piano di ritentativo → problema
    muto = sospeso.replace("nuovo tentativo fra 4 run", "")
    (site / "stato.html").write_text(f"<table>{muto}</table>", encoding="utf-8")
    fails, _ = vs.check_status(site)
    assert fails and "piano di ritentativo" in fails[0]

    # sospeso ma con richieste fatte → il backoff non sta funzionando
    chiama = sospeso.replace('<td class="r">0</td><td class="r">0</td>',
                             '<td class="r">2</td><td class="r">0</td>')
    (site / "stato.html").write_text(f"<table>{chiama}</table>", encoding="utf-8")
    fails, _ = vs.check_status(site)
    assert fails and "richieste" in fails[0]


def test_verify_site_stime_stabilizzate_dichiarano_gruppo_e_peso(tmp_path):
    """[32] (docs/19 §1.10): una stima ◇/◎ senza media dei pari, peso e n non è verificabile.

    Il difetto che il controllo previene è quello misurato nelle schede: 8.705 celle per-90
    marcate con un valore «stabilizzato» che però non diceva verso cosa (e con l'unità del
    prior sbagliata: peso 180′ fisso, media dei tiri presa dalla costante dell'xG+xA).
    """
    vs = _site_module()
    site = tmp_path / "site"
    (site / "giocatori").mkdir(parents=True)
    testa = ('<th scope="row">Minuti</th><td class="r">95</td>'
             '<tr><td>Tiri<x> <span class="mut small" title="media dei pari (attaccanti di Serie A) 3,00/90 '
             '· peso k=225′ · n=42">◎</span></td><td class="r">6</td>'
             '<td class="r"><span title="grezzo 5,68/90 · stima stabilizzata 4,62/90">5,68 '
             '<span class="mut small">◎ 4,62</span></span></td></tr>')
    (site / "giocatori" / "1.html").write_text(testa.replace("<x>", ""), encoding="utf-8")
    fails, checks = vs.check_stime(site)
    assert fails == [] and checks == 1

    # stima senza gruppo né peso → problema
    (site / "giocatori" / "1.html").write_text(
        testa.replace('title="media dei pari (attaccanti di Serie A) 3,00/90 · peso k=225′ · n=42"',
                      'title="valore stimato"').replace("<x>", ""), encoding="utf-8")
    fails, _ = vs.check_stime(site)
    assert fails and "media dei pari" in fails[0]

    # 1′ di gioco con una rata grezza pubblicata → il difetto originale
    (site / "giocatori" / "1.html").write_text(
        '<th scope="row">Minuti</th><td class="r">1</td>'
        '<tr><td>Tiri</td><td class="r">1</td><td class="r">90,00</td></tr>', encoding="utf-8")
    fails, _ = vs.check_stime(site)
    assert fails and "con 1′ giocati" in fails[0]


def test_verify_site_quote_non_dichiarate_come_rate_per_90(tmp_path):
    """[32] regola 4 (docs/23 §2): una percentuale non è una rata per 90 e il tooltip non deve dirlo.

    Difetto misurato sulla build del 2026-09-16: le celle «Passaggi riusciti %» e «Duelli vinti %»
    pubblicavano il grezzo già sotto i 90′ e lo dichiaravano «89,2%/90′» — un numero su tre duelli
    presentato come una rata per 90 minuti. Il controllo ora rifiuta «/90′» nei tooltip delle quote
    e la pubblicazione del grezzo sotto i 90′.
    """
    vs = _site_module()
    site = tmp_path / "site"
    (site / "giocatori").mkdir(parents=True)
    ok = ('<th scope="row">Minuti</th><td class="r">900</td>'
          '<tr><td>Passaggi riusciti %</td><td class="r">85%</td>'
          '<td class="r"><span title="765 passaggi riusciti su 900 tentati (totale stagionale): '
          'la percentuale non è una rata per 90 minuti">85,0%</span></td></tr>'
          '<tr><td>Duelli vinti %</td><td class="r">50%</td>'
          '<td class="r"><span title="grezzo 50,0% · media dei pari (difensori di Serie A) 50,0% · '
          'peso k=30 duelli · n=9">50,0% <span class="mut small">◎ 50,1%</span></span></td></tr>')
    (site / "giocatori" / "1.html").write_text(ok, encoding="utf-8")
    fails, checks = vs.check_stime(site)
    assert fails == [] and checks == 2

    # quota dichiarata come rata per 90 → problema
    (site / "giocatori" / "1.html").write_text(
        '<th scope="row">Minuti</th><td class="r">900</td>'
        '<tr><td>Passaggi riusciti %</td><td class="r">85%</td>'
        '<td class="r"><span title="85,0%/90′">85,0%</span></td></tr>', encoding="utf-8")
    fails, _ = vs.check_stime(site)
    assert fails and "/90′" in fails[0]

    # quota grezza pubblicata sotto i 90′ → problema (stesso caso della build)
    (site / "giocatori" / "1.html").write_text(
        '<th scope="row">Minuti</th><td class="r">37</td>'
        '<tr><td>Duelli vinti %</td><td class="r">33%</td>'
        '<td class="r"><span title="33,3%/90′">33,3%</span></td></tr>', encoding="utf-8")
    fails, _ = vs.check_stime(site)
    assert fails and any("37′ giocati" in f for f in fails)


# --- [11e] presidio sul peso delle pagine (docs/19 §3.10) ---


def _load_verify_site():
    p = Path(__file__).parent.parent / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_il_tetto_sul_peso_delle_pagine_esiste_ed_e_quello_dichiarato():
    """`docs/19` §3.10 dava questo presidio per esistente: non c'era (verificato su main)."""
    vsite = _load_verify_site()
    assert vsite.MAX_PAGE_KB == 900
    # prossime.html contiene di proposito l'intero calendario: eccezione dichiarata, non
    # un tetto alzato per tutti (che renderebbe il controllo inutile sulle altre pagine)
    assert vsite.PAGINE_FUORI_TETTO["prossime.html"] > vsite.MAX_PAGE_KB


def test_una_pagina_oltre_il_tetto_viene_segnalata(tmp_path):
    """La regressione da intercettare: una pagina che gonfia senza che nessuno se ne accorga."""
    vsite = _load_verify_site()
    (tmp_path / "leggera.html").write_text("<html>ok</html>", encoding="utf-8")
    (tmp_path / "pesante.html").write_text("<html>" + "x" * (901 * 1024) + "</html>",
                                           encoding="utf-8")
    fails, checks = vsite.check_page_weight(tmp_path)
    assert checks == 2, "ogni pagina deve contare come un controllo"
    assert len(fails) == 1
    assert fails[0].startswith("pesante.html: pagina di ")
    # il riepilogo raggruppa per la prima parola dopo «: »: deve essere una categoria,
    # non una cifra (altrimenti il sommario elenca un numero diverso per ogni pagina)
    assert fails[0].split(": ", 1)[1].split(" ")[0] == "pagina"


def test_l_eccezione_dichiarata_non_viene_segnalata(tmp_path):
    """`prossime.html` sta sopra 900 KB per scelta: non deve produrre un falso allarme."""
    vsite = _load_verify_site()
    (tmp_path / "prossime.html").write_text("<html>" + "x" * (1000 * 1024) + "</html>",
                                            encoding="utf-8")
    fails, checks = vsite.check_page_weight(tmp_path)
    assert checks == 1
    assert fails == []


def test_anche_l_eccezione_ha_un_tetto(tmp_path):
    """L'eccezione non è un permesso di crescere all'infinito: oltre il suo tetto, fallisce."""
    vsite = _load_verify_site()
    oltre = vsite.PAGINE_FUORI_TETTO["prossime.html"] + 10
    (tmp_path / "prossime.html").write_text("<html>" + "x" * (oltre * 1024) + "</html>",
                                            encoding="utf-8")
    fails, _ = vsite.check_page_weight(tmp_path)
    assert len(fails) == 1 and "prossime.html" in fails[0]


def test_verify_site_due_squadre_su_ogni_scheda(tmp_path):
    """[44] (docs/64): la card «Le due squadre» esiste ovunque e i suoi numeri si ricalcolano.

    I difetti che l'invariante blocca sono quelli misurati sulla build del 2026-10-09: tre
    schede in cui le due squadre confrontavano fonti xG diverse (Understat da una parte,
    FotMob dall'altra) senza dirlo, il valore dei titolari attribuito a Transfermarkt invece
    che alla distinta FotMob, un piè di card che spiegava la stringa «Ruolo n.d.» (mai
    stampata) e un verdetto sullo scarto punti−xPTS con una soglia fissa a ±2 punti, sotto
    il rumore della misura. Il controllo gira su **tutte** le pagine di `site/partite`, così
    nessuna partita resta fuori dalla revisione.
    """
    from datetime import UTC, datetime, timedelta

    from fda.site.build import SiteBuilder
    from tests.test_site import _fixture_lontana, _seed

    vs = _site_module()
    st = _seed(tmp_path)
    now = datetime.now(UTC)
    st.upsert("fixtures", [_fixture_lontana(5900010, 3, "Inter", "Napoli", now)])
    st.upsert("understat_team_matches", [
        {"league_slug": "Serie_A", "season": 2026, "team_id": 999100 + t,
         "team_name": ["Inter", "Napoli", *[f"Prova {i}" for i in range(9)]][t],
         "date": (now - timedelta(days=7 * (4 - i))).isoformat(), "is_home": bool(i % 2),
         "goals": 2, "goals_against": 1, "xg": 2.4 if t == 0 else 1.2,
         "xga": 0.8 if t == 0 else 1.4, "xpts": 2.2 if t == 0 else 1.2,
         "pts": 3 if t == 0 else 1, "ppda": 8.0 if t == 0 else 14.0}
        for t in range(11) for i in range(4)])
    # una gara precedente fra le stesse due squadre, con le statistiche FotMob da cui esce
    # l'indice di pressione (docs/64 §9): senza, la casella userebbe il ripiego Understat e
    # il controllo dell'indice non verificherebbe nulla
    passata = dict(_fixture_lontana(5900009, 3, "Inter", "Napoli", now - timedelta(days=7)),
                   status="finished", home_goals=1, away_goals=1)
    st.upsert("fixtures", [passata])
    st.upsert("team_stats", [
        {"match_id": 5900009, "team_id": tid, "period": "All", "key": k, "value": v, "text": ""}
        for tid, pas in ((passata["home_id"], 300.0), (passata["away_id"], 240.0))
        for k, v in (("own_half_passes", pas), ("matchstats.headers.tackles", 40.0),
                     ("interceptions", 10.0), ("fouls", 10.0))])
    # docs/66: una vera popolazione di lega (≥10 squadre) e uno storico sintetico.
    # Senza questi dati la riga della forza non uscirebbe e la manomissione sarebbe vacua.
    st.upsert("fixtures", [dict(_fixture_lontana(5910000 + i, 15, f"Prova {2*i}",
                                               f"Prova {2*i+1}", now),
                               home_id=990000 + 2*i, away_id=990001 + 2*i) for i in range(4)])
    from fda.teams import canonical
    fx = st.read("fixtures")
    names = sorted({canonical(t) for t in [*fx.home_name, *fx.away_name]})
    st.upsert("history", [{"league_key": "ITA1", "season": "2026/2027",
                           "date": now - timedelta(days=90 - i), "home": name,
                           "away": names[(i + 1) % len(names)], "home_goals": i % 4,
                           "away_goals": 1} for i, name in enumerate(names)])
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5900010})
    st.close()
    dati = tmp_path / "processed"

    fails, checks = vs.check_due_squadre(out, dati)
    assert fails == [] and checks > 20

    pagina = out / "partite" / "5900010.html"
    originale = pagina.read_text(encoding="utf-8")

    def rotta(html: str) -> list[str]:
        pagina.write_text(html, encoding="utf-8")
        return vs.check_due_squadre(out, dati)[0]

    # 1) card assente → la scheda non è «senza dati», è rotta
    assert "non c'è" in rotta(originale.replace('id="squadre"', 'id="altro"'))[0]

    # 2) attribuzione sbagliata del valore dei titolari e piè di card con stringhe fantasma
    fails = rotta(originale.replace("Che cosa c'è in questa card:",
                                    "Transfermarkt · Ruolo n.d. · Che cosa c'è in questa card:"))
    assert any("Transfermarkt" in f for f in fails)
    assert any("Ruolo n.d." in f for f in fails)

    # 3) piè di card rimosso
    assert any("Che cosa c'è" in f
               for f in rotta(originale.replace("Che cosa c'è in questa card:", "Note:")))

    # 4) numero di stagione manomesso: xG creati e campione non tornano più dai Parquet
    guasto = re.sub(
        r"(xG creati / gara</div>\s*<div[^>]*>)[\d,]+ (<span[^>]*>\()(Understat|FotMob), \d+",
        r"\g<1>9,99 \g<2>\g<3>, 99", originale, count=1)
    fails = rotta(guasto)
    assert any("xG creati 9,99" in f for f in fails)
    assert any("campione xG 99" in f for f in fails)

    # 5) rapporto di lega sparito o sbagliato (la parità fra le 7 leghe passa di qui)
    senza_rif = originale.replace("× la media del campionato", "× qualcosa", 1)
    assert any("riferimento di lega assente" in f for f in rotta(senza_rif))
    sballato = re.sub(r"[\d,]+(× la media del campionato)", r"9,99\1", originale, count=1)
    assert any("rapporto xG 9,99×" in f for f in rotta(sballato))

    # 6) fonti miste nella stessa scheda (il difetto degli alias Understat non agganciati)
    assert any("mescolano fonti xG diverse" in f or "fonte xG stampata" in f
               for f in rotta(originale.replace("(Understat, ", "(FotMob, ", 1)))

    # 7) verdetto xPTS incoerente con la banda di rumore misurata
    assert any("verdetto xPTS" in f
               for f in rotta(originale.replace("sopra gli attesi", "sotto gli attesi", 1)))

    # 9) il riposo torna a dire «coppe incluse» senza il nome della coppa
    assert any("coppe incluse" in f
               for f in rotta(originale.replace("Che cosa c'è in questa card:",
                                                "coppe incluse · Che cosa c'è in questa card:")))

    # 10bis) indice di pressione: numero manomesso e casella svuotata (docs/64 §9)
    press = re.search(r"Passaggi che l'avversario[^\"]*\">([\d,]+)</span>", originale)
    assert press, "la gara sintetica deve pubblicare l'indice di pressione"
    assert any("indice di pressione 9,99" in f for f in
               rotta(originale.replace(f'">{press.group(1)}</span>', '">9,99</span>', 1)))
    assert any("indici di pressione stampati" in f for f in
               rotta(originale.replace("Passaggi che l'avversario", "Qualcos'altro", 1)))

    # 10ter) forza degli avversari: media, riferimento, giudizio, rango e assenza della riga.
    assert 'Avversari affrontati: forza media <b>' in originale
    assert 'class="form-opp-rank"' in originale
    altered = re.sub(r'(Avversari affrontati: forza media <b>)[\d.]+',
                     r'\g<1>9.999', originale, count=1)
    assert any("forza media avversari 9.999" in f for f in rotta(altered))
    altered = re.sub(r'(</b> contro )[\d.]+( del campionato)',
                     r'\g<1>9.999\g<2>', originale, count=1)
    assert any("media Elo di lega 9.999" in f for f in rotta(altered))
    altered = re.sub(r'(<span class="form-strength-label">)[^<]+',
                     r'\g<1>giudizio inventato', originale, count=1)
    assert any("giudizio della forma" in f for f in rotta(altered))
    altered = re.sub(r'(class="form-opp-rank" title="[^"]*">)\(\d+ª\)',
                     r'\g<1>(99ª)', originale, count=1)
    assert any("ranghi/Elo degli avversari" in f for f in rotta(altered))
    assert any("righe «Avversari affrontati»" in f for f in
               rotta(originale.replace('class="form-strength mut small"', 'class="rimossa"', 1)))

    # docs/68: i numeri giusti accanto all'avversario sbagliato non sono una forma corretta.
    altered, replacements = re.subn(
        r'(<span class="small mut">\d+-\d+ in (?:casa|trasferta) con )([^<]+?)'
        r'(<span class="form-opp-rank")',
        r'\g<1>Avversario inventato \g<3>', originale, count=1)
    assert replacements == 1
    assert any("elenco della forma" in f for f in rotta(altered))
    altered, replacements = re.subn(
        r'(<span class="small mut">)\d+-\d+( in (?:casa|trasferta) con )',
        r'\g<1>9-9\g<2>', originale, count=1)
    assert replacements == 1
    assert any("elenco della forma" in f for f in rotta(altered))
    altered, replacements = re.subn(
        r'(<span class="form-dot [VNP]" title=")[^"]*', r'\g<1>Avversario inventato',
        originale, count=1)
    assert replacements == 1
    assert any("pallini/tooltip della forma" in f for f in rotta(altered))

    # 10) infermeria: il totale non è la somma della colonna «impatto» (docs/64 §8)
    pillola = ('<span class="mut small" style="display:inline-block;padding:1px 6px;'
               'background:var(--surface2);border:1px solid var(--line);border-radius:999px;'
               'font-size:10px">attaccante</span>')
    riga = ('<tr><td><b>Tizio {n}</b>' + pillola + '</td><td class="mut small">infortunio</td>'
            '<td class="r small">200′ · 1+1 · <b style="color:var(--accent)">{v}</b>/90</td></tr>')
    def infermeria(totale: str, righe: str) -> str:
        blocco = (f'<p id="infermeria-home"><b>Indisponibili (2)</b> <span class="mut small">'
                  f'· {totale} xG+xA a partita in meno</span></p>'
                  f'<div class="tablewrap"><table>{righe}</table></div>')
        return originale.replace("Che cosa c'è in questa card:",
                                 blocco + "Che cosa c'è in questa card:")

    due = riga.format(n=1, v="0,60") + riga.format(n=2, v="0,40")
    assert rotta(infermeria("1,00", due)) == []                # somma giusta: nessun allarme
    fails = rotta(infermeria("0,80", due))
    assert any("totale 0,80 ≠ somma della colonna 1.00" in f for f in fails)

    # 11) una riga senza la pillola del ruolo (nemmeno «ruolo n.d.»): la cella resta muta
    muta = due.replace(pillola, "", 1)
    assert any("senza la pillola del ruolo" in f for f in rotta(infermeria("1,00", muta)))

    # 12) attacco contro difesa (docs/76 §2): numero manomesso, striscia rimossa, striscia
    # pubblicata su una gara che non è più pre-partita (i requisiti non sono più soddisfatti)
    blocco = re.search(r"Attacco contro difesa</div>(.*?)</div>", originale, re.DOTALL)
    assert blocco, "la scheda sintetica pre-partita deve pubblicare l'incrocio"
    primo = re.search(r"<b>([\d,]+)×</b>", blocco.group(1)).group(1)
    assert any("attacco contro difesa" in f for f in
               rotta(originale.replace(f"<b>{primo}×</b>", "<b>9,99×</b>", 1)))
    assert any("assente" in f for f in rotta(originale.replace(blocco.group(0), "", 1)))
    # «Analisi pre-partita» compare anche nel titolo della sezione lettura: si sostituisce
    # ovunque, così la pagina risulta a gara finita e la striscia non ha più i requisiti
    assert any("senza i requisiti" in f for f in
               rotta(originale.replace("Analisi pre-partita", "Finale")))

    assert rotta(originale) == []


def test_verify_site_due_squadre_finestra_alla_vigilia(tmp_path):
    """[44] (docs/64 §7): il campione non può contenere gare successive alla partita.

    Il difetto misurato sulla build del 2026-10-09: **750 riquadri su 750** delle schede già
    giocate pubblicavano medie di stagione che includevano le gare successive a quella
    descritta (mediana 3, fino a 7). Il controllo ricalcola il campione dal calendario e da
    Understat **senza passare da `season_xg`**, così una regressione del codice (il taglio
    alla vigilia che sparisce) viene vista anche se l'HTML è coerente con il codice rotto.
    """
    from datetime import UTC, datetime, timedelta
    from unittest.mock import patch

    from fda.site.analysis import MatchAnalysis
    from fda.site.build import SiteBuilder
    from tests.test_site import _seed

    vs = _site_module()
    st = _seed(tmp_path)
    riga = st.read("fixtures").query("match_id == 5749645").iloc[0]
    ko = datetime.fromisoformat(str(riga.utc_kickoff)).astimezone(UTC)
    # gare Understat successive alla partita descritta: fuori dal suo campione
    st.upsert("understat_team_matches", [
        {"league_slug": "Serie_A", "season": 2026, "team_id": 999400, "team_name": str(riga.home_name),
         "date": (ko + timedelta(days=g)).isoformat(), "is_home": bool(g % 2), "goals": 3,
         "goals_against": 0, "xg": 3.4, "xga": 0.3, "xpts": 2.7, "pts": 3, "ppda": 6.5}
        for g in (2, 9, 16)])
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749645})
    st.close()
    dati = tmp_path / "processed"

    assert vs.check_due_squadre(out, dati)[0] == []

    senza_taglio = MatchAnalysis.season_xg
    with patch.object(MatchAnalysis, "season_xg",
                      lambda self, nome, tid, before=None: senza_taglio(self, nome, tid)):
        fails, _ = vs.check_due_squadre(out, dati)
    assert any("prima del calcio d'inizio" in f for f in fails), fails[:3]


def test_verify_site_elo_reference_fermo_alla_vigilia():
    """L'oracolo del gate non legge la serie del generatore, né anticipa risultati solo-data."""
    from fda.models.predict import EloModel
    from fda.teams import canonical

    vs = _site_module()
    dates = pd.to_datetime(["2026-08-01 18:00", "2026-08-08 00:00", "2026-08-09 18:00"],
                           utc=True)
    history = pd.DataFrame([
        {"date": dt, "home": name, "away": "Napoli", "home_goals": h, "away_goals": a}
        for dt, name, h, a in zip(dates, ["Inter", "Internazionale", "Inter"],
                                 [2, 0, 4], [0, 3, 0], strict=True)])
    fixtures = pd.DataFrame([{"league_id": 55, "home_name": "Internazionale", "away_name": "Napoli"}])
    noon = dates[1] + pd.Timedelta(hours=12)
    tomorrow = dates[1] + pd.Timedelta(days=1)
    last = dates[-1] + pd.Timedelta(hours=3)
    cuts = [last, noon, tomorrow, dates[0], dates[0] - pd.Timedelta(days=1)]  # disordinati
    ratings, leagues = vs.elo_reference_at_dates(history.iloc[::-1], fixtures, cuts, min_teams=2)
    canonical_history = history.assign(home=history.home.map(canonical))
    after_first = EloModel().fit(canonical_history.head(1)).ratings["Inter"]
    after_second = EloModel().fit(canonical_history.head(2)).ratings["Inter"]
    assert ratings[dates[0] - pd.Timedelta(days=1)] == {}
    assert ratings[dates[0]]["Inter"] == 1500
    assert ratings[noon]["Inter"] == after_first
    assert ratings[tomorrow]["Inter"] == after_second
    assert ratings[last]["Inter"] == EloModel().fit(canonical_history).ratings["Inter"]
    assert ratings[noon]["Inter"] != ratings[last]["Inter"]  # copie, non un dizionario mutabile
    assert leagues[(55, dates[0])]["ranks"] == {"Inter": 1, "Napoli": 1}
    assert (55, dates[0] - pd.Timedelta(days=1)) not in leagues
    assert vs.elo_reference_at_dates(history, fixtures, cuts)[1] == {}  # minimo reale = 10
    assert vs.elo_reference_at_dates(pd.DataFrame(), fixtures, cuts) == ({}, {})


def test_verify_site_forma_non_autocertifica_elo_odierno(tmp_path, monkeypatch):
    """Se generatore e gate condividono team_elo guasto, il vecchio [44] dava ancora verde."""
    from fda.site.analysis import MatchAnalysis
    from fda.site.build import SiteBuilder
    from tests.test_oggi_depth import KICK, _store

    vs = _site_module()
    st = _store(tmp_path)
    st.upsert("fixtures", [
        {"match_id": 200 + i, "league_id": 55, "home_id": 30 + 2*i, "away_id": 31 + 2*i,
         "home_name": f"Pari {2*i}", "away_name": f"Pari {2*i+1}", "utc_kickoff": KICK,
         "status": "scheduled"} for i in range(4)])
    names = ["Alpha", "Beta"] + [f"Pari {i}" for i in range(8)]
    st.write("history", pd.DataFrame([
        {"date": KICK - pd.Timedelta(days=100 - i), "home": name,
         "away": names[(i + 1) % 10], "home_goals": i % 4, "away_goals": 0}
        for i, name in enumerate(names)] + [
        {"date": KICK + pd.Timedelta(days=1), "home": "Beta", "away": "Alpha",
         "home_goals": 10, "away_goals": 0}]))
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_match_pages({100})
    assert vs.check_due_squadre(out, tmp_path / "processed")[0] == []
    page = out / "partite" / "100.html"
    original = page.read_text()
    # Il guasto viene lasciato attivo ANCHE durante la verifica: l'oracolo deve essere separato.
    method = MatchAnalysis.team_elo
    monkeypatch.setattr(MatchAnalysis, "team_elo", lambda self, name, before:
                        method(self, name, KICK + pd.Timedelta(days=2)))
    SiteBuilder(store=st, out_dir=out).build_match_pages({100})
    assert re.findall(r'class="form-opp-rank"[^>]*>', page.read_text()) != re.findall(
        r'class="form-opp-rank"[^>]*>', original)
    fails, _ = vs.check_due_squadre(out, tmp_path / "processed")
    assert any("ranghi/Elo degli avversari" in f for f in fails)
    assert any("forza media avversari" in f for f in fails)
    st.close()
