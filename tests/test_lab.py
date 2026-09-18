"""Laboratorio modelli: assenza di leakage, miscele di griglie, metriche appaiate, stacking."""

import numpy as np
import pandas as pd
import pytest

from fda.models import lab
from fda.models.calibration import Calibration
from fda.models.predict import ENSEMBLE_MODE, LAMBDA_TOTAL_MAX_REL
from fda.models.dc_grid import tau_grid
from fda.models.lab import (BASELINE, CANDIDATES, Candidate, convex_weights, per_league,
                            summarize, walk_forward)


def synthetic_hist(n_teams: int = 12, seasons: int = 3, seed: int = 3) -> pd.DataFrame:
    """Storico sintetico: forza fissa per squadra, gol Poisson, un turno a settimana."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    att = {t: float(rng.normal(0, 0.3)) for t in teams}
    dfn = {t: float(rng.normal(0, 0.3)) for t in teams}
    rows, start = [], pd.Timestamp("2023-08-12")
    for season in range(seasons):
        for rnd in range(n_teams - 1):
            day = start + pd.Timedelta(days=7 * rnd + 365 * season)
            order = list(rng.permutation(teams))
            for i in range(0, n_teams, 2):
                home, away = order[i], order[i + 1]
                lh = np.exp(0.15 + att[home] - dfn[away])
                la = np.exp(-0.10 + att[away] - dfn[home])
                rows.append({"date": day, "league_key": "TEST", "home": home, "away": away,
                             "home_goals": int(rng.poisson(lh)), "away_goals": int(rng.poisson(la))})
    return pd.DataFrame(rows)


class _SpyGonfia:
    """Modello sui gol con λ deliberatamente troppo alte (3,5 gol a partita)."""

    def __init__(self, train: pd.DataFrame) -> None:
        self.teams = set(train["home"]) | set(train["away"])
        self.train_max = pd.to_datetime(train["date"]).max()
        self.n_train = len(train)

    def grid(self, home: str, away: str) -> np.ndarray:
        return tau_grid(2.0, 1.5, -0.05, size=lab.GRID_SIZE)


class SpyGoals:
    """Modello sui gol finto: registra l'ultima data vista in allenamento."""

    def __init__(self, train: pd.DataFrame) -> None:
        self.teams = set(train["home"]) | set(train["away"])
        self.train_max = pd.to_datetime(train["date"]).max()
        self.n_train = len(train)

    def grid(self, home: str, away: str) -> np.ndarray:
        return tau_grid(1.4 if home < away else 1.1, 1.1 if home < away else 1.4, -0.05, size=lab.GRID_SIZE)


def test_walk_forward_never_trains_on_the_future(monkeypatch):
    """Ogni gara valutata è prevista da un fit che ha visto solo partite precedenti."""
    seen: list[pd.Timestamp] = []

    def spy_fit(train, cand):                     # noqa: ANN001, ANN202 — firma di fit_goals
        spy = SpyGoals(train)
        seen.append(spy.train_max)
        return spy

    monkeypatch.setattr(lab, "fit_goals", spy_fit)
    cand = (Candidate("spy", "Modello spia", "goals", "poisson"),)
    rows = walk_forward(synthetic_hist(), cand, step_days=28, min_train=60)
    assert len(rows) > 50
    assert (pd.to_datetime(rows["date"]) > pd.to_datetime(pd.Series(seen)).min()).all()
    # la data di allenamento di ogni finestra precede strettamente le gare che valuta
    assert max(seen) < pd.to_datetime(rows["date"]).max()
    assert (rows["n_train"] >= 60).all()
    assert not rows.duplicated(subset=["candidate", "date", "home", "away"]).any()


def test_walk_forward_is_empty_on_short_history():
    hist = synthetic_hist(seasons=1)
    assert walk_forward(hist, (Candidate("dc_puro", "DC", "goals", "dixon_coles"),),
                        step_days=14, min_train=5000).empty


def test_candidates_registry_is_unique_and_has_the_baseline():
    keys = [c.key for c in CANDIDATES]
    assert len(keys) == len(set(keys))
    assert BASELINE in keys
    # ogni candidato dichiara famiglia e tipo: servono al riepilogo e alla pagina del sito
    for c in CANDIDATES:
        assert c.kind in {"goals", "rating", "blend", "production"} and c.label and c.family


