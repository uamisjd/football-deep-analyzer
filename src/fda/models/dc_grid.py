"""Griglia Dixon-Coles condivisa: un'unica implementazione del τ, per modelli e sito.

Perché esiste questo modulo (verifica del 2026-09-12, precisione di macchina):

penaltyblog calcola la matrice dei risultati in **due** modi e i due non coincidono.

* ``DixonColesGoalModel.predict`` (quello che genera le probabilità pubblicate) applica il
  τ di Dixon & Coles (1997, eq. 2.3) con λ = gol attesi casa e μ = gol attesi trasferta::

      τ(0,0) = 1 − λμρ      τ(0,1) = 1 + λρ      τ(1,0) = 1 + μρ      τ(1,1) = 1 − ρ

  cioè il fattore ``1 + λρ`` sta sulla cella 0-1 (casa a zero, trasferta a uno).
* ``penaltyblog.models.create_dixon_coles_grid`` applica gli stessi fattori **a celle
  invertite** (``grid[1,0] *= 1 + rho*home_lambda`` e ``grid[0,1] *= 1 + rho*away_lambda``).

Su un fit sintetico (12 squadre, 264 partite) le due griglie divergono fino a 1,6e-2 su una
singola cella e di ~1,3 punti percentuali sull'1X2 (52,8% contro 54,1%); la ricostruzione qui
sotto riproduce ``model.predict`` a 2,8e-17. Usare l'una per le probabilità e l'altra per la
matrice mostrata sul sito produce pagine incoerenti con se stesse: da qui il modulo unico.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import poisson

# Le λ nulle o negative (partita chiusa, tempo residuo zero) diventano ~0: la Poisson resta
# definita e la matrice resta valida, invece di sollevare come fa l'helper di penaltyblog.
MIN_LAMBDA = 1e-9


def clamp_rho(lh: float, la: float, rho: float) -> float:
    """ρ ammissibile perché ogni τ resti ≥ 0: max(−1/λ, −1/μ) ≤ ρ ≤ min(1, 1/(λμ))."""
    lh, la = max(float(lh), MIN_LAMBDA), max(float(la), MIN_LAMBDA)
    lo = max(-1.0 / lh, -1.0 / la)
    hi = min(1.0, 1.0 / (lh * la))
    return float(min(max(float(rho), lo), hi))


def tau_grid(lh: float, la: float, rho: float = 0.0, size: int = 12) -> np.ndarray:
    """P(casa = i, trasferta = j) per i, j < ``size``, Dixon-Coles, troncata e rinormalizzata.

    ``size`` è il lato della matrice (gol da 0 a ``size`` − 1). Stessa convenzione di
    ``DixonColesGoalModel.predict(max_goals=size)``; si noti che l'helper
    ``create_dixon_coles_grid(max_goals=n)`` di penaltyblog produce invece n+1 righe.
    """
    lh = max(float(lh), MIN_LAMBDA)
    la = max(float(la), MIN_LAMBDA)
    rho = clamp_rho(lh, la, float(rho or 0.0))
    i = np.arange(max(int(size), 1))
    grid = np.outer(poisson.pmf(i, lh), poisson.pmf(i, la))
    grid[0, 0] *= 1.0 - lh * la * rho
    if size >= 2:
        grid[0, 1] *= 1.0 + lh * rho     # casa 0, trasferta 1 → 1 + λρ
        grid[1, 0] *= 1.0 + la * rho     # casa 1, trasferta 0 → 1 + μρ
        grid[1, 1] *= 1.0 - rho
    grid = np.maximum(grid, 0.0)
    total = float(grid.sum())
    if total > 0:
        grid /= total
    return grid


def probability_grid(lh: float, la: float, rho: float = 0.0, size: int = 11) -> Any:
    """``FootballProbabilityGrid`` di penaltyblog costruita sulla griglia τ corretta.

    Sostituisce ``penaltyblog.models.create_dixon_coles_grid`` nei mercati (1X2, Over/Under,
    BTTS, risultati esatti) così che derivino dalla stessa matrice del modello addestrato.
    """
    import penaltyblog as pb

    lh_eff = max(float(lh), MIN_LAMBDA)
    la_eff = max(float(la), MIN_LAMBDA)
    return pb.models.FootballProbabilityGrid(
        goal_matrix=tau_grid(lh_eff, la_eff, rho, size=size),
        home_goal_expectation=lh_eff,
        away_goal_expectation=la_eff,
        normalize=True,
    )
