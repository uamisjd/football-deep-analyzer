"""Test del layer di profondità per le partite «oggi»: trend, precedenti, giocatori, assenze, arbitro.

Ogni test usa uno store sintetico minimo e verifica i numeri a mano, così le soglie
(soglia di minutaggio, ruolo dai codici FotMob, esiti dal punto di vista della squadra di
casa attuale) sono inchiodate da asserzioni e non da un controllo a occhio sul sito.
"""

from __future__ import annotations

import pandas as pd

from fda.site.analysis import POSITION_NAMES, MatchAnalysis
from fda.store import Store

KICK = pd.Timestamp("2026-09-12 18:00", tz="UTC")


def _fixtures() -> pd.DataFrame:
    """Stagione in corso (gara 100 da giocare) più 4 gare giocate fra le stesse squadre."""
    rows = [{"match_id": 100, "league_id": 55, "home_id": 10, "away_id": 20,
             "home_name": "Alpha", "away_name": "Beta", "utc_kickoff": KICK,
             "status": "scheduled", "round": "4", "home_goals": None, "away_goals": None}]
    for i, (mid, hid, aid, hg, ag, day) in enumerate([
            (1, 10, 20, 2, 0, "2026-08-23"), (2, 20, 10, 1, 1, "2026-08-30"),
            (3, 10, 20, 0, 3, "2026-09-05"), (4, 20, 10, 2, 2, "2026-09-07")]):
        rows.append({"match_id": mid, "league_id": 55, "home_id": hid, "away_id": aid,
                     "home_name": "Alpha" if hid == 10 else "Beta",
                     "away_name": "Beta" if aid == 20 else "Alpha",
                     "utc_kickoff": pd.Timestamp(f"{day} 18:00", tz="UTC"),
                     "status": "finished", "round": str(i + 1),
                     "home_goals": hg, "away_goals": ag})
    return pd.DataFrame(rows)


