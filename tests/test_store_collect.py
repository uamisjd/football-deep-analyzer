import json
from datetime import date
from pathlib import Path

import pandas as pd

from fda.collect import collect_league
from fda.config import league
from fda.sources.espn import EspnClient
from fda.sources.fotmob import FotMobClient
from fda.sources.understat import UnderstatClient
from fda.store import Store

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def test_store_upsert_and_sql(tmp_path):
    st = Store(tmp_path)
    assert st.upsert("fixtures", [{"match_id": 1, "status": "scheduled", "home_goals": None},
                                  {"match_id": 2, "status": "scheduled", "home_goals": None}]) == 2
    # aggiornamento della stessa chiave: la riga nuova sostituisce la vecchia
    st.upsert("fixtures", [{"match_id": 1, "status": "finished", "home_goals": 2}])
    df = st.read("fixtures")
    assert len(df) == 2
    assert df.loc[df.match_id == 1, "status"].item() == "finished"
    assert st.sql("SELECT count(*) AS n FROM fixtures WHERE status='finished'")["n"].item() == 1
    assert st.summary().iloc[0]["table"] == "fixtures"
    st.close()


class FakeFotMob(FotMobClient):
    def fixtures_raw(self, league_id, season_str=None):
        return _load("fotmob_fixtures_sample.json")

    def match_details_raw(self, match_id, finished_hint=None):
        raw = _load("fotmob_match_sample.json")
        raw["general"]["matchId"] = str(match_id)
        return raw


class FakeUnderstat(UnderstatClient):
    def league_raw(self, slug, season):
        return _load("understat_league_sample.json")


class FakeEspn(EspnClient):
    def scoreboard_raw(self, code, day=None):
        return _load("espn_scoreboard_sample.json")

    def standings_raw(self, code):
        return _load("espn_standings_sample.json")


def test_collect_league_offline(tmp_path):
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(), espn=FakeEspn(),
        today=date(2026, 9, 6),
    )
    assert rep.errors == []
    assert rep.fixtures == 3
    assert rep.matches_fetched == 2          # la partita cancellata è esclusa
    assert rep.understat_rows > 0 and rep.espn_events > 0

    info = st.read("match_info")
    assert set(info.match_id) == {5749645, 5749669}
    assert st.read("shots").shape[0] == 4    # 2 tiri x 2 partite
    assert st.read("lineup").query("role == 'unavailable'").shape[0] == 4
    assert "understat_team_matches" in set(st.summary()["table"])
    assert st.read("espn_standings").iloc[0]["team_name"] == "AS Roma"

    # secondo run: la partita finita non viene riscaricata, quella futura sì (formazioni/assenze)
    rep2 = collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(), espn=FakeEspn(),
        today=date(2026, 9, 6),
    )
    assert rep2.matches_skipped == 1 and rep2.matches_fetched == 1
    status = st.read("source_status")
    assert status["ok"].all() and len(status) == 6
    # i datetime sono salvati in UTC
    assert str(pd.read_parquet(st.path("fixtures"))["utc_kickoff"].dt.tz) == "UTC"
    st.close()
