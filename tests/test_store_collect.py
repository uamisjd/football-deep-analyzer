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


def _remap_ids(obj, mapping):
    """Sostituisce gli id squadra (chiavi id/teamId) nel JSON campione per renderlo coerente col calendario."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("id", "teamId") and str(v) in mapping:
                obj[k] = type(v)(mapping[str(v)]) if isinstance(v, (int, str)) else v
            else:
                _remap_ids(v, mapping)
    elif isinstance(obj, list):
        for v in obj:
            _remap_ids(v, mapping)
    return obj


class FakeFotMob(FotMobClient):
    # partita campione (Inter 8636 - Napoli 9875) → squadre del calendario campione
    TEAM_MAP = {5749645: ("8636", "6504"), 5749669: ("8600", "8543")}

    def fixtures_raw(self, league_id, season_str=None):
        return _load("fotmob_fixtures_sample.json")

    def match_details_raw(self, match_id, finished_hint=None):
        raw = _load("fotmob_match_sample.json")
        raw["general"]["matchId"] = str(match_id)
        home, away = self.TEAM_MAP.get(match_id, ("8636", "9875"))
        return _remap_ids(raw, {"8636": home, "9875": away})

    def league_raw(self, league_id, season_str=None):
        return _load("fotmob_leagues_sample.json")


class FakeUnderstat(UnderstatClient):
    def league_raw(self, slug, season):
        return _load("understat_league_sample.json")


class FakeEspn(EspnClient):
    def scoreboard_raw(self, code, day=None):
        return _load("espn_scoreboard_sample.json")

    def standings_raw(self, code):
        return _load("espn_standings_sample.json")


class FakeEspnNoStandings(FakeEspn):
    def standings_raw(self, code):
        raise RuntimeError("standings temporarily unavailable")


class FakeOpenMeteo:
    """Previsione fissa, senza rete (per i test del passo meteo)."""

    def __init__(self):
        self.http = type("S", (), {"stats": type("T", (), {"requests": 1, "cache_hits": 0})()})()

    def forecast(self, lat, lon, when):
        return {"temp_c": 21.0, "precip_prob": 60.0, "desc": "pioggia debole", "code": 61,
                "hour": f"{when:%Y-%m-%dT%H:00}"}


class FakeFotMobNoWeather(FakeFotMob):
    """Come FakeFotMob, ma la partita futura non ha ancora il meteo FotMob."""

    def match_details_raw(self, match_id, finished_hint=None):
        raw = super().match_details_raw(match_id, finished_hint)
        if match_id == 5749669:  # la futura: meteo non ancora pubblicato da FotMob
            raw["content"].pop("weather", None)
        return raw


class FakeFotMobNoTable(FakeFotMob):
    def league_raw(self, league_id, season_str=None):
        raise RuntimeError("leagues temporarily unavailable")


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
    assert rep.standings == 3                # tabella FotMob raccolta
    tab = st.read("fotmob_standings")
    assert tab.loc[tab.team_name == "Inter", "points"].item() == 9
    assert tab.loc[tab.team_name == "Inter", "rank"].item() == 1

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


def test_collect_continues_when_league_table_fails(tmp_path):
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMobNoTable(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    assert any("fotmob standings" in e for e in rep.errors)
    assert rep.fixtures == 3 and rep.matches_fetched == 2
    assert st.read("fotmob_standings").empty
    st.close()


def test_collect_survives_bad_match_save(tmp_path, monkeypatch):
    """Una partita che esplode durante il salvataggio non deve fermare il run.

    Regressione del run `daily` 2026-09-08 14:31 UTC su main: il collect moriva su
    NED1 nel nuovo backfill perché `bundle_to_dicts` + `store.upsert` erano fuori
    da `_safe`, e la pipe senza pipefail mascherava il fallimento.
    """
    import fda.collect as coll

    real_btd = coll.bundle_to_dicts

    def boom_on_one(bundle):
        rows = real_btd(bundle)
        if bundle.info.match_id == 5749669:  # la seconda partita in finestra
            raise ValueError("riga anomala nel bundle (simula il crash del run 14:31 UTC)")
        return rows

    monkeypatch.setattr(coll, "bundle_to_dicts", boom_on_one)
    st = Store(tmp_path / "processed")
    rep = coll.collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    # il run arriva in fondo: errore isolato sulla partita guasta, il resto è raccolto
    assert any("fotmob save 5749669" in e and "ValueError" in e for e in rep.errors)
    assert rep.matches_fetched == 1
    assert rep.standings == 3 and rep.understat_rows > 0 and rep.espn_events > 0
    assert set(st.read("match_info").match_id) == {5749645}   # l'altra partita è salva
    st.close()


def test_collect_backfills_season_finished_ned1(tmp_path):
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("NED1"), st,     # finestra default ±3 gg: la finita del 22/08 è fuori
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    assert rep.errors == []
    assert rep.matches_fetched == 1        # Udinese-Lazio in finestra
    assert rep.matches_backfilled == 1     # Inter-Monza 22/08 recuperata fuori finestra
    mi = st.read("match_info")
    assert mi.loc[mi.match_id == 5749645, "home_xg"].notna().item()
    # secondo run: la finita è già in archivio, niente da recuperare
    rep2 = collect_league(
        league("NED1"), st,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    assert rep2.matches_backfilled == 0 and rep2.matches_fetched == 1
    st.close()


def test_collect_backfills_season_finished_all_leagues(tmp_path):
    """Dal 2026-09-09 il backfill vale per TUTTE le leghe (fase 3: schede giocatore
    complete dall'1ª giornata, docs/07): anche ITA1 (che ha Understat) recupera le
    finite fuori finestra, una sola volta."""
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("ITA1"), st,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    assert rep.errors == []
    assert rep.matches_backfilled == 1     # Inter-Monza 22/08 recuperata fuori finestra
    assert 5749645 in set(st.read("match_info").match_id)
    # secondo run: la finita è già in archivio, niente da recuperare
    rep2 = collect_league(
        league("ITA1"), st,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    assert rep2.matches_backfilled == 0
    st.close()


def test_collect_uses_espn_scoreboard_when_standings_fail(tmp_path):
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspnNoStandings(), today=date(2026, 9, 6),
    )
    assert any("espn standings" in error for error in rep.errors)
    assert rep.espn_events > 0
    assert not st.read("espn_events").empty
    st.close()


def test_collect_openmeteo_weather_fallback(tmp_path):
    """Passo meteo: previsione Open-Meteo solo per i futuri senza meteo FotMob e con coordinate."""
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMobNoWeather(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), openmeteo=FakeOpenMeteo(), today=date(2026, 9, 6),
    )
    assert rep.errors == []
    wf = st.read("weather_forecast")
    assert 5749669 in set(wf.match_id)          # futura (Udinese-Lazio) senza meteo FotMob
    assert 5749645 not in set(wf.match_id)      # la finita non è un futura
    assert wf.loc[wf.match_id == 5749669, "desc"].item() == "pioggia debole"
    # richieste openmeteo registrate nel report
    assert rep.requests["openmeteo"] >= 1
    st.close()


def test_collect_no_forecast_when_fotmob_weather_present(tmp_path):
    """Se FotMob ha già il meteo non si chiama Open-Meteo (fonte primaria rispettata)."""
    st = Store(tmp_path / "processed")
    collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), openmeteo=FakeOpenMeteo(), today=date(2026, 9, 6),
    )
    assert st.read("weather_forecast").empty
    st.close()


def test_collect_skips_openmeteo_when_not_provided(tmp_path):
    """Senza client Open-Meteo il passo meteo è disattivato (test offline, nessuna rete)."""
    st = Store(tmp_path / "processed")
    rep = collect_league(
        league("ITA1"), st, past_days=30, future_days=30,
        fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
        espn=FakeEspn(), today=date(2026, 9, 6),
    )
    assert st.read("weather_forecast").empty
    assert "openmeteo" not in rep.requests     # passo disattivato: nessuna fonte registrata
    st.close()


def test_upsert_replace_by_snapshot(tmp_path):
    """Le tabelle per-partita sono snapshot: lo snapshot nuovo sostituisce il vecchio.

    Regressione sui dati 2026-09-12: 573 coppie (partita, giocatore) in doppia riga su
    15985 (titolare della formazione probabile + subentrato/indisponibile di quella
    ufficiale) → «formazioni» da 13-19 nomi sul sito.
    """
    st = Store(tmp_path / "processed")
    st.upsert("lineup", [
        {"match_id": 1, "team_id": 10, "player_id": 100, "role": "starter", "player_name": "A"},
        {"match_id": 1, "team_id": 10, "player_id": 101, "role": "starter", "player_name": "B"},
    ])
    st.upsert("lineup", [
        {"match_id": 1, "team_id": 10, "player_id": 100, "role": "sub", "player_name": "A"},
        {"match_id": 1, "team_id": 10, "player_id": 102, "role": "starter", "player_name": "C"},
    ], replace_by="match_id")
    df = st.read("lineup")
    assert len(df) == 2                                          # B esce, A cambia ruolo
    assert df.loc[df.player_id == 100, "role"].iloc[0] == "sub"
    assert set(df.player_id) == {100, 102}
    # le altre partite non vengono toccate
    st.upsert("lineup", [{"match_id": 2, "team_id": 10, "player_id": 100, "role": "starter",
                          "player_name": "A"}], replace_by="match_id")
    assert len(st.read("lineup")) == 3
    st.close()


def test_upsert_events_double_substitution_same_minute(tmp_path):
    """Due sostituzioni allo stesso minuto sopravvivono (chiave `events` non le distingue).

    Le righe di sostituzione hanno `player_id` nullo (i due giocatori stanno in `swap`):
    con la sola fusione per chiave una delle due veniva scartata — 6,5 sostituzioni per
    partita in archivio invece di ~10.
    """
    st = Store(tmp_path / "processed")
    rows = [
        {"match_id": 7, "type": "Substitution", "minute": 68, "minute_added": None, "is_home": True,
         "player_id": None, "player_name": None, "swap": "[(1, 'Entra Uno'), (2, 'Esce Due')]"},
        {"match_id": 7, "type": "Substitution", "minute": 68, "minute_added": None, "is_home": True,
         "player_id": None, "player_name": None, "swap": "[(3, 'Entra Tre'), (4, 'Esce Quattro')]"},
    ]
    st.upsert("events", rows, replace_by="match_id")
    df = st.read("events")
    assert len(df) == 2
    st.close()