def _store(tmp_path, with_understat: bool = True) -> Store:
    st = Store(tmp_path / "processed")
    st.write("fixtures", _fixtures())
    st.write("lineup", pd.DataFrame([
        # titolare con usualPosition (0 portiere … 3 attaccante) e indisponibile senza ruolo
        {"match_id": 100, "team_id": 10, "player_id": 101, "player_name": "Portiere A", "role": "starter",
         "usual_position_id": 0, "position_id": 11, "season_rating": 6.9, "rating": None,
         "shirt_number": 1, "is_captain": False, "unavailability_type": None, "expected_return": None},
        {"match_id": 100, "team_id": 10, "player_id": 102, "player_name": "Regista A", "role": "starter",
         "usual_position_id": 2, "position_id": 64, "season_rating": 7.2, "rating": None,
         "shirt_number": 8, "is_captain": False, "unavailability_type": None, "expected_return": None},
        {"match_id": 100, "team_id": 10, "player_id": 103, "player_name": "Punta A", "role": "starter",
         "usual_position_id": 3, "position_id": 115, "season_rating": 7.5, "rating": None,
         "shirt_number": 9, "is_captain": True, "unavailability_type": None, "expected_return": None},
        # indisponibile con ruolo solo nello storico (riga 4) e indisponibile senza alcun ruolo
        {"match_id": 100, "team_id": 10, "player_id": 104, "player_name": "Ala A", "role": "unavailable",
         "usual_position_id": None, "position_id": None, "season_rating": None, "rating": None,
         "shirt_number": 11, "is_captain": False, "unavailability_type": "Injury",
         "expected_return": "Early October 2026", "market_value_eur": 12_000_000},
        {"match_id": 100, "team_id": 10, "player_id": 105, "player_name": "Esordiente A", "role": "unavailable",
         "usual_position_id": None, "position_id": None, "season_rating": None, "rating": None,
         "shirt_number": 30, "is_captain": False, "unavailability_type": "Suspended",
         "expected_return": None, "market_value_eur": 500_000},
        {"match_id": 4, "team_id": 10, "player_id": 104, "player_name": "Ala A", "role": "starter",
         "usual_position_id": 1, "position_id": 34, "season_rating": 7.0, "rating": 7.1,
         "shirt_number": 11, "is_captain": False, "unavailability_type": None, "expected_return": None},
    ]))
    st.write("player_stats", pd.DataFrame([
        # Regista A: 180' (soglia 0,4 × 270 = 108 → dentro), xG 0,60 + xA 0,30 = 0,90 → 0,45/90
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "minutes_played", "value": 90.0},
        {"match_id": 3, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "minutes_played", "value": 90.0},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "expected_goals", "value": 0.40},
        {"match_id": 3, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "expected_goals", "value": 0.20},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "expected_assists", "value": 0.30},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "goals", "value": 1.0},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "assists", "value": 2.0},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "chances_created", "value": 4.0},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "rating_title", "value": 7.4},
        {"match_id": 3, "team_id": 10, "player_id": 102, "player_name": "Regista A", "key": "rating_title", "value": 7.0},
        # Punta A: 270', xG 1,20 + xA 0,30 = 1,50 → 0,50/90 (prima in classifica)
        {"match_id": 1, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "minutes_played", "value": 90.0},
        {"match_id": 2, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "minutes_played", "value": 90.0},
        {"match_id": 3, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "minutes_played", "value": 90.0},
        {"match_id": 1, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "expected_goals", "value": 0.60},
        {"match_id": 2, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "expected_goals", "value": 0.60},
        {"match_id": 3, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "expected_assists", "value": 0.30},
        {"match_id": 1, "team_id": 10, "player_id": 103, "player_name": "Punta A", "key": "goals", "value": 2.0},
        # Ala A (indisponibile): 135', 1 gol, xG 0,30 + xA 0,15 → 0,30/90
        {"match_id": 1, "team_id": 10, "player_id": 104, "player_name": "Ala A", "key": "minutes_played", "value": 90.0},
        {"match_id": 2, "team_id": 10, "player_id": 104, "player_name": "Ala A", "key": "minutes_played", "value": 45.0},
        {"match_id": 1, "team_id": 10, "player_id": 104, "player_name": "Ala A", "key": "goals", "value": 1.0},
        {"match_id": 1, "team_id": 10, "player_id": 104, "player_name": "Ala A", "key": "expected_goals", "value": 0.30},
        {"match_id": 1, "team_id": 10, "player_id": 104, "player_name": "Ala A", "key": "expected_assists", "value": 0.15},
        # Portiere A: 270' ma nessuna riga xG/xA → fuori dalla classifica (non è «a zero»)
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "Portiere A", "key": "minutes_played", "value": 90.0},
        {"match_id": 2, "team_id": 10, "player_id": 101, "player_name": "Portiere A", "key": "minutes_played", "value": 90.0},
        {"match_id": 3, "team_id": 10, "player_id": 101, "player_name": "Portiere A", "key": "minutes_played", "value": 90.0},
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "Portiere A", "key": "saves", "value": 4.0},
    ]))
    st.write("team_stats", pd.DataFrame([
        {"match_id": m, "team_id": t, "period": "All", "key": "expected_goals", "value": v,
         "text": f"{v:.2f}"}
        for m, t, v in [(1, 10, 1.80), (1, 20, 0.60), (2, 20, 1.10), (2, 10, 1.40),
                        (3, 10, 0.90), (3, 20, 2.20), (4, 20, 1.60), (4, 10, 1.20)]
    ]))
    st.write("h2h", pd.DataFrame([
        # 5 precedenti: dal punto di vista di Alpha (casa in gara 100) → 2V 2N 1P
        {"match_id": 100, "home_id": 10, "away_id": 20, "home_goals": 2, "away_goals": 0,
         "utc": pd.Timestamp("2025-05-10 18:00", tz="UTC"), "league": "Serie A"},
        {"match_id": 100, "home_id": 20, "away_id": 10, "home_goals": 1, "away_goals": 1,
         "utc": pd.Timestamp("2025-01-10 18:00", tz="UTC"), "league": "Serie A"},
        {"match_id": 100, "home_id": 10, "away_id": 20, "home_goals": 0, "away_goals": 1,
         "utc": pd.Timestamp("2024-09-10 18:00", tz="UTC"), "league": "Coppa Italia"},
        {"match_id": 100, "home_id": 20, "away_id": 10, "home_goals": 0, "away_goals": 3,
         "utc": pd.Timestamp("2024-03-10 18:00", tz="UTC"), "league": "Serie A"},
        {"match_id": 100, "home_id": 10, "away_id": 20, "home_goals": 1, "away_goals": 1,
         "utc": pd.Timestamp("2023-11-10 18:00", tz="UTC"), "league": "Serie A"},
        # riga anomala (terza squadra) e riga successiva al calcio d'inizio: entrambe escluse
        {"match_id": 100, "home_id": 10, "away_id": 30, "home_goals": 5, "away_goals": 0,
         "utc": pd.Timestamp("2023-05-10 18:00", tz="UTC"), "league": "Serie A"},
        {"match_id": 100, "home_id": 10, "away_id": 20, "home_goals": 9, "away_goals": 9,
         "utc": pd.Timestamp("2026-09-20 18:00", tz="UTC"), "league": "Serie A"},
    ]))
    # match_info con tutte le colonne lette da build(): i valori non usati restano None
    _mi_extra = {"home_id": None, "away_id": None, "home_goals": None, "away_goals": None, "round": None,
                 "utc_kickoff": None, "coverage_level": None, "lineup_type": None, "home_formation": None,
                 "away_formation": None, "home_rating": None, "away_rating": None,
                 "home_starters_value_eur": None, "away_starters_value_eur": None,
                 "home_avg_starter_age": None, "away_avg_starter_age": None, "stadium_name": None,
                 "stadium_city": None, "stadium_lat": None, "stadium_lon": None, "stadium_capacity": None,
                 "attendance": None, "weather_desc": None, "weather_temp_c": None,
                 "weather_precip_chance": None, "weather_wind": None, "home_xg": None, "away_xg": None,
                 "home_xgot": None, "away_xgot": None, "h2h_home_wins": None, "h2h_draws": None,
                 "h2h_away_wins": None}
    st.write("match_info", pd.DataFrame([
        {**_mi_extra, "match_id": 100, "league_id": 55, "status": "scheduled", "home_id": 10, "away_id": 20,
         "referee_name": "Mario Rossi", "referee_matches": 20,
         "referee_yellows_per_match": 5.0, "referee_reds_total": 2, "referee_penalties_total": 4,
         "referee_fouls_per_match": 30.0},
        {**_mi_extra, "match_id": 4, "league_id": 55, "status": "finished", "home_id": 20, "away_id": 10,
         "referee_name": "AltraPersona", "referee_matches": 10,
         "referee_yellows_per_match": 3.0, "referee_reds_total": 0, "referee_penalties_total": 0,
         "referee_fouls_per_match": 26.0},
    ]))
    if with_understat:
        st.write("understat_team_matches", pd.DataFrame([
            {"league_slug": "Serie_A", "season": "2026", "team_id": 1, "team_name": "Alpha",
             "date": d, "is_home": h, "goals": g, "goals_against": a, "xg": x, "xga": xa,
             "npxg": x, "npxga": xa, "npxgd": 0.0, "xpts": xp, "pts": p,
             "ppda": 12.0, "ppda_allowed": 14.0, "deep": 20, "deep_allowed": 18, "result": "W"}
            for d, h, g, a, x, xa, xp, p in [
                ("2026-08-23", True, 2, 0, 1.8, 0.6, 2.6, 3),
                ("2026-08-30", False, 1, 1, 1.4, 1.1, 1.4, 1),
                ("2026-09-05", True, 0, 3, 0.9, 2.2, 0.3, 0),
                ("2026-09-07", False, 2, 2, 1.2, 1.6, 0.8, 1)]
        ]))
    return st


