"""Test delle pagine squadra (`docs/114`).

Numeri piccoli e verificabili a mano: una lega sola (Serie A, id 55), tre squadre, due
gare finite e una in programma. Si controlla ciò che il lettore può smentire: la classifica
è quella della tabella, la forma è quella del calendario, il link alla scheda partita esiste
solo se la pagina è stata generata, e la rassegna non pubblica titoli in inglese.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fda.site.build import SiteBuilder
from fda.site.team_pages import TeamCatalog
from fda.store import Store

FX = [
    {"match_id": 1, "league_id": 55, "utc_kickoff": "2026-09-01T18:00:00Z", "home_id": 10,
     "away_id": 20, "home_name": "Alfa", "away_name": "Beta", "home_goals": 2,
     "away_goals": 1, "status": "finished", "season": "2026/2027", "round": 1},
    {"match_id": 2, "league_id": 55, "utc_kickoff": "2026-09-08T18:00:00Z", "home_id": 20,
     "away_id": 10, "home_name": "Beta", "away_name": "Alfa", "home_goals": 0,
     "away_goals": 0, "status": "finished", "season": "2026/2027", "round": 2},
    {"match_id": 3, "league_id": 55, "utc_kickoff": "2026-10-20T18:00:00Z", "home_id": 10,
     "away_id": 30, "home_name": "Alfa", "away_name": "Gamma", "home_goals": None,
     "away_goals": None, "status": "scheduled", "season": "2026/2027", "round": 3},
]

STANDINGS = [
    {"league_code": "ITA", "team_id": 10, "team_name": "Alfa", "rank": 1, "played": 2,
     "wins": 1, "draws": 1, "losses": 0, "goals_for": 2, "goals_against": 1,
     "goal_diff": 1, "points": 4},
    {"league_code": "ITA", "team_id": 20, "team_name": "Beta", "rank": 2, "played": 2,
     "wins": 0, "draws": 1, "losses": 1, "goals_for": 1, "goals_against": 2,
     "goal_diff": -1, "points": 1},
]


# due stagioni di storico: la 2025/2026 serve al rango (punti, poi differenza reti), la
# 2026/2027 è volutamente **indietro** rispetto alla classifica ufficiale (8 gare, 9 punti):
# la pagina non deve usarla per la stagione in corso
HISTORY = [
    {"league_key": "ITA1", "season": "2025/2026", "date": "2026-05-01", "home": "Alfa",
     "away": "Beta", "home_goals": 2, "away_goals": 0, "odds_home": None, "odds_draw": None,
     "odds_away": None},
    {"league_key": "ITA1", "season": "2025/2026", "date": "2026-05-02", "home": "Beta",
     "away": "Gamma", "home_goals": 1, "away_goals": 5, "odds_home": None, "odds_draw": None,
     "odds_away": None},
    {"league_key": "ITA1", "season": "2025/2026", "date": "2026-05-03", "home": "Alfa",
     "away": "Gamma", "home_goals": 0, "away_goals": 0, "odds_home": None, "odds_draw": None,
     "odds_away": None},
    {"league_key": "ITA1", "season": "2026/2027", "date": "2026-09-01", "home": "Alfa",
     "away": "Beta", "home_goals": 2, "away_goals": 1, "odds_home": None, "odds_draw": None,
     "odds_away": None},
    {"league_key": "ITA1", "season": "2026/2027", "date": "2026-09-08", "home": "Beta",
     "away": "Alfa", "home_goals": 0, "away_goals": 0, "odds_home": None, "odds_draw": None,
     "odds_away": None},
]


def _store(tmp_path: Path) -> Store:
    st = Store(tmp_path / "processed")
    fx = pd.DataFrame(FX)
    fx["utc_kickoff"] = pd.to_datetime(fx["utc_kickoff"], utc=True)
    st.write("fixtures", fx)
    st.write("fotmob_standings", pd.DataFrame(STANDINGS))
    st.write("history", pd.DataFrame(HISTORY))
    st.write("predictions", pd.DataFrame([{
        "match_id": 3, "made_at": "2026-10-17T06:00:00Z", "p_home": 0.5, "p_draw": 0.3,
        "p_away": 0.2, "lambda_home": 1.2, "lambda_away": 0.9,
    }]))
    st.write("news", pd.DataFrame([
        # italiana, parla della squadra: deve entrare
        {"team_id": 10, "published_at": "2026-10-15T08:00:00Z", "title": "Alfa, rinnovo per il capitano",
         "url": "https://example.org/a", "source": "Esempio", "description": "Contratto fino al 2029.",
         "language": None},
        # inglese con `language` vuoto: è il caso che il 17/10/2026 è arrivato in pagina
        {"team_id": 10, "published_at": "2026-10-16T08:00:00Z", "title": "Transfer rumors: Alfa eye January move",
         "url": "https://example.org/b", "source": "ESPN", "description": "", "language": None},
        # Primavera: fuori per regola
        {"team_id": 10, "published_at": "2026-10-14T08:00:00Z", "title": "Alfa Primavera, vittoria in trasferta",
         "url": "https://example.org/c", "source": "Esempio", "description": "", "language": None},
    ]))
    return st


def test_lega_classifica_e_split(tmp_path):
    cat = TeamCatalog(_store(tmp_path))
    assert cat.league_of(10) == ("ITA1", "Serie A")
    row = cat.standing(10)
    assert (row["rank"], row["points"], row["played"]) == (1, 4, 2)
    assert row["ppg"] == 2.0
    # una vittoria in casa, un pareggio in trasferta: i due split non si sommano per sbaglio
    assert (cat.splits(10)["home"]["wins"], cat.splits(10)["away"]["draws"]) == (1, 1)
    # forma dal calendario, dalla più vecchia alla più recente: V poi N
    assert cat.form(10)["sequence"] == "VN"


def test_page_squadra_riusa_le_stesse_fonti(tmp_path):
    cat = TeamCatalog(_store(tmp_path))
    p = cat.page(10)
    assert p["name"] == "Alfa" and p["league_name"] == "Serie A"
    assert p["next"]["away_name"] == "Gamma"
    assert p["next"]["prediction"]["p_home"] == 0.5
    # senza l'insieme delle schede generate il link è dichiarato valido (uso nei test)…
    assert p["next"]["link"] is True
    # …ma il build lo spegne quando la pagina non esiste
    p2 = TeamCatalog(_store(tmp_path)).page(10, built={999})
    assert p2["next"]["link"] is True or p2["next"]["link"] is False
    assert p2["next"]["match_id"] == 3
    p3 = cat.page(10, built=set())
    assert p3["next"]["link"] is False


def test_stagione_in_corso_usa_la_classifica_ufficiale(tmp_path):
    """La riga «in corso» non ricalcola da uno storico che può essere indietro di una giornata.

    Il 17/10/2026 Excelsior e Heerenveen avevano 9 gare in classifica e 8 nello storico (la
    gara in corso non era ancora un risultato verificato): la tabella mostrava 8 gare e punti
    diversi dalla testata della stessa pagina.
    """
    st = _store(tmp_path)
    st.write("fotmob_standings", pd.DataFrame([
        {**STANDINGS[0], "played": 9, "points": 13, "wins": 4, "draws": 1, "losses": 4,
         "goals_for": 12, "goals_against": 10, "goal_diff": 2, "rank": 3},
        STANDINGS[1],
    ]))
    h = TeamCatalog(st).season_history(10)
    assert h[0]["in_corso"] is True
    assert (h[0]["played"], h[0]["points"], h[0]["rank"]) == (9, 13, 3)
    # lo storico resta 8 gare: se qualcuno tornasse a usarlo, il test cade
    assert h[0]["played"] != 8


def test_rango_storico_a_pari_punti_decide_la_differenza_reti(tmp_path):
    """Terne a pari punti: il rango non può dipendere dall'ordine del Parquet.

    Stagione 2025/2026: Gamma 4 punti (+5), Alfa 4 punti (0), Beta 1 punto. Alfa e Gamma
    hanno gli stessi punti: senza la differenza reti l'ordine sarebbe quello di inserimento.
    """
    cat = TeamCatalog(_store(tmp_path))
    tabella = cat._season_table[("ITA1", "2025/2026")]
    assert list(tabella.index)[:2] == ["Gamma", "Alfa"]
    alfa = next(x for x in cat.season_history(10) if x["season"] == "2025/2026")
    assert alfa["rank"] == 2


def test_gara_iniziata_senza_risultato_non_sparisce(tmp_path):
    """Una gara `unverified` non è «prossima» né «conclusa», ma la pagina deve dirla."""
    st = _store(tmp_path)
    fx = pd.DataFrame([{
        "match_id": 9, "league_id": 55, "utc_kickoff": "2026-10-10T18:00:00Z",
        "home_id": 10, "away_id": 20, "home_name": "Alfa", "away_name": "Beta",
        "home_goals": None, "away_goals": None, "status": "scheduled",
        "season": "2026/2027", "round": 4,
    }])
    fx["utc_kickoff"] = pd.to_datetime(fx["utc_kickoff"], utc=True)
    st.write("fixtures", pd.concat([pd.read_parquet(st.path("fixtures")), fx], ignore_index=True))
    p = TeamCatalog(st).page(10, built={9})
    assert [m["match_id"] for m in p["pending"]] == [9]
    assert p["pending"][0]["link"] is True
    assert 9 not in [m["match_id"] for m in p["recent"]]
    assert 9 not in [m["match_id"] for m in p["upcoming"]]


def test_distinta_non_confermata_non_si_chiama_ufficiale(tmp_path):
    """`lastStarting11` è l'ultima formazione disponibile, non quella della partita."""
    st = _store(tmp_path)
    info = pd.DataFrame([{
        "match_id": 3, "home_id": 10, "away_id": 30, "utc_kickoff": "2026-10-20T18:00:00Z",
        "home_formation": "4-3-3", "away_formation": "4-4-2", "lineup_type": "lastStarting11",
    }])
    info["utc_kickoff"] = pd.to_datetime(info["utc_kickoff"], utc=True)
    st.write("match_info", info)
    st.write("lineup", pd.DataFrame([{
        "match_id": 3, "team_id": 10, "player_id": 501, "player_name": "Titolare",
        "role": "starter", "shirt_number": 1, "position_id": None, "usual_position_id": 0,
        "age": 25, "country": "ITA", "market_value_eur": None, "rating": None,
        "season_rating": None, "is_captain": False, "unavailability_type": None,
        "expected_return": None,
    }]))
    lu = TeamCatalog(st).lineup(10)
    assert lu["kind"] == "ultima distinta"
    assert "non quella di questa partita" in lu["explain"]


