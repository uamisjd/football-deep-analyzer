"""Test del layer di profondità per le partite «oggi»: trend, precedenti, giocatori, assenze, arbitro.

Ogni test usa uno store sintetico minimo e verifica i numeri a mano, così le soglie
(soglia di minutaggio, ruolo dai codici FotMob, esiti dal punto di vista della squadra di
casa attuale) sono inchiodate da asserzioni e non da un controllo a occhio sul sito.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from fda.site.analysis import POSITION_NAMES, MatchAnalysis, prediction_meta
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
    assert a["trend_recent"] is None and a["trend_before"] is None


def test_favorite_track_record_bands_and_current_flag():
    """Fasce storiche del pronostico: conteggi, frequenze e Wilson ricostruiti dal backtest,
    riga «questa» sulla fascia del favorito in scheda (l'infallibilità è la verifica)."""
    from fda.models.predict import wilson_interval

    ma = MatchAnalysis.__new__(MatchAnalysis)
    favs = ([0.37] * 40 + [0.45] * 60 + [0.55] * 60 + [0.66] * 60 + [0.80] * 60 +
            [0.36] * 20)  # 20 partite nella microcoda <30: fascia 34-40% passa comunque
    rows = []
    for i, v in enumerate(favs):
        rest = 1.0 - v
        rows.append({"p_home": v, "p_draw": rest * 0.6, "p_away": rest * 0.4,
                     "outcome": 0 if i % 3 else 2})  # il favorito (casa) esce ~1 su 3
    ma.backtest = pd.DataFrame(rows)
    pred = {"p_home": 0.52, "p_draw": 0.28, "p_away": 0.20}
    fr = ma.favorite_track_record(pred)
    assert fr is not None and fr["fav"] == 0.52
    cur = [r for r in fr["rows"] if r["current"]]
    assert len(cur) == 1 and cur[0]["label"] == "fra 50% e 60%"
    r = cur[0]
    assert r["n"] == 60 and r["k"] == 40          # outcome=0 (casa=favorito) per i%3 != 0: 40 su 60
    assert r["obs"] == pytest.approx(40 / 60)
    wl, wh = wilson_interval(40, 60)
    assert r["wil_lo"] == wl and r["wil_hi"] == wh
    assert [x["label"] for x in fr["rows"]] == [
        "fino al 40%", "fra 40% e 50%", "fra 50% e 60%", "fra 60% e 75%", "oltre il 75%"]
    # favorito al confine superiore di fascia → fascia successiva
    fr2 = ma.favorite_track_record({"p_home": 0.80, "p_draw": 0.12, "p_away": 0.08})
    assert [r["label"] for r in fr2["rows"] if r["current"]] == ["oltre il 75%"]


def test_first_goal_clock_pubblica_distribuzione_osservata_e_banda():
    """P2.3 (`docs/28` §3): la card «Quando arriva il primo gol» non è più di solo testo.

    Il micro-visivo ha due righe: sopra la distribuzione **osservata** dei primi gol (quarti
    d'ora, ricavata dagli stessi eventi della quota di 1° tempo), sotto la banda del **modello**
    per questa partita. Qui si verificano i due pezzi separatamente: i conteggi devono chiudere
    sul numero di partite in cui un gol è arrivato, e le posizioni della banda devono essere i
    quartili del modello portati sulla scala 0–90 dell'asse.
    """
    rows = []
    # 40 partite con il primo gol nel 1° quarto d'ora, 30 nel 3°, 20 nell'ultimo
    for i in range(40):
        rows.append({"type": "Goal", "minute": 7, "minute_added": None, "match_id": i})
    for i in range(30):
        rows.append({"type": "Goal", "minute": 38, "minute_added": None, "match_id": 100 + i})
    for i in range(20):
        rows.append({"type": "Goal", "minute": 80, "minute_added": None, "match_id": 200 + i})
    # una partita senza gol: non entra nella distribuzione, ma conta per la quota «0-0»
    rows.append({"type": "Shot", "minute": 12, "minute_added": None, "match_id": 999})
    ma = MatchAnalysis.__new__(MatchAnalysis)
    ma.events = pd.DataFrame(rows)
    pred = {"lambda_home": 1.5, "lambda_away": 1.5, "dc_rho": 0.0}
    fg = ma.first_goal_clock(pred)
    assert fg is not None
    assert fg["n_first"] == 90, "solo le partite con almeno un gol entrano nella distribuzione"
    per100 = [b["per100"] for b in fg["bins"]]
    assert per100 == [44, 0, 33, 0, 0, 22], per100          # 40/90, 30/90, 20/90 arrotondati
    assert [b["h"] for b in fg["bins"]] == [100, 0, 75, 0, 0, 50]
    assert sum(b["n"] for b in fg["bins"]) == fg["n_first"]
    assert fg["senza_gol_oss"] == pytest.approx(1 / 91)     # una partita su 91 senza gol
    # la banda: i quartili del modello in percentuale dei 90', non in minuti. La quota di
    # 1° tempo è quella MISURATA su questi eventi (70 gol su 90 entro il 45'), non un'ipotesi
    lam = 3.0
    s_ev = 70 / 90
    r1, r2 = s_ev * lam / 45, (1 - s_ev) * lam / 45
    s_ht = np.exp(-r1 * 45)
    for chiave, p_ in (("from", 0.25), ("med", 0.50), ("to", 0.75)):
        tail = 1.0 - p_
        t = (-np.log(tail) / r1) if tail >= s_ht else 45.0 + (-np.log(tail) - r1 * 45) / r2
        assert fg["band"][chiave] == pytest.approx(100.0 * t / 90.0, abs=0.01), chiave
    assert fg["band"]["from"] < fg["band"]["med"] < fg["band"]["to"]
    assert not fg["band"]["q1_oltre"]


def test_first_goal_clock_banda_oltre_il_90_va_a_fondo_scala():
    """Un quartile oltre il fischio finale non inventa un minuto: la banda finisce a 100%."""
    ma = MatchAnalysis.__new__(MatchAnalysis)
    # 40 primi gol nel 1° tempo e 20 nel 2°: la quota di 1° tempo è 2/3, e con un λ totale di
    # 0,4 il 3° quartile cade oltre il fischio finale (il caso «dopo il 90'»)
    righe = ([{"type": "Goal", "minute": 30, "minute_added": None, "match_id": i} for i in range(40)] +
             [{"type": "Goal", "minute": 60, "minute_added": None, "match_id": 100 + i}
              for i in range(20)])
    ma.events = pd.DataFrame(righe)
    fg = ma.first_goal_clock({"lambda_home": 0.2, "lambda_away": 0.2, "dc_rho": 0.0})
    assert fg is not None
    assert fg["q"][2][1] is None and fg["band"]["q3_oltre"] and fg["band"]["to"] == 100.0


def test_league_goals_percentile_la_barra_e_un_extra_non_la_card():
    """Se la scala di lega non ha spazio la card resta e la barra no (P2.3).

    Le 121 partite NED1 del test qui sotto stanno tutte a 3,4: la frase ha senso, il grafico
    no. Il campo `viz` vale None e il template non disegna nulla — la card non sparisce mai
    per colpa di un grafico (sarebbe una differenza di struttura fra due schede).
    """
    ma = MatchAnalysis.__new__(MatchAnalysis)
    ma.preds = pd.DataFrame([
        {"match_id": 1000 + i, "league_key": "NED1", "lambda_home": 1.7, "lambda_away": 1.7,
         "made_at": "2026-01-01"} for i in range(121)])
    lp = ma.league_goals_percentile({"league_key": "NED1", "lambda_home": 1.7,
                                     "lambda_away": 1.7, "dc_rho": 0.0})
    assert lp is not None and lp["viz"] is None
    # con una distribuzione vera la barra c'è, e il segno sta sul percentile pubblicato
    righe = [dict(r) for r in ma.preds.to_dict("records")]
    for i in range(40):
        righe.append({"match_id": 5000 + i, "league_key": "NED1", "lambda_home": 1.0 + i / 20,
                      "lambda_away": 1.0 + i / 20, "made_at": "2026-01-01"})
    ma.preds = pd.DataFrame(righe)
    lp = ma.league_goals_percentile({"league_key": "NED1", "lambda_home": 2.0,
                                     "lambda_away": 1.0, "dc_rho": 0.0})
    assert lp is not None and lp["viz"] is not None
    assert 0.0 <= lp["viz"]["pct"] <= 100.0
    assert lp["viz"]["lo"] <= lp["viz"]["hi"]
    # la posizione è monotona nei gol attesi: la stessa scala, un λ più basso sta più a sinistra
    lp_basso = ma.league_goals_percentile({"league_key": "NED1", "lambda_home": 1.0,
                                           "lambda_away": 1.0, "dc_rho": 0.0})
    lp_alto = ma.league_goals_percentile({"league_key": "NED1", "lambda_home": 3.0,
                                          "lambda_away": 3.0, "dc_rho": 0.0})
    assert lp_basso["viz"]["pct"] < lp["viz"]["pct"] < lp_alto["viz"]["pct"]


def test_league_goals_percentile_uses_same_league_distribution_only():
    """Il percentile dei gol attesi conta SOLO le partite dello stesso campionato:
    3,4 gol attesi può essere «tanto» in una lega e «poco» in NED1 — il lettore deve
    ricevere la posizione sulla scala giusta, rifaciibile da predictions.parquet."""
    ma = MatchAnalysis.__new__(MatchAnalysis)
    rows = []
    for i in range(120):  # NED1: tutte a 3,4 gol attesi totali
        rows.append({"match_id": 1000 + i, "league_key": "NED1", "lambda_home": 1.7,
                     "lambda_away": 1.7, "made_at": "2026-01-01"})
    rows.append({"match_id": 42, "league_key": "NED1", "lambda_home": 2.0,
                 "lambda_away": 2.4, "made_at": "2026-01-01"})
    for i in range(80):  # ESP1: più basse — se entrassero nel conteggio il percentile mentirebbe
        rows.append({"match_id": 2000 + i, "league_key": "ESP1", "lambda_home": 1.0,
                     "lambda_away": 1.0, "made_at": "2026-01-01"})
    ma.preds = pd.DataFrame(rows)
    pred = {"league_key": "NED1", "lambda_home": 2.0, "lambda_away": 2.4, "dc_rho": 0.0}
    lp = ma.league_goals_percentile(pred)
    assert lp is not None
    assert lp["n"] == 121, "le altre leghe devono restare fuori"
    assert lp["below"] == pytest.approx(120 / 121)      # 4,4 supera tutte le partite NED1
    assert lp["label"] == "fra le partite che promettono più gol"
    assert lp["league"] == "Eredivisie"
    # scheda «chiusa»: stessa logica, quartile basso → etichetta opposta
    rows_low = rows[:1] + [{"match_id": 3000 + i, "league_key": "NED1", "lambda_home": 3.0,
                            "lambda_away": 3.0, "made_at": "2026-01-01"} for i in range(119)]
    ma.preds = pd.DataFrame(rows_low + [dict(r, match_id=42) for r in rows[:1]])
    lp2 = ma.league_goals_percentile(pred)
    assert lp2["label"] == "fra le partite più chiuse del campionato"


def test_first_goal_clock_two_half_rate_closed_form_and_90_cap():
    """Tasso a due tempi: s MISURATA dagli eventi (regola minuto≤45 = 1° tempo), quartili in
    forma chiusa; λ microscopici spingerebbero il 3° quartile a 208' — la coda va «oltre fischio»,
    non oltre 90, e la card deve mostrare «dopo il 90'» (o il verificatore sgama l'inventato)."""
    rows = ([{"type": "Goal", "minute": 30, "minute_added": None, "match_id": 1}] * 45 +
            [{"type": "Goal", "minute": 60, "minute_added": None, "match_id": 2}] * 45)
    ma = MatchAnalysis.__new__(MatchAnalysis)
    ma.events = pd.DataFrame(rows)
    pred = {"lambda_home": 1.8, "lambda_away": 1.8, "dc_rho": 0.0}
    fg = ma.first_goal_clock(pred)
    assert fg is not None and fg["s_half"] == 0.5 and fg["n_goals"] == 90
    lam = 3.6
    rate = 0.5 * lam / 45                                     # = 0,04 gol/min in entrambi i tempi
    assert fg["q"][0][1] == pytest.approx(-np.log(0.75) / rate)
    assert fg["q"][1][1] == pytest.approx(np.log(2.0) / rate)
    assert fg["q"][2][1] == pytest.approx(-np.log(0.25) / rate)
    assert fg["s_ht"] == pytest.approx(np.exp(-0.5 * lam))
    assert fg["zero"] == pytest.approx(np.exp(-lam))
    # quartile che cade nel SECONDO tempo controllato nel ramo dopo 45:
    fg2 = ma.first_goal_clock({"lambda_home": 0.9, "lambda_away": 0.9, "dc_rho": 0.0})
    r2 = 0.5 * 1.8 / 45
    assert fg2["q"][2][1] == pytest.approx(45 + (-np.log(0.25) - 0.5 * 1.8) / r2)  # 69,3'
    # λ piccoli: il 3° quartile supera il fischio finale → None (mai «104'» in faccia al lettore)
    fg3 = ma.first_goal_clock({"lambda_home": 0.3, "lambda_away": 0.3, "dc_rho": 0.0})
    assert fg3["q"][2][1] is None and fg3["q"][0][1] is not None
    # regola del minuto esatto: 45' e 45+x valgono 1° tempo
    ma.events = pd.DataFrame(
        [{"type": "Goal", "minute": 45, "minute_added": None, "match_id": 1}] * 30 +
        [{"type": "Goal", "minute": 45, "minute_added": 2, "match_id": 1}] * 30)
    fg4 = ma.first_goal_clock(pred)
    assert fg4 is None or fg4["s_half"] == 1.0


def test_narrative_reports_form_and_absences_weight_in_every_league(tmp_path):
    """Forma sempre presente (non solo se estrema) e «giocatore di peso» = titolare abituale
    (criterio interno alla squadra, uguale in tutte e 7 le leghe — docs/20 §13)."""
    ma = MatchAnalysis(_store(tmp_path))
    ctx = ma.build(100)
    narr = ctx["narrative"]
    # P2.5 (`docs/28` §3): la riga tiene i numeri e il giudizio, non ripete più la serie per
    # lettere — quella sta nel badge in testa alla scheda (`home_form_badge`/`away_form_badge`)
    assert "Alpha: 5 punti nelle ultime 4 — andamento nella norma." in narr
    assert "Beta: 5 punti nelle ultime 4 — andamento nella norma." in narr
    assert not any("(VNPN)" in s or "(PNVN)" in s for s in narr)
    # il badge della forma: serie, punti e finestra dichiarata, per entrambe le squadre
    for lato, seq, pt in (("home", "VNPN", 5), ("away", "PNVN", 5)):
        b = ctx[f"{lato}_form_badge"]
        assert b["n"] == 4 and b["points"] == pt and b["sequence"] == seq
    # Ala A (135' su 855 di squadra → titolare, min >= metà media) pesa anche se vale
    # 12M (sotto la vecchia soglia assoluta di 15M); Esordiente A non pesa.
    # P2.4 (docs/19 §2.8): la frase è stata riscritta in italiano corrente — il criterio
    # di «peso» (titolare abituale) non cambia, cambia solo come viene detto.
    # P2.2: la frase tiene il peso e non ripete più i nomi (sono nella tabella dell'infermeria)
    frase_assenze = next(s for s in narr if "deve rinunciare a" in s)
    assert frase_assenze.startswith("Alpha deve rinunciare a 2 assenti, uno dei quali titolare abituale —")
    assert "Ala A" not in frase_assenze and "Esordiente A" not in frase_assenze


def test_badge_della_forma_solo_con_almeno_tre_gare(tmp_path):
    """P2.5 (`docs/28` §3): il badge della forma in testa alla scheda è la stessa serie della
    narrativa, con la stessa soglia: da tre gare giocate in su (due pallini non sono una forma).

    Il badge è un dato del contesto (`home_form_badge` / `away_form_badge`), non una stringa
    scritta a mano: serie, punti e numerosità arrivano dal calendario, così il template può
    ripeterli nella descrizione per chi usa un lettore di schermo senza ricalcolarli.
    """
    st = _store(tmp_path)
    # due sole gare giocate per squadra: sotto la soglia, niente badge (e niente riga)
    fx = _fixtures()
    st.write("fixtures", fx[fx.match_id.isin([100, 3, 4])])
    ctx = MatchAnalysis(st).build(100)
    assert ctx["home_form_badge"] is None and ctx["away_form_badge"] is None
    assert not any("punti nelle ultime" in s for s in ctx["narrative"])


def test_arrival_trend_publishes_the_numbers_behind_the_judgement():
    """La tendenza nominata porta accanto i due valori che la generano (docs/20 §10)."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        ma = MatchAnalysis(_store(Path(td)))
        # 6 gare fittizie: ultime 3 con xG bassi → «in calo» con i numeri a verbale
        base_dates = ["2026-08-01", "2026-08-08", "2026-08-15", "2026-08-22", "2026-08-29", "2026-09-05"]
        xgs = [2.4, 2.4, 2.4, 0.8, 0.8, 0.8]
        ma.fixtures = pd.DataFrame([
            {"match_id": 900 + i, "league_id": 55, "season": "2026", "utc_kickoff": d,
             "home_id": 10, "home_name": "Alpha", "away_id": 20 + i, "away_name": f"Avv{i}",
             "home_goals": 1, "away_goals": 0, "status": "finished", "source": "t", "round": i}
            for i, d in enumerate(base_dates)])
        ma.us_team = pd.DataFrame([
            {"team_name": "Alpha", "date": d, "is_home": True, "xg": x, "xga": 1.0,
             "goals": 1, "goals_against": 0, "ppda": 10.0, "xpts": 2.0, "pts": 3}
            for d, x in zip(base_dates, xgs)])
        a = ma.arrival_trend("Alpha", 10, n=6)
        assert a["trend"] == "in calo"
        assert a["trend_recent"] == pytest.approx(0.8) and a["trend_before"] == pytest.approx(2.4)
        assert a["trend_threshold"] == 0.15


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
    # sotto 8 casi con la casa attuale in casa: nessuna sotto-serie pubblicata
    assert hp["venue"] is None


def test_h2h_venue_subset_published_from_eight_cases(tmp_path):
    """I precedenti si distinguono per campo solo quando il campione regge una frase (docs/20 §11)."""
    ma = MatchAnalysis(_store(tmp_path))
    rows = [{"match_id": 100, "home_id": 10 if i % 2 == 0 else 20, "away_id": 20 if i % 2 == 0 else 10,
             "home_goals": 1 + int(i % 3 == 0), "away_goals": 1,
             "utc": pd.Timestamp(f"20{20 - i:02d}-05-01 18:00", tz="UTC"), "league": "Serie A"}
            for i in range(16)]          # 16 precedenti; 8 con Alpha in casa: V N N V N N V N
    ma.h2h_df = pd.DataFrame(rows)
    hp = ma.h2h_pattern(100, 10, 20, KICK)
    assert hp is not None and hp["venue"] is not None
    assert hp["venue"]["n"] == 8
    assert (hp["venue"]["wins"], hp["venue"]["draws"], hp["venue"]["losses"]) == (3, 5, 0)
    assert hp["venue"]["wins"] + hp["venue"]["draws"] + hp["venue"]["losses"] == hp["venue"]["n"]
    assert hp["venue"]["gpg"] == pytest.approx((3 + 2 + 2 + 3 + 2 + 2 + 3 + 2) / 8)
    # calcio d'inizio troppo presto: prima del 2006 resta un solo precedente (< 3) → niente blocco
    assert ma.h2h_pattern(100, 10, 20, pd.Timestamp("2006-01-01", tz="UTC")) is None


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


def test_prediction_meta_is_explicit_about_margin_and_agreement():
    """La lista non chiama «confidenza» ciò che è solo un margine e confronto fra modelli."""
    pred = {"p_home": 0.381, "p_draw": 0.247, "p_away": 0.372,
            "elo_p_home": 0.36, "elo_p_draw": 0.25, "elo_p_away": 0.39}
    meta = prediction_meta(pred, "Alpha", "Beta")
    assert meta["top_key"] == "1" and meta["top_name"] == "Alpha"
    # il margine è la differenza fra le percentuali intere stampate (38 − 37), non quello grezzo
    assert meta["pct"] == [38, 25, 37] and meta["top_pct"] == 38 and meta["second_pct"] == 37
    assert meta["margin_pp"] == 1
    assert meta["signal_label"] == "DC ed Elo divergono" and meta["signal_tone"] == "split"
    assert meta["elo_gap_pp"] == 2.1
    draw = prediction_meta({"p_home": 0.29, "p_draw": 0.43, "p_away": 0.28}, "Alpha", "Beta")
    assert draw["top_key"] == "X" and draw["top_name"] == "Pareggio"
    assert prediction_meta({"p_home": 0.5}, "Alpha", "Beta") is None


def test_prediction_meta_signal_names_both_engines_with_recomputeable_numbers():
    """Il segnale DC/Elo nomina i due soggetti e le percentuali tornano dai vettori salvati."""
    agree = prediction_meta(
        {"p_home": 0.402, "p_draw": 0.258, "p_away": 0.340,
         "dc_p_home": 0.402, "dc_p_draw": 0.260, "dc_p_away": 0.338,
         "elo_p_home": 0.394, "elo_p_draw": 0.263, "elo_p_away": 0.343,
         "w_dc": 0.7, "ensemble_mode": "tilt"}, "Alpha", "Beta")
    assert agree["signal_tone"] == "agree"
    assert agree["signal_label"] == ("DC ed Elo sullo stesso preferito (Alpha): "
                                     "DC 40,2% · Elo 39,4% · distanza 0,8 punti")
    split = prediction_meta(
        {"p_home": 0.478, "p_draw": 0.281, "p_away": 0.241,
         "dc_p_home": 0.478, "dc_p_draw": 0.281, "dc_p_away": 0.241,
         "elo_p_home": 0.240, "elo_p_draw": 0.537, "elo_p_away": 0.223,
         "w_dc": 0.7, "ensemble_mode": "tilt"}, "Alpha", "Beta")
    assert split["signal_tone"] == "split"
    assert split["signal_label"] == "Preferiti diversi: DC Alpha 47,8% · Elo Pareggio 53,7%"
    # il margine coincide sempre con la differenza delle percentuali stampate accanto a esso
    for m in (agree, split):
        assert m["margin_pp"] == m["top_pct"] - m["second_pct"]


def test_list_context_reuses_form_and_h2h_without_building_post_match_cards(tmp_path):
    """Il riepilogo della lista espone solo dati già verificabili e mantiene l'ordine della forma."""
    ma = MatchAnalysis(_store(tmp_path))
    ctx = ma.list_context(100, 10, 20, "Alpha", "Beta", KICK)
    assert ctx["home"]["form"]["sequence"] == "VNPN"
    assert ctx["home"]["form"]["points"] == 5
    assert ctx["away"]["form"]["n"] == 4
    assert ctx["h2h_n"] == 5
    assert ctx["prediction"] is None


def test_build_exposes_new_pre_match_keys(tmp_path):
    """build() espone le nuove chiavi solo in pre-partita (nessun segnaposto a vuoto)."""
    ma = MatchAnalysis(_store(tmp_path))
    ctx = ma.build(100)
    for k in ("home_arrival", "away_arrival", "h2h_pattern", "home_key_deep", "away_key_deep",
              "home_absences", "away_absences", "referee"):
        assert k in ctx
    assert ctx["home_arrival"]["played"] == 4
    assert ctx["away_arrival"]["source"] == "FotMob" and ctx["away_arrival"]["played"] == 4
    assert ctx["h2h_pattern"]["n"] == 5
    assert ctx["home_absences"]["n"] == 2 and ctx["away_absences"] is None
    ctx_fin = ma.build(4)
    assert ctx_fin["home_arrival"] is None and ctx_fin["h2h_pattern"] is None
    assert ctx_fin["referee"]["name"] == "AltraPersona"
    # P1.3 (docs/19 §2.6): un solo profilo arbitro — la chiave duplicata non esiste più
    assert "referee_profile" not in ctx and "referee_profile" not in ctx_fin
    # il profilo unico porta anche il confronto con la lega che il vecchio dict non aveva
    assert ctx["referee"]["league_yellows"] == 4.0


# ---- P1.2 (docs/19 §2.6): etichette arbitro relative alla lega, campione minimo ------------
def test_referee_narrative_relative_to_league(tmp_path):
    """In una lega severa (media 5,04) 5,0 gialli/partita è «nella media», non «molto severo»."""
    ma = MatchAnalysis(_store(tmp_path))
    base = {"home_name": "Alpha", "away_name": "Beta"}
    frasi = ma.narrative({**base, "referee": {"name": "Hugo Miguel", "matches": 34, "yellows": 5.0,
                                              "pens": 2, "league_yellows": 5.04}})
    ref = [f for f in frasi if f.startswith("Arbitro Hugo Miguel")]
    assert len(ref) == 1
    assert "nella media del campionato" in ref[0]
    assert "molto severo" not in ref[0]
    assert "(5,0 la media di lega)" in ref[0]


def test_referee_narrative_above_and_below_league(tmp_path):
    ma = MatchAnalysis(_store(tmp_path))
    base = {"home_name": "Alpha", "away_name": "Beta"}
    sopra = ma.narrative({**base, "referee": {"name": "A", "matches": 30, "yellows": 6.0,
                                              "pens": 1, "league_yellows": 5.0}})
    sotto = ma.narrative({**base, "referee": {"name": "B", "matches": 30, "yellows": 3.0,
                                              "league_yellows": 4.0}})
    assert any("sopra la media del campionato" in f for f in sopra)
    assert any("sotto la media del campionato" in f for f in sotto)
    # nessun giudizio assoluto residuo
    assert not any("molto severo" in f or "permissivo" in f for f in sopra + sotto)


def test_referee_narrative_small_sample_numbers_only(tmp_path):
    """Campione ridotto (minimo 6, mediana 33): il numero sì, l'aggettivo mai, no doppi numeri."""
    ma = MatchAnalysis(_store(tmp_path))
    base = {"home_name": "Alpha", "away_name": "Beta"}
    frasi = ma.narrative({**base, "referee": {"name": "C", "matches": 6, "yellows": 6.4,
                                              "league_yellows": 4.0}})
    ref = [f for f in frasi if f.startswith("Arbitro C")]
    assert len(ref) == 1
    assert "campione ridotto, nessuna valutazione" in ref[0]
    assert "6 6 gare" not in ref[0]           # it_plural include già il numero
    assert "su 6 gare designate" in ref[0]
    assert not any("molto severo" in f for f in frasi)


def test_referee_narrative_without_league_mean_no_judgment(tmp_path):
    """Senza media di lega si pubblicano i numeri, non un giudizio non verificabile."""
    ma = MatchAnalysis(_store(tmp_path))
    base = {"home_name": "Alpha", "away_name": "Beta"}
    frasi = ma.narrative({**base, "referee": {"name": "D", "matches": 30, "yellows": 5.9,
                                              "league_yellows": None}})
    ref = [f for f in frasi if f.startswith("Arbitro D")]
    assert len(ref) == 1
    assert "media del campionato" not in ref[0] and "molto severo" not in ref[0]
    assert "30 gare designate" in ref[0]


# ---- post-partita: assist, tempi, portieri, fisiche, statistiche di dettaglio --------------
def _finished_store(tmp_path) -> Store:
    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame([
        {"match_id": 1, "league_id": 55, "home_id": 10, "away_id": 20, "home_name": "Alpha",
         "away_name": "Beta", "utc_kickoff": pd.Timestamp("2026-09-05 18:00", tz="UTC"),
         "status": "finished", "round": "3", "home_goals": 2, "away_goals": 1},
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 1, "team_id": 10, "player_id": 201, "player_name": "Punta A", "role": "starter",
         "usual_position_id": 3, "position_id": 115, "rating": 8.0, "season_rating": 7.4,
         "shirt_number": 9, "is_captain": False, "unavailability_type": None, "expected_return": None,
         "market_value_eur": 1_000_000},
        {"match_id": 1, "team_id": 10, "player_id": 202, "player_name": "Portiere A", "role": "starter",
         "usual_position_id": 0, "position_id": 11, "rating": 7.0, "season_rating": 7.0,
         "shirt_number": 1, "is_captain": False, "unavailability_type": None, "expected_return": None,
         "market_value_eur": 1_000_000},
        {"match_id": 1, "team_id": 20, "player_id": 203, "player_name": "Terzino B", "role": "starter",
         "usual_position_id": 1, "position_id": 34, "rating": 6.5, "season_rating": 6.8,
         "shirt_number": 2, "is_captain": False, "unavailability_type": None, "expected_return": None,
         "market_value_eur": 1_000_000},
        {"match_id": 1, "team_id": 20, "player_id": 204, "player_name": "Portiere B", "role": "starter",
         "usual_position_id": 0, "position_id": 11, "rating": 6.9, "season_rating": 6.9,
         "shirt_number": 1, "is_captain": False, "unavailability_type": None, "expected_return": None,
         "market_value_eur": 1_000_000},
    ]))
    st.write("events", pd.DataFrame([
        # gol con assist, gol di testa senza assist, autogol (descrizione ignorata)
        {"match_id": 1, "type": "Goal", "minute": 12, "minute_added": None, "is_home": True,
         "player_id": 201, "player_name": "Punta A", "card": None, "own_goal": False,
         "assist_player_id": 202, "home_score": 0, "away_score": 0, "swap": None,
         "goal_description": None},
        {"match_id": 1, "type": "Goal", "minute": 55, "minute_added": 1, "is_home": True,
         "player_id": 201, "player_name": "Punta A", "card": None, "own_goal": False,
         "assist_player_id": None, "home_score": 1, "away_score": 0, "swap": None,
         "goal_description": "Header"},
        # autogol di un giocatore di Alpha: il gol è accreditato a Beta (is_home=False)
        {"match_id": 1, "type": "Goal", "minute": 70, "minute_added": None, "is_home": False,
         "player_id": 201, "player_name": "Punta A", "card": None, "own_goal": True,
         "assist_player_id": None, "home_score": 2, "away_score": 0, "swap": None,
         "goal_description": "Own goal"},
    ]))
    stats = [("expected_goals", 1.8, 0.6), ("total_shots", 14, 5), ("ShotsOnTarget", 6, 2),
             ("BallPossesion", 62, 38), ("corners", 4, 1), ("big_chance", 3, 0),
             ("duel_won", 40, 33), ("interceptions", 9, 12), ("Offsides", 2, 1)]
    rows = []
    for period, mul in (("All", 1.0), ("FirstHalf", 0.4), ("SecondHalf", 0.6)):
        for key, hv, av in stats:
            rows.append({"match_id": 1, "team_id": 10, "period": period, "key": key,
                         "value": round(hv * mul, 2), "text": f"{hv * mul:.2f}"})
            rows.append({"match_id": 1, "team_id": 20, "period": period, "key": key,
                         "value": round(av * mul, 2), "text": f"{av * mul:.2f}"})
    st.write("team_stats", pd.DataFrame(rows))
    ps = []
    for pid, name, tid, mins, saves, gp in ((201, "Punta A", 10, 90, None, None),
                                            (202, "Portiere A", 10, 90, 3, 0.8),
                                            (203, "Terzino B", 20, 90, None, None),
                                            (204, "Portiere B", 20, 90, 5, -1.2)):
        ps.append({"match_id": 1, "team_id": tid, "player_id": pid, "player_name": name,
                   "key": "minutes_played", "value": float(mins)})
        if saves is not None:
            ps.append({"match_id": 1, "team_id": tid, "player_id": pid, "player_name": name,
                       "key": "saves", "value": float(saves)})
            ps.append({"match_id": 1, "team_id": tid, "player_id": pid, "player_name": name,
                       "key": "goals_prevented", "value": gp})
    # il terzino ha un errore che porta a un gol: non deve diventare il portiere
    ps.append({"match_id": 1, "team_id": 20, "player_id": 203, "player_name": "Terzino B",
               "key": "errors_led_to_goal", "value": 1.0})
    # metriche fisiche solo per la squadra di casa
    for pid, name, dist, spr, top in ((201, "Punta A", 10_000, 12, 33.5), (202, "Portiere A", 5_000, 2, 28.0)):
        for key, val in (("physical_metrics_distance_covered", dist),
                         ("physical_metrics_number_of_sprints", spr),
                         ("physical_metrics_sprinting", 200),
                         ("physical_metrics_topspeed", top)):
            ps.append({"match_id": 1, "team_id": 10, "player_id": pid, "player_name": name,
                       "key": key, "value": float(val)})
    st.write("player_stats", pd.DataFrame(ps))
    return st


