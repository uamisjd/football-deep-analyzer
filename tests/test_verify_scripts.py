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