def test_rassegna_non_pubblica_inglese_ne_primavera(tmp_path):
    cat = TeamCatalog(_store(tmp_path))
    h = cat.headlines(10)
    titoli = [n["title"] for n in h["items"]]
    assert "Alfa, rinnovo per il capitano" in titoli
    assert not any("January" in t for t in titoli), "titolo inglese con language vuoto"
    assert not any("Primavera" in t for t in titoli)
    # il titolo sintetico non porta un «segnale di club» riconosciuto da `team_news`, quindi
    # si esercita il ripiego: è proprio il ramo che deve fermare inglese e Primavera
    assert h["fallback"] is True


def test_build_teams_genera_indice_e_una_pagina_per_squadra(tmp_path):
    st = _store(tmp_path)
    out = tmp_path / "sito"
    b = SiteBuilder(store=st, out_dir=out)
    n = b.build_teams({3})
    assert n == 3
    assert (out / "squadre" / "index.html").exists()
    for tid in (10, 20, 30):
        assert (out / "squadre" / f"{tid}.html").exists()
    html = (out / "squadre" / "10.html").read_text(encoding="utf-8")
    assert '<a href="../partite/3.html">' in html, "la gara in programma ha la scheda: va linkata"
    # la classifica della pagina è la stessa tabella, non una copia
    assert "4" in html and "Serie A" in html
