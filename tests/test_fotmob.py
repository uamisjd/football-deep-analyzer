import json
from pathlib import Path

import pytest

from fda.sources.fotmob import FotMobClient, bundle_to_dicts

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # Nessuna rete: si usano solo i parser su JSON campione.
    return FotMobClient(raw_dir=tmp_path_factory.mktemp("raw"))


def test_parse_fixtures(client):
    raw = json.loads((FIX / "fotmob_fixtures_sample.json").read_text())
    fx = client.parse_fixtures(55, raw)
    assert [f.status for f in fx] == ["finished", "scheduled", "cancelled"]
    assert fx[0].home_goals == 4 and fx[0].away_goals == 1
    assert fx[1].home_goals is None                      # non ancora giocata: niente 0-0 finti
    assert fx[1].utc_kickoff.isoformat() == "2026-09-07T18:45:00+00:00"
    assert fx[0].league_id == 55 and fx[0].season == "2026/2027"


def test_parse_match_bundle(client):
    raw = json.loads((FIX / "fotmob_match_sample.json").read_text())
    b = client.parse_match(raw)
    info = b.info
    assert info.match_id == 5749666 and info.status == "finished"
    assert (info.home_goals, info.away_goals) == (3, 2)
    assert info.referee_name == "Simone Sozza" and info.referee_yellows_per_match == 3.76
    assert info.referee_penalties_total == 18 and info.referee_matches == 33
    assert info.stadium_lat == 45.478 and info.attendance == 75423
    assert info.home_xg == 3.86 and info.away_xg == 2.43
    assert info.home_xgot == 3.20 and info.away_xgot == 1.95
    assert info.lineup_type == "official"
    assert (info.home_formation, info.away_formation) == ("3-5-2", "4-3-3")
    assert info.home_starters_value_eur == 303886692
    assert info.weather_desc == "Partly Cloudy" and info.weather_temp_c == 25
    assert (info.h2h_home_wins, info.h2h_draws, info.h2h_away_wins) == (10, 12, 9)

    # tiri
    assert len(b.shots) == 2
    goal = next(s for s in b.shots if s.event_type == "Goal")
    assert goal.player_name == "Lautaro Martínez" and goal.xg == 0.88 and goal.is_inside_box

    # statistiche squadra: percentuali e "486 (89%)" -> 486
    ts = {(s.team_id, s.period, s.key): s for s in b.team_stats}
    assert ts[(8636, "All", "BallPossesion")].value == 63
    assert ts[(8636, "All", "accurate_passes")].value == 486
    assert ts[(9875, "All", "total_shots")].value == 16
    assert ts[(8636, "FirstHalf", "expected_goals")].value == 1.50
    assert (8636, "All", "shots") not in ts                # le righe "title" vengono scartate

    # statistiche giocatore
    ps = {(p.player_id, p.key): p for p in b.player_stats}
    assert ps[(415539, "rating_title")].value == 7.47
    assert ps[(415539, "accurate_passes")].total == 23
    assert not any(k == (415539, None) for k in ps)         # il campo boolean "Shotmap" è escluso

    # formazioni e indisponibili
    roles = {(p.player_id, p.role) for p in b.lineup}
    assert (690230, "starter") in roles and (611223, "sub") in roles
    assert (843099, "unavailable") in roles and (129745, "coach") in roles
    mct = next(p for p in b.lineup if p.player_id == 843099)
    assert mct.unavailability_type == "injury" and mct.expected_return == "Mid October 2026"
    cap = next(p for p in b.lineup if p.player_id == 690230)
    assert cap.is_captain and cap.rating == 9.1

    # eventi, momentum, h2h, insight
    assert [e["type"] for e in b.events] == ["Goal", "Substitution", "Card", "Half"]
    assert b.events[1]["swap"][0] == ("940829", "Carlos Augusto")
    assert len(b.momentum) == 2
    assert len(b.h2h_matches) == 1 and b.h2h_matches[0]["home_goals"] == 1   # la futura è esclusa
    assert b.insights[0]["text"].startswith("Haven't lost")


def test_bundle_to_dicts(client):
    raw = json.loads((FIX / "fotmob_match_sample.json").read_text())
    d = bundle_to_dicts(client.parse_match(raw))
    assert set(d) == {"match_info", "shots", "team_stats", "player_stats", "lineup",
                      "events", "momentum", "h2h", "insights"}
    assert all(row["match_id"] == 5749666 for row in d["events"] + d["h2h"] + d["momentum"])
