"""L'audit dello storico deve riconoscere buchi e disallineamenti tra le due fonti."""

import pandas as pd
import pytest

from scripts.audit_understat_storico import audit


@pytest.fixture
def archive():
    matches, teams = [], []
    mid = 0
    for season in range(2021, 2026):
        for league in ("EPL", "La_Liga", "Serie_A", "Bundesliga", "Ligue_1"):
            n = 306 if league == "Bundesliga" or (league == "Ligue_1" and season >= 2023) else 380
            for i in range(n):
                mid += 1
                date = pd.Timestamp(f"{season}-08-01", tz="UTC") + pd.Timedelta(hours=i)
                matches.append({"understat_id": mid, "league_slug": league, "season": season,
                                "utc_kickoff": date, "is_result": True,
                                "home_id": 1, "away_id": 2, "home_goals": 2, "away_goals": 0,
                                "home_xg": 1.25, "away_xg": 0.75})
                for home in (True, False):
                    teams.append({"league_slug": league, "season": season, "date": date,
                                  "team_id": 1 if home else 2, "is_home": home,
                                  "goals": 2 if home else 0, "goals_against": 0 if home else 2,
                                  "xg": 1.25 if home else 0.75, "xga": 0.75 if home else 1.25})
    return pd.DataFrame(matches), pd.DataFrame(teams)


def test_archivio_completo_con_due_lati_per_gara(archive):
    matches, teams = archive
    counts, problems = audit(matches, teams)
    assert problems == []
    assert counts.sum(axis=1).tolist() == [1826, 1826, 1752, 1752, 1752]
    assert counts.to_numpy().sum() == 8908
    assert len(teams) == 17816


@pytest.mark.parametrize("defect,expected", [
    ("gara_assente", "finite, attese"),
    ("lato_assente", "senza corrispondenza"),
    ("id_duplicato", "ID Understat duplicati"),
    ("lato_duplicato", "chiavi lato-squadra duplicate"),
    ("xg_diverso", "incrocio xg"),
    ("xg_assente", "gol/xG mancanti"),
    ("casa_trasferta", "incrocio is_home"),
    ("non_finita", "gare non finite"),
])
def test_audit_rileva_difetti_reali(archive, defect, expected):
    matches, teams = archive
    if defect == "gara_assente":
        matches = matches.iloc[1:]
    elif defect == "lato_assente":
        teams = teams.iloc[1:]
    elif defect == "id_duplicato":
        matches.loc[1, "understat_id"] = matches.loc[0, "understat_id"]
    elif defect == "lato_duplicato":
        teams = pd.concat([teams, teams.iloc[[0]]], ignore_index=True)
    elif defect == "xg_diverso":
        teams.loc[0, "xg"] += 0.1
    elif defect == "xg_assente":
        matches.loc[0, "home_xg"] = float("nan")
    elif defect == "casa_trasferta":
        teams.loc[0, "is_home"] = False
    elif defect == "non_finita":
        matches.loc[0, "is_result"] = False
    _, problems = audit(matches, teams)
    assert any(expected in message for message in problems), problems


def test_archivio_assente_non_puo_passare():
    counts, problems = audit(pd.DataFrame(), pd.DataFrame())
    assert counts.to_numpy().sum() == 0
    assert len(problems) == 2 and all("colonne mancanti" in p for p in problems)