def test_position_names_start_from_zero():
    """Il ruolo FotMob parte da 0: 0 portiere, 3 attaccante (misurato su 616 formazioni)."""
    assert POSITION_NAMES[0] == "portiere"
    assert POSITION_NAMES[1] == "difensore"
    assert POSITION_NAMES[2] == "centrocampista"
    assert POSITION_NAMES[3] == "attaccante"
    assert 4 not in POSITION_NAMES


def test_role_resolution_chain(tmp_path):
    """Ruolo: usualPosition → positionId mappato → storico distinte → stringa vuota."""
    ma = MatchAnalysis(_store(tmp_path))
    assert ma._role_it(101, 0, 11) == "portiere"
    assert ma._role_it(999, None, 11) == "portiere"        # solo positionId tattico
    assert ma._role_it(104, None, None) == "difensore"     # dallo storico (gara 4, usualPosition 1)
    assert ma._role_it(105, None, None) == ""              # mai schierato: nessun ruolo inventato
    un = ma.unavailable(100, 10)
    by_name = {u["name"]: u for u in un}
    assert by_name["Ala A"]["pos"] == "difensore"
    assert by_name["Esordiente A"]["pos"] == ""


def test_arrival_trend_understat(tmp_path):
    """Trend da Understat: medie per gara, punti contro xPTS, PPDA, avversario ed esito."""
    ma = MatchAnalysis(_store(tmp_path))
    a = ma.arrival_trend("Alpha", 10, n=4)
    assert a["source"] == "Understat" and a["played"] == 4
    assert a["xg_pm"] == (1.8 + 1.4 + 0.9 + 1.2) / 4
    assert a["xga_pm"] == (0.6 + 1.1 + 2.2 + 1.6) / 4
    assert a["pts"] == 5 and a["xpts"] == 5.1
    assert a["ppda"] == 12.0
    assert [r["opp"] for r in a["rows"]] == ["Beta"] * 4     # avversario recuperato dal calendario
    assert [r["res"] for r in a["rows"]] == ["V", "N", "P", "N"]
    assert a["home_pm"] == (1.8 + 0.9) / 2 and a["away_pm"] == (1.4 + 1.2) / 2
    assert a["trend"] is None                                 # meno di 6 gare: nessuna etichetta


