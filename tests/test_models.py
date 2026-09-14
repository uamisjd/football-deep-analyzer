from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fda.config import league
from fda.models.calibration import Calibration
from fda.models.dc_grid import GRID_SIZE, tau_grid
from fda.models.predict import (
    LAMBDA_MAX,
    LAMBDA_TOTAL_MAX_ABS,
    LAMBDA_TOTAL_MAX_REL,
    DixonColesModel,
    EloModel,
    _clamp_lambda,
    calibrated_prediction,
    ensemble,
    latest_per_match,
    outcome_index,
    predict_matches,
    rps,
)
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


def test_lambda_estreme_rientrano_nei_limiti_di_sicurezza():
    """L'inversione dell'1X2 mediato non può inventare partite da otto reti.

    Misurato sulle previsioni pubblicate: Barcellona-Racing Santander λ 6,17+2,25 = 8,4 gol
    attesi (Over 2,5 al 99%, risultati esatti centrati sul 5-1). Il modello sui gol, da solo,
    su 5.791 gare fuori campione non supera mai 3,84 per squadra né 4,73 totali.
    """
    # caso reale: l'Elo spinge l'1X2, l'inversione gonfia le λ
    out = _clamp_lambda(6.17, 2.25, 2.60, 0.62)
    assert out is not None
    assert out[0] + out[1] == pytest.approx((2.60 + 0.62) * 1.35, abs=1e-9)
    assert out[0] / out[1] == pytest.approx(6.17 / 2.25, abs=1e-9)   # l'inclinazione si conserva
    # λ entro i limiti: nessun intervento
    assert _clamp_lambda(1.60, 1.10, 1.55, 1.05) is None
    # anche all'ingiù: l'inversione non deve svuotare la partita
    basso = _clamp_lambda(1.00, 0.40, 1.90, 0.90)
    assert basso is not None and basso[0] + basso[1] == pytest.approx(2.80 * 0.70, abs=1e-9)
    # il tetto assoluto vale anche se è il modello sui gol a esagerare
    tetto = _clamp_lambda(5.0, 3.0, 4.8, 2.6)
    assert tetto is not None and tetto[0] + tetto[1] <= LAMBDA_TOTAL_MAX_ABS + 1e-9
    assert max(tetto) <= LAMBDA_MAX + 1e-9
    # senza λ di riferimento valgono i limiti assoluti, e i NaN non fanno esplodere nulla
    assert _clamp_lambda(9.0, 1.0, float("nan"), float("nan")) is not None
    assert _clamp_lambda(float("nan"), 1.0, 1.5, 1.2) is None


def _dc_coerente(lh: float, la: float, rho: float) -> dict:
    """Una previsione del modello sui gol **coerente** (1X2 calcolato dalla sua griglia)."""
    g = tau_grid(lh, la, rho, size=GRID_SIZE)
    i, j = np.indices(g.shape)
    return {"p_home": float(g[i > j].sum()), "p_draw": float(g[i == j].sum()),
            "p_away": float(g[i < j].sum()), "dc_rho": rho, "lambda_home": lh, "lambda_away": la}