def test_timeline_assist_and_goal_kind(tmp_path):
    """Cronaca: assist risolto dalla distinta, tipo di gol tradotto, autogol senza tipo."""
    ma = MatchAnalysis(_finished_store(tmp_path))
    goals = [e for e in ma.timeline(1) if e["type"] == "Goal"]
    # l'autogol è accreditato alla squadra che ne beneficia (is_home già al netto, 22/22)
    assert [g["score"] for g in goals] == ["1-0", "2-0", "2-1"]
    assert goals[2]["scorer_home"] is True          # chi segna è di Alpha, il gol vale per Beta
    assert goals[0]["assist"] == "Portiere A" and goals[0]["kind"] == ""
    assert goals[1]["assist"] is None and goals[1]["kind"] == "di testa"
    assert goals[2]["own_goal"] is True and goals[2]["kind"] == ""     # niente «autogol» due volte


def test_half_split(tmp_path):
    """Primo/secondo tempo: stesse voci, testi della fonte con la virgola decimale."""
    ma = MatchAnalysis(_finished_store(tmp_path))
    hs = ma.half_split(1, 10, 20)
    assert [c["label"] for c in hs["cols"]] == ["Primo tempo", "Secondo tempo"]
    assert hs["labels"] == [r["label"] for r in hs["cols"][0]["rows"]]
    first = hs["cols"][0]["rows"][0]
    assert first["label"] == "xG" and first["home"] == "0.72".replace(".", ",")
    assert len(hs["cols"][1]["rows"]) == len(hs["labels"])


