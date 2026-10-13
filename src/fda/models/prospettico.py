"""Test prospettico di γ-sharpening 1,12 (docs/86 §3, docs/89).

PROTOCOLLO (fissato prima di raccogliere dati, non modificabile a posteriori):
- ogni run di ``fda predict`` registra, per ogni partita futura, due righe nella tabella
  ``prospettico``: ``prod`` (la previsione pubblicata, copiata così com'è) e ``gamma_112``
  (le **stesse λ pubblicate** con γ-sharpening 1,12 sul rapporto, a totale invariato, poi
  griglia Dixon-Coles e 1X2; nessuna ricalibrazione aggiuntiva);
- una riga per (partita, variante): l'ultima prima del calcio d'inizio. Dopo il calcio
  d'inizio la partita non viene più prevista, quindi la riga non si sovrascrive;
- si valuta solo su partite finite con entrambe le varianti registrate prima del calcio d'inizio;
- **promozione** solo se: almeno ``MIN_N`` partite valutate, IC 95% appaiato di ΔRPS
  interamente negativo, e migliore in almeno ``MIN_LEAGUES`` campionati su 7.

Differenza dichiarata rispetto al candidato del laboratorio (``lab.py``): quello applica γ
all'ensemble prima dei gol attesi finali; questo la applica alle λ pubblicate. Il test misura
quindi la **ricetta pubblicabile**, non il candidato in provetta.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .dc_grid import GRID_SIZE, tau_grid

VARIANT_GAMMA = "gamma_112"
VARIANT_PROD = "prod"
GAMMA = 1.12
MIN_N = 200
MIN_LEAGUES = 5
N_BOOT = 2000
SEED = 20261012


def gamma_variant(lambda_home: float, lambda_away: float, rho: float) -> dict[str, float]:
    """1X2 della variante γ a partire dalle λ pubblicate (stesso percorso del laboratorio)."""
    from .lab import _row_from_grid, sharpen_lambda_ratio  # import locale: lab è pesante

    lh, la = sharpen_lambda_ratio(float(lambda_home), float(lambda_away), GAMMA)
    row = _row_from_grid(tau_grid(lh, la, float(rho or 0.0), size=GRID_SIZE), lh, la, float(rho or 0.0))
    return {"p_home": row["p_home"], "p_draw": row["p_draw"], "p_away": row["p_away"],
            "lambda_home": lh, "lambda_away": la}


def _valid_probabilities(df: pd.DataFrame) -> pd.Series:
    """Un vettore 1X2 deve essere finito, nel simplesso e normalizzato."""
    p = df[["p_home", "p_draw", "p_away"]].apply(pd.to_numeric, errors="coerce")
    return (np.isfinite(p).all(axis=1) & p.ge(0).all(axis=1) & p.le(1).all(axis=1)
            & np.isclose(p.sum(axis=1), 1.0, atol=1e-9, rtol=0))


def record(store: Any, pred: pd.DataFrame, *, now: pd.Timestamp | None = None) -> int:
    """Registra solo prima del kickoff e non riscrive mai una coppia già congelata.

    Il filtro del chiamante non basta: il fit può attraversare il calcio d'inizio e un
    calendario aggiornato può spostare una data già archiviata. Il kickoff salvato è
    quindi un secondo limite, conservativo anche per i rinvii (docs/91). ``now`` rende
    verificabili le condizioni al confine senza dipendere dall'orologio dei test.
    """
    if pred is None or pred.empty:
        return 0
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.to_datetime(now, utc=True)
    if pd.isna(now):
        raise ValueError("prospettico: istante di registrazione non valido")
    pred = pred.copy()
    pred["utc_kickoff"] = pd.to_datetime(pred["utc_kickoff"], utc=True, errors="coerce")
    pred = pred[pred["utc_kickoff"] > now]
    old = store.read("prospettico")
    if not old.empty:
        kickoff = pd.to_datetime(old["utc_kickoff"], utc=True, errors="coerce")
        frozen = old.loc[kickoff.isna() | (kickoff <= now), "match_id"]
        pred = pred[~pred["match_id"].isin(frozen)]
    if pred.empty:
        return 0
    if "dc_rho" not in pred.columns:  # niente ρ = niente variante: non si inventa un valore
        raise ValueError("prospettico: manca dc_rho nelle previsioni, impossibile costruire γ")
    values = pred[["lambda_home", "lambda_away", "dc_rho"]].apply(pd.to_numeric, errors="coerce")
    if (not _valid_probabilities(pred).all() or not np.isfinite(values).all().all()
            or not values[["lambda_home", "lambda_away"]].gt(0).all().all()
            or pred["match_id"].duplicated().any()):
        raise ValueError("prospettico: probabilità, λ, ρ o chiavi non validi")
    recs: list[dict[str, Any]] = []
    for r in pred.itertuples(index=False):
        base = {"match_id": int(r.match_id), "league_key": r.league_key, "made_at": now,
                "utc_kickoff": r.utc_kickoff}
        recs.append(base | {"variant": VARIANT_PROD, "p_home": float(r.p_home),
                            "p_draw": float(r.p_draw), "p_away": float(r.p_away)})
        g = gamma_variant(r.lambda_home, r.lambda_away, r.dc_rho)
        recs.append(base | {"variant": VARIANT_GAMMA, "p_home": g["p_home"],
                            "p_draw": g["p_draw"], "p_away": g["p_away"]})
    return store.upsert("prospettico", recs)


def evaluate(store: Any, fixtures: pd.DataFrame) -> dict[str, Any]:
    """Valuta coppie finite, valide, dallo stesso snapshot strettamente pre-partita.

    La lettura difensiva protegge anche da Parquet importati o scritti da versioni vecchie:
    una previsione postuma, ambigua o incompleta non può diventare evidenza di promozione.
    """
    empty = {"n": 0, "delta": None, "lo": None, "hi": None, "leagues_better": 0,
             "n_leagues": 0, "passes": False, "min_n": MIN_N, "min_leagues": MIN_LEAGUES}
    pr = store.read("prospettico")
    if pr.empty or fixtures is None or fixtures.empty:
        return empty
    fin_cols = ["match_id", "home_goals", "away_goals"]
    if "utc_kickoff" in fixtures.columns:
        fin_cols.append("utc_kickoff")
    fin = fixtures[fixtures["status"] == "finished"][fin_cols].dropna()
    fin = fin.rename(columns={"utc_kickoff": "actual_kickoff"})
    fin = fin.assign(match_id=fin["match_id"].astype(int)).drop_duplicates("match_id", keep=False)
    pr = pr.assign(match_id=pr["match_id"].astype(int))
    for col in ("made_at", "utc_kickoff"):
        pr[col] = pd.to_datetime(pr[col], utc=True, errors="coerce")
    pr = pr[~pr.duplicated(["match_id", "variant"], keep=False)]
    pr = pr[_valid_probabilities(pr) & (pr["made_at"] < pr["utc_kickoff"])]
    cols = ["p_home", "p_draw", "p_away"]
    pair_keys = ["match_id", "league_key", "made_at", "utc_kickoff"]
    wide = None
    for v in (VARIANT_PROD, VARIANT_GAMMA):
        part = pr[pr["variant"] == v][[*pair_keys, *cols]].dropna(subset=pair_keys)
        part = part.rename(columns={c: f"{c}_{v}" for c in cols})
        wide = part if wide is None else wide.merge(part, on=pair_keys, validate="one_to_one")
    m = wide.merge(fin, on="match_id", validate="one_to_one")
    if "actual_kickoff" in m.columns:
        actual = pd.to_datetime(m["actual_kickoff"], utc=True, errors="coerce")
        m = m[m["made_at"] < actual]
    if m.empty:
        return empty
    out = np.where(m["home_goals"] > m["away_goals"], 0, np.where(m["home_goals"] == m["away_goals"], 1, 2))

    def rps(variant: str) -> np.ndarray:
        p = np.column_stack([m[f"{c}_{variant}"].to_numpy(float) for c in cols])
        o = np.eye(3)[out]
        cp, co = np.cumsum(p, axis=1), np.cumsum(o, axis=1)
        return ((cp - co) ** 2).sum(axis=1) / 2.0

    d = rps(VARIANT_GAMMA) - rps(VARIANT_PROD)           # negativo = γ migliore
    n = len(d)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boots = d[idx].mean(axis=1)
    lo, hi = float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))
    per = pd.Series(d).groupby(m["league_key"].to_numpy()).mean()
    better = int((per < 0).sum())
    passes = n >= MIN_N and hi < 0 and better >= MIN_LEAGUES
    return {"n": n, "delta": float(d.mean()), "lo": lo, "hi": hi, "leagues_better": better,
            "n_leagues": len(per), "passes": bool(passes), "min_n": MIN_N, "min_leagues": MIN_LEAGUES}
