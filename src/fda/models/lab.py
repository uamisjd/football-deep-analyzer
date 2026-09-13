"""Laboratorio modelli: confronto **fuori campione** di famiglie, iperparametri e miscele.

Serve alla regola B8 di ``docs/00_regole_di_lavoro.md`` («prima si dimostra, poi si
integra»): nessuna variante entra in produzione perché "sembra migliore", ma solo se
batte il modello corrente sullo stesso identico insieme di gare, con metriche proprie
(RPS, log-loss, Brier) e con un intervallo di confidenza sulla differenza.

Come funziona
-------------
1. lo storico di ogni lega viene diviso in finestre cronologiche (``step_days``);
2. per ogni finestra ogni candidato è addestrato **solo** sulle gare precedenti e valuta
   quelle successive (nessuna informazione futura entra nel fit);
3. ogni candidato produce, per ogni gara, il vettore 1X2 e — quando la famiglia lo
   consente — λ e i mercati sui gol, tutti derivati dalla sua matrice dei punteggi;
4. :func:`summarize` confronta i candidati a coppie sulle stesse gare con un bootstrap
   appaiato (95%) e con la quota di gare in cui il candidato è migliore del riferimento.

Costo: ogni candidato richiede un fit per finestra. Per questo il laboratorio **non** gira
nel ``daily`` (che deve restare entro i 40 minuti) ma in un workflow dedicato/on demand,
con ``--step-days`` e ``--candidates`` per ridurre il perimetro.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .calibration import SCALE_BOUNDS, Calibration
from .dc_grid import GRID_SIZE, grid_markets_many, tau_grid, tau_grid_many
from .predict import DixonColesModel, EloModel, _clamp_lambda, ensemble

log = logging.getLogger("fda.lab")

#: gare minime già valutate da un candidato prima di applicargli la correzione del livello dei gol
MIN_SELF_CAL = 100
BASELINE = "dc_elo_prod"

#: famiglie di verosimiglianza disponibili in penaltyblog (stessa API: fit + predict → griglia)
GOAL_FAMILIES: dict[str, str] = {
    "poisson": "PoissonGoalsModel",
    "dixon_coles": "DixonColesGoalModel",
    "bivariate_poisson": "BivariatePoissonGoalModel",
    "negative_binomial": "NegativeBinomialGoalModel",
    "zero_inflated": "ZeroInflatedPoissonGoalsModel",
    "weibull_copula": "WeibullCopulaGoalsModel",
}


@dataclass(frozen=True)
class Candidate:
    """Un concorrente del laboratorio: famiglia, iperparametri e, per le miscele, il peso."""

    key: str
    label: str
    kind: str                                    # goals | rating | blend | production
    family: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def xi(self) -> float:
        return float(self.params.get("xi", 0.0018))


#: insieme predefinito: il modello in produzione, i suoi iperparametri critici, le famiglie
#: di verosimiglianza alternative e i sistemi di rating puri.
CANDIDATES: tuple[Candidate, ...] = (
    Candidate(BASELINE, "DC+Elo in produzione (w 0,7)", "production", "dixon_coles",
              {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.7}),
    Candidate("dc_puro", "Dixon-Coles senza Elo", "goals", "dixon_coles", {"xi": 0.0018, "shrink": 8.0}),
    Candidate("dc_xi10", "Dixon-Coles ξ 0,0010 (memoria lunga)", "goals", "dixon_coles",
              {"xi": 0.0010, "shrink": 8.0}),
    Candidate("dc_xi30", "Dixon-Coles ξ 0,0030 (memoria corta)", "goals", "dixon_coles",
              {"xi": 0.0030, "shrink": 8.0}),
    Candidate("dc_no_shrink", "Dixon-Coles senza shrinkage", "goals", "dixon_coles",
              {"xi": 0.0018, "shrink": 0.0}),
    Candidate("dc_shrink16", "Dixon-Coles shrinkage 16", "goals", "dixon_coles",
              {"xi": 0.0018, "shrink": 16.0}),
    Candidate("poisson", "Poisson indipendente", "goals", "poisson"),
    Candidate("biv_poisson", "Poisson bivariata", "goals", "bivariate_poisson"),
    Candidate("neg_binomial", "Binomiale negativa", "goals", "negative_binomial"),
    Candidate("zero_inflated", "Poisson zero-inflazionata", "goals", "zero_inflated"),
    Candidate("weibull_copula", "Weibull + copula", "goals", "weibull_copula"),
    Candidate("elo", "Elo puro (k 20, HFA 60)", "rating", "elo"),
    Candidate("pi_ratings", "Pi-ratings (Constantinou-Fenton)", "rating", "pi"),
    Candidate("mix_50", "Miscela di griglie DC+Elo 50/50", "blend", "dixon_coles",
              {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.5}),
    Candidate("mix_85", "Miscela di griglie DC+Elo 85/15", "blend", "dixon_coles",
              {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.85}),
    # alternativa strutturale alla ricetta di produzione: l'Elo inclina solo il rapporto
    # casa/trasferta, il totale dei gol attesi resta quello del modello sui gol (vedi _tilt_grid)
    Candidate("dc_elo_tilt", "DC+Elo a gol attesi invariati (solo inclinazione)", "blend", "dixon_coles",
              {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.7, "mode": "tilt"}),
    # il peso della media pesata in produzione (0,7) non è mai stato misurato: ecco 0,5 e 0,85
    Candidate("prod_w50", "Produzione con peso DC 0,50", "production", "dixon_coles",
              {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.5}),
    Candidate("prod_w85", "Produzione con peso DC 0,85", "production", "dixon_coles",
              {"xi": 0.0018, "shrink": 8.0, "w_dc": 0.85}),
    # iperparametri Elo: k e vantaggio del campo sono quelli di default di penaltyblog, mai tarati
    Candidate("elo_k10", "Elo k 10 (rating lenti)", "rating", "elo", {"k": 10.0, "hfa": 60.0}),
    Candidate("elo_k40", "Elo k 40 (rating reattivi)", "rating", "elo", {"k": 40.0, "hfa": 60.0}),
    Candidate("elo_hfa40", "Elo vantaggio casa 40", "rating", "elo", {"k": 20.0, "hfa": 40.0}),
    Candidate("elo_hfa80", "Elo vantaggio casa 80", "rating", "elo", {"k": 20.0, "hfa": 80.0}),
)


# --------------------------------------------------------------------------- modelli addestrati
class _FittedGoals:
    """Modello sui gol addestrato: espone λ, ρ (se c'è) e la matrice dei punteggi."""

    def __init__(self, model: Any, family: str, teams: set[str], params: dict[str, float]) -> None:
        self.model = model
        self.family = family
        self.teams = teams
        self.params = params

    def grid(self, home: str, away: str) -> np.ndarray:
        g = self.model.predict(home, away, max_goals=GRID_SIZE - 1, normalize=True)
        return np.asarray(g.grid, dtype=float)[:GRID_SIZE, :GRID_SIZE]

    def knows(self, home: str, away: str) -> bool:
        return home in self.teams and away in self.teams


def fit_goals(hist: pd.DataFrame, cand: Candidate) -> _FittedGoals | DixonColesModel | None:
    """Addestra la famiglia richiesta; ``None`` se lo storico è insufficiente."""
    import penaltyblog as pb

    if cand.family == "dixon_coles":
        return DixonColesModel(xi=cand.xi, shrink_prior=float(cand.params.get("shrink", 8.0))).fit(hist)
    cls_name = GOAL_FAMILIES.get(cand.family)
    if cls_name is None:
        raise ValueError(f"famiglia sconosciuta: {cand.family}")
    dates = pd.to_datetime(hist["date"])
    weights = np.asarray(pb.models.dixon_coles_weights(
        dates.dt.tz_localize(None) if dates.dt.tz is not None else dates, xi=cand.xi), dtype=float)
    model = getattr(pb.models, cls_name)(
        hist["home_goals"].to_numpy(dtype=float).copy(), hist["away_goals"].to_numpy(dtype=float).copy(),
        hist["home"].to_numpy().copy(), hist["away"].to_numpy().copy(), weights=weights.copy())
    model.fit()
    teams = set(hist["home"]) | set(hist["away"])
    return _FittedGoals(model, cand.family, teams, {str(k): float(v) for k, v in model.get_params().items()})


class _PiRatings:
    """Pi-ratings di penaltyblog: aggiornati con la differenza reti osservata."""

    def __init__(self, hist: pd.DataFrame, **kwargs: Any) -> None:
        import penaltyblog as pb

        self.system = pb.ratings.PiRatingSystem(**kwargs)
        df = hist.dropna(subset=["home_goals", "away_goals"]).sort_values("date")
        self.teams: set[str] = set()
        for r in df.itertuples(index=False):
            self.system.update_ratings(r.home, r.away, int(r.home_goals - r.away_goals))
            self.teams.update((r.home, r.away))

    def probabilities(self, home: str, away: str) -> tuple[float, float, float]:
        p = self.system.calculate_match_probabilities(home, away)
        total = float(p["home_win"] + p["draw"] + p["away_win"]) or 1.0
        return p["home_win"] / total, p["draw"] / total, p["away_win"] / total


def _knows(model: Any, home: str, away: str) -> bool:
    """La squadra è presente nel fit? (le due classi di modello espongono l'insieme in modo diverso)"""
    teams = getattr(model, "teams", None)
    if teams is None:
        return bool(model.knows(home, away))
    return home in teams and away in teams


def _rating_probs(model: Any, kind: str, home: str, away: str) -> tuple[float, float, float] | None:
    if kind == "elo":
        if home not in model.ratings or away not in model.ratings:
            return None
        p = model.predict(home, away)
        return p["elo_p_home"], p["elo_p_draw"], p["elo_p_away"]
    if kind == "pi":
        if home not in model.teams or away not in model.teams:
            return None
        return model.probabilities(home, away)
    return None


def _dc_lambdas(model: Any, home: str, away: str) -> tuple[float, float, float]:
    """λ e ρ del Dixon-Coles con shrinkage (stessa strada della produzione)."""
    params = model.shrunk_params(model.model.get_params())
    lh, la = model.lambdas(home, away, params)
    return lh, la, float(params.get("rho", 0.0) or 0.0)


def _family_lambdas(model: Any, grid: np.ndarray) -> tuple[float, float, float]:
    """λ dalla media della matrice (le famiglie non-DC non espongono sempre λ esplicite)."""
    i, j = np.indices(grid.shape)
    return float((grid * i).sum()), float((grid * j).sum()), 0.0


def _mix_grids(lh_a: float, la_a: float, rho_a: float, probs_b: tuple[float, float, float],
               w: float) -> tuple[np.ndarray, float, float]:
    """Miscela **nella matrice dei punteggi**: w·G_A + (1−w)·G_B, con λ_B invertite da G_A.

    Miscele di distribuzioni restano distribuzioni: 1X2, Over, BTTS, risultati esatti e λ
    derivano tutti dalla stessa matrice, quindi la scheda resta coerente con se stessa (è il
    difetto della ricetta attuale, che pubblica l'1X2 mediato accanto ai mercati di un'altra
    griglia). λ_B sono ricavate dal vettore del rating con ``goal_expectancy`` e poi riportate
    entro gli stessi limiti di sicurezza della produzione (:func:`fda.models.predict.
    _clamp_lambda`): senza, un vettore irraggiungibile per una griglia (pareggio al 9%) fa
    "scappare" l'inversione a 8,9 gol attesi e la miscela viene bocciata per un difetto
    dell'inversione. Restituisce la griglia mista e le **sue** λ (media della matrice).
    """
    import penaltyblog as pb

    ga = tau_grid(lh_a, la_a, rho_a, size=GRID_SIZE)
    ge = pb.models.goal_expectancy(float(probs_b[0]), float(probs_b[1]), float(probs_b[2]), dc_adj=True,
                                   rho=rho_a, max_goals=GRID_SIZE,
                                   x0=(np.log(max(lh_a, 1e-6)), np.log(max(la_a, 1e-6))),
                                   minimizer_options={"maxiter": 120}, return_details=False)
    lh_b, la_b = float(ge["home_exp"]), float(ge["away_exp"])
    # stessa protezione della produzione: se il vettore del rating è irraggiungibile per una
    # griglia (pareggio al 9%) l'inversione "scappa" e inventa partite da 9 gol attesi, che
    # farebbero bocciare la miscela per un difetto dell'inversione e non del candidato
    limita = _clamp_lambda(lh_b, la_b, lh_a, la_a)
    if limita is not None:
        lh_b, la_b = limita
    gb = tau_grid(lh_b, la_b, rho_a, size=GRID_SIZE)
    g = w * ga + (1.0 - w) * gb
    g = g / g.sum()
    lh_m, la_m, _ = _family_lambdas(None, g)     # le λ della miscela, non quelle del DC
    return g, lh_m, la_m


#: inclinazioni casa/trasferta provate da ``_tilt_grid`` (1,00 = λ invariate)
TILT_GRID: tuple[float, ...] = tuple(round(0.85 + 0.01 * i, 3) for i in range(31))


def _tilt_grid(lh_a: float, la_a: float, rho_a: float, probs_b: tuple[float, float, float],
               w: float) -> tuple[np.ndarray, float, float]:
    """Media pesata sull'1X2 **senza gonfiare i gol attesi**: cambia solo l'inclinazione.

    La ricetta di produzione cerca due λ libere che riproducano il vettore mediato
    (``goal_expectancy``): il totale che ne esce è +8,6% sopra i gol osservati sul backtest,
    ed è il difetto che la calibrazione deve poi correggere. Qui il totale dei gol attesi
    resta quello stimato dal modello sui gol e l'Elo sposta soltanto il rapporto
    casa/trasferta; il vettore 1X2 pubblicato è quello della griglia risultante, quindi
    mercati e 1X2 restano coerenti fra loro. Il candidato serve proprio a misurare quanto
    vale, in RPS e Brier, la libertà di gonfiare le λ.
    """
    ii, jj = np.indices((GRID_SIZE, GRID_SIZE))
    ga = tau_grid(lh_a, la_a, rho_a, size=GRID_SIZE)
    probs_a = (float(ga[ii > jj].sum()), float(ga[ii == jj].sum()), float(ga[ii < jj].sum()))
    target = tuple(w * a + (1.0 - w) * b for a, b in zip(probs_a, probs_b))
    totale = lh_a + la_a
    best: tuple[float, float, np.ndarray] | None = None
    for t in TILT_GRID:
        lh_t, la_t = lh_a * t, la_a / max(t, 1e-9)
        s = totale / (lh_t + la_t) if (lh_t + la_t) > 0 else 1.0     # il totale non cambia
        g = tau_grid(lh_t * s, la_t * s, rho_a, size=GRID_SIZE)
        err = ((float(g[ii > jj].sum()) - target[0]) ** 2
               + (float(g[ii == jj].sum()) - target[1]) ** 2
               + (float(g[ii < jj].sum()) - target[2]) ** 2)
        if best is None or err < best[0]:
            best = (err, t, g)
    assert best is not None
    t = best[1]
    lh_t, la_t = lh_a * t, la_a / max(t, 1e-9)
    s = totale / (lh_t + la_t) if (lh_t + la_t) > 0 else 1.0
    g = best[2]
    return g / g.sum(), float(lh_t * s), float(la_t * s)


# --------------------------------------------------------------------------- walk-forward
def walk_forward(hist: pd.DataFrame, candidates: tuple[Candidate, ...] = CANDIDATES,
                 step_days: int = 28, min_train: int = 600, calibration: Calibration | None = None,
                 max_windows: int | None = None, self_calibrate: bool = True) -> pd.DataFrame:
    """Una riga per (candidato, gara valutata): probabilità, λ, mercati ed esito osservato.

    ``self_calibrate`` (default) dà a **ogni candidato la propria correzione del livello dei
    gol**, stimata solo sulle gare che quel candidato ha già valutato nelle finestre
    precedenti (moltiplicatore a momenti, gli stessi limiti di sicurezza della calibrazione
    di produzione; servono almeno ``MIN_SELF_CAL`` gare). Senza questa correzione il
    confronto sarebbe iniquo: la produzione è pubblicata calibrata, e un candidato con λ più
    basse verrebbe penalizzato due volte. Con ``self_calibrate=False`` si applica a tutti la
    calibrazione salvata, cioè si confronta la ricetta pubblicata così com'è.
    """
    df = hist.dropna(subset=["home_goals", "away_goals"]).copy()
    if df.empty:
        return pd.DataFrame()
    d = pd.to_datetime(df["date"])
    df["date"] = d.dt.tz_localize(None) if d.dt.tz is not None else d
    df = df.sort_values("date").reset_index(drop=True)
    cal = calibration or Calibration()
    rows: list[dict[str, Any]] = []
    groups = ([(str(k), g.reset_index(drop=True)) for k, g in df.groupby("league_key")]
              if "league_key" in df.columns else [("?", df)])
    for league_key, g in groups:
        rows.extend(_walk_league(g, league_key, candidates, step_days, min_train, cal, max_windows,
                                 self_calibrate))
    return pd.DataFrame(rows)


def _walk_league(g: pd.DataFrame, league_key: str, candidates: tuple[Candidate, ...],
                 step_days: int, min_train: int, cal: Calibration,
                 max_windows: int | None, self_calibrate: bool = True) -> list[dict[str, Any]]:
    if len(g) <= min_train:
        return []
    d = g["date"]
    cutoff = d.iloc[min_train].normalize()
    last = d.max()
    rows: list[dict[str, Any]] = []
    # per candidato: [gol osservati, λ totali grezze, gare] sulle finestre già valutate
    acc: dict[str, list[float]] = {c.key: [0.0, 0.0, 0] for c in candidates}
    windows = 0
    while cutoff <= last:
        if max_windows is not None and windows >= max_windows:
            break
        window_end = cutoff + pd.Timedelta(days=step_days)
        train = g[d < cutoff]
        test = g[(d >= cutoff) & (d < window_end)]
        cutoff = window_end
        if len(train) < min_train or test.empty:
            continue
        windows += 1
        scales: dict[str, float] = {}
        if self_calibrate:
            for cand in candidates:
                gol, lam, n = acc[cand.key]
                scales[cand.key] = (float(np.clip(gol / lam, *SCALE_BOUNDS))
                                    if n >= MIN_SELF_CAL and lam > 0 else 1.0)
        fitted: dict[str, Any] = {}
        for cand in candidates:
            t0 = time.time()
            try:
                fitted[cand.key] = _fit_candidate(cand, train)
            except Exception as exc:                                # un candidato non ferma gli altri
                log.warning("%s/%s: fit saltato (%s: %s)", league_key, cand.key, type(exc).__name__, exc)
                fitted[cand.key] = None
            log.debug("%s/%s fit in %.1fs su %d gare", league_key, cand.key, time.time() - t0, len(train))
        for r in test.itertuples(index=False):
            obs = {"date": r.date, "league_key": league_key, "home": r.home, "away": r.away,
                   "home_goals": int(r.home_goals), "away_goals": int(r.away_goals),
                   "outcome": 0 if r.home_goals > r.away_goals else (1 if r.home_goals == r.away_goals else 2),
                   "n_train": int(len(train))}
            for cand in candidates:
                cal_c = (Calibration(scales.get(cand.key, 1.0), cal.rho_shift) if self_calibrate
                         else cal)
                row = _predict_candidate(cand, fitted.get(cand.key), fitted, r.home, r.away, cal_c)
                if row is None:
                    continue
                row["lambda_scale"] = float(cal_c.lambda_scale)
                # l'accumulo usa le λ **grezze** del candidato: è su quelle che si stima la correzione
                lam_raw = float(row.get("lambda_home_raw", row.get("lambda_home", float("nan")))
                                + row.get("lambda_away_raw", row.get("lambda_away", float("nan"))))
                if np.isfinite(lam_raw):
                    a = acc[cand.key]
                    a[0] += float(r.home_goals) + float(r.away_goals)
                    a[1] += lam_raw
                    a[2] += 1
                rows.append({**obs, "candidate": cand.key, "label": cand.label, "kind": cand.kind,
                             "family": cand.family, **row})
    return rows


def _fit_candidate(cand: Candidate, train: pd.DataFrame) -> Any:
    if cand.kind == "rating" and cand.family == "elo":
        return EloModel(k=float(cand.params.get("k", 20.0)),
                        home_field_advantage=float(cand.params.get("hfa", 60.0))).fit(train)
    if cand.kind == "rating" and cand.family == "pi":
        return _PiRatings(train)
    model = fit_goals(train, cand)
    if cand.kind == "blend" or cand.kind == "production":
        return {"goals": model,
                "elo": EloModel(k=float(cand.params.get("k", 20.0)),
                                home_field_advantage=float(cand.params.get("hfa", 60.0))).fit(train)}
    return model


def _predict_candidate(cand: Candidate, fitted: Any, all_fitted: dict[str, Any], home: str, away: str,
                       cal: Calibration) -> dict[str, Any] | None:
    if fitted is None:
        return None
    if cand.kind == "rating":
        probs = _rating_probs(fitted, cand.family, home, away)
        if probs is None:
            return None
        return {"p_home": probs[0], "p_draw": probs[1], "p_away": probs[2],
                "lambda_home": float("nan"), "lambda_away": float("nan"), "rho": float("nan")}

    if cand.kind in ("blend", "production"):
        goals, elo = fitted["goals"], fitted["elo"]
        if goals is None or not _knows(goals, home, away):
            return None
        dc = goals.predict(home, away)
        e = elo.predict(home, away) if home in elo.ratings and away in elo.ratings else None
        if cand.kind == "production":
            out = ensemble(dc, e, w_dc=float(cand.params.get("w_dc", 0.7))) if e else dc
            # fedele alla produzione: mercati dalla griglia invertita, 1X2 dalla media pesata
            row = _row_from_grid(tau_grid(float(out["lambda_home"]), float(out["lambda_away"]),
                                          float(out.get("dc_rho", 0.0) or 0.0), size=GRID_SIZE),
                                 float(out["lambda_home"]), float(out["lambda_away"]),
                                 float(out.get("dc_rho", 0.0) or 0.0))
            row.update({"p_home": float(out["p_home"]), "p_draw": float(out["p_draw"]),
                        "p_away": float(out["p_away"])})
        else:
            lh, la, rho = _dc_lambdas(goals, home, away)
            probs_b = _rating_probs(elo, "elo", home, away) if e else None
            w = float(cand.params.get("w_dc", 0.7))
            if probs_b is None:
                grid = tau_grid(lh, la, rho, size=GRID_SIZE)
            elif cand.params.get("mode") == "tilt":
                grid, lh, la = _tilt_grid(lh, la, rho, probs_b, w)
            else:
                grid, lh, la = _mix_grids(lh, la, rho, probs_b, w)
            # la superficie qui è la miscela (o la griglia inclinata): va corretta nel livello
            # senza essere sostituita da una griglia DC (vedi _apply_grid_level)
            return _apply_grid_level(_row_from_grid(grid, lh, la, rho), grid, cal)
        return _apply_calibration(row, cal)

    # famiglia sui gol
    if isinstance(fitted, DixonColesModel):
        if home not in fitted.teams or away not in fitted.teams:
            return None
        lh, la, rho = _dc_lambdas(fitted, home, away)
        return _apply_calibration(_row_from_grid(tau_grid(lh, la, rho, size=GRID_SIZE), lh, la, rho), cal)
    if not _knows(fitted, home, away):
        return None
    grid = np.asarray(fitted.grid(home, away), dtype=float)
    grid = grid / grid.sum() if grid.sum() > 0 else grid
    lh, la, rho = _family_lambdas(fitted, grid)
    # anche queste famiglie vanno corrette nel livello dei gol: senza, il laboratorio
    # confronta candidati calibrati (DC, produzione) con candidati che non lo sono
    return _apply_grid_level(_row_from_grid(grid, lh, la, rho), grid, cal)


def _tilt_total(grid: np.ndarray, target: float, lo: float = 0.05, hi: float = 8.0) -> np.ndarray:
    """Riporta la media dei gol della griglia a ``target`` per **inclinazione esponenziale**.

    p′(i,j) ∝ p(i,j)·θ^(i+j), con θ cercato per bisezione (la media è monotòna in θ). Per
    Poisson indipendenti coincide esattamente con λ·θ; per le altre famiglie conserva la
    struttura di dipendenza invece di sostituirla con la superficie di Dixon-Coles. È il modo
    onesto di togliere a ogni candidato il vantaggio/svantaggio del **livello** dei gol senza
    toccarne la forma, cioè senza trasformare una binomiale negativa in un Dixon-Coles.
    """
    g = np.asarray(grid, dtype=float)
    tot = float(g.sum())
    if tot <= 0 or not np.isfinite(target) or target <= 0:
        return g
    g = g / tot
    k = np.sum(np.indices(g.shape), axis=0).astype(float)

    def media(theta: float) -> float:
        w = g * theta ** k
        s = float(w.sum())
        return float((w * k).sum() / s) if s > 0 else 0.0

    if abs(media(1.0) - target) < 1e-12:
        return g
    if media(lo) >= target:                      # target sotto il raggiungibile: si usa il limite
        w = g * lo ** k
        return w / w.sum()
    if media(hi) <= target:
        w = g * hi ** k
        return w / w.sum()
    a, b = lo, hi
    for _ in range(60):
        m = 0.5 * (a + b)
        if media(m) < target:
            a = m
        else:
            b = m
    w = g * (0.5 * (a + b)) ** k
    return w / w.sum()


def _apply_grid_level(row: dict[str, Any], grid: np.ndarray, cal: Calibration) -> dict[str, Any]:
    """Correzione del **livello** dei gol su una griglia qualunque, conservandone la forma.

    Serve per i candidati la cui superficie non è una griglia di Dixon-Coles parametrizzata da
    (λ, ρ): le miscele di griglie e le famiglie non-DC (Poisson, binomiale negativa,
    zero-inflazionata, copula Weibull). Passare da :func:`_apply_calibration` — che ricostruisce
    una griglia τ dalle λ — cancellerebbe proprio ciò che quei candidati vogliono misurare:
    misurato il 2026-09-13, con una calibrazione non identica ``mix_50`` diventava identico a
    ``dc_puro`` riga per riga, perché la miscela restituisce le λ del DC e la ricostruzione
    buttava via la forma mista. Lo spostamento di ρ resta una proprietà della superficie DC di
    produzione e qui non viene applicato.
    """
    if cal.is_identity or not np.isfinite(row.get("lambda_home", float("nan"))):
        return row
    m = float(cal.lambda_scale)
    if abs(m - 1.0) < 1e-12:
        return row
    g = np.asarray(grid, dtype=float)
    k = np.sum(np.indices(g.shape), axis=0).astype(float)
    attuale = float((g * k).sum() / g.sum()) if g.sum() > 0 else 0.0
    g2 = _tilt_total(g, attuale * m)
    lh, la, _ = _family_lambdas(None, g2)
    rho = float(row.get("rho", 0.0) or 0.0)
    out = _row_from_grid(g2, lh, la, rho)
    out["lambda_home_raw"] = row["lambda_home"]
    out["lambda_away_raw"] = row["lambda_away"]
    return out


def _row_from_grid(grid: np.ndarray, lh: float, la: float, rho: float) -> dict[str, Any]:
    m = grid_markets_many(np.asarray(grid, dtype=float)[None, :, :])
    return {k: float(v[0]) for k, v in m.items()} | {"lambda_home": lh, "lambda_away": la, "rho": rho}


def _apply_calibration(row: dict[str, Any], cal: Calibration) -> dict[str, Any]:
    if cal.is_identity or not np.isfinite(row.get("lambda_home", np.nan)):
        return row
    lh, la, rho = cal.apply(row["lambda_home"], row["lambda_away"], row.get("rho", 0.0))
    grids = tau_grid_many(np.array([lh]), np.array([la]), np.array([rho]), size=GRID_SIZE)
    out = _row_from_grid(grids[0], lh, la, rho)
    out["lambda_home_raw"] = row["lambda_home"]
    out["lambda_away_raw"] = row["lambda_away"]
    return out


# --------------------------------------------------------------------------- metriche
def _rps_rows(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    onehot = np.eye(3)[np.asarray(outcome, dtype=int)]
    p = np.asarray(probs, dtype=float)
    return ((p.cumsum(1) - onehot.cumsum(1)) ** 2).sum(1) / 2.0


def _logloss_rows(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    p = np.asarray(probs, dtype=float)
    oc = np.asarray(outcome, dtype=int)
    return -np.log(np.clip(p[np.arange(len(p)), oc], 1e-12, 1.0))


def _market_rows(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray] | None:
    keys = ("p_over15", "p_over25", "p_over35", "p_btts", "p_home_clean_sheet", "p_away_clean_sheet")
    if not all(k in df.columns for k in keys):
        return None
    pred = df[list(keys)].to_numpy(float)
    if not np.isfinite(pred).all():
        return None
    hg = df["home_goals"].to_numpy(float)
    ag = df["away_goals"].to_numpy(float)
    total = hg + ag
    obs = np.column_stack([total > 1.5, total > 2.5, total > 3.5, (hg > 0) & (ag > 0),
                           ag == 0, hg == 0]).astype(float)
    return pred, obs


def paired_bootstrap(delta: np.ndarray, draws: int = 2000, seed: int = 11) -> tuple[float, float]:
    """IC 95% della media di ``delta`` (differenze appaiate candidato − riferimento)."""
    delta = np.asarray(delta, dtype=float)
    delta = delta[np.isfinite(delta)]
    if len(delta) < 20:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(delta), size=(draws, len(delta)))
    means = delta[idx].mean(1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize(rows: pd.DataFrame, baseline: str = BASELINE, draws: int = 2000) -> pd.DataFrame:
    """Tabella di confronto: una riga per candidato, con IC appaiato sul ΔRPS."""
    if rows.empty:
        return pd.DataFrame()
    keys = ["date", "league_key", "home", "away"]
    wide = {c: g.set_index(keys).sort_index() for c, g in rows.groupby("candidate")}
    if baseline not in wide:
        baseline = str(sorted(wide)[0])
    ref = wide[baseline]
    out: list[dict[str, Any]] = []
    for cand, g in wide.items():
        common = g.index.intersection(ref.index)
        if len(common) < 30:
            continue
        gg, rr = g.loc[common], ref.loc[common]
        probs = gg[["p_home", "p_draw", "p_away"]].to_numpy(float)
        oc = gg["outcome"].to_numpy(int)
        row: dict[str, Any] = {
            "candidate": cand, "label": str(gg["label"].iloc[0]), "kind": str(gg["kind"].iloc[0]),
            "family": str(gg["family"].iloc[0]), "n": int(len(common)),
            "leagues": int(pd.Series([i[1] for i in common]).nunique()),
            "rps": float(_rps_rows(probs, oc).mean()),
            "logloss": float(_logloss_rows(probs, oc).mean()),
            "brier_1x2": float(((probs - np.eye(3)[oc]) ** 2).sum(1).mean()),
            "hit": float((probs.argmax(1) == oc).mean()),
            "pareggio_previsto": float(probs[:, 1].mean()),
            "pareggio_osservato": float((oc == 1).mean()),
        }
        # λ effettiva = media della matrice dei punteggi (dopo la correzione τ), non il parametro grezzo
        lam = (gg["lambda_total"].to_numpy(float) if "lambda_total" in gg.columns
               and np.isfinite(gg["lambda_total"].to_numpy(float)).any()
               else gg["lambda_home"].to_numpy(float) + gg["lambda_away"].to_numpy(float))
        goals = gg["home_goals"].to_numpy(float) + gg["away_goals"].to_numpy(float)
        if np.isfinite(lam).any():
            row["lambda_media"] = float(np.nanmean(lam))
            row["bias_lambda"] = float(np.nanmean(lam - goals))
        if "lambda_scale" in gg.columns:
            sc = pd.to_numeric(gg["lambda_scale"], errors="coerce").to_numpy(float)
            if np.isfinite(sc).any():
                # quanta correzione del livello dei gol serve a questo candidato: 1,00 = nessuna
                row["scala_media"] = float(np.nanmean(sc))
        mk = _market_rows(gg)
        if mk is not None:
            pred, obs = mk
            row["brier_mercati"] = float(((pred - obs) ** 2).mean())
            row["over25_previsto"] = float(pred[:, 1].mean())
            row["over25_osservato"] = float(obs[:, 1].mean())
        dr = _rps_rows(probs, oc) - _rps_rows(rr[["p_home", "p_draw", "p_away"]].to_numpy(float),
                                              rr["outcome"].to_numpy(int))
        lo, hi = paired_bootstrap(dr, draws=draws)
        row["delta_rps"] = float(np.nanmean(dr))
        row["delta_rps_lo95"] = lo
        row["delta_rps_hi95"] = hi
        row["migliore_in"] = float(np.nanmean(dr < -1e-12))
        row["peggiore_in"] = float(np.nanmean(dr > 1e-12))
        out.append(row)
    df = pd.DataFrame(out).sort_values("rps").reset_index(drop=True)
    df["riferimento"] = baseline
    return df


def per_league(rows: pd.DataFrame) -> pd.DataFrame:
    """RPS per candidato e per lega: un modello può essere buono in media e cattivo dove serve."""
    if rows.empty:
        return pd.DataFrame()
    recs = []
    for (cand, lg), g in rows.groupby(["candidate", "league_key"]):
        probs = g[["p_home", "p_draw", "p_away"]].to_numpy(float)
        oc = g["outcome"].to_numpy(int)
        recs.append({"candidate": cand, "league_key": lg, "n": int(len(g)),
                     "rps": float(_rps_rows(probs, oc).mean()),
                     "logloss": float(_logloss_rows(probs, oc).mean()),
                     "hit": float((probs.argmax(1) == oc).mean())})
    return pd.DataFrame(recs).sort_values(["league_key", "rps"]).reset_index(drop=True)


def convex_weights(rows: pd.DataFrame, members: list[str], draws: int = 0) -> dict[str, float]:
    """Pesi di una miscela convessa dei vettori 1X2 che minimizza l'RPS sulle gare comuni.

    È lo "stacking" minimo e interpretabile: niente dipendenze nuove (solo numpy), pesi
    vincolati a sommare 1 e non negativi, e — se ``rows`` ha una colonna ``date`` — la
    possibilità di validarli a finestre cronologiche dal chiamante.
    """
    from scipy.optimize import minimize

    keys = ["date", "league_key", "home", "away"] if "date" in rows.columns else None
    wide = {c: g.set_index(keys).sort_index() if keys else g for c, g in rows.groupby("candidate")}
    members = [m for m in members if m in wide]
    if len(members) < 2:
        return {m: 1.0 for m in members} if members else {}
    idx = wide[members[0]].index
    for m in members[1:]:
        idx = idx.intersection(wide[m].index)
    if len(idx) < 50:
        return {m: 1.0 / len(members) for m in members}
    stack = np.stack([wide[m].loc[idx, ["p_home", "p_draw", "p_away"]].to_numpy(float) for m in members])
    oc = wide[members[0]].loc[idx, "outcome"].to_numpy(int)

    def objective(x: np.ndarray) -> float:
        w = np.abs(x)
        w = w / w.sum()
        mixed = np.tensordot(w, stack, axes=(0, 0))
        return float(_rps_rows(mixed, oc).mean())

    x0 = np.full(len(members), 1.0 / len(members))
    res = minimize(objective, x0, method="Nelder-Mead",
                   options={"maxiter": 4000, "xatol": 1e-4, "fatol": 1e-8})
    w = np.abs(res.x)
    w = w / w.sum()
    return {m: float(round(v, 4)) for m, v in zip(members, w)}