def test_keeper_stats_excludes_outfielders(tmp_path):
    """Portiere = chi ha saves/goals_prevented: gli errori di un terzino non bastano."""
    ma = MatchAnalysis(_finished_store(tmp_path))
    k = ma.keeper_stats(1, 10, 20)
    assert k["home"]["name"] == "Portiere A" and k["home"]["saves"] == 3
    assert k["home"]["goals_prevented"] == 0.8
    assert k["away"]["name"] == "Portiere B" and k["away"]["saves"] == 5
    assert k["away"]["goals_prevented"] == -1.2
    assert all(k[s]["errors_led_to_goal"] is None for s in ("home", "away"))


def test_physical_stats_is_conditional(tmp_path):
    """Fisiche: card solo se entrambe le squadre hanno i dati (qui manca la trasferta)."""
    ma = MatchAnalysis(_finished_store(tmp_path))
    assert ma.physical_stats(1, 10, 20) is None
    st = _finished_store(tmp_path)
    extra = pd.DataFrame([{"match_id": 1, "team_id": 20, "player_id": 204, "player_name": "Portiere B",
                           "key": k, "value": v}
                          for k, v in (("physical_metrics_distance_covered", 5_500.0),
                                       ("physical_metrics_number_of_sprints", 3.0),
                                       ("physical_metrics_sprinting", 120.0),
                                       ("physical_metrics_topspeed", 29.5))])
    st.write("player_stats", pd.concat([st.read("player_stats"), extra], ignore_index=True))
    ma2 = MatchAnalysis(st)
    ph = ma2.physical_stats(1, 10, 20)
    assert ph["home"]["km"] == 15.0 and ph["home"]["sprints"] == 14
    assert ph["home"]["fastest"] == "Punta A" and ph["home"]["topspeed"] == 33.5
    assert ph["away"]["km"] == 5.5