def test_ensemble_tilt_conserva_il_totale_dei_gol_attesi():
    """Ricetta promossa (2026-09-13): l'Elo **inclina**, il totale dei gol resta del modello gol.

    Verdetto del laboratorio in Actions (1.527 gare walk-forward, 7 leghe, ``model_lab.parquet``):
    ΔRPS −0,000406 con IC 95% appaiato [−0,000773; −0,000041] interamente negativo e RPS più
    basso in 5 leghe su 7. Il guadagno dichiarato però non è l'RPS: è che i gol attesi tornano
    quelli del modello sui gol (bias λ −0,086 invece di +0,105), cioè la calibrazione non deve
    più correggere un difetto che la ricetta precedente introduceva da sé.
    """
    lh, la, rho = 1.70, 1.00, -0.08
    dc = _dc_coerente(lh, la, rho)
    elo = {"elo_p_home": dc["p_home"] + 0.10, "elo_p_draw": dc["p_draw"] - 0.03,
           "elo_p_away": dc["p_away"] - 0.07}
    out = ensemble(dc, elo, w_dc=0.7)
    assert out["ensemble_mode"] == "tilt"
    assert out["lambda_limitata"] is False
    # il totale è identico a quello del modello sui gol: l'Elo non gonfia le λ
    assert out["lambda_home"] + out["lambda_away"] == pytest.approx(2.70, abs=1e-9)
    # e l'inclinazione segue il rating (più casa, meno trasferta)
    assert out["lambda_home"] > lh and out["lambda_away"] < la
    assert out["lambda_home"] / out["lambda_away"] > lh / la
    # l'1X2 pubblicato è quello della griglia inclinata: 1X2, doppie chance e mercati coerenti
    g = tau_grid(out["lambda_home"], out["lambda_away"], out["dc_rho"], size=GRID_SIZE)
    i, j = np.indices(g.shape)
    assert out["p_home"] == pytest.approx(float(g[i > j].sum()), abs=1e-9)
    assert out["p_draw"] == pytest.approx(float(g[i == j].sum()), abs=1e-9)
    assert abs(out["p_1x"] - (out["p_home"] + out["p_draw"])) < 1e-12
    # la probabilità della casa sale verso il rating, senza superarlo
    assert dc["p_home"] < out["p_home"] < elo["elo_p_home"]
    # la scomposizione mostrata in scheda conserva sia il modello sui gol sia i rating
    assert out["dc_p_home"] == pytest.approx(dc["p_home"])
    assert out["elo_p_home"] == pytest.approx(elo["elo_p_home"])
    # con un rating identico al modello sui gol la griglia non si muove
    stesso = ensemble(dc, {"elo_p_home": dc["p_home"], "elo_p_draw": dc["p_draw"],
                           "elo_p_away": dc["p_away"]}, w_dc=0.7)
    assert (stesso["lambda_home"], stesso["lambda_away"]) == pytest.approx((lh, la), abs=1e-9)


def test_ensemble_tilt_con_elo_estremo_resta_leggibile():
    """Con un rating estremo l'inclinazione si ferma al bordo dell'intervallo cercato (0,85…1,15).

    È la differenza strutturale con la ricetta precedente: lì l'inversione inventava 8,4 gol
    attesi (Barcellona-Racing Santander 6,17+2,25) e serviva il limite di sicurezza; qui il
    totale è per costruzione quello del modello sui gol, quindi non c'è nulla da limitare.
    """
    dc = {"p_home": 0.86, "p_draw": 0.09, "p_away": 0.05, "dc_rho": -0.10,
          "lambda_home": 3.40, "lambda_away": 0.45}
    elo = {"elo_p_home": 0.96, "elo_p_draw": 0.03, "elo_p_away": 0.01}
    out = ensemble(dc, elo, w_dc=0.7)
    assert out["lambda_limitata"] is False
    assert out["lambda_home"] + out["lambda_away"] == pytest.approx(3.85, abs=1e-9)
    assert out["lambda_home"] <= LAMBDA_MAX + 1e-9
    # il pareggio resta fra quello chiesto dal rating estremo e quello del modello sui gol
    assert elo["elo_p_draw"] < out["p_draw"] <= dc["p_draw"] + 1e-9
    assert abs(out["p_1x"] - (out["p_home"] + out["p_draw"])) < 1e-12


