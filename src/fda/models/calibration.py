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

from .dc_grid import GRID_SIZE, MIN_LAMBDA, clamp_rho_many, grid_markets_many, tau_grid_many

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
CALIBRATION_VERSION = "cal-momenti-1.1"
#: finestra usata per stimare i parametri: il bias delle λ **non è stazionario** (misure
#: 2026-09-13 su backtest.parquet: m necessario 0,963 nel 2024H1, 0,881 nel 2025H1,
#: 0,902 nel 2026H1) quindi si stima sul regime più vicino a quello corrente.
FIT_WINDOW_DAYS = 730
#: limiti di sicurezza del moltiplicatore: una correzione oltre questi valori significa che
#: è cambiato il modello, non che va corretta la griglia (meglio identità + avviso).
SCALE_BOUNDS: tuple[float, float] = (0.85, 1.05)


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
    #: finestre di giorni usate per la stima (None = tutto lo storico disponibile)
    window_days: int | None = None
    #: come è stato scelto il moltiplicatore: "momenti" (media dei gol) o "griglia" (punteggio)
    estimator: str = "momenti"
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
        flat: dict[str, Any] = {"lambda_scale": round(self.lambda_scale, 6),
                                "rho_shift": round(self.rho_shift, 6),
                                "n_fit": int(self.n_fit), "folds": int(self.folds),
                                "fitted_at": self.fitted_at, "corpus": self.corpus,
                                "version": self.version, "estimator": self.estimator,
                                "window_days": self.window_days}
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


def moment_scale(lh: np.ndarray, la: np.ndarray, goals: np.ndarray) -> float:
    """Moltiplicatore che fa riprodurre alla griglia la **media dei gol osservati**.

    Perché non sceglierlo sull'RPS/Brier: misurato in walk-forward su 4.825 gare, il
    punteggio probabilistico è quasi piatto in λ (spostare m da 0,94 a 0,88 cambia l'RPS
    di <0,0003) mentre il bias dei gol attesi cambia di 0,1 gol. Il punteggio quindi
    **non vede** il difetto che la scheda mostra (gol attesi, distribuzione dei gol,
    Over/Under, BTTS). Confronto walk-forward (stesse gare tenute fuori)::

        stimatore            RPS      Brier mercati   bias λ fuori campione
        nessuna correzione   0,20056  0,20646         +0,264
        griglia di punteggio 0,20070  0,20548         +0,128
        momenti, tutto       0,20081  0,20514         +0,056
        momenti, 730 giorni  0,20081  0,20516         +0,053   ← scelto
        momenti, 365 giorni  0,20084  0,20525         +0,030
        momenti, 180 giorni  0,20089  0,20519         +0,024

    Costo: 0,00025 di RPS 1X2 (rumore) per un Brier mercati migliore di 0,0013 e un bias
    dei gol ridotto di un fattore 5. La finestra di 730 giorni è il compromesso fra
    aderenza al regime corrente (il bias non è stazionario) e numerosità della stima.
    """
    pred = float(np.mean(np.asarray(lh, dtype=float) + np.asarray(la, dtype=float)))
    obs = float(np.mean(np.asarray(goals, dtype=float)))
    if not np.isfinite(pred) or pred <= 0 or not np.isfinite(obs):
        return 1.0
    return float(np.clip(obs / pred, *SCALE_BOUNDS))


def _best_shift(lh: np.ndarray, la: np.ndarray, rho: np.ndarray, outcome: np.ndarray,
                flags: np.ndarray, scale: float) -> float:
    """Δρ che minimizza RPS + ``BRIER_WEIGHT`` · Brier mercati, a moltiplicatore fissato."""
    best: tuple[float, float] | None = None
    for shift in RHO_SHIFT_GRID:
        s_lh, s_la, s_rho = Calibration(scale, shift).apply_many(lh, la, rho)
        rps_rows, _, brier_markets = _scores(s_lh, s_la, s_rho, outcome, flags)
        obj = float(rps_rows.mean() + BRIER_WEIGHT * brier_markets.mean())
        if best is None or obj < best[0]:
            best = (obj, shift)
    assert best is not None
    return best[1]


def _estimate(lh: np.ndarray, la: np.ndarray, rho: np.ndarray, goals: np.ndarray,
              outcome: np.ndarray, flags: np.ndarray) -> tuple[float, float]:
    """(moltiplicatore dai momenti, Δρ dal punteggio) su un insieme di gare."""
    scale = moment_scale(lh, la, goals)
    return scale, _best_shift(lh, la, rho, outcome, flags, scale)


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