def test_detail_stats_only_shared_keys(tmp_path):
    """Statistiche di dettaglio: solo le chiavi presenti per entrambe le squadre."""
    ma = MatchAnalysis(_finished_store(tmp_path))
    rows = ma.detail_stats(1, 10, 20)
    labels = [r["label"] for r in rows]
    assert "Duelli vinti" in labels and "Intercetti" in labels and "Fuorigioco" in labels
    assert "Possesso palla" not in labels                 # sta nel riquadro principale
    assert all(r["home"] and r["away"] for r in rows)
    # stesse chiavi anche per periodo (1T/2T) e nessuna chiave fantasma
    assert ma.key_stats(1, 10, 20)[0]["label"] == "Possesso palla"


def test_peso_infermeria_con_stima_stabilizzata(tmp_path):
    """Un assente con 1′ giocato entra come stima, non con la rata grezza (docs/19 §1.10).

    Con un minuto e 0,17 xG la rata grezza è 15,30 xG+xA a partita: prima del 2026-09-16 quel
    numero finiva in pagina e nella somma dell'infermeria (docs/22 §5).
    """
    st = _store(tmp_path)
    pari = [{"match_id": 2, "team_id": 20, "player_id": 300 + i, "player_name": f"Pari {i}",
             "key": k, "value": v}
            for i in range(10)
            for k, v in (("minutes_played", 900.0), ("expected_goals", 5.0), ("expected_assists", 0.0))]
    nuovo = pd.DataFrame([{"match_id": 1, "team_id": 10, "player_id": 105, "player_name": "Esordiente A",
                           "key": "minutes_played", "value": 1.0},
                          {"match_id": 1, "team_id": 10, "player_id": 105, "player_name": "Esordiente A",
                           "key": "expected_goals", "value": 0.17}])
    st.write("player_stats", pd.concat([st.read("player_stats"), pd.DataFrame(pari), nuovo]))
    vuoto = {"shirt_number": None, "position_id": None, "age": 25, "country": "ITA",
             "market_value_eur": None, "rating": None, "season_rating": None, "is_captain": False,
             "unavailability_type": None, "expected_return": None}
    st.write("lineup", pd.concat([st.read("lineup"), pd.DataFrame(
        [{"match_id": 2, "team_id": 20, "player_id": 300 + i, "player_name": f"Pari {i}",
          "role": "starter", "usual_position_id": 3, **vuoto} for i in range(10)])]))
    ma = MatchAnalysis(st)
    ab = ma.absences_weight(100, 10)
    riga = next(p for p in ab["players"] if p["name"] == "Esordiente A")
    assert riga["contrib_raw"] == pytest.approx(15.3)          # la rata grezza: 0,17 su 1′
    assert riga["pubblicabile"] is False
    assert riga["contrib_p90"] == riga["contrib_est"]          # si pubblica la stima
    assert riga["contrib_p90"] < 1.5                           # non 15,30
    assert "media dei pari" in riga["est_note"] and "peso k=" in riga["est_note"]
    # Ala A (135′, 0,30/90 grezzo): il campione è pubblicabile, resta il grezzo
    ala = next(p for p in ab["players"] if p["name"] == "Ala A")
    assert ala["pubblicabile"] is True and ala["contrib_p90"] == pytest.approx(0.3)
    assert ab["contrib_lost_p90"] == pytest.approx(riga["contrib_est"] + ala["contrib_est"])