def test_arrival_trend_falls_back_to_fotmob(tmp_path):
    """Senza Understat il trend usa gli xG FotMob delle gare finite e gli xPTS di Poisson."""
    ma = MatchAnalysis(_store(tmp_path, with_understat=False))
    a = ma.arrival_trend("Alpha", 10, n=6)
    assert a["source"] == "FotMob" and a["played"] == 4
    assert a["xg_pm"] == (1.8 + 1.4 + 0.9 + 1.2) / 4
    assert a["xga_pm"] == (0.6 + 1.1 + 2.2 + 1.6) / 4
    assert a["pts"] == 5                                       # 2V 2N 0P
    assert 0 < a["xpts"] < 12                                  # xPTS ricalcolato, non la fonte
    assert a["ppda"] is None                                   # FotMob non pubblica il PPDA
    assert a["rows"][0]["opp"] == "Beta" and a["rows"][0]["res"] == "V"


def test_h2h_pattern_from_current_home_side(tmp_path):
    """Precedenti: esiti dal punto di vista della squadra di casa attuale, riga anomala esclusa."""
    ma = MatchAnalysis(_store(tmp_path))
    hp = ma.h2h_pattern(100, 10, 20, KICK)
    assert hp["n"] == 5                                        # la riga con la terza squadra è scartata
    assert (hp["wins"], hp["draws"], hp["losses"]) == (2, 2, 1)
    assert hp["gpg"] == (2 + 2 + 1 + 3 + 2) / 5                # gol totali a gara, sempre positivi
    assert hp["btts"] == 2 / 5 and hp["over25"] == 1 / 5
    assert hp["draw_drought"] == 1                             # l'ultimo precedente non è pari, il 2° sì
    assert hp["top_scores"][0]["score"] == "1-1" and hp["top_scores"][0]["n"] == 2
    assert hp["first"] == pd.Timestamp("2023-11-10 18:00", tz="UTC")
    assert hp["last"] == pd.Timestamp("2025-05-10 18:00", tz="UTC")
    assert ma.h2h_pattern(100, 10, 20, pd.Timestamp("2020-01-01", tz="UTC")) is None  # < 3 casi


