"""Calibrazione fuori campione della griglia: scala delle λ e correzione di ρ.

Perché esiste (misure del 2026-09-13 su ``data/processed/backtest.parquet``, 5.791 gare
**fuori campione** prodotte da ``fda backtest``, 7 leghe, 2024-01 → 2026-09)::

    gol totali: λ pubblicate 3,107 contro 2,862 osservati   → bias +8,6%
    pareggio:   previsto 23,9% contro 25,6% osservato        → sottostima di 1,7 punti
    Over 2,5:   previsto 59,0% contro 54,8% osservato        → Brier 0,2432 (base 0,2477)
    BTTS:       previsto 59,1% contro 55,0% osservato        → Brier peggiore della base

Il bias è presente in **tutte e 7 le leghe** (+0,16 … +0,36 gol) e in tutti i semestri del
campione: non è un periodo sfortunato. La causa strutturale è nota e riproducibile:
``ensemble()`` ricava le λ dalla media pesata 1X2 con ``penaltyblog.goal_expectancy``, che
inverte un vettore appiattito dall'Elo in λ più alte di quelle stimate dal Dixon-Coles
(misurato su storico reale: +15% ITA1, +20% ENG1, +17% ESP1). Poiché in un modello di gol
il pareggio perde massa al crescere di λ, lo stesso errore spiega entrambe le distorsioni.

L'intervento è deliberatamente **minimo e coerente**: due parametri applicati alla griglia
(moltiplicatore delle λ e spostamento di ρ), così *tutto* ciò che il sito mostra — 1X2,
matrice, risultati esatti, Over/Under, BTTS, porte inviolate e λ — continua a derivare da
una sola matrice di probabilità. Nessuna probabilità viene "aggiustata" a valle in modo
incoerente con la matrice.

Onestà sul guadagno (walk-forward: i parametri sono scelti solo sulle fold precedenti e
valutati sulla successiva, 4.825 gare tenute fuori)::

    RPS 1X2         0,2006 → 0,2007 (+0,0001, entro il rumore)
    log-loss        0,9896 → 0,9893 (−0,0003)
    Brier 6 mercati 0,2065 → 0,2055 (−0,0010)
    bias λ          +8,6%  → +2,0%
    pareggio        23,9%  → 25,7% contro 25,6% osservato

La calibrazione **non** migliora l'1X2 in modo significativo: su questo insieme di
informazioni l'RPS è vicino al pavimento raggiungibile (0,199 contro ~0,19-0,20 dei
riferimenti pubblicati). Serve a rimuovere una distorsione visibile e a rendere i mercati
sui gol migliori della frequenza di base. I guadagni veri sull'1X2 richiedono informazioni
nuove (xG storici, distinte, riposo): vedi ``docs/13_modelli_e_schede_piano_2026-09-13.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from .dc_grid import MIN_LAMBDA, clamp_rho_many, grid_markets_many, tau_grid_many

log = logging.getLogger(__name__)

#: griglia di ricerca del moltiplicatore delle λ (1,00 = nessuna correzione)
LAMBDA_SCALE_GRID: tuple[float, ...] = tuple(round(float(x), 3) for x in np.arange(0.90, 1.031, 0.02))
#: griglia di ricerca dello spostamento di ρ (0,00 = ρ stimata dal modello)
RHO_SHIFT_GRID: tuple[float, ...] = (-0.06, -0.04, -0.02, 0.0, 0.02)
#: sotto questa numerosità la calibrazione resta identica: troppo poche gare per stimare
MIN_ROWS = 1200
#: fold cronologiche per la validazione walk-forward (nessuna scelta guarda il futuro)
FOLDS = 6
#: peso del Brier dei mercati sui gol nell'obiettivo (l'RPS resta il termine principale)
BRIER_WEIGHT = 0.5
#: mercati binari valutati, nella stessa definizione di ``fda.models.backtest``
MARKET_KEYS: tuple[str, ...] = ("p_over15", "p_over25", "p_over35", "p_btts",
                                "p_home_clean_sheet", "p_away_clean_sheet")
GRID_SIZE = 11
CALIBRATION_VERSION = "grid-cal-1.0"


@dataclass(frozen=True)
class Calibration:
    """Due parametri + la traccia di come sono stati scelti (per auditarli in ogni momento)."""

    lambda_scale: float = 1.0
    rho_shift: float = 0.0
    n_fit: int = 0
    folds: int = FOLDS
    fitted_at: datetime | None = None
    corpus: str = ""
    version: str = CALIBRATION_VERSION
    #: metriche walk-forward (guadagno onesto) e sul campione pieno (solo descrittivo)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def is_identity(self) -> bool:
        return abs(self.lambda_scale - 1.0) < 1e-9 and abs(self.rho_shift) < 1e-9

    def apply(self, lambda_home: float, lambda_away: float, rho: float | None) -> tuple[float, float, float]:
        """λ e ρ corrette; ρ resta nei bound matematici del τ (mai una griglia negativa)."""
        lh = max(float(lambda_home) * float(self.lambda_scale), MIN_LAMBDA)
        la = max(float(lambda_away) * float(self.lambda_scale), MIN_LAMBDA)
        r = float(clamp_rho_many(lh, la, float(rho or 0.0) + float(self.rho_shift)))
        return lh, la, r

    def apply_many(self, lh: np.ndarray, la: np.ndarray,
                   rho: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """:meth:`apply` vettorizzata: identica, ma per migliaia di gare in un colpo solo."""
        lh2 = np.maximum(np.asarray(lh, dtype=float) * float(self.lambda_scale), MIN_LAMBDA)
        la2 = np.maximum(np.asarray(la, dtype=float) * float(self.lambda_scale), MIN_LAMBDA)
        rho2 = clamp_rho_many(lh2, la2, np.nan_to_num(np.asarray(rho, dtype=float)) + float(self.rho_shift))
        return lh2, la2, rho2

    def as_row(self) -> dict[str, Any]:
        """Riga piatta per lo store (una sola riga attiva, versione inclusa)."""
        flat: dict[str, Any] = {"lambda_scale": round(self.lambda_scale, 4),
                                "rho_shift": round(self.rho_shift, 4),
                                "n_fit": int(self.n_fit), "folds": int(self.folds),
                                "fitted_at": self.fitted_at, "corpus": self.corpus,
                                "version": self.version}
        flat.update({f"m_{k}": round(float(v), 6) for k, v in self.metrics.items()})
        return flat


def _targets(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Esito 1X2 (0/1/2) e matrice binaria dei sei mercati, nella definizione del backtest."""
    hg = pd.to_numeric(df["home_goals"], errors="coerce").to_numpy(float)
    ag = pd.to_numeric(df["away_goals"], errors="coerce").to_numpy(float)
    total = hg + ag
    outcome = np.where(hg > ag, 0, np.where(hg == ag, 1, 2)).astype(int)
    flags = np.column_stack([total > 1.5, total > 2.5, total > 3.5, (hg > 0) & (ag > 0),
                             ag == 0, hg == 0]).astype(float)
    return outcome, flags


