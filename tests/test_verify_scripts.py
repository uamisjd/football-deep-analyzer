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