def test_ensemble_inverti_riproduce_il_vettore_mediato_ricetta_precedente():
    """La ricetta precedente resta disponibile al laboratorio (candidato ``dc_elo_ge``).

    È il comportamento su cui il tilt è stato misurato e poi promosso: due λ libere cercate da
    ``goal_expectancy`` per riprodurre l'1X2 mediato. Qui — a differenza del tilt — il totale
    dei gol attesi si gonfia appena il rating riduce il pareggio, ed è il difetto misurato
    (+8,6% sopra i gol osservati) che la calibrazione doveva correggere a valle.
    """
    lh, la, rho = 1.70, 1.00, -0.08
    dc = _dc_coerente(lh, la, rho)
    elo = {"elo_p_home": dc["p_home"] + 0.10, "elo_p_draw": dc["p_draw"] - 0.03,
           "elo_p_away": dc["p_away"] - 0.07}
    out = ensemble(dc, elo, w_dc=0.7, mode="inverti")
    assert out["ensemble_mode"] == "inverti"
    assert out["lambda_limitata"] is False
    # riproduce l'1X2 mediato (0,7·DC + 0,3·Elo) e lo fa **gonfiando** il totale
    assert out["p_home"] == pytest.approx(0.7 * dc["p_home"] + 0.3 * elo["elo_p_home"], abs=1e-6)
    assert out["lambda_home"] + out["lambda_away"] > lh + la
    assert abs(out["p_1x"] - (out["p_home"] + out["p_draw"])) < 1e-12
    # a parità di partita, il tilt pubblica lo stesso 1X2 con gol attesi inferiori
    tilt = ensemble(dc, elo, w_dc=0.7)
    assert tilt["p_home"] == pytest.approx(out["p_home"], abs=5e-3)
    assert tilt["lambda_home"] + tilt["lambda_away"] < out["lambda_home"] + out["lambda_away"]


def test_ensemble_inverti_con_elo_estremo_resta_leggibile_e_coerente():
    """Con la ricetta ``inverti``, se il vettore mediato chiede l'impossibile scatta il limite.

    È la rete di sicurezza introdotta con la calibrazione v1.1: λ≤4,0 per squadra, totale fra il
    70% e il 135% di quello del modello sui gol (e comunque ≤ 5,5). Misurato sulle previsioni
    pubblicate con la ricetta precedente: interviene sull'1,2% delle gare.
    """
    dc = {"p_home": 0.86, "p_draw": 0.09, "p_away": 0.05, "dc_rho": -0.10,
          "lambda_home": 3.40, "lambda_away": 0.45}
    elo = {"elo_p_home": 0.96, "elo_p_draw": 0.03, "elo_p_away": 0.01}
    out = ensemble(dc, elo, w_dc=0.7, mode="inverti")
    assert out["lambda_limitata"] is True
    assert out["lambda_home"] <= LAMBDA_MAX + 1e-9 and out["lambda_away"] <= LAMBDA_MAX + 1e-9
    assert out["lambda_home"] + out["lambda_away"] <= LAMBDA_TOTAL_MAX_ABS + 1e-9
    assert out["lambda_home"] + out["lambda_away"] <= (3.40 + 0.45) * LAMBDA_TOTAL_MAX_REL + 1e-9
    # l'1X2 pubblicato è quello della griglia limitata, non il vettore mediato irraggiungibile
    g = tau_grid(out["lambda_home"], out["lambda_away"], out["dc_rho"], size=GRID_SIZE)
    i, j = np.indices(g.shape)
    assert out["p_home"] == pytest.approx(float(g[i > j].sum()), abs=1e-9)
    assert out["p_draw"] == pytest.approx(float(g[i == j].sum()), abs=1e-9)
    # la griglia limitata è più prudente del vettore mediato: il pareggio risale, non scende
    assert out["p_draw"] > 0.7 * dc["p_draw"] + 0.3 * elo["elo_p_draw"]
    assert abs(out["p_1x"] - (out["p_home"] + out["p_draw"])) < 1e-12
    # la scomposizione mostrata in scheda conserva sia il modello sui gol sia i rating
    assert out["dc_p_home"] == pytest.approx(0.86) and out["elo_p_home"] == pytest.approx(0.96)


def test_ensemble_non_tocca_le_lambda_quando_la_media_e_normale():
    """Il limite di sicurezza non deve scattare sulle partite ordinarie (misurato: 1,2% delle gare)."""
    dc = {"p_home": 0.50, "p_draw": 0.27, "p_away": 0.23, "dc_rho": -0.08,
          "lambda_home": 1.70, "lambda_away": 1.00}
    elo = {"elo_p_home": 0.46, "elo_p_draw": 0.28, "elo_p_away": 0.26}
    out = ensemble(dc, elo, w_dc=0.7)
    assert out["lambda_limitata"] is False
    assert out["lambda_home"] + out["lambda_away"] < 3.2
    # senza Elo non c'è inversione: le λ restano quelle del modello sui gol
    solo = ensemble(dc, None)
    assert solo["model"] == "dc" and solo["lambda_limitata"] is False
    assert solo["lambda_home"] == pytest.approx(1.70)


