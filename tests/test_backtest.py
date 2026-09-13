"""Backtest cronologico: assenza di leakage, metriche e pubblicazione sulla pagina accuratezza."""


import numpy as np
import pandas as pd
import pytest

from fda.models.backtest import backtest_summary, chronological_backtest, observed_flags
from fda.models.predict import rps as pb_rps
from fda.models.predict import wilson_interval
from fda.site.build import SiteBuilder


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
                rows.append({"date": day, "league_key": "TEST", "home": home,
                             "away": away, "home_goals": int(rng.poisson(lh)),
                             "away_goals": int(rng.poisson(la))})
    return pd.DataFrame(rows)


class SpyDC:
    """Sostituisce Dixon-Coles: registra l'ultima data di allenamento e la restituisce."""

    def __init__(self, xi: float = 0.0018, shrink_prior: float = 0.0) -> None:
        self.n_matches = 0
        self.train_max: pd.Timestamp | None = None
        self.teams: set[str] = set()

    def fit(self, hist: pd.DataFrame, as_of=None) -> "SpyDC":
        self.n_matches = len(hist)
        self.train_max = pd.to_datetime(hist["date"]).max()
        self.teams = set(hist["home"]) | set(hist["away"])
        return self

    def predict(self, home: str, away: str) -> dict[str, float]:
        if home not in self.teams or away not in self.teams:
            raise KeyError(home)          # come il modello vero: squadra mai vista nello storico
        return {"p_home": 0.45, "p_draw": 0.28, "p_away": 0.27, "lambda_home": 1.4,
                "lambda_away": 1.1, "p_over15": 0.72, "p_over25": 0.5, "p_over35": 0.28,
                "p_btts": 0.52, "p_1x": 0.73, "p_12": 0.72, "p_x2": 0.55,
                "p_home_clean_sheet": 0.28, "p_away_clean_sheet": 0.24,
                "_train_max": self.train_max}


class StubElo:
    """Elo senza valutazioni: `_walk` passa `elo=None` e resta la previsione Dixon-Coles pura."""

    def fit(self, hist: pd.DataFrame) -> "StubElo":
        self.ratings: dict[str, float] = {}
        return self

    def predict(self, home: str, away: str) -> dict[str, float]:
        return {}


def test_backtest_never_trains_on_the_future(monkeypatch):
    """Ogni gara valutata è prevista da un modello allenato su partite strettamente precedenti."""
    monkeypatch.setattr("fda.models.backtest.DixonColesModel", SpyDC)
    monkeypatch.setattr("fda.models.backtest.EloModel", StubElo)
    hist = synthetic_hist()
    res = chronological_backtest(hist, step_days=14, min_train=60)

    assert len(res) > 100, f"attese molte gare valutate, trovate {len(res)}"
    assert (pd.to_datetime(res["_train_max"]) < pd.to_datetime(res["date"])).all(), \
        "trovata una previsione allenata su partite non precedenti alla gara"
    assert (res["n_train"] >= 60).all()
    # la valutazione inizia solo dopo le prime min_train partite
    soglia = hist.sort_values("date")["date"].iloc[60]
    assert pd.to_datetime(res["date"]).min() >= soglia
    # ogni gara dello storico compare al più una volta (nessuna finestra sovrapposta)
    assert not res.duplicated(subset=["date", "home", "away"]).any()


def test_backtest_skips_teams_missing_from_history(monkeypatch):
    monkeypatch.setattr("fda.models.backtest.DixonColesModel", SpyDC)
    monkeypatch.setattr("fda.models.backtest.EloModel", StubElo)
    hist = synthetic_hist()
    # una squadra che esordisce nell'ultima finestra: non è nel training di quella finestra,
    # quindi la sua gara non è valutabile, mentre le altre della stessa finestra restano
    ultimo = hist["date"].max()
    extra = pd.DataFrame([
        {"date": ultimo + pd.Timedelta(days=1), "league_key": "TEST", "home": "T00",
         "away": "NEOPROMOSSA", "home_goals": 2, "away_goals": 0},
        {"date": ultimo + pd.Timedelta(days=1), "league_key": "TEST", "home": "T02",
         "away": "T03", "home_goals": 1, "away_goals": 1},
    ])
    tutto = pd.concat([hist, extra], ignore_index=True)
    res = chronological_backtest(tutto, step_days=14, min_train=60)
    assert "NEOPROMOSSA" not in set(res["away"]) and "NEOPROMOSSA" not in set(res["home"])
    ultima_finestra = res[pd.to_datetime(res["date"]) > ultimo]
    assert len(ultima_finestra) == 1 and ultima_finestra.iloc[0]["home"] == "T02"


