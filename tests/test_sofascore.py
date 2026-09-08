from datetime import datetime, timezone

from fda.sources.sofascore import SofaScoreClient


def test_match_event_requires_both_teams_and_picks_nearest():
    kickoff = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    events = [
        {"id": 1, "startTimestamp": kickoff.timestamp() - 7200,
         "homeTeam": {"name": "Roma"}, "awayTeam": {"name": "Atalanta"}},
        {"id": 2, "startTimestamp": kickoff.timestamp() + 60,
         "homeTeam": {"name": "AS Roma"}, "awayTeam": {"name": "Atalanta BC"}},
    ]
    match = SofaScoreClient.match_event(events, "Roma", "Atalanta", kickoff)
    assert match["id"] == 2
    assert SofaScoreClient.match_event(events, "Roma", "Lazio", kickoff) is None


def test_utc_kickoff():
    event = {"startTimestamp": 0}
    assert SofaScoreClient.utc_kickoff(event).year == 1970
    assert SofaScoreClient.utc_kickoff({}) is None
