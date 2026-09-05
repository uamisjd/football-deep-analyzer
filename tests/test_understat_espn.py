import json
from pathlib import Path

from fda.sources.espn import EspnClient
from fda.sources.understat import UnderstatClient, team_season_table

FIX = Path(__file__).parent / "fixtures"


def test_understat_parsers():
    raw = json.loads((FIX / "understat_league_sample.json").read_text())
    uc = UnderstatClient()
    matches = uc.parse_matches("Serie_A", 2026, raw)
    assert len(matches) == 2
    played, future = matches
    assert played.is_result and played.home_xg == 1.23456 and played.home_goals == 1
    assert not future.is_result and future.home_xg is None and future.forecast_w == 0.5
    assert played.utc_kickoff.isoformat() == "2026-08-30T16:30:00+00:00"

    tm = uc.parse_team_matches("Serie_A", 2026, raw)
    assert len(tm) == 3
    nap_home = next(r for r in tm if r.team_id == 72 and r.is_home)
    assert nap_home.ppda == 10.0 and nap_home.ppda_allowed == 15.0
    assert nap_home.xpts == 1.5 and nap_home.deep == 8 and nap_home.result == "d"

    table = team_season_table(tm)
    nap = next(r for r in table if r["team_id"] == 72)
    assert nap["played"] == 2 and nap["pts"] == 4 and nap["xpts"] == 3.9
    assert nap["xgd"] == round(1.23456 + 2.0 - 0.98765 - 0.5, 3)
    assert nap["pts_minus_xpts"] == 0.1 and nap["ppda"] == 9.0
    assert table[0]["team_id"] == 72          # ordinata per punti

    players = uc.parse_players("Serie_A", 2026, raw)
    assert players[0].player_name == "Rasmus Højlund" and players[0].xg == 1.8 and players[0].minutes == 250


def test_espn_scoreboard_and_standings():
    ec = EspnClient()
    raw = json.loads((FIX / "espn_scoreboard_sample.json").read_text())
    events, stats = ec.parse_scoreboard("ned.1", raw)
    assert [e.status for e in events] == ["finished", "scheduled"]
    assert (events[0].home_goals, events[0].away_goals) == (1, 3)
    assert events[1].home_goals is None
    assert events[0].attendance == 12650 and events[0].home_form == "LWLLW"
    assert events[0].venue == "Goffertstadion" and events[0].city == "Nijmegen"
    keys = {(s.team_id, s.key): s.value for s in stats}
    assert keys[(147, "possessionPct")] == 62.5 and keys[(142, "totalShots")] == 15
    assert not any(k == "appearances" for _, k in keys)

    rows = ec.parse_standings("ita.1", json.loads((FIX / "espn_standings_sample.json").read_text()))
    assert [r.team_name for r in rows] == ["AS Roma", "Internazionale"]
    assert rows[0].points == 9 and rows[0].goal_diff == 7 and rows[0].note == "Champions League"
    assert rows[1].goals_against == 3
