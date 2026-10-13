"""λ da xG continui, solo laboratorio (protocollo preregistrato in docs/92).

penaltyblog tronca i risultati a interi: NON gli passiamo gli xG. Il fit quasi-Poisson
usa i valori decimali; il DC sui gol del medesimo prefisso fornisce solo ρ. Ensemble,
shrinkage e griglia restano quelli del riferimento. Non importato dal predict di produzione.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import penaltyblog as pb
from scipy.optimize import minimize

from .predict import DixonColesModel

FALLBACK_LEAGUES = frozenset({"NED1", "POR1"})
XG_COLUMNS = ["home_xg", "away_xg"]


@dataclass
class _Parameters:
    values: dict[str, float]
    iterations: int
    loss: float

    def get_params(self) -> dict[str, float]:
        return dict(self.values)


def _poisson_loss(theta: np.ndarray, home: np.ndarray, away: np.ndarray,
                  xgh: np.ndarray, xga: np.ndarray, weights: np.ndarray) -> tuple[float, np.ndarray]:
    """Quasi-verosimiglianza e gradiente analitico, senza arrotondamenti degli xG.

    L'attacco viene centrato: la direzione costante dei primi n parametri è ininfluente
    (gradiente a somma zero). La difesa mantiene il livello medio, hfa l'asimmetria casa.
    Il termine log Γ(xG+1), costante rispetto ai parametri, non serve all'ottimizzazione.
    """
    n = (len(theta) - 1) // 2
    attack = theta[:n] - theta[:n].mean()
    defence = theta[n:2 * n]
    eh = attack[home] + defence[away] + theta[-1]
    ea = attack[away] + defence[home]
    lh, la = np.exp(eh), np.exp(ea)
    w = weights / weights.sum()
    loss = float(np.sum(w * (lh - xgh * eh + la - xga * ea)))
    rh, ra = w * (lh - xgh), w * (la - xga)
    ga = np.bincount(home, weights=rh, minlength=n) + np.bincount(away, weights=ra, minlength=n)
    gd = np.bincount(away, weights=rh, minlength=n) + np.bincount(home, weights=ra, minlength=n)
    gradient = np.concatenate((ga - ga.mean(), gd, [rh.sum()]))
    return loss, gradient


def fit_fractional_poisson(hist: pd.DataFrame, weights: np.ndarray, rho: float) -> _Parameters:
    """Stima i parametri log-lineari su xG continui già validati; errore se non converge."""
    teams = sorted(set(hist["home"]) | set(hist["away"]))
    n = len(teams)
    index = {team: i for i, team in enumerate(teams)}
    home = hist["home"].map(index).to_numpy(int)
    away = hist["away"].map(index).to_numpy(int)
    xgh, xga = (hist[col].to_numpy(float) for col in XG_COLUMNS)
    mh = max(float(np.average(xgh, weights=weights)), 1e-6)
    ma = max(float(np.average(xga, weights=weights)), 1e-6)
    initial = np.concatenate((np.zeros(n), np.full(n, np.clip(np.log(ma), -4, 4)),
                              [np.clip(np.log(mh / ma), -2, 2)]))
    result = minimize(_poisson_loss, initial, args=(home, away, xgh, xga, weights), jac=True,
                      method="L-BFGS-B", bounds=[(-4.0, 4.0)] * (2 * n) + [(-2.0, 2.0)],
                      options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-7, "maxls": 40})
    if not result.success or not np.isfinite(result.fun) or not np.isfinite(result.x).all():
        raise ValueError(f"fit xG non convergente: {result.message}")
    attack = result.x[:n] - result.x[:n].mean()
    params = {f"attack_{team}": float(attack[i]) for i, team in enumerate(teams)}
    params.update({f"defence_{team}": float(result.x[n + i]) for i, team in enumerate(teams)})
    params.update(home_advantage=float(result.x[-1]), rho=float(rho))
    return _Parameters(params, int(result.nit), float(result.fun))


class XGDixonColesModel(DixonColesModel):
    """Interfaccia DC invariata, λ quasi-Poisson xG e ρ del DC sugli stessi gol passati."""

    uses_xg: bool = False

    def fit(self, hist: pd.DataFrame, as_of: datetime | None = None) -> XGDixonColesModel:
        self.uses_xg = False
        df = hist.copy()
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")
        if df["date"].isna().any():
            raise ValueError("xG: date mancanti")
        if as_of is not None:
            df = df[df["date"] < pd.to_datetime(as_of, utc=True)]
        if df.empty:
            raise ValueError("xG: storico vuoto prima del cutoff")
        leagues = set(df["league_key"].dropna()) if "league_key" in df else set()
        if len(leagues) > 1:
            raise ValueError("xG: il fit deve riguardare un solo campionato")
        fallback = bool(leagues) and leagues <= FALLBACK_LEAGUES
        if fallback:
            if any(c in df and df[c].notna().any() for c in XG_COLUMNS):
                raise ValueError("xG inattesi in una lega dichiarata fallback dal protocollo")
        else:
            if not set(XG_COLUMNS) <= set(df):
                raise ValueError("xG: mancano le colonne home_xg/away_xg")
            values = df[XG_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(float, na_value=np.nan)
            if not np.isfinite(values).all() or (values < 0).any():
                raise ValueError("xG mancanti, non finiti o negativi: nessun fallback sui gol")
        goals = df[["home_goals", "away_goals"]].to_numpy(float, na_value=np.nan)
        if not np.isfinite(goals).all() or (goals < 0).any() or not np.equal(goals, np.round(goals)).all():
            raise ValueError("xG: servono gol osservati interi e non negativi")
        # Questi gol reali, non gli xG, entrano nel DC. Esattamente lo stesso prefisso
        # e lo stesso ρ del riferimento; nei due fallback il modello resta identico.
        super().fit(df)
        if fallback:
            return self
        rho = float(self.model.get_params()["rho"])
        weights = np.asarray(pb.models.dixon_coles_weights(df["date"].dt.tz_localize(None),
                                                          xi=self.xi), dtype=float)
        self.model = fit_fractional_poisson(df, weights, rho)
        self.uses_xg = True
        return self