# --- P2.4: le tre frasi-macchina di narrative() riscritte in italiano (docs/19 §2.8) ---


@pytest.mark.parametrize("diff", [-3.0, -3.1, -5.4, -9.9])
def test_narrative_xpts_negativo_non_stampa_il_segno_meno(diff):
    """«ha −3,0 punti rispetto agli xPTS» non è italiano: si dice «3,0 punti in meno».

    Caso esplicitamente chiesto dall'audit (`diff=-3.0`). Il segno si porta nelle parole,
    il numero resta in valore assoluto.
    """
    ctx = {"home_name": "Inter", "away_name": "Milan",
           "home_xg": {"xpts": 40.0, "pts": 40.0 + diff, "played": 10}}
    frase = next(s for s in MatchAnalysis.narrative(ctx) if "xPTS" in s)
    assert "punti in meno" in frase
    assert "−" not in frase and "-" not in frase, f"segno meno rimasto nella frase: {frase}"
    assert f"{abs(diff):.1f}".replace(".", ",") in frase


def test_narrative_xpts_positivo_resta_esplicito():
    """Il verso opposto deve restare distinguibile: «in più», non solo un segno."""
    ctx = {"home_name": "Inter", "away_name": "Milan",
           "home_xg": {"xpts": 40.0, "pts": 44.2, "played": 10}}
    frase = next(s for s in MatchAnalysis.narrative(ctx) if "xPTS" in s)
    assert "punti in più" in frase and "4,2" in frase