def fit(df: pd.DataFrame, folds: int = FOLDS, min_rows: int = MIN_ROWS,
        window_days: int | None = FIT_WINDOW_DAYS) -> Calibration:
    """Stima i due parametri e misura il guadagno **senza mai guardare il futuro**.

    1. walk-forward su ``folds`` finestre cronologiche: i parametri sono stimati sulle
       finestre 1..k e valutati sulla k+1 → il guadagno riportato è fuori campione;
    2. i parametri pubblicati sono stimati sulla finestra più recente disponibile
       (``window_days``), che è già tutta passato: le previsioni a cui verranno applicati
       sono gare non ancora giocate;
    3. il moltiplicatore delle λ viene dalla **media dei gol osservati**
       (:func:`moment_scale`), lo spostamento di ρ dal punteggio probabilistico
       (:func:`_best_shift`): vedi i confronti misurati nelle due docstring.
    Con meno di ``min_rows`` gare la calibrazione resta identica e lo dichiara.
    """
    df = df.dropna(subset=["lambda_home", "lambda_away", "home_goals", "away_goals"]).copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    n = len(df)
    if n < min_rows:
        log.info("calibrazione saltata: %d gare (minimo %d)", n, min_rows)
        return Calibration(n_fit=n, corpus=f"{n} gare (sotto la soglia di {min_rows})",
                           window_days=window_days)

    lh = pd.to_numeric(df["lambda_home"], errors="coerce").to_numpy(float)
    la = pd.to_numeric(df["lambda_away"], errors="coerce").to_numpy(float)
    goals = (pd.to_numeric(df["home_goals"], errors="coerce").to_numpy(float)
             + pd.to_numeric(df["away_goals"], errors="coerce").to_numpy(float))
    rho = np.zeros(n)
    if "dc_rho" in df.columns:
        rho = np.nan_to_num(pd.to_numeric(df["dc_rho"], errors="coerce").to_numpy(float), nan=0.0)
    outcome, flags = _targets(df)
    dates = (pd.to_datetime(df["date"]).to_numpy() if "date" in df.columns
             and pd.api.types.is_datetime64_any_dtype(df["date"]) else None)
    min_window = max(min_rows // 3, 200)

    def _window(idx: np.ndarray) -> np.ndarray:
        """Indici usati per la stima: gli ultimi ``window_days`` giorni, se bastano."""
        if dates is None or not window_days or window_days <= 0:
            return idx
        cut = dates[idx].max() - np.timedelta64(int(window_days), "D")
        sub = idx[dates[idx] >= cut]
        return sub if len(sub) >= min_window else idx

    parts = [np.asarray(x) for x in np.array_split(np.arange(n), max(int(folds), 2))]
    held_rps: list[np.ndarray] = []
    held_brier: list[np.ndarray] = []
    held_base_rps: list[np.ndarray] = []
    held_base_brier: list[np.ndarray] = []
    held_bias: list[float] = []
    held_bias_base: list[float] = []
    held_n: list[int] = []
    chosen: list[tuple[float, float]] = []
    for k in range(1, len(parts)):
        train = _window(np.concatenate(parts[:k]))
        test = parts[k]
        scale, shift = _estimate(lh[train], la[train], rho[train], goals[train],
                                 outcome[train], flags[train])
        chosen.append((scale, shift))
        s_lh, s_la, s_rho = Calibration(scale, shift).apply_many(lh[test], la[test], rho[test])
        r, _, bm = _scores(s_lh, s_la, s_rho, outcome[test], flags[test])
        r0, _, bm0 = _scores(lh[test], la[test], rho[test], outcome[test], flags[test])
        held_rps.append(r)
        held_brier.append(bm)
        held_base_rps.append(r0)
        held_base_brier.append(bm0)
        held_bias.append(float((s_lh + s_la).mean() - goals[test].mean()))
        held_bias_base.append(float((lh[test] + la[test]).mean() - goals[test].mean()))
        held_n.append(int(len(test)))

    win = _window(np.arange(n))
    scale_full, shift_full = _estimate(lh[win], la[win], rho[win], goals[win],
                                       outcome[win], flags[win])
    scale_grid, shift_grid = _best_params(lh[win], la[win], rho[win], outcome[win], flags[win])
    before = evaluate(df, Calibration())
    holdout_rps = float(np.concatenate(held_rps).mean())
    holdout_rps_base = float(np.concatenate(held_base_rps).mean())
    holdout_brier = float(np.concatenate(held_brier).mean())
    holdout_brier_base = float(np.concatenate(held_base_brier).mean())
    metrics = {
        "holdout_n": float(int(sum(held_n))),
        "holdout_rps_prima": holdout_rps_base, "holdout_rps_dopo": holdout_rps,
        "holdout_rps_delta": holdout_rps - holdout_rps_base,
        "holdout_brier_prima": holdout_brier_base, "holdout_brier_dopo": holdout_brier,
        "holdout_brier_delta": holdout_brier - holdout_brier_base,
        "holdout_bias_lambda_prima": float(np.average(held_bias_base, weights=held_n)),
        "holdout_bias_lambda_dopo": float(np.average(held_bias, weights=held_n)),
        "stima_n": float(len(win)),
        "campione_n": float(n),
        "stima_window_days": float(window_days or 0),
        "scale_scelti_min": float(min(s for s, _ in chosen)), "scale_scelti_max": float(max(s for s, _ in chosen)),
        "confronto_scale_griglia": float(scale_grid), "confronto_shift_griglia": float(shift_grid),
    }
    metrics.update({f"campione_{k}": v for k, v in before.items()})
    after = evaluate(df, Calibration(scale_full, shift_full))
    metrics.update({f"dopo_{k}": v for k, v in after.items()})
    span = ""
    if dates is not None:
        span = f"{df['date'].min():%Y-%m-%d}→{df['date'].max():%Y-%m-%d}"
    corpus = (f"{n} gare fuori campione {span} · parametri stimati su {len(win)} gare"
              f"{f' degli ultimi {window_days} giorni' if window_days else ''}").strip()
    if "model_version" in df.columns:
        # le righe del backtest dichiarano la versione del modello: una correzione stimata su
        # un misto di versioni vale meno, e va detto invece di nasconderlo nel log
        mix = df["model_version"].astype(str).value_counts()
        corpus += " · versioni modello: " + ", ".join(f"{k} ({v} gare)" for k, v in mix.items())
        if len(mix) > 1:
            log.warning("calibrazione stimata su un misto di versioni del modello: %s",
                        dict(mix.items()))
    # n_fit = gare su cui i parametri sono stati **stimati** (la finestra), non il campione intero:
    # è il numero che la scheda dichiara («stimata su N gare fuori campione») e dichiarare 5.791
    # quando la stima ne usa 4.743 sarebbe una precisione falsa. Il campione resta nel corpus.
    cal = Calibration(lambda_scale=scale_full, rho_shift=shift_full, n_fit=len(win), folds=len(parts),
                      fitted_at=datetime.now(timezone.utc), corpus=corpus,
                      window_days=window_days, estimator="momenti", metrics=metrics)
    log.info("calibrazione: λ×%.3f ρ%+.2f (momenti su %d gare) — Brier mercati holdout %.4f → %.4f "
             "(%+.4f), RPS %.4f → %.4f (%+.4f), bias λ holdout %+.3f → %+.3f",
             scale_full, shift_full, len(win), holdout_brier_base, holdout_brier,
             holdout_brier - holdout_brier_base, holdout_rps_base, holdout_rps,
             holdout_rps - holdout_rps_base, metrics["holdout_bias_lambda_prima"],
             metrics["holdout_bias_lambda_dopo"])
    if abs(after["bias_lambda"]) > 0.10:
        log.warning("bias dei gol ancora %+0.3f dopo la calibrazione: il regime è cambiato "
                    "oppure è cambiato il modello (versione corrente %s)",
                    after["bias_lambda"], df["model_version"].iloc[-1] if "model_version" in df.columns else "?")
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
                           window_days=(int(row["window_days"]) if pd.notna(row.get("window_days"))
                                        else None),
                           estimator=str(row.get("estimator", "momenti") or "momenti"),
                           metrics=metrics)
    except Exception as exc:                                   # una riga malformata non blocca i modelli
        log.warning("calibrazione ignorata (%s): uso identità", exc)
        return Calibration()


__all__ = ["BRIER_WEIGHT", "CALIBRATION_VERSION", "Calibration",
           "FIT_WINDOW_DAYS", "FOLDS", "LAMBDA_SCALE_GRID", "MARKET_KEYS", "MIN_ROWS",
           "RHO_SHIFT_GRID", "SCALE_BOUNDS", "evaluate", "fit", "from_store", "moment_scale"]