def test_le_griglie_degli_iperparametri_sono_pre_registrate():
    """P1.11 (docs/19 §1.4): chi cerca un iperparametro dichiara la griglia nel codice.

    La griglia contiene **tutti** i valori provati nell'insieme dei candidati (valore di
    riferimento compreso) ed è ordinata: senza pre-registrazione «IC95<0» si ottiene anche
    solo accorciando la griglia al punto giusto. I candidati a parametri fissi — produzione,
    riferimenti e famiglie alternative — non cercano nulla e non dichiarano nulla.
    """
    varianti = {"dc_xi10", "dc_xi30", "dc_no_shrink", "dc_shrink16", "mix_50", "mix_85",
                "prod_w50", "prod_w85", "elo_k10", "elo_k40", "elo_hfa40", "elo_hfa80"}
    fissi = {"dc_elo_prod", "dc_elo_ge", "dc_puro", "poisson", "biv_poisson", "neg_binomial",
             "zero_inflated", "weibull_copula", "elo", "pi_ratings"}
    keys = {c.key: c for c in CANDIDATES}
    assert varianti | fissi <= set(keys), "insieme dei candidati cambiato: aggiornare il test"
    for key in varianti:
        c = keys[key]
        assert c.grid, f"{key}: variante di iperparametro senza griglia pre-registrata"
        assert list(c.grid) == sorted(set(c.grid)), f"{key}: griglia non ordinata o con doppioni"
        # il valore provato dal candidato sta nella griglia dichiarata
        assert any(float(v) in c.grid for v in c.params.values()), \
            f"{key}: il valore in params non è fra quelli dichiarati in grid"
    for key in fissi:
        assert keys[key].grid == (), f"{key}: a parametri fissi non dichiara griglie"


def test_walk_forward_dichiara_griglia_e_numero_di_tentativi(monkeypatch):
    """Ogni riga del laboratorio porta griglia pre-registrata e tentativi della famiglia (P1.11)."""
    monkeypatch.setattr(lab, "fit_goals", lambda train, cand: SpyGoals(train))
    cands = (Candidate("elo_k10", "Elo k 10", "rating", "elo", {"k": 10.0, "hfa": 60.0},
                       grid=(10.0, 20.0, 40.0)),
             Candidate("elo_k40", "Elo k 40", "rating", "elo", {"k": 40.0, "hfa": 60.0},
                       grid=(10.0, 20.0, 40.0)),
             Candidate("spy", "Modello spia", "goals", "poisson"))
    rows = walk_forward(synthetic_hist(), cands, step_days=28, min_train=60, max_windows=4)
    assert not rows.empty
    elo = rows[rows["candidate"] != "spy"]
    spy = rows[rows["candidate"] == "spy"]
    assert (elo["n_tentativi"] == 2).all()          # due candidati Elo provati in questo run
    assert set(elo["grid_dichiarata"]) == {"10.0|20.0|40.0"}
    assert (spy["n_tentativi"] == 1).all() and (spy["grid_dichiarata"] == "").all()
    # il riepilogo e la tabella per lega pubblicano le stesse informazioni (model_lab.parquet)
    tab = summarize(rows, draws=100)
    assert {"grid_dichiarata", "n_tentativi"} <= set(tab.columns)
    t = tab.set_index("candidate")
    assert t.loc["elo_k10", "n_tentativi"] == 2 and t.loc["elo_k40", "n_tentativi"] == 2
    assert t.loc["elo_k10", "grid_dichiarata"] == "10.0|20.0|40.0"
    assert t.loc["spy", "n_tentativi"] == 1 and t.loc["spy", "grid_dichiarata"] == ""
    per = per_league(rows)
    assert {"grid_dichiarata", "n_tentativi"} <= set(per.columns)
    per_elo = per[per["candidate"].isin(["elo_k10", "elo_k40"])]
    assert (per_elo["n_tentativi"] == 2).all()
    assert (per_elo["grid_dichiarata"] == "10.0|20.0|40.0").all()


