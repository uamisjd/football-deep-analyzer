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


def test_dc_shrinkage_pulls_thin_history_to_league_mean(hist):
    """Shrinkage: 2 partite non possono lasciare una squadra al bordo dell'ottimizzazione.

    Caso reale che ha motivato la correzione: a inizio stagione Dortmund–Paderborn usciva
    con λ 1,02–0,19 (Over 2,5 al 12%) perché l'attacco del Paderborn era stimato −2,5, il
    limite del risolutore, contro 0,71 xG/gara reali.
    """
    last = hist["date"].max()
    extra = pd.DataFrame([
        {"date": last, "home": "Nuova Promossa", "away": "Inter", "home_goals": 5, "away_goals": 0},
        {"date": last, "home": "AC Milan", "away": "Nuova Promossa", "home_goals": 0, "away_goals": 4},
    ])
    df = pd.concat([hist, extra], ignore_index=True)
    m = DixonColesModel().fit(df)

    assert m.team_weight["Nuova Promossa"] < 5 < m.team_weight["Inter"]   # 2 gare vs 3 stagioni

    raw = dict(m.model.get_params())
    sh = m.shrunk_params(raw)
    teams = sorted(m.teams)
    mean_att = sum(raw[f"attack_{t}"] for t in teams) / len(teams)
    mean_dfn = sum(raw[f"defence_{t}"] for t in teams) / len(teams)

    # gauge invariante: le medie di lega non si spostano
    assert abs(sum(sh[f"attack_{t}"] for t in teams) / len(teams) - mean_att) < 1e-9
    assert abs(sum(sh[f"defence_{t}"] for t in teams) / len(teams) - mean_dfn) < 1e-9

    # contrazione proporzionale ai dati: 2 partite → quasi tutta la deviazione sparisce,
    # una stagione intera (peso ~27 con xi=0.0018, quindi f = 27/35) → resta per lo più
    dev_raw = abs(raw["attack_Nuova Promossa"] - mean_att)
    ratio_new = abs(sh["attack_Nuova Promossa"] - mean_att) / dev_raw
    ratio_inter = abs(sh["attack_Inter"] - mean_att) / abs(raw["attack_Inter"] - mean_att)
    assert ratio_new < 0.5
    assert ratio_inter > 0.75
    assert ratio_new < ratio_inter

    # senza prior: parametri identici al fit (nessun comportamento nascosto)
    assert DixonColesModel(shrink_prior=0.0).fit(df).shrunk_params(raw) == raw


def test_dc_lambda_reconstruction_matches_grid(hist):
    """λ pubblicate = exp(attacco casa + difesa ospite + vantaggio campo), come penaltyblog."""
    import math

    m = DixonColesModel(shrink_prior=0.0).fit(hist)
    d = m.predict("Inter", "AC Milan")
    ref = m.model.predict("Inter", "AC Milan", max_goals=m.max_goals)
    assert abs(d["lambda_home"] - ref.home_goal_expectation) < 1e-9
    assert abs(d["lambda_away"] - ref.away_goal_expectation) < 1e-9
    p = m.model.get_params()
    assert abs(d["lambda_home"] - math.exp(p["attack_Inter"] + p["defence_AC Milan"] + p["home_advantage"])) < 1e-9


def test_ensemble_double_chance_matches_1x2():
    """1X/12/X2 sono somme del 1X2 pubblicato: la scheda non deve contraddirsi.

    Regressione: i mercati venivano dalla griglia ricostruita mentre il 1X2 era la media
    pesata DC/Elo → scarto fino a 1,1 punti e intero a schermo incoerente nel 14,3% dei casi.
    """
    dc = {"p_home": 0.50, "p_draw": 0.27, "p_away": 0.23, "dc_rho": -0.08,
          "lambda_home": 1.7, "lambda_away": 1.0}
    elo = {"elo_p_home": 0.40, "elo_p_draw": 0.29, "elo_p_away": 0.31}
    out = ensemble(dc, elo, w_dc=0.7)
    assert abs(out["p_1x"] - (out["p_home"] + out["p_draw"])) < 1e-12
    assert abs(out["p_12"] - (out["p_home"] + out["p_away"])) < 1e-12
    assert abs(out["p_x2"] - (out["p_draw"] + out["p_away"])) < 1e-12
    assert abs(out["p_1x"] - (1.0 - out["p_away"])) < 1e-12
