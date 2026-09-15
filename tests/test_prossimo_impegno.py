"""Test offline di next_commitment («Il prossimo impegno») e della conversione
delle grandi occasioni (shot_summary.big_goals) per la sezione post-partita."""

import pandas as pd
import pytest

from fda.site.analysis import MatchAnalysis
from fda.store import Store

KO = lambda s: pd.Timestamp(s, tz="UTC")

FX = pd.DataFrame([
    # la gara appena finita: sabato 12/09 ore 18:00 UTC
    {"match_id": 10, "league_id": 55, "season": "2026", "round": "3",
     "utc_kickoff": KO("2026-09-12 18:00"), "home_id": 2, "home_name": "Inter",
     "away_id": 1, "away_name": "Roma", "home_goals": 3, "away_goals": 1,
     "status": "finished", "source": "fotmob"},
    # annullata in mezzo: non deve diventare il prossimo impegno di nessuno
    {"match_id": 13, "league_id": 55, "season": "2026", "round": "4",
     "utc_kickoff": KO("2026-09-14 18:00"), "home_id": 2, "home_name": "Inter",
     "away_id": 5, "away_name": "Lazio", "home_goals": None, "away_goals": None,
     "status": "cancelled", "source": "fotmob"},
    # prossima di campionato dell'Inter (dopo la coppa del mercoledì)
    {"match_id": 11, "league_id": 55, "season": "2026", "round": "4",
     "utc_kickoff": KO("2026-09-21 16:00"), "home_id": 2, "home_name": "Inter",
     "away_id": 3, "away_name": "Milan", "home_goals": None, "away_goals": None,
     "status": "scheduled", "source": "fotmob"},
    # prossima della Roma: martedì 15/09 ore 18:45 UTC = 20:45 in Italia
    {"match_id": 12, "league_id": 55, "season": "2026", "round": "4",
     "utc_kickoff": KO("2026-09-15 18:45"), "home_id": 4, "home_name": "Napoli",
     "away_id": 1, "away_name": "Roma", "home_goals": None, "away_goals": None,
     "status": "scheduled", "source": "fotmob"},
])

CUPS = pd.DataFrame([
    {"match_id": 92, "league_id": 42, "league_key": "UCL", "cup_name": "Champions League",
     "season": "2026", "round": "MD1", "utc_kickoff": KO("2026-09-16 19:00"),
     "home_id": 9, "home_name": "Ajax", "away_id": 2, "away_name": "Inter",
     "home_goals": None, "away_goals": None, "status": "scheduled", "source": "fotmob"},
])

SHOTS = pd.DataFrame([
    # Inter, gara 10: 2 grandi occasioni (xG ≥ 0,30) di cui 1 convertita; l'autogol è escluso
    {"match_id": 10, "shot_id": 1, "team_id": 2, "player_id": 7, "player_name": "Punta Uno",
     "minute": 12, "xg": 0.40, "event_type": "Goal", "is_on_target": True, "is_blocked": False,
     "is_own_goal": False, "is_inside_box": True},
    {"match_id": 10, "shot_id": 2, "team_id": 2, "player_id": 7, "player_name": "Punta Uno",
     "minute": 55, "xg": 0.35, "event_type": "AttemptSaved", "is_on_target": True,
     "is_blocked": False, "is_own_goal": False, "is_inside_box": True},
    {"match_id": 10, "shot_id": 3, "team_id": 2, "player_id": 8, "player_name": "Ala Due",
     "minute": 70, "xg": 0.10, "event_type": "Goal", "is_on_target": True, "is_blocked": False,
     "is_own_goal": False, "is_inside_box": True},
    {"match_id": 10, "shot_id": 4, "team_id": 2, "player_id": 9, "player_name": "Difensore Tre",
     "minute": 80, "xg": 0.50, "event_type": "Goal", "is_on_target": True, "is_blocked": False,
     "is_own_goal": True, "is_inside_box": True},
])


@pytest.fixture()
def an(tmp_path):
    st = Store(tmp_path / "prossimo")
    st.write("fixtures", FX)
    st.write("cup_fixtures", CUPS)
    st.write("shots", SHOTS)
    return MatchAnalysis(st)


def test_prossimo_impegno_coppa_batte_campionato(an):
    """L'Inter rigioca mercoledì in Champions (4 giorni di riposo), non lunedì 21."""
    nx = an.next_commitment(2, KO("2026-09-12 18:00"))
    assert nx is not None
    assert nx["line"] == ("Champions League · Ajax in trasferta · "
                          "mercoledì 16/09, ore 21:00 · 4 giorni di riposo")
    assert nx["is_cup"] and nx["rest"] == 4 and nx["opponent"] == "Ajax"


def test_prossimo_impegno_campionato(an):
    """La Roma rigioca martedì in campionato: 3 giorni di riposo, trasferta a Napoli."""
    nx = an.next_commitment(1, KO("2026-09-12 18:00"))
    assert nx is not None
    assert nx["line"] == ("Campionato · Napoli in trasferta · "
                          "martedì 15/09, ore 20:45 · 3 giorni di riposo")
    assert not nx["is_cup"] and nx["rest"] == 3


def test_annullata_saltata_e_nessun_impegno(an):
    """La gara annullata del 14 non conta; la Lazio (solo quella) non ha prossimo impegno."""
    assert an.next_commitment(5, KO("2026-09-12 18:00")) is None


def test_grandi_occasioni_convertite(an):
    """2 grandi occasioni, 1 convertita; autogol escluso da conteggi e gol."""
    s = an.shot_summary(10, 2)
    assert s["n"] == 3 and s["goals"] == 2
    assert s["big_chances"] == 2 and s["big_goals"] == 1
