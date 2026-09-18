import importlib.util
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
        '<a href="mancante.html">x</a><p>1 gare · nan · 1.69 · RegularPlay · clean sheet</p>', encoding="utf-8")
    fails, pages = vs.check_pages(site)
    kinds = {f.split(": ", 1)[1] for f in fails if f.startswith("rotta.html")}
    assert pages == 3
    assert any("collegamento interno mancante" in k for k in kinds)
    assert any("concordanza '1 gare'" in k for k in kinds)
    assert any("residuo 'nan'" in k for k in kinds)
    assert any("decimale col punto '1.69'" in k for k in kinds)
    assert any("inglese" in k for k in kinds)


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