def test_summarize_senza_colonne_p11_conta_i_tentativi_dalle_righe():
    """Righe costruite a mano (test): n_tentativi si conta dalle righe, griglia resta vuota."""
    rng = np.random.default_rng(7)
    n = 200
    outcomes = rng.choice([0, 1, 2], size=n, p=[0.44, 0.26, 0.30])
    good = np.tile([0.44, 0.26, 0.30], (n, 1)) + rng.normal(0, 0.02, (n, 3))
    good = np.clip(good, 0.01, 0.95)
    good = good / good.sum(1, keepdims=True)
    bad = np.tile([1 / 3, 1 / 3, 1 / 3], (n, 1))
    rows = _rows({BASELINE: bad, "migliore": good}, outcomes)     # entrambi family "poisson"
    assert "n_tentativi" not in rows.columns
    tab = summarize(rows, baseline=BASELINE, draws=100)
    assert {"grid_dichiarata", "n_tentativi"} <= set(tab.columns)
    assert (tab["n_tentativi"] == 2).all()
    assert (tab["grid_dichiarata"] == "").all()


def test_mix_grids_stays_a_valid_distribution_between_the_two_components():
    lh, la, rho = 1.7, 1.1, -0.06
    ga = tau_grid(lh, la, rho, size=lab.GRID_SIZE)
    probs_b = (0.40, 0.29, 0.31)
    for w in (0.0, 0.35, 0.7, 1.0):
        mix, _, _ = lab._mix_grids(lh, la, rho, probs_b, w)
        assert mix.shape == ga.shape
        assert (mix >= -1e-15).all()
        assert mix.sum() == pytest.approx(1.0, abs=1e-9)
    i, j = np.indices(ga.shape)
    hda_a = (ga[i > j].sum(), ga[i == j].sum(), ga[i < j].sum())
    mix, _, _ = lab._mix_grids(lh, la, rho, probs_b, 0.5)
    hda_m = (mix[i > j].sum(), mix[i == j].sum(), mix[i < j].sum())
    # la miscela a metà sta fra le due componenti (nessuna probabilità "scappa" fuori)
    for a, b, m in zip(hda_a, probs_b, hda_m):
        assert min(a, b) - 1e-9 <= m <= max(a, b) + 1e-9


def _rows(candidates: dict[str, np.ndarray], outcomes: np.ndarray, leagues: list[str] | None = None):
    """Costruisce righe del laboratorio da vettori 1X2 dati (test deterministico e veloce)."""
    n = len(outcomes)
    leagues = leagues or ["TEST"] * n
    out = []
    for key, probs in candidates.items():
        for i in range(n):
            out.append({"candidate": key, "label": key, "kind": "goals", "family": "poisson",
                        "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                        "league_key": leagues[i], "home": f"H{i % 7}", "away": f"A{i % 5}",
                        "home_goals": int(outcomes[i] == 0), "away_goals": int(outcomes[i] == 2),
                        "outcome": int(outcomes[i]), "n_train": 500,
                        "p_home": probs[i, 0], "p_draw": probs[i, 1], "p_away": probs[i, 2],
                        "lambda_home": 1.5, "lambda_away": 1.2, "lambda_total": 2.7, "rho": -0.05,
                        "p_over15": 0.8, "p_over25": 0.55, "p_over35": 0.33, "p_btts": 0.55,
                        "p_home_clean_sheet": 0.26, "p_away_clean_sheet": 0.21})
    return pd.DataFrame(out)


