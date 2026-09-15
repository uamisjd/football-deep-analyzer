"""Test offline di clash_ranks (graduatorie + duello chiave) e key_status («giocherà?»)."""

import pandas as pd
import pytest

from fda.site.analysis import MatchAnalysis
from fda.store import Store

KO = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731

FX = pd.DataFrame([
    {"match_id": 8, "league_id": 55, "season": "2026", "round": "8",
     "utc_kickoff": KO("2026-09-16 18:00"), "home_id": 1, "home_name": "Roma",
     "away_id": 2, "away_name": "Inter", "home_goals": None, "away_goals": None,
     "status": "scheduled", "source": "fotmob"},
])

STANDINGS = pd.DataFrame([
    {"league_code": "ITA1", "team_id": 1, "team_name": "Roma", "rank": 1, "played": 3,
     "goals_for": 8, "goals_against": 3, "goal_diff": 5, "points": 9},
    {"league_code": "ITA1", "team_id": 2, "team_name": "Inter", "rank": 2, "played": 3,
     "goals_for": 6, "goals_against": 3, "goal_diff": 3, "points": 7},
    {"league_code": "ITA1", "team_id": 3, "team_name": "Milan", "rank": 3, "played": 3,
     "goals_for": 4, "goals_against": 4, "goal_diff": 0, "points": 4},
    {"league_code": "ITA1", "team_id": 4, "team_name": "Lazio", "rank": 4, "played": 3,
     "goals_for": 2, "goals_against": 6, "goal_diff": -4, "points": 1},
])

LINEUP = pd.DataFrame([
    {"match_id": 8, "team_id": 1, "player_id": 500, "player_name": "Top Uno", "role": "starter"},
    {"match_id": 8, "team_id": 1, "player_id": 501, "player_name": "Riserva Uno", "role": "sub"},
    {"match_id": 8, "team_id": 1, "player_id": 502, "player_name": "Fermo Uno", "role": "unavailable",
     "unavailability_type": "injury", "expected_return": "day to day"},
    # la fonte elenca Fermo Uno anche titolare: deve vincere l'indisponibilità
    {"match_id": 8, "team_id": 1, "player_id": 502, "player_name": "Fermo Uno", "role": "starter"},
])


@pytest.fixture()
def an(tmp_path):
    st = Store(tmp_path / "duello")
    st.write("fixtures", FX)
    st.write("fotmob_standings", STANDINGS)
    lu = LINEUP.copy()
    for col in ("position_id", "usual_position_id"):
        lu[col] = pd.NA
    st.write("lineup", lu)
    return MatchAnalysis(st)


def test_clash_ranks_graduatorie_e_duello(an):
    cr = an.clash_ranks("Roma", "Inter")
    assert cr["home_line"] == "1º attacco · 1ª difesa per gol in campionato (su 4)"
    assert cr["away_line"] == "2º attacco · 2ª difesa per gol in campionato (su 4)"
    # skew casa 1,60×0,75 = 1,20 > skew ospite 1,20×0,75 = 0,90 → duello casa
    assert cr["duel_line"] == ("duello chiave: attacco Roma (1,60× la media gol della lega) "
                               "contro difesa Inter (0,75× la media gol subiti): il lato più "
                               "sbilanciato del match")


def test_key_status_titolare_panchina_assente(an):
    sts = an.key_status(8, 1)
    assert sts[500] == {"status": "starter"}
    assert sts[501] == {"status": "sub"}
    assert sts[502]["status"] == "unavailable"
    assert sts[502]["note"] == "infortunio · giorno per giorno"
    assert an.key_status(8, 2) == {}