def _scores(lh: np.ndarray, la: np.ndarray, rho: np.ndarray, outcome: np.ndarray,
            flags: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RPS per gara, Brier 1X2 per gara e Brier medio dei sei mercati per gara."""
    grids = tau_grid_many(lh, la, rho, size=GRID_SIZE)
    m = grid_markets_many(grids)
    probs = np.column_stack([m["p_home"], m["p_draw"], m["p_away"]])
    onehot = np.eye(3)[outcome]
    rps_rows = ((probs.cumsum(1) - onehot.cumsum(1)) ** 2).sum(1) / 2.0
    brier_1x2 = ((probs - onehot) ** 2).sum(1)
    predicted = np.column_stack([m[k] for k in MARKET_KEYS])
    brier_markets = ((predicted - flags) ** 2).mean(1)
    return rps_rows, brier_1x2, brier_markets


def evaluate(df: pd.DataFrame, cal: Calibration | None = None) -> dict[str, float]:
    """Metriche pubblicate (RPS, log-loss, Brier, bias λ, pareggio) con una data calibrazione."""
    cal = cal or Calibration()
    df = df.dropna(subset=["lambda_home", "lambda_away", "home_goals", "away_goals"])
    if df.empty:
        return {}
    lh = pd.to_numeric(df["lambda_home"], errors="coerce").to_numpy(float)
    la = pd.to_numeric(df["lambda_away"], errors="coerce").to_numpy(float)
    rho = (pd.to_numeric(df["dc_rho"], errors="coerce").to_numpy(float)
           if "dc_rho" in df.columns else np.zeros(len(df)))
    rho = np.nan_to_num(rho, nan=0.0)
    lh2, la2, rho2 = cal.apply_many(lh, la, rho)
    outcome, flags = _targets(df)
    rps_rows, brier_1x2, brier_markets = _scores(lh2, la2, rho2, outcome, flags)
    grids = tau_grid_many(lh2, la2, rho2, size=GRID_SIZE)
    m = grid_markets_many(grids)
    probs = np.column_stack([m["p_home"], m["p_draw"], m["p_away"]])
    hit = float((probs.argmax(1) == outcome).mean())
    ll = float(-np.log(np.clip(probs[np.arange(len(probs)), outcome], 1e-12, 1.0)).mean())
    goals = (pd.to_numeric(df["home_goals"], errors="coerce").to_numpy(float)
             + pd.to_numeric(df["away_goals"], errors="coerce").to_numpy(float))
    out = {
        "n": float(len(df)), "rps": float(rps_rows.mean()), "logloss": ll, "brier_1x2": float(brier_1x2.mean()),
        "brier_mercati": float(brier_markets.mean()), "hit": hit,
        "lambda_media": float(m["lambda_total"].mean()), "gol_osservati": float(goals.mean()),
        "bias_lambda": float(m["lambda_total"].mean() - goals.mean()),
        "pareggio_previsto": float(m["p_draw"].mean()), "pareggio_osservato": float((outcome == 1).mean()),
        "over25_previsto": float(m["p_over25"].mean()),
        "over25_osservato": float(flags[:, 1].mean()),
        "obiettivo": float(rps_rows.mean() + BRIER_WEIGHT * brier_markets.mean()),
    }
    for i, key in enumerate(MARKET_KEYS):
        out[f"brier_{key}"] = float(((m[key] - flags[:, i]) ** 2).mean())
    return out


def _best_params(lh: np.ndarray, la: np.ndarray, rho: np.ndarray, outcome: np.ndarray,
                 flags: np.ndarray) -> tuple[float, float]:
    """(moltiplicatore λ, shift ρ) che minimizza RPS + ``BRIER_WEIGHT`` · Brier mercati."""
    best: tuple[float, float, float] | None = None
    for scale in LAMBDA_SCALE_GRID:
        for shift in RHO_SHIFT_GRID:
            s_lh, s_la, s_rho = Calibration(scale, shift).apply_many(lh, la, rho)
            rps_rows, _, brier_markets = _scores(s_lh, s_la, s_rho, outcome, flags)
            obj = float(rps_rows.mean() + BRIER_WEIGHT * brier_markets.mean())
            if best is None or obj < best[0]:
                best = (obj, scale, shift)
    assert best is not None
    return best[1], best[2]


def fit(df: pd.DataFrame, folds: int = FOLDS, min_rows: int = MIN_ROWS) -> Calibration:
    """Stima i due parametri e misura il guadagno **senza mai guardare il futuro**.

    1. walk-forward su ``folds`` finestre cronologiche: i parametri sono scelti sulle
       finestre 1..k e valutati sulla k+1 → il guadagno riportato è fuori campione;
    2. i parametri pubblicati sono quelli ottimi sull'intero campione (che è già tutto
       passato: le previsioni a cui verranno applicati sono gare non ancora giocate).
    Con meno di ``min_rows`` gare la calibrazione resta identica e lo dichiara.
    """
    df = df.dropna(subset=["lambda_home", "lambda_away", "home_goals", "away_goals"]).copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    if n < min_rows:
        log.info("calibrazione saltata: %d gare (minimo %d)", n, min_rows)
        return Calibration(n_fit=n, corpus=f"{n} gare (sotto la soglia di {min_rows})")

    lh = pd.to_numeric(df["lambda_home"], errors="coerce").to_numpy(float)
    la = pd.to_numeric(df["lambda_away"], errors="coerce").to_numpy(float)
    rho = np.zeros(n)
    if "dc_rho" in df.columns:
        rho = np.nan_to_num(pd.to_numeric(df["dc_rho"], errors="coerce").to_numpy(float), nan=0.0)
    outcome, flags = _targets(df)

    parts = [np.asarray(x) for x in np.array_split(np.arange(n), max(int(folds), 2))]
    held_rps: list[np.ndarray] = []
    held_brier: list[np.ndarray] = []
    held_base_rps: list[np.ndarray] = []
    held_base_brier: list[np.ndarray] = []
    chosen: list[tuple[float, float]] = []
    for k in range(1, len(parts)):
        train = np.concatenate(parts[:k])
        test = parts[k]
        scale, shift = _best_params(lh[train], la[train], rho[train], outcome[train], flags[train])
        chosen.append((scale, shift))
        cal = Calibration(scale, shift)
        s_lh, s_la, s_rho = cal.apply_many(lh[test], la[test], rho[test])
        r, _, bm = _scores(s_lh, s_la, s_rho, outcome[test], flags[test])
        r0, _, bm0 = _scores(lh[test], la[test], rho[test], outcome[test], flags[test])
        held_rps.append(r)
        held_brier.append(bm)
        held_base_rps.append(r0)
        held_base_brier.append(bm0)

    scale_full, shift_full = _best_params(lh, la, rho, outcome, flags)
    before = evaluate(df, Calibration())
    holdout_rps = float(np.concatenate(held_rps).mean())
    holdout_rps_base = float(np.concatenate(held_base_rps).mean())
    holdout_brier = float(np.concatenate(held_brier).mean())
    holdout_brier_base = float(np.concatenate(held_base_brier).mean())
    metrics = {
        "holdout_n": float(int(sum(len(x) for x in held_rps))),
        "holdout_rps_prima": holdout_rps_base, "holdout_rps_dopo": holdout_rps,
        "holdout_rps_delta": holdout_rps - holdout_rps_base,
        "holdout_brier_prima": holdout_brier_base, "holdout_brier_dopo": holdout_brier,
        "holdout_brier_delta": holdout_brier - holdout_brier_base,
        "scale_scelti_min": float(min(s for s, _ in chosen)), "scale_scelti_max": float(max(s for s, _ in chosen)),
    }
    metrics.update({f"campione_{k}": v for k, v in before.items()})
    after = evaluate(df, Calibration(scale_full, shift_full))
    metrics.update({f"dopo_{k}": v for k, v in after.items()})
    span = ""
    if "date" in df.columns and pd.api.types.is_datetime64_any_dtype(df["date"]):
        span = f"{df['date'].min():%Y-%m-%d}→{df['date'].max():%Y-%m-%d}"
    corpus = f"{n} gare fuori campione {span}".strip()
    cal = Calibration(lambda_scale=scale_full, rho_shift=shift_full, n_fit=n, folds=len(parts),
                      fitted_at=datetime.now(timezone.utc), corpus=corpus, metrics=metrics)
    log.info("calibrazione: λ×%.2f ρ%+.2f su %d gare — Brier mercati holdout %.4f → %.4f (%+.4f), "
             "RPS %.4f → %.4f (%+.4f)", scale_full, shift_full, n,
             holdout_brier_base, holdout_brier, holdout_brier - holdout_brier_base,
             holdout_rps_base, holdout_rps, holdout_rps - holdout_rps_base)
    return cal


def from_store(store: Any) -> Calibration:
    """Rilegge l'ultima calibrazione salvata; se manca o è illeggibile → identica."""
    try:
        df = store.read("calibration")
    except Exception as exc:                                   # tabella assente/corrotta
        log.warning("calibrazione non letta (%s): uso identità", exc)
        return Calibration()
    if df.empty:
        return Calibration()
    if "fitted_at" in df.columns and not df.empty:
        df = df.sort_values("fitted_at")
    row = df.iloc[-1]
    try:
        metrics = {str(k)[2:]: float(v) for k, v in row.items()
                   if str(k).startswith("m_") and pd.notna(v)}
        return Calibration(lambda_scale=float(row.get("lambda_scale", 1.0) or 1.0),
                           rho_shift=float(row.get("rho_shift", 0.0) or 0.0),
                           n_fit=int(row.get("n_fit", 0) or 0),
                           folds=int(row.get("folds", FOLDS) or FOLDS),
                           fitted_at=(row["fitted_at"].to_pydatetime()
                                      if pd.notna(row.get("fitted_at")) else None),
                           corpus=str(row.get("corpus", "") or ""),
                           version=str(row.get("version", CALIBRATION_VERSION) or CALIBRATION_VERSION),
                           metrics=metrics)
    except Exception as exc:                                   # una riga malformata non blocca i modelli
        log.warning("calibrazione ignorata (%s): uso identità", exc)
        return Calibration()


__all__ = ["BRIER_WEIGHT", "CALIBRATION_VERSION", "Calibration", "FOLDS", "LAMBDA_SCALE_GRID",
           "MARKET_KEYS", "MIN_ROWS", "RHO_SHIFT_GRID", "evaluate", "fit", "from_store"]