@pytest.mark.parametrize(("n", "titolari"), [(1, 1), (1, 0), (2, 1), (3, 3), (5, 2)])
def test_narrative_assenze_non_ripete_i_nomi_della_tabella(n, titolari):
    """P2.2 (`docs/28` §3): i nomi degli assenti stanno in un posto solo, la tabella.

    Prima la frase ne elencava fino a quattro (con la congiunzione italiana e il troncamento a
    «…»): le stesse persone tornavano nella tabella dell'infermeria con minuti, gol+assist,
    xG+xA per 90, motivo e rientro — più informazione di quanta ne desse la frase. Adesso la
    frase tiene il *peso* (quanti, quanti titolari abituali) e manda alla tabella, che è la
    fonte unica; l'ancora del link la mette il template (test_site).
    """
    un = [{"name": f"G{i}", "value": 20_000_000} for i in range(1, n + 1)]
    ctx = {"home_name": "Inter", "away_name": "Milan", "home_unavailable": un,
           "home_absences": {"has_stats": True, "players": [{"starter": True}] * titolari}}
    frase = next(s for s in MatchAnalysis.narrative(ctx) if "rinunciare" in s)
    assert not frase.startswith("Assenze "), "tornato il formato elenco-dati"
    # il trattino da record («Napoli: 3 — A, B, C») resta vietato: dopo il numero non si
    # elencano nomi. Il trattino come segno di prosa («… titolare abituale — nomi e impatto in
    # «Indisponibili»») è un'altra cosa, e adesso è quello che separa il peso dal rimando.
    assert not re.search(r"\d\s+—\s+[A-ZÀ-Ý]", frase), frase
    # nessun nome nella frase: la tabella li elenca tutti, con l'impatto di ognuno
    assert not any(f"G{i}" in frase for i in range(1, n + 1)), frase
    assert frase.endswith("— nomi e impatto in «Indisponibili»."), frase
    # il peso resta dichiarato: quanti sono e quanti titolari abituali
    atteso = f"{n} assente" if n == 1 else f"{n} assenti"
    assert atteso in frase
    if titolari:
        assert "titolare abituale" in frase or "titolari abituali" in frase