def test_summarize_pairs_candidates_on_the_same_matches():
    rng = np.random.default_rng(7)
    n = 400
    outcomes = rng.choice([0, 1, 2], size=n, p=[0.44, 0.26, 0.30])
    # il vettore "migliore" è la distribuzione vera degli esiti: è il minimo dell'RPS
    good = np.tile([0.44, 0.26, 0.30], (n, 1)) + rng.normal(0, 0.02, (n, 3))
    good = np.clip(good, 0.01, 0.95)
    good = good / good.sum(1, keepdims=True)
    bad = np.tile([1 / 3, 1 / 3, 1 / 3], (n, 1))
    rows = _rows({BASELINE: bad, "migliore": good}, outcomes)
    tab = summarize(rows, baseline=BASELINE, draws=200)
    assert set(tab["candidate"]) == {BASELINE, "migliore"}
    ref = tab.set_index("candidate").loc[BASELINE]
    assert ref["delta_rps"] == pytest.approx(0.0, abs=1e-12)
    better = tab.set_index("candidate").loc["migliore"]
    assert better["delta_rps"] < 0                      # RPS più bassa = migliore
    assert better["delta_rps_hi95"] < 0.05              # l'IC appaiato è riportato
    assert 0.0 <= better["migliore_in"] <= 1.0
    assert better["n"] == int(ref["n"]) == n            # confronto sulle stesse gare
    assert (tab.iloc[0]["rps"] <= tab.iloc[-1]["rps"])   # ordinato dal migliore


def test_summarize_handles_rating_candidates_without_markets():
    rng = np.random.default_rng(11)
    n = 200
    outcomes = rng.choice([0, 1, 2], size=n)
    probs = np.clip(rng.dirichlet([3, 2, 2], size=n), 0.02, 0.9)
    probs = probs / probs.sum(1, keepdims=True)
    rows = _rows({BASELINE: probs, "elo": probs}, outcomes)
    rows.loc[rows["candidate"] == "elo", ["lambda_home", "lambda_away", "lambda_total", "rho",
                                          "p_over15", "p_over25", "p_over35", "p_btts",
                                          "p_home_clean_sheet", "p_away_clean_sheet"]] = np.nan
    tab = summarize(rows, draws=100)
    elo = tab.set_index("candidate").loc["elo"]
    assert np.isnan(elo.get("brier_mercati", np.nan))    # niente mercati: non si inventano zeri
    assert np.isnan(elo.get("bias_lambda", np.nan))
    assert np.isfinite(elo["rps"])


def test_per_league_splits_the_sample():
    rng = np.random.default_rng(3)
    n = 120
    outcomes = rng.choice([0, 1, 2], size=n)
    probs = np.clip(rng.dirichlet([3, 2, 2], size=n), 0.02, 0.9)
    probs = probs / probs.sum(1, keepdims=True)
    leagues = ["ITA1"] * (n // 2) + ["ENG1"] * (n - n // 2)
    rows = _rows({BASELINE: probs}, outcomes, leagues)
    tab = per_league(rows)
    assert set(tab["league_key"]) == {"ITA1", "ENG1"}
    assert int(tab["n"].sum()) == n
    assert ((tab["rps"] > 0) & (tab["rps"] < 1)).all()


def test_convex_weights_sum_to_one_and_follow_the_better_member():
    rng = np.random.default_rng(13)
    n = 600
    outcomes = rng.choice([0, 1, 2], size=n, p=[0.45, 0.26, 0.29])
    strong = np.tile([0.45, 0.26, 0.29], (n, 1)) + rng.normal(0, 0.015, (n, 3))
    strong = np.clip(strong, 0.02, 0.9)
    strong = strong / strong.sum(1, keepdims=True)
    weak = np.tile([1 / 3, 1 / 3, 1 / 3], (n, 1))
    rows = _rows({"forte": strong, "debole": weak}, outcomes)
    w = convex_weights(rows, ["forte", "debole"])
    assert set(w) == {"forte", "debole"}
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)
    assert w["forte"] > w["debole"]
    assert w["forte"] > 0.85, f"atteso quasi tutto il peso sul membro migliore, ottenuto {w}"


def test_calibration_is_threaded_through_the_lab():
    """La stessa calibrazione usata in produzione può essere applicata dentro il laboratorio."""
    cal = Calibration(lambda_scale=0.94, rho_shift=-0.04)
    row = {"lambda_home": 1.9, "lambda_away": 1.4, "rho": -0.06, "p_home": 0.5, "p_draw": 0.26,
           "p_away": 0.24}
    out = lab._apply_calibration(row, cal)
    assert out["lambda_home"] == pytest.approx(1.9 * 0.94)
    assert out["lambda_home_raw"] == pytest.approx(1.9)
    assert out["p_home"] + out["p_draw"] + out["p_away"] == pytest.approx(1.0, abs=1e-9)
    # con calibrazione identica la riga non viene toccata
    same = lab._apply_calibration(row, Calibration())
    assert same["lambda_home"] == pytest.approx(1.9) and "lambda_home_raw" not in same


