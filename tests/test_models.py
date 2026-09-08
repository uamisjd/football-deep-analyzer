import pandas as pd
import pytest
from pathlib import Path

from fda.config import league
from fda.models.predict import DixonColesModel, EloModel, ensemble, outcome_index, predict_matches, rps
from fda.sources.history import HistoryClient, season_code
from fda.teams import canonical, same_team

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def hist():
    raw = pd.read_csv(FIX / "datahub_serie_a_2526.csv")
    df = HistoryClient._normalize(raw, league("ITA1"), 2025)
    df["home"] = df["home"].map(canonical)
    df["away"] = df["away"].map(canonical)
    return df


def test_team_aliases():
    assert canonical("Inter") == canonical("Internazionale") == canonical("Inter Milan") == "Inter"
    assert canonical("Milan") == "AC Milan" and canonical("Man City") == "Manchester City"
    assert canonical("Ath Madrid") == canonical("Atlético Madrid") == "Atletico Madrid"
    assert canonical("Paris SG") == canonical("PSG") == "Paris Saint-Germain"
    assert canonical("Sp Lisbon") == "Sporting CP" and canonical("FC Barcelona") == "Barcelona"
    assert canonical("Squadra Ignota") == "Squadra Ignota"
    assert same_team("Nott'm Forest", "Nottingham Forest")


def test_ned_por_footballdata_spellings():
    # grafie football-data.co.uk (mirror NED1/POR1) → nome FotMob
    assert canonical("For Sittard") == canonical("Fortuna Sittard") == "Fortuna Sittard"
    assert canonical("Estrela") == canonical("Estrela Amadora") == canonical("Estrela da Amadora") == "Estrela da Amadora"
    # nomi usati nei CSV N1/P1 che devono convergere
    assert canonical("Groningen") == canonical("FC Groningen")
    assert canonical("Heerenveen") == canonical("SC Heerenveen")
    assert canonical("Utrecht") == canonical("FC Utrecht")
    assert canonical("Twente") == canonical("FC Twente")
    assert canonical("Guimaraes") == canonical("Vitória de Guimarães")
    assert canonical("Sp Braga") == canonical("Braga") == canonical("SC Braga")


def test_history_normalize(hist):
    assert len(hist) == 380
    assert hist["date"].min().date().isoformat() == "2025-08-23"
    assert hist["date"].max().date().isoformat() == "2026-05-24"
    assert set(hist.columns) >= {"date", "season", "league_key", "home", "away", "home_goals", "away_goals"}
    assert hist["season"].iloc[0] == "2025/2026" and season_code(2025) == "2526"
    assert hist["home_goals"].dtype.kind == "i"
    assert "odds_home" not in hist.columns             # datahub non ha quote


def test_history_uses_datahub_base_override():
    # NED1 non è nel mirror datasets/football-datasets: datahub_base punta al mirror dedicato.
    calls = {}

    class _Stub:
        def get_text(self, url, ttl_h=None):
            calls["url"] = url
            return "Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n" \
                   "10/08/2025,Ajax,Feyenoord,2,1,H\n" \
                   "11/08/2025,Feyenoord,Ajax,0,0,D\n"

    ned = league("NED1")
    hc = HistoryClient(client=_Stub())
    df = hc.datahub_csv(ned, 2025)
    assert df is not None and len(df) == 2
    assert calls["url"] == f"{ned.datahub_base}/eredivisie/season-2526.csv"

    # le 5 grandi leghe restano sul mirror datasets/football-datasets (nessun datahub_base)
    ita = league("ITA1")
    assert ita.datahub_base is None
    hc2 = HistoryClient(client=_Stub())
    hc2.datahub_csv(ita, 2025)
    assert "datasets/football-datasets" in calls["url"] and calls["url"].endswith("/serie-a/season-2526.csv")


def test_history_parses_footballdata_dates():
    raw = pd.DataFrame({"Date": ["15/08/2025", "16/08/25"], "HomeTeam": ["A", "B"], "AwayTeam": ["B", "A"],
                        "FTHG": [1, 0], "FTAG": [0, 0], "PSCH": [1.9, 2.5], "PSCD": [3.5, 3.2], "PSCA": [4.0, 2.9]})
    df = HistoryClient._normalize(raw, league("ITA1"), 2025)
    assert df["date"].dt.year.tolist() == [2025, 2025] and df["date"].dt.day.tolist() == [15, 16]
    assert df["odds_home"].tolist() == [1.9, 2.5]


def test_dixon_coles_and_elo(hist):
    dc = DixonColesModel().fit(hist)
    p = dc.predict("Inter", "Napoli")
    assert abs(p["p_home"] + p["p_draw"] + p["p_away"] - 1) < 1e-6
    assert p["p_home"] > p["p_away"]                   # Inter favorita in casa nel 2025/26
    assert 0 < p["p_over25"] < 1 and 0 < p["p_btts"] < 1
    assert p["lambda_home"] > 0 and len(p["top_scores"]) == 6
    with pytest.raises(KeyError):
        dc.predict("Inter", "Squadra Ignota")
    table = dc.strength_table()
    assert table.iloc[0]["team"] in {"Inter", "Como", "AC Milan", "Napoli", "Juventus", "Roma", "Atalanta"}

    elo = EloModel().fit(hist)
    e = elo.predict("Inter", "Napoli")
    assert abs(e["elo_p_home"] + e["elo_p_draw"] + e["elo_p_away"] - 1) < 1e-6
    assert e["elo_home"] != 1500.0

    ens = ensemble(p, e, w_dc=0.7)
    assert ens["model"] == "ensemble"
    assert abs(ens["p_home"] + ens["p_draw"] + ens["p_away"] - 1) < 1e-6
    assert min(p["p_home"], e["elo_p_home"]) - 1e-9 <= ens["p_home"] <= max(p["p_home"], e["elo_p_home"]) + 1e-9


def test_backtest_beats_naive(hist):
    train, test = hist.iloc[:300], hist.iloc[300:].copy()
    test["match_id"] = range(len(test))
    pred, _, _ = predict_matches(train, test)
    assert len(pred) == 80 and pred["model"].eq("ensemble").all()
    m = pred.merge(test[["match_id", "home_goals", "away_goals"]], on="match_id")
    outs = [outcome_index(h, a) for h, a in zip(m.home_goals, m.away_goals)]
    score = rps(m[["p_home", "p_draw", "p_away"]].values.tolist(), outs)
    naive = rps([[0.45, 0.27, 0.28]] * len(outs), outs)
    assert score < naive - 0.02
    assert pred["fair_home"].gt(1).all()