def test_narrative_assenza_singola_non_dice_uno_dei_quali():
    """Con un solo assente «1 assente, uno dei quali titolare» stona: va detto per esteso."""
    ctx = {"home_name": "Inter", "away_name": "Milan",
           "home_unavailable": [{"name": "G1", "value": 20_000_000}],
           "home_absences": {"has_stats": True, "players": [{"starter": True}]}}
    frase = next(s for s in MatchAnalysis.narrative(ctx) if "rinunciare" in s)
    assert "uno dei quali" not in frase
    assert "titolare abituale" in frase


def test_narrative_peso_non_valutabile_resta_dichiarato():
    """Se la fonte non ha né minuti né valori, la scheda lo dice invece di tacere."""
    ctx = {"home_name": "Inter", "away_name": "Milan",
           "home_unavailable": [{"name": "G1"}, {"name": "G2"}]}
    frase = next(s for s in MatchAnalysis.narrative(ctx) if "rinunciare" in s)
    assert "peso non valutabile" in frase


@pytest.mark.parametrize("p", [0.60, 0.72, 0.85])
def test_narrative_1x2_usa_le_frequenze_naturali_e_non_dice_nettamente(p):
    """A 60% il favorito perde 4 volte su 10: «nettamente favorito» è più forte del dato."""
    ctx = {"home_name": "Inter", "away_name": "Milan",
           "prediction": {"p_home": p, "p_draw": (1 - p) / 2, "p_away": (1 - p) / 2,
                          "lambda_home": 1.4, "lambda_away": 1.1, "p_over25": 0.55}}
    frase = MatchAnalysis.narrative(ctx)[0]
    assert "nettamente" not in frase
    assert "su 100 partite così" in frase
    assert f"{round(p * 100)} finiscono" in frase


def test_elenco_it_mette_la_congiunzione_prima_dell_ultimo_nome():
    """È la differenza fra una frase e un elenco separato da virgole."""
    from fda.site.analysis import _elenco_it

    assert _elenco_it(["A"]) == "A"
    assert _elenco_it(["A", "B"]) == "A e B"
    assert _elenco_it(["A", "B", "C"]) == "A, B e C"
    assert _elenco_it([]) == ""