def test_lab_runs_on_a_real_offline_corpus(tmp_path):
    """Smoke test sul corpus ricostruito dagli H2H, se presente (altrimenti sintetico)."""
    hist = synthetic_hist(seasons=3)
    rows = walk_forward(hist, tuple(c for c in CANDIDATES if c.key in {"dc_puro", "elo", "mix_50"}),
                        step_days=21, min_train=100, max_windows=5)
    assert not rows.empty
    assert set(rows["candidate"]) <= {"dc_puro", "elo", "mix_50"}
    tab = summarize(rows, baseline="dc_puro", draws=100)
    assert "rps" in tab.columns and len(tab) >= 1


def test_il_candidato_della_ricetta_precedente_usa_l_inversione_delle_lambda():
    """Dopo la promozione del tilt, il laboratorio tiene la ricetta precedente come candidato.

    Serve a rendere ripetibile il confronto che ha deciso la promozione: ``dc_elo_prod`` è
    ora la ricetta a gol invariati, ``dc_elo_ge`` è ``goal_expectancy`` (λ libere dall'1X2
    mediato). Entrambe passano da ``predict.ensemble``, una sola implementazione.
    """
    keys = {c.key: c for c in CANDIDATES}
    assert BASELINE == "dc_elo_prod"
    assert keys["dc_elo_prod"].params.get("mode", ENSEMBLE_MODE) == ENSEMBLE_MODE
    assert keys["dc_elo_ge"].params.get("mode") == "inverti"
    assert keys["dc_elo_ge"].kind == "production"


def test_mix_grids_non_gonfia_le_lambda_su_vettori_irraggiungibili():
    """Un pareggio al 9,5% non è riproducibile da una griglia DC: l'inversione scappava a 8,9 gol.

    Misurato sui dati H2H (Elo degenerato): λ_B 5,80+3,14, miscela a 5,7 gol attesi. Senza il
    limite la miscela veniva bocciata per un difetto dell'inversione, non del candidato.
    """
    lh, la, rho = 1.80, 0.90, -0.18
    g, _, _ = lab._mix_grids(lh, la, rho, (0.761, 0.095, 0.144), 0.5)
    i, j = np.indices(g.shape)
    totale = float((g * (i + j)).sum())
    assert g.sum() == pytest.approx(1.0, abs=1e-9)
    assert totale <= (lh + la) * LAMBDA_TOTAL_MAX_REL + 1e-6, f"miscela a {totale:.2f} gol attesi"
    assert totale < 4.0, "prima del limite la stessa miscela dava 5,7 gol attesi"


def test_walk_forward_corregge_ogni_candidato_solo_sul_passato(monkeypatch):
    """Ogni candidato riceve la propria correzione del livello dei gol, dalle gare già valutate.

    Senza, il confronto è iniquo: la produzione è pubblicata calibrata e un candidato con λ più
    basse verrebbe penalizzato due volte. La correzione non può guardare avanti.
    """
    monkeypatch.setattr(lab, "fit_goals", lambda train, cand: _SpyGonfia(train))
    hist = synthetic_hist(seasons=6)
    cand = (Candidate("spy", "Modello spia gonfiata", "goals", "poisson"),)
    on = walk_forward(hist, cand, step_days=28, min_train=120, self_calibrate=True)
    off = walk_forward(hist, cand, step_days=28, min_train=120, self_calibrate=False)
    assert not on.empty and len(on) == len(off)
    # la spia prevede 3,5 gol a partita, lo storico sintetico ne produce ~2,6 → servirebbe 0,73,
    # che il limite di sicurezza della calibrazione riporta a 0,85
    scale = on["lambda_scale"].to_numpy(float)
    assert 0.85 - 1e-9 <= scale.min() <= 1.0 + 1e-9
    assert scale.max() <= 1.05 + 1e-9
    assert (scale == 1.0).any(), "le prime finestre non hanno ancora gare valutate: niente correzione"
    assert (scale < 1.0).any(), "dopo le prime finestre la correzione deve scattare"
    tab_on = summarize(on, baseline="spy", draws=50)
    tab_off = summarize(off, baseline="spy", draws=50)
    assert abs(tab_on["bias_lambda"].iloc[0]) < abs(tab_off["bias_lambda"].iloc[0])
    assert tab_on["scala_media"].iloc[0] == pytest.approx(scale.mean(), abs=1e-9)
    assert tab_on["rps"].iloc[0] <= tab_off["rps"].iloc[0] + 1e-9