def test_key_players_deep_ranks_by_expected_contribution(tmp_path):
    """(xG+xA)/90: soglia relativa al minutaggio, esclusi i giocatori senza dato xG."""
    ma = MatchAnalysis(_store(tmp_path))
    kp = ma.key_players_deep(10)
    assert kp["floor"] == 108                                  # 0,4 × 270 minuti del più impiegato
    assert kp["eligible"] == 3                                 # Regista, Punta, Ala
    assert [r["name"] for r in kp["rows"]] == ["Punta A", "Regista A", "Ala A"]
    top = kp["rows"][0]
    assert top["contrib_p90"] == 1.5 / 3.0                     # (1,20 xG + 0,30 xA) su 270'
    assert top["goals"] == 2 and top["minutes"] == 270 and top["pos"] == "attaccante"
    assert kp["rows"][1]["chances"] == 4 and kp["rows"][1]["rating"] == 7.2   # media voti 7,4 e 7,0
    assert all("Portiere A" != r["name"] for r in kp["rows"])  # senza righe xG non entra in classifica


def test_absences_weight(tmp_path):
    """Infermeria pesata: ruolo, minuti, gol+assist, contributo perso, titolari fuori."""
    ma = MatchAnalysis(_store(tmp_path))
    ab = ma.absences_weight(100, 10)
    assert ab["n"] == 2 and ab["has_stats"] is True
    assert ab["players"][0]["name"] == "Ala A"                 # prima per contributo (0,30/90)
    assert ab["players"][0]["starter"] is True                 # 135' ≥ metà dei 990/11 = 90' medi
    assert ab["players"][0]["goals"] == 1 and ab["players"][0]["minutes"] == 135
    assert ab["contrib_lost_p90"] == 0.45 / 1.5                # 0,45 xG+xA su 135' → 0,30/90
    assert ab["starters_out"] == 1
    assert ab["players"][1]["name"] == "Esordiente A" and ab["players"][1]["minutes"] is None
    assert ma.absences_weight(100, 20) is None                 # nessuna assenza → nessuna card


def test_referee_profile_against_league_average(tmp_path):
    """Arbitro a confronto con la media delle designazioni della stessa lega."""
    ma = MatchAnalysis(_store(tmp_path))
    rp = ma.referee_profile(100)
    assert rp["name"] == "Mario Rossi" and rp["yellows"] == 5.0
    assert rp["league_yellows"] == 4.0                         # media di 5,0 e 3,0
    assert rp["league_fouls"] == 28.0 and rp["league_matches"] == 2
    assert ma.referee_profile(999) is None                     # partita senza designazione


def test_build_exposes_new_pre_match_keys(tmp_path):
    """build() espone le nuove chiavi solo in pre-partita (nessun segnaposto a vuoto)."""
    ma = MatchAnalysis(_store(tmp_path))
    ctx = ma.build(100)
    for k in ("home_arrival", "away_arrival", "h2h_pattern", "home_key_deep", "away_key_deep",
              "home_absences", "away_absences", "referee_profile"):
        assert k in ctx
    assert ctx["home_arrival"]["played"] == 4
    assert ctx["away_arrival"]["source"] == "FotMob" and ctx["away_arrival"]["played"] == 4
    assert ctx["h2h_pattern"]["n"] == 5
    assert ctx["home_absences"]["n"] == 2 and ctx["away_absences"] is None
    ctx_fin = ma.build(4)
    assert ctx_fin["home_arrival"] is None and ctx_fin["h2h_pattern"] is None
    assert ctx_fin["referee_profile"]["name"] == "AltraPersona"
