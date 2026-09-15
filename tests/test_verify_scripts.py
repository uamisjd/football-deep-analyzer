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