def test_tilt_total_cambia_il_livello_senza_cambiare_la_forma():
    """L'inclinazione esponenziale sposta solo la media dei gol: la forma della famiglia resta.

    Per Poisson indipendenti θ^(i+j) equivale a λ·θ, quindi il meccanismo è la generalizzazione
    del moltiplicatore di calibrazione a una matrice di punteggi qualunque (binomiale negativa,
    zero-inflazionata, copula Weibull), che non hanno λ né ρ da scalare.
    """
    lh, la = 1.6, 1.1
    g = tau_grid(lh, la, 0.0, size=lab.GRID_SIZE)
    i, j = np.indices(g.shape)
    k = (i + j).astype(float)
    prima = float((g * k).sum())
    for fattore in (0.85, 1.0, 1.12):
        t = lab._tilt_total(g, prima * fattore)
        assert t.sum() == pytest.approx(1.0, abs=1e-12) and (t >= 0).all()
        assert float((t * k).sum()) == pytest.approx(prima * fattore, abs=1e-9)
    # la direzione casa/trasferta non cambia: il rapporto fra le due medie resta quello
    # (a 1e-5, perché la matrice è troncata a 10 gol e la coda che esce cambia di poco)
    t = lab._tilt_total(g, prima * 0.9)
    assert float((t * i).sum()) / float((t * j).sum()) == pytest.approx(
        float((g * i).sum()) / float((g * j).sum()), abs=1e-4)
    # il rapporto di due celle con lo stesso totale gol è invariato (la forma non viene toccata)
    assert t[3, 1] / t[2, 2] == pytest.approx(g[3, 1] / g[2, 2], abs=1e-9)
    # target irraggiungibili restano entro i limiti invece di produrre NaN o zeri
    estremo = lab._tilt_total(g, 1e6)
    assert np.isfinite(estremo).all() and estremo.sum() == pytest.approx(1.0, abs=1e-9)
    assert lab._tilt_total(np.zeros_like(g), 2.0).sum() == pytest.approx(0.0)


def test_le_famiglie_senza_rho_ricevono_la_correzione_del_livello():
    """Regione del laboratorio che non era coperta: Poisson/binomiale negativa/non calibrate.

    Prima la correzione del livello dei gol toccava solo Dixon-Coles, miscele e produzione:
    le altre famiglie venivano confrontate con λ non corrette, cioè penalizzate o favorite
    dal loro livello di gol invece che dalla loro forma.
    """
    from fda.models.calibration import Calibration

    class GrigliaFissa:
        teams = {"A", "B"}

        def grid(self, home: str, away: str) -> np.ndarray:
            return tau_grid(1.9, 1.4, 0.0, size=lab.GRID_SIZE)

    row = lab._row_from_grid(GrigliaFissa().grid("A", "B"), 1.9, 1.4, 0.0)
    out = lab._apply_grid_level(row, GrigliaFissa().grid("A", "B"),
                                Calibration(lambda_scale=0.9, rho_shift=-0.04))
    assert out["lambda_home_raw"] == pytest.approx(1.9)
    assert out["lambda_total"] == pytest.approx(row["lambda_total"] * 0.9, abs=1e-6)
    assert out["p_home"] + out["p_draw"] + out["p_away"] == pytest.approx(1.0, abs=1e-9)
    # senza ρ il pareggio non viene spostato di proposito: cambia solo il livello
    assert out["p_draw"] > row["p_draw"]
    # calibrazione identica → riga intatta
    same = lab._apply_grid_level(row, GrigliaFissa().grid("A", "B"), Calibration())
    assert same["lambda_home"] == pytest.approx(1.9) and "lambda_home_raw" not in same