def test_i_limiti_di_sicurezza_valgono_sui_gol_attesi_pubblicati():
    """Il limite è sui gol attesi che il lettore vede, non su quelli grezzi.

    Con la ricetta promossa la calibrazione **moltiplica** (λ×1,04) invece di dividere: una λ
    già al tetto (4,00) uscirebbe a 4,16. Misurato rigenerando le previsioni il 2026-09-13:
    2 partite su 2.071 sopra i tetti prima della correzione, 0 dopo.
    """
    dc = {"p_home": 0.70, "p_draw": 0.18, "p_away": 0.12, "dc_rho": -0.09,
          "lambda_home": 4.60, "lambda_away": 1.00}
    elo = {"elo_p_home": 0.60, "elo_p_draw": 0.24, "elo_p_away": 0.16}
    out = ensemble(dc, elo, w_dc=0.7)
    assert out["lambda_limitata"] is True
    pub = calibrated_prediction(out, Calibration(lambda_scale=1.0401, rho_shift=-0.04))
    assert pub["lambda_home"] <= LAMBDA_MAX + 1e-9
    assert pub["lambda_home"] + pub["lambda_away"] <= LAMBDA_TOTAL_MAX_ABS + 1e-9
    assert pub["lambda_limitata"] is True
    # la griglia pubblicata è quella limitata: 1X2 e mercati restano coerenti
    g = tau_grid(pub["lambda_home"], pub["lambda_away"], pub["dc_rho"], size=GRID_SIZE)
    i, j = np.indices(g.shape)
    assert pub["p_home"] == pytest.approx(float(g[i > j].sum()), abs=1e-9)
    # il vincolo relativo (70%-135% del modello sui gol) è invariante alla scala
    assert pub["lambda_home"] + pub["lambda_away"] <= (4.60 + 1.00) * LAMBDA_TOTAL_MAX_REL * 1.0401 + 1e-9


def test_latest_per_match_tiene_solo_l_ultima_versione():
    """Una riga per (partita, modello): è la previsione che l'utente ha davvero visto.

    Con l'orizzonte esteso a tutto il calendario una partita viene riprevista a ogni run
    (5 al giorno): senza collasso il file cresce di ~23 versioni per partita e nessuna
    pagina le usa. Il collasso serve anche da migrazione della chiave vecchia.
    """
    base = pd.Timestamp("2026-09-13T12:00:00+00:00")
    df = pd.DataFrame([
        {"match_id": 1, "model": "ensemble", "made_at": base, "p_home": 0.40},
        {"match_id": 1, "model": "ensemble", "made_at": base + pd.Timedelta(hours=6), "p_home": 0.44},
        {"match_id": 1, "model": "ensemble", "made_at": base - pd.Timedelta(hours=6), "p_home": 0.36},
        {"match_id": 2, "model": "ensemble", "made_at": base, "p_home": 0.55},
    ])
    out = latest_per_match(df)
    assert len(out) == 2 and sorted(out.match_id) == [1, 2]
    # tiene la più recente, non la prima incontrata: l'ordine in ingresso non conta
    assert out.loc[out.match_id == 1, "p_home"].iloc[0] == 0.44
    assert list(out.columns) == list(df.columns)          # nessuna colonna persa
    # idempotente: rieseguire il collasso non cambia nulla
    assert len(latest_per_match(out)) == len(out)


def test_latest_per_match_casi_degeneri():
    vuoto = latest_per_match(pd.DataFrame())
    assert vuoto.empty
    senza_chiave = pd.DataFrame({"p_home": [0.4]})
    assert latest_per_match(senza_chiave) is senza_chiave  # nessuna chiave → restituita intatta
    # due modelli diversi sulla stessa partita restano due righe
    due = pd.DataFrame([
        {"match_id": 1, "model": "ensemble", "made_at": pd.Timestamp("2026-09-13", tz="UTC")},
        {"match_id": 1, "model": "dc", "made_at": pd.Timestamp("2026-09-13", tz="UTC")},
    ])
    assert len(latest_per_match(due)) == 2
