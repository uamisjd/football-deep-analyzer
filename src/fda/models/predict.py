"""Previsioni partita: Dixon-Coles (penaltyblog) + Elo + ensemble → mercati.

Input: DataFrame storico normalizzato (date, home, away, home_goals, away_goals) con nomi
canonici. Output: per ogni partita richiesta un dict con λ attese, 1X2, risultati esatti,
Over/Under, BTTS, doppia chance, e i contributi dei singoli modelli.

Nota tecnica: penaltyblog richiede array NumPy scrivibili (con pandas 3 copy-on-write le Series
sono read-only) → `.to_numpy().copy()`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import penaltyblog as pb

from .dc_grid import probability_grid

log = logging.getLogger(__name__)

MODEL_VERSION = "dc-elo-ens-0.2"   # 0.2: shrinkage dei parametri DC verso la media di lega

# Pseudo-partite del prior sui parametri attacco/difesa (shrinkage verso la media di lega).
SHRINK_PRIOR = 8.0


def _grid_markets(grid: Any) -> dict[str, float]:
    """Estrae i mercati principali da un FootballProbabilityGrid di penaltyblog."""
    hda = grid.home_draw_away
    top = {}
    m = np.asarray(grid.grid)
    flat = [(int(i), int(j), float(m[i, j])) for i in range(min(m.shape[0], 8)) for j in range(min(m.shape[1], 8))]
    flat.sort(key=lambda t: -t[2])
    for i, j, p in flat[:6]:
        top[f"{i}-{j}"] = round(p, 4)
    return {
        "p_home": float(hda[0]), "p_draw": float(hda[1]), "p_away": float(hda[2]),
        "lambda_home": float(grid.home_goal_expectation),
        "lambda_away": float(grid.away_goal_expectation),
        "p_over15": float(grid.total_goals("over", 1.5)),
        "p_over25": float(grid.total_goals("over", 2.5)),
        "p_over35": float(grid.total_goals("over", 3.5)),
        "p_btts": float(grid.btts_yes),
        "p_1x": float(grid.double_chance_1x), "p_12": float(grid.double_chance_12),
        "p_x2": float(grid.double_chance_x2),
        "p_home_clean_sheet": float(np.asarray(grid.grid)[:, 0].sum()),
        "p_away_clean_sheet": float(np.asarray(grid.grid)[0, :].sum()),
        "top_scores": top,
    }


@dataclass
class DixonColesModel:
    xi: float = 0.0018             # decadimento temporale (Dixon & Coles 1997: ~0.0065/settimana ≈ 0.0009/giorno)
    max_goals: int = 10
    # Shrinkage dei parametri attacco/difesa verso la media di lega. A inizio stagione una
    # neopromossa ha 2-3 partite: il suo stimatore finisce al bordo dell'ottimizzazione
    # (attacco −2,5) e la rende "incapace di segnare" (Dortmund–Paderborn λ 1,02–0,19 con
    # Over 2,5 al 12%, contro 0,71 xG/gara reali del Paderborn). Il parametro viene
    # contratto di f = w/(w+shrink_prior), dove w è il peso temporale delle sue partite.
    # shrink_prior = 0 disattiva la contrazione (comportamento penaltyblog puro).
    shrink_prior: float = SHRINK_PRIOR
    model: Any = field(default=None, init=False, repr=False)
    teams: set[str] = field(default_factory=set, init=False)
    team_weight: dict[str, float] = field(default_factory=dict, init=False)
    fitted_at: datetime | None = field(default=None, init=False)
    n_matches: int = field(default=0, init=False)

    def fit(self, hist: pd.DataFrame, as_of: datetime | None = None) -> "DixonColesModel":
        df = hist.dropna(subset=["home_goals", "away_goals"]).copy()
        if as_of is not None:
            df = df[df["date"] <= pd.Timestamp(as_of).tz_localize(None) if df["date"].dt.tz is None
                    else df["date"] <= pd.Timestamp(as_of)]
        if len(df) < 50:
            raise ValueError(f"storico insufficiente per Dixon-Coles: {len(df)} partite")
        dates = pd.to_datetime(df["date"]).dt.tz_localize(None) if df["date"].dt.tz is not None else df["date"]
        weights = pb.models.dixon_coles_weights(dates, xi=self.xi)
        self.model = pb.models.DixonColesGoalModel(
            df["home_goals"].to_numpy(dtype=float).copy(),
            df["away_goals"].to_numpy(dtype=float).copy(),
            df["home"].to_numpy().copy(),
            df["away"].to_numpy().copy(),
            weights=np.asarray(weights, dtype=float).copy(),
        )
        self.model.fit()
        self.teams = set(df["home"]) | set(df["away"])
        w = pd.Series(np.asarray(weights, dtype=float), index=df.index)
        per_team = w.groupby(df["home"]).sum().add(w.groupby(df["away"]).sum(), fill_value=0.0)
        self.team_weight = {str(t): float(v) for t, v in per_team.items()}
        self.n_matches = int(len(df))
        self.fitted_at = datetime.now(timezone.utc)
        return self

    def shrunk_params(self, params: dict[str, float] | Any) -> dict[str, float]:
        """Parametri attacco/difesa contratti verso la media di lega, in proporzione ai dati.

        ``f = w / (w + shrink_prior)`` con ``w`` = peso temporale accumulato dalla squadra
        (una squadra presente da 3 stagioni pesa ~130 con xi=0.0018, una neopromossa ~2).

        Poiché ``f`` cambia da squadra a squadra, la contrazione sposterebbe le medie di
        lega e con esse il gauge scelto dall'ottimizzatore (λ = exp(attacco + difesa +
        hfa)): le due medie vengono quindi riportate al valore del fit. Restano intatte
        graduatorie e differenze relative, che sono ciò che determina λ.
        """
        params = dict(params)
        if self.shrink_prior <= 0 or not self.teams:
            return params
        att = {t: float(params.get(f"attack_{t}", 0.0)) for t in self.teams}
        dfn = {t: float(params.get(f"defence_{t}", 0.0)) for t in self.teams}
        mean_att = sum(att.values()) / len(att)
        mean_dfn = sum(dfn.values()) / len(dfn)
        shrunk_att, shrunk_dfn = {}, {}
        for t in self.teams:
            w = self.team_weight.get(t, 0.0)
            f = w / (w + self.shrink_prior)
            shrunk_att[t] = mean_att + (att[t] - mean_att) * f
            shrunk_dfn[t] = mean_dfn + (dfn[t] - mean_dfn) * f
        shift_att = sum(shrunk_att.values()) / len(shrunk_att) - mean_att
        shift_dfn = sum(shrunk_dfn.values()) / len(shrunk_dfn) - mean_dfn
        for t in self.teams:
            params[f"attack_{t}"] = shrunk_att[t] - shift_att
            params[f"defence_{t}"] = shrunk_dfn[t] - shift_dfn
        return params

    def lambdas(self, home: str, away: str, params: dict[str, float]) -> tuple[float, float]:
        """λ attese dalla parametrizzazione moltiplicativa di penaltyblog (exp di att+dif+hfa)."""
        hfa = float(params.get("home_advantage", 0.0))
        att_h = float(params.get(f"attack_{home}", 0.0))
        att_a = float(params.get(f"attack_{away}", 0.0))
        dfn_h = float(params.get(f"defence_{home}", 0.0))
        dfn_a = float(params.get(f"defence_{away}", 0.0))
        return math.exp(att_h + dfn_a + hfa), math.exp(att_a + dfn_h)

    def predict(self, home: str, away: str) -> dict[str, Any]:
        if home not in self.teams or away not in self.teams:
            missing = [t for t in (home, away) if t not in self.teams]
            raise KeyError(f"squadre non nello storico DC: {missing}")
        params = self.shrunk_params(self.model.get_params())
        lh, la = self.lambdas(home, away, params)
        # griglia ricostruita sui parametri contratti (stessa τ del modello addestrato)
        grid = probability_grid(lh, la, params.get("rho", 0.0) or 0.0, size=self.max_goals)
        out = _grid_markets(grid)
        out["dc_attack_home"] = float(params.get(f"attack_{home}", float("nan")))
        out["dc_defence_home"] = float(params.get(f"defence_{home}", float("nan")))
        out["dc_attack_away"] = float(params.get(f"attack_{away}", float("nan")))
        out["dc_defence_away"] = float(params.get(f"defence_{away}", float("nan")))
        out["dc_home_advantage"] = float(params.get("home_advantage", float("nan")))
        out["dc_rho"] = float(params.get("rho", float("nan")))
        return out

    def strength_table(self) -> pd.DataFrame:
        p = self.shrunk_params(self.model.get_params())
        rows = [{"team": t, "attack": p[f"attack_{t}"], "defence": p[f"defence_{t}"],
                 "matches_weight": round(self.team_weight.get(t, 0.0), 1)} for t in sorted(self.teams)]
        df = pd.DataFrame(rows)
        # più alto = meglio, per entrambi (attack alto = segna di più; defence basso = subisce meno)
        df["rating"] = df["attack"] - df["defence"]
        return df.sort_values("rating", ascending=False).reset_index(drop=True)


@dataclass
class EloModel:
    k: float = 20.0
    home_field_advantage: float = 60.0
    ratings: dict[str, float] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list, init=False)

    def fit(self, hist: pd.DataFrame) -> "EloModel":
        elo = pb.ratings.Elo(k=self.k, home_field_advantage=self.home_field_advantage)
        df = hist.dropna(subset=["home_goals", "away_goals"]).sort_values("date")
        # 0 = vittoria casa, 1 = pareggio, 2 = vittoria trasferta (convenzione penaltyblog)
        for r in df.itertuples(index=False):
            result = 0 if r.home_goals > r.away_goals else (1 if r.home_goals == r.away_goals else 2)
            elo.update_ratings(r.home, r.away, result)
        self._elo = elo
        teams = set(df["home"]) | set(df["away"])
        self.ratings = {t: float(elo.get_team_rating(t)) for t in teams}
        return self

    def predict(self, home: str, away: str) -> dict[str, float]:
        p = self._elo.calculate_match_probabilities(home, away)
        # penaltyblog restituisce un oggetto/dict con home_win, draw, away_win
        ph, pd_, pa = (p["home_win"], p["draw"], p["away_win"]) if isinstance(p, dict) \
            else (p.home_win, p.draw, p.away_win)
        return {"elo_home": self.ratings.get(home, 1500.0), "elo_away": self.ratings.get(away, 1500.0),
                "elo_p_home": float(ph), "elo_p_draw": float(pd_), "elo_p_away": float(pa)}


def ensemble(dc: dict[str, Any], elo: dict[str, float] | None, w_dc: float = 0.7) -> dict[str, Any]:
    """Media pesata 1X2 tra Dixon-Coles ed Elo; i mercati sui gol restano dal DC (l'Elo non ha λ).

    Se la media sposta il 1X2, si ricalcola una griglia DC coerente con le nuove probabilità
    (goal_expectancy di penaltyblog) così risultati esatti/Over/BTTS restano allineati.
    """
    out = dict(dc)
    if not elo:
        out["model"] = "dc"
        return out
    ph = w_dc * dc["p_home"] + (1 - w_dc) * elo["elo_p_home"]
    pdw = w_dc * dc["p_draw"] + (1 - w_dc) * elo["elo_p_draw"]
    pa = w_dc * dc["p_away"] + (1 - w_dc) * elo["elo_p_away"]
    s = ph + pdw + pa
    ph, pdw, pa = ph / s, pdw / s, pa / s
    try:
        ge = pb.models.goal_expectancy(ph, pdw, pa, dc_adj=True, rho=dc.get("dc_rho", 0.0) or 0.0)
        lh, la = float(ge["home_exp"]), float(ge["away_exp"])
        grid = probability_grid(lh, la, dc.get("dc_rho", 0.0) or 0.0, size=10)
        markets = _grid_markets(grid)
        # la doppia chance è per definizione una somma di esiti 1X2: va ricalcolata sul 1X2
        # mediato, altrimenti la scheda mostra «1X 73%» accanto a «1X2 48/27/26» (100−26=74).
        # Sui dati pubblicati lo scarto arrivava a 1,1 punti e l'intero a schermo era
        # incoerente nel 14,3% delle partite.
        markets.update({"p_home": ph, "p_draw": pdw, "p_away": pa,
                        "p_1x": ph + pdw, "p_12": ph + pa, "p_x2": pdw + pa})
        out.update(markets)
    except Exception as exc:  # fallback: solo 1X2 mediato
        log.debug("goal_expectancy fallita (%s): uso 1X2 mediato e mercati DC", exc)
        out.update({"p_home": ph, "p_draw": pdw, "p_away": pa})
    out.update(elo)
    out["model"] = "ensemble"
    out["w_dc"] = w_dc
    return out


def fair_odds(p: float) -> float | None:
    return None if not p or p <= 0 else round(1.0 / p, 2)


def predict_matches(hist: pd.DataFrame, fixtures: pd.DataFrame, xi: float = 0.0018,
                    w_dc: float = 0.7,
                    shrink_prior: float = SHRINK_PRIOR) -> tuple[pd.DataFrame, DixonColesModel, EloModel]:
    """Addestra DC+Elo su `hist` e prevede le righe di `fixtures` (colonne: match_id, home, away, ...)."""
    dc = DixonColesModel(xi=xi, shrink_prior=shrink_prior).fit(hist)
    elo = EloModel().fit(hist)
    made_at = datetime.now(timezone.utc)
    rows = []
    for f in fixtures.itertuples(index=False):
        try:
            d = dc.predict(f.home, f.away)
        except KeyError as exc:
            log.warning("previsione saltata %s: %s", getattr(f, "match_id", "?"), exc)
            continue
        e = elo.predict(f.home, f.away) if f.home in elo.ratings and f.away in elo.ratings else None
        r = ensemble(d, e, w_dc=w_dc)
        r.update({
            "match_id": getattr(f, "match_id", None), "home": f.home, "away": f.away,
            "utc_kickoff": getattr(f, "utc_kickoff", None), "league_key": getattr(f, "league_key", None),
            "made_at": made_at, "model_version": MODEL_VERSION, "n_train": dc.n_matches,
            "fair_home": fair_odds(r["p_home"]), "fair_draw": fair_odds(r["p_draw"]),
            "fair_away": fair_odds(r["p_away"]),
            "top_scores": str(r.get("top_scores")),
        })
        rows.append(r)
    cols_first = ["match_id", "league_key", "utc_kickoff", "home", "away", "model", "p_home", "p_draw", "p_away",
                  "lambda_home", "lambda_away", "p_over25", "p_btts"]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[[c for c in cols_first if c in df.columns] + [c for c in df.columns if c not in cols_first]]
    return df, dc, elo


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di Wilson al 95% per una frequenza osservata ``k`` su ``n``.

    Serve a distinguere una distorsione reale dal rumore di campionamento: su 50 gare una
    differenza di 10 punti fra previsto e osservato può essere del tutto compatibile con il
    caso, e non giustifica una correzione del modello. L'intervallo di Wilson resta sensato
    anche per ``k = 0`` o ``k = n`` (a differenza dell'approssimazione normale).
    """
    if n <= 0:
        return (0.0, 1.0)
    p_hat = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = p_hat + z2 / (2 * n)
    half = z * float(np.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n)))
    return ((centre - half) / den, (centre + half) / den)


def rps(probs: list[list[float]], outcomes: list[int]) -> float:
    """Ranked Probability Score medio (0 = perfetto; ~0.2 tipico per il calcio)."""
    return float(pb.metrics.rps_average(np.asarray(probs, dtype=float), np.asarray(outcomes, dtype=int)))


def outcome_index(hg: int, ag: int) -> int:
    return 0 if hg > ag else (1 if hg == ag else 2)


def log_loss(p: float) -> float:
    return -math.log(max(p, 1e-12))