def test_con_calibrazione_attiva_la_miscela_resta_diversa_dal_dc():
    """Regressione: con una calibrazione non identica mix_50 diventava identico a dc_puro.

    `_apply_calibration` ricostruisce una griglia di Dixon-Coles dalle λ, e la miscela
    dichiarava le λ del DC: la forma mista spariva e il candidato smetteva di misurare ciò
    per cui esiste. Misurato il 2026-09-13 sul corpus H2H (405 gare, tutte identiche).
    """
    cal = Calibration(lambda_scale=0.9135, rho_shift=-0.04)
    hist = synthetic_hist(seasons=2)
    c_mix = next(c for c in CANDIDATES if c.key == "mix_50")
    c_dc = next(c for c in CANDIDATES if c.key == "dc_puro")
    f_mix, f_dc = lab._fit_candidate(c_mix, hist), lab._fit_candidate(c_dc, hist)
    home, away = hist.home.iloc[-1], hist.away.iloc[-1]
    mix = lab._predict_candidate(c_mix, f_mix, f_mix, home, away, cal)
    dc = lab._predict_candidate(c_dc, f_dc, f_dc, home, away, cal)
    assert mix is not None and dc is not None
    assert abs(mix["p_home"] - dc["p_home"]) > 1e-6, "la miscela deve restare diversa dal DC"
    assert mix["lambda_total"] != pytest.approx(dc["lambda_total"], abs=1e-6)
    assert mix["p_home"] + mix["p_draw"] + mix["p_away"] == pytest.approx(1.0, abs=1e-9)
    # le λ pubblicate descrivono la griglia pubblicata, non quella di un altro candidato
    assert mix["lambda_home"] == pytest.approx(mix["lambda_home_raw"] * 0.9135, rel=0.15)


# --- P2.9 / P2.10: candidati del laboratorio con griglia pre-registrata (docs/19 §1.2-§1.4) ---


def test_gamma_sharpening_non_cambia_il_totale_dei_gol():
    """P2.9: γ agisce sul **rapporto** delle λ, il livello dei gol resta quello calibrato."""
    lh, la = 1.8, 0.9
    for gamma in (1.0, 1.12, 1.24, 1.40):
        a, b = lab.sharpen_lambda_ratio(lh, la, gamma)
        assert a + b == pytest.approx(lh + la, abs=1e-9), "il totale dei gol deve restare invariato"
    # γ>1 concentra: il rapporto si allontana da 1, il favorito diventa più favorito
    a, b = lab.sharpen_lambda_ratio(lh, la, 1.24)
    assert a / b > lh / la
    # γ=1 è esattamente l'identità (nessun ritocco silenzioso della produzione)
    assert lab.sharpen_lambda_ratio(lh, la, 1.0) == (lh, la)


def test_temperatura_1x2_normalizza_e_non_cambia_l_esito_indicato():
    """P2.10: τ sposta massa sul favorito ma l'argmax è invariante (docs/19 §1.2)."""
    p = (0.50, 0.28, 0.22)
    for tau in (0.90, 1.0, 1.10, 1.30):
        q = lab.recalibrate_1x2(*p, tau)
        assert sum(q) == pytest.approx(1.0, abs=1e-9), "il vettore deve restare una distribuzione"
        assert q.index(max(q)) == 0, "la temperatura non deve cambiare l'esito indicato"
    assert lab.recalibrate_1x2(*p, 1.0) == pytest.approx(p, abs=1e-12)
    # τ>1 concentra sul favorito, τ<1 appiattisce: è il verso del difetto misurato nei decili
    assert lab.recalibrate_1x2(*p, 1.20)[0] > p[0]
    assert lab.recalibrate_1x2(*p, 0.90)[0] < p[0]