def test_backtest_summary_metrics_are_recomputed_independently():
    rng = np.random.default_rng(11)
    n = 60
    rows = []
    for i in range(n):
        p = np.sort(rng.dirichlet([2, 1.4, 1.4]))[::-1]
        outcome = int(rng.choice(3, p=p))
        hg, ag = (2, 0) if outcome == 0 else ((1, 1) if outcome == 1 else (0, 2))
        rows.append({"date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                     "league_key": "TEST", "home": f"H{i}", "away": f"A{i}",
                     "home_goals": hg, "away_goals": ag,
                     "outcome": outcome, "p_home": p[0], "p_draw": p[1], "p_away": p[2],
                     "p_over15": 0.75, "p_over25": 0.5, "p_over35": 0.25, "p_btts": 0.5,
                     "p_1x": p[0] + p[1], "p_12": p[0] + p[2], "p_x2": p[1] + p[2],
                     "p_home_clean_sheet": 0.3, "p_away_clean_sheet": 0.3})
    df = pd.DataFrame(rows)
    s = backtest_summary(df)

    oc = df["outcome"].to_numpy(int)
    probs = df[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist()
    assert abs(s["rps"] - pb_rps(probs, oc.tolist())) < 1e-9          # RPS = funzione indipendente
    p_real = df[["p_home", "p_draw", "p_away"]].to_numpy(float)[np.arange(n), oc]
    assert abs(s["logloss"] - float(-np.log(p_real).mean())) < 1e-9
    assert abs(s["hit"] - float((np.asarray(probs).argmax(1) == oc).mean())) < 1e-9
    assert s["n"] == n and s["leagues"] == 1
    assert [c["k"] for c in s["calib"]] == [int((oc == i).sum()) for i in range(3)]
    assert all(c["n"] == n for c in s["calib"])
    # Over 1,5 dichiarato 75% su esiti 2-0/1-1/0-2: osservato ben sotto → fuori intervallo
    o15 = next(m for m in s["markets"] if m["label"] == "Over 1,5 gol")
    lo, hi = wilson_interval(int(round(o15["obs"] * o15["n"])), o15["n"])
    assert o15["outside"] is bool(not (lo <= o15["prev"] <= hi))
    for m in s["markets"]:
        assert abs(m["delta"] - (m["brier"] - m["brier_base"])) < 1e-12
    assert backtest_summary(pd.DataFrame()) == {}


def test_observed_flags_match_their_definition():
    df = pd.DataFrame({"home_goals": [2, 0, 1, 3], "away_goals": [0, 0, 1, 1]})
    f = observed_flags(df)
    assert f["over15"].tolist() == [True, False, True, True]
    assert f["btts"].tolist() == [False, False, True, True]
    assert f["d1x"].tolist() == [True, True, True, True]
    assert f["d12"].tolist() == [True, False, False, True]
    assert f["cs_h"].tolist() == [True, True, False, False]


def _bt_rows() -> list[dict]:
    rows = []
    for i in range(40):
        rows.append({"date": pd.Timestamp("2025-08-16") + pd.Timedelta(days=7 * i),
                     "league_key": "TEST", "home": f"H{i}", "away": f"A{i}",
                     "home_goals": 2, "away_goals": 1, "outcome": 0, "p_home": 0.42,
                     "p_draw": 0.27, "p_away": 0.31, "p_over15": 0.78, "p_over25": 0.52,
                     "p_over35": 0.29, "p_btts": 0.55, "p_1x": 0.69, "p_12": 0.73,
                     "p_x2": 0.58,
                     "p_home_clean_sheet": 0.26, "p_away_clean_sheet": 0.24})
    return rows


def test_accuracy_page_renders_backtest_card(tmp_path):
    from tests.test_site import _seed

    st = _seed(tmp_path)
    st.upsert("backtest", _bt_rows())
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_accuracy(st.read("fixtures"))
    html = (out / "accuratezza.html").read_text(encoding="utf-8")

    assert "Backtest storico fuori campione" in html
    assert "su <b>40</b> partite già giocate" in html
    # 40 vittorie interne su 40: osservato 100% e previsto 42% → scarto fuori intervallo
    assert "100,0% <span class=\"mut\">(40/40)</span>" in html
    assert "fuori intervallo" in html
    i = html.find("Backtest storico fuori campione")
    assert "RPS <b>" in html[i:] and "log-loss <b>" in html[i:]
    assert "Over 2,5 gol" in html[i:] and "Doppia chance 1X" in html[i:]   # etichette italiane


def test_accuracy_page_without_backtest_table_has_no_card(tmp_path):
    from tests.test_site import _seed

    st = _seed(tmp_path)
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_accuracy(st.read("fixtures"))
    html = (out / "accuratezza.html").read_text(encoding="utf-8")
    assert "Backtest storico fuori campione" not in html
    assert (out / "accuratezza.html").exists()


@pytest.mark.parametrize("step_days,min_train", [(14, 60), (7, 80)])
def test_backtest_windows_are_configurable(monkeypatch, step_days, min_train):
    monkeypatch.setattr("fda.models.backtest.DixonColesModel", SpyDC)
    monkeypatch.setattr("fda.models.backtest.EloModel", StubElo)
    hist = synthetic_hist()
    res = chronological_backtest(hist, step_days=step_days, min_train=min_train)
    assert not res.empty and (res["n_train"] >= min_train).all()
    assert (pd.to_datetime(res["_train_max"]) < pd.to_datetime(res["date"])).all()