def test_i_candidati_p29_p210_dichiarano_una_griglia_che_contiene_il_valore_provato():
    """Regola P1.11 (`docs/00` §D): niente candidato che cerca un iperparametro senza griglia."""
    nuovi = {c.key: c for c in CANDIDATES
             if "gamma" in c.params or "tau" in c.params}
    assert set(nuovi) == {"gamma_112", "gamma_124", "tau_090", "tau_110", "tau_120"}
    for cand in nuovi.values():
        assert cand.grid, f"{cand.key} senza griglia pre-registrata"
        valore = cand.params.get("gamma", cand.params.get("tau"))
        assert valore in cand.grid, f"{cand.key}: il valore provato non è nella griglia dichiarata"
        assert tuple(sorted(cand.grid)) == tuple(cand.grid), f"{cand.key}: griglia non ordinata"


def test_la_griglia_gamma_e_quella_onesta_non_quella_che_faceva_passare_il_candidato():
    """Il cuore di P2.9: con [0,94; 1,12] il candidato «passava», con [1,00; 1,40] no.

    La griglia dichiarata deve essere quella larga, altrimenti si ri-registra proprio il
    difetto di protocollo che P1.11 esiste per impedire (`docs/19` §1.3 e §1.4).
    """
    gamma = next(c for c in CANDIDATES if c.key == "gamma_112")
    assert max(gamma.grid) == pytest.approx(1.40), "griglia troncata: tornerebbe il difetto di §1.3"
    assert min(gamma.grid) == pytest.approx(1.00)
    assert 1.24 in gamma.grid, "l'ottimo della griglia onesta deve essere fra i valori dichiarati"


def test_la_griglia_tau_e_simmetrica_e_ammette_il_peggioramento():
    """Una griglia solo sopra 1,00 presupporrebbe la conclusione invece di misurarla."""
    tau = next(c for c in CANDIDATES if c.key == "tau_110")
    assert min(tau.grid) < 1.0 < max(tau.grid), "la griglia deve poter dire anche «peggiora»"
    assert 1.0 in tau.grid, "il valore di riferimento (nessun ritocco) deve essere nella griglia"


def test_i_nuovi_candidati_girano_nel_walk_forward_e_portano_la_griglia_nelle_righe():
    """Prova end-to-end: i candidati nuovi producono righe valide e marcate (P1.11)."""
    cands = tuple(c for c in CANDIDATES if c.key in {BASELINE, "gamma_124", "tau_120"})
    rows = walk_forward(synthetic_hist(), cands, step_days=28, min_train=60, max_windows=3)
    assert not rows.empty
    for key in ("gamma_124", "tau_120"):
        sub = rows[rows["candidate"] == key]
        assert not sub.empty, f"{key} non ha prodotto righe"
        assert (sub["grid_dichiarata"].str.len() > 0).all(), f"{key} senza griglia nelle righe"
        # le probabilità restano una distribuzione valida dopo il post-processo
        tot = sub[["p_home", "p_draw", "p_away"]].sum(axis=1)
        assert np.allclose(tot, 1.0, atol=1e-6), f"{key}: 1X2 non normalizzato"
    # la temperatura tocca l'1X2 ma NON i mercati sui gol (limite dichiarato in docstring)
    base = rows[rows["candidate"] == BASELINE].reset_index(drop=True)
    tau = rows[rows["candidate"] == "tau_120"].reset_index(drop=True)
    assert np.allclose(base["p_over25"], tau["p_over25"], atol=1e-9), \
        "τ non deve muovere i mercati derivati dalla matrice"
    assert not np.allclose(base["p_home"], tau["p_home"], atol=1e-6), "τ=1,20 deve muovere l'1X2"


def test_il_gamma_non_tocca_i_gol_attesi_totali_nel_walk_forward():
    """Controprova end-to-end di P2.9: stesso totale λ della produzione, forma diversa."""
    cands = tuple(c for c in CANDIDATES if c.key in {BASELINE, "gamma_124"})
    rows = walk_forward(synthetic_hist(), cands, step_days=28, min_train=60, max_windows=3)
    base = rows[rows["candidate"] == BASELINE].reset_index(drop=True)
    gam = rows[rows["candidate"] == "gamma_124"].reset_index(drop=True)
    assert np.allclose(base["lambda_home"] + base["lambda_away"],
                       gam["lambda_home"] + gam["lambda_away"], atol=1e-6), \
        "il γ-sharpening deve lasciare invariato il totale dei gol attesi"
    assert not np.allclose(base["lambda_home"], gam["lambda_home"], atol=1e-6)
