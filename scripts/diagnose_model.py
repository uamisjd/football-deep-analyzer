"""Diagnosi quantitativa del modello pubblicato, sui dati già nello store.

Legge ``data/processed/backtest.parquet`` (stime **fuori campione** prodotte da
``fda backtest``) e misura, senza toccare la rete:

1. accuratezza 1X2 dell'ensemble contro Elo puro e frequenza di base;
2. coerenza fra λ dichiarate e media reale della griglia Dixon-Coles (effetto τ);
3. bias sui gol totali e sui mercati derivati (Over/Under, BTTS, clean sheet);
4. calibrazione 1X2 per decile (diagramma di affidabilità in forma tabellare);
5. dettaglio per lega con intervalli di Wilson;
6. guadagno potenziale di due ricalibrazioni **walk-forward** (fit solo sul passato):
   temperatura sul vettore 1X2 e moltiplicatore delle λ per i mercati sui gol;
7. andamento temporale dei gol osservati (per capire se il bias è strutturale o di periodo).

Uso: ``python scripts/diagnose_model.py [--backtest data/processed/backtest.parquet]``.
Stampa solo un riepilogo (regole 3-4 di ``docs/00_regole_di_lavoro.md``).
"""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np
import pandas as pd

from fda.models.dc_grid import tau_grid
from fda.models.predict import wilson_interval

NAIVE = (0.45, 0.27, 0.28)
GOAL_MARKETS = ("p_over15", "p_over25", "p_over35", "p_btts",
                "p_home_clean_sheet", "p_away_clean_sheet")


def rps_rows(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    """RPS per riga (0 = perfetto): somma delle differenze delle cumulative / 2."""
    onehot = np.eye(3)[np.asarray(outcome, dtype=int)]
    p = np.asarray(probs, dtype=float)
    return ((p.cumsum(1) - onehot.cumsum(1)) ** 2).sum(1) / 2.0


def logloss_rows(probs: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    p = np.asarray(probs, dtype=float)
    oc = np.asarray(outcome, dtype=int)
    return -np.log(np.clip(p[np.arange(len(p)), oc], 1e-12, 1.0))


def temperature(p: np.ndarray, alpha: float) -> np.ndarray:
    """Ricalibrazione a temperatura: p_i^α normalizzato (α > 1 = vettore più estremo)."""
    q = np.power(np.clip(np.asarray(p, dtype=float), 1e-9, 1.0), alpha)
    return q / q.sum(1, keepdims=True)


def flags_of(df: pd.DataFrame) -> dict[str, np.ndarray]:
    tot = df["home_goals"].to_numpy(float) + df["away_goals"].to_numpy(float)
    hg, ag = df["home_goals"].to_numpy(float), df["away_goals"].to_numpy(float)
    return {"p_over15": tot > 1.5, "p_over25": tot > 2.5, "p_over35": tot > 3.5,
            "p_btts": (hg > 0) & (ag > 0), "p_home_clean_sheet": ag == 0,
            "p_away_clean_sheet": hg == 0}


def grid_stats(lh: float, la: float, rho: float) -> tuple[float, np.ndarray, np.ndarray]:
    """Media dei gol totali della griglia τ + probabilità Over 1,5/2,5/3,5 e BTTS."""
    g = tau_grid(float(lh), float(la), float(rho or 0.0), size=11)
    idx = np.indices(g.shape)
    tot = idx[0] + idx[1]
    mean = float((g * tot).sum())
    over = np.array([float(g[tot > t].sum()) for t in (1.5, 2.5, 3.5)])
    btts = float(g[1:, 1:].sum())
    return mean, over, np.array([btts, float(g[:, 0].sum()), float(g[0, :].sum())])


def grid_bias(df: pd.DataFrame, sample: int = 400) -> dict[str, float]:
    """λ dichiarate contro media reale della griglia τ (effetto della correzione DC)."""
    rows = df.sample(min(sample, len(df)), random_state=7) if sample else df
    means = [grid_stats(lh, la, r)[0] for lh, la, r in
             zip(rows["lambda_home"], rows["lambda_away"], rows.get("dc_rho", pd.Series(0.0, index=rows.index)))]
    declared = float((rows["lambda_home"] + rows["lambda_away"]).mean())
    return {"n_campione": float(len(rows)), "lam_dichiarate": declared,
            "media_griglia": float(np.mean(means)), "scarto": declared - float(np.mean(means))}


def _folds(n: int, k: int) -> list[np.ndarray]:
    return [np.asarray(x) for x in np.array_split(np.arange(n), k)]


def walk_forward_temperature(df: pd.DataFrame, alphas: np.ndarray, folds: int = 6) -> dict[str, Any]:
    """α scelto minimizzando l'RPS sul passato, valutato sulla finestra successiva."""
    d = df.sort_values("date").reset_index(drop=True)
    probs = d[["p_home", "p_draw", "p_away"]].to_numpy(float)
    oc = d["outcome"].to_numpy(int)
    parts = _folds(len(d), folds)
    held_rps, held_ll, chosen = [], [], []
    for k in range(1, len(parts)):
        train = np.concatenate(parts[:k])
        test = parts[k]
        scores = [rps_rows(temperature(probs[train], a), oc[train]).mean() for a in alphas]
        best = float(alphas[int(np.argmin(scores))])
        chosen.append(best)
        held_rps.extend(rps_rows(temperature(probs[test], best), oc[test]).tolist())
        held_ll.extend(logloss_rows(temperature(probs[test], best), oc[test]).tolist())
    raw_idx = np.concatenate(parts[1:])
    return {"n": len(raw_idx), "rps_raw": float(rps_rows(probs[raw_idx], oc[raw_idx]).mean()),
            "rps_calibrato": float(np.mean(held_rps)),
            "ll_raw": float(logloss_rows(probs[raw_idx], oc[raw_idx]).mean()),
            "ll_calibrato": float(np.mean(held_ll)),
            "alpha_scelti": [round(a, 3) for a in chosen]}


def walk_forward_lambda(df: pd.DataFrame, mults: np.ndarray, folds: int = 6) -> dict[str, Any]:
    """Moltiplicatore m delle λ (λ' = m·λ) scelto sui mercati dei gol del passato.

    Le probabilità dei mercati vengono ricalcolate dalla griglia τ, quindi restano
    coerenti con la matrice mostrata sul sito: è esattamente l'intervento che si
    farebbe in produzione.
    """
    d = df.sort_values("date").reset_index(drop=True)
    flags = flags_of(d)
    y = np.column_stack([flags[k].astype(float) for k in
                         ("p_over15", "p_over25", "p_over35", "p_btts",
                          "p_home_clean_sheet", "p_away_clean_sheet")])
    p_raw = d[list(GOAL_MARKETS)].to_numpy(float)
    lam = d[["lambda_home", "lambda_away"]].to_numpy(float)
    rho = (d["dc_rho"].to_numpy(float) if "dc_rho" in d.columns else np.zeros(len(d)))
    cache: dict[float, np.ndarray] = {}
    for m in mults:
        cols = np.array([grid_stats(lam[i, 0] * m, lam[i, 1] * m, rho[i])[1:] for i in range(len(d))])
        cache[float(m)] = np.concatenate([cols[:, 0, :], cols[:, 1, :]], axis=1)

    parts = _folds(len(d), folds)
    held_brier, chosen = [], []
    for k in range(1, len(parts)):
        train = np.concatenate(parts[:k])
        test = parts[k]
        scores = {m: float(((cache[m][train] - y[train]) ** 2).mean()) for m in cache}
        best = min(scores, key=scores.get)
        chosen.append(best)
        held_brier.append(((cache[best][test] - y[test]) ** 2).mean(axis=0))
    raw_idx = np.concatenate(parts[1:])
    per_market = {}
    for j, name in enumerate(GOAL_MARKETS):
        per_market[name] = {"brier_raw": float(((p_raw[raw_idx, j] - y[raw_idx, j]) ** 2).mean()),
                            "brier_calibrato": float(np.mean([b[j] for b in held_brier]))}
    return {"m_scelti": [round(m, 3) for m in chosen],
            "brier_tot_raw": float(((p_raw[raw_idx] - y[raw_idx]) ** 2).mean()),
            "brier_tot_calibrato": float(np.mean([float(np.mean(b)) for b in held_brier])),
            "per_mercato": per_market}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", default="data/processed/backtest.parquet")
    ap.add_argument("--sample-grid", type=int, default=400)
    args = ap.parse_args()
    df = pd.read_parquet(args.backtest)
    df["date"] = pd.to_datetime(df["date"])
    n = len(df)
    print(f"campione fuori campione: {n} gare · {df['date'].min():%Y-%m-%d} → {df['date'].max():%Y-%m-%d}"
          f" · {df['league_key'].nunique()} leghe")

    probs = df[["p_home", "p_draw", "p_away"]].to_numpy(float)
    oc = df["outcome"].to_numpy(int)
    elo = df[["elo_p_home", "elo_p_draw", "elo_p_away"]].to_numpy(float)
    naive = np.tile(NAIVE, (n, 1))
    print("\n[1] accuratezza 1X2")
    for label, p in (("ensemble (pubblicato)", probs), ("Elo puro", elo), ("frequenza di base", naive)):
        print(f"  {label:<22} RPS {rps_rows(p, oc).mean():.4f} · log-loss {logloss_rows(p, oc).mean():.4f}"
              f" · esito azzeccato {(p.argmax(1) == oc).mean():.3f}")

    print("\n[2] λ dichiarate contro media reale della griglia τ (effetto della correzione DC)")
    for k, v in grid_bias(df, args.sample_grid).items():
        print(f"  {k:<16} {v:.4f}")

    tot_pred = float((df["lambda_home"] + df["lambda_away"]).mean())
    tot_obs = float((df["home_goals"] + df["away_goals"]).mean())
    print(f"\n[3] gol totali: λ {tot_pred:.3f} contro osservati {tot_obs:.3f} "
          f"(bias {tot_pred - tot_obs:+.3f}, {(tot_pred / tot_obs - 1) * 100:+.1f}%)")
    print("  mercati derivati (previsto · osservato · Brier · Brier base · Δ):")
    flags = flags_of(df)
    for k in GOAL_MARKETS:
        p, y = df[k].to_numpy(float), flags[k].astype(float)
        b = float(((p - y) ** 2).mean())
        base = float(((y.mean() - y) ** 2).mean())
        print(f"    {k:<22} {p.mean():.3f} · {y.mean():.3f} · {b:.4f} · {base:.4f} · {b - base:+.4f}")

    print("\n[4] calibrazione 1X2 per decile di p_home (previsto contro osservato)")
    bins = pd.qcut(df["p_home"], 10, duplicates="drop")
    tab = df.groupby(bins, observed=True).apply(
        lambda g: pd.Series({"n": len(g), "prev_1": g["p_home"].mean(), "obs_1": (g["outcome"] == 0).mean(),
                             "prev_X": g["p_draw"].mean(), "obs_X": (g["outcome"] == 1).mean(),
                             "prev_2": g["p_away"].mean(), "obs_2": (g["outcome"] == 2).mean()}),
        include_groups=False)
    print(tab.round(3).to_string())

    print("\n[5] per lega: RPS ensemble / Elo / base, bias λ, Wilson sull'esito casa")
    for lg, g in df.groupby("league_key"):
        gp = g[["p_home", "p_draw", "p_away"]].to_numpy(float)
        ge = g[["elo_p_home", "elo_p_draw", "elo_p_away"]].to_numpy(float)
        go = g["outcome"].to_numpy(int)
        bias_lg = float((g["lambda_home"] + g["lambda_away"]).mean()
                        - (g["home_goals"] + g["away_goals"]).mean())
        k = int((go == 0).sum())
        lo, hi = wilson_interval(k, len(g))
        print(f"  {lg}: n={len(g):4d} RPS {rps_rows(gp, go).mean():.4f} / Elo {rps_rows(ge, go).mean():.4f}"
              f" / base {rps_rows(np.tile(NAIVE, (len(g), 1)), go).mean():.4f}"
              f" · bias λ {bias_lg:+.3f} · casa obs {k / len(g):.3f} (Wilson {lo:.3f}-{hi:.3f},"
              f" prev {g['p_home'].mean():.3f})")

    print("\n[6] guadagno potenziale di ricalibrazioni walk-forward (fit solo sul passato)")
    alphas = np.round(np.arange(0.90, 1.36, 0.02), 3)
    wf = walk_forward_temperature(df, alphas)
    print(f"  temperatura 1X2 su {wf['n']} gare: RPS {wf['rps_raw']:.4f} → {wf['rps_calibrato']:.4f}"
          f" ({wf['rps_calibrato'] - wf['rps_raw']:+.4f}) · log-loss {wf['ll_raw']:.4f} → {wf['ll_calibrato']:.4f}"
          f" · α scelti {wf['alpha_scelti']}")
    mults = np.round(np.arange(0.88, 1.07, 0.01), 3)
    wl = walk_forward_lambda(df, mults)
    print(f"  moltiplicatore λ: Brier mercati {wl['brier_tot_raw']:.4f} → {wl['brier_tot_calibrato']:.4f}"
          f" · m scelti {wl['m_scelti']}")
    for name, v in wl["per_mercato"].items():
        print(f"    {name:<22} {v['brier_raw']:.4f} → {v['brier_calibrato']:.4f}"
              f" ({v['brier_calibrato'] - v['brier_raw']:+.4f})")

    print("\n[7] andamento per semestre (gol osservati contro λ, RPS)")
    sem = df["date"].dt.year.astype(str) + np.where(df["date"].dt.month < 7, "H1", "H2")
    print(df.assign(sem=sem).groupby("sem").apply(
        lambda g: pd.Series({"n": len(g), "gol_obs": (g["home_goals"] + g["away_goals"]).mean(),
                             "lam": (g["lambda_home"] + g["lambda_away"]).mean(),
                             "rps": rps_rows(g[["p_home", "p_draw", "p_away"]].to_numpy(float),
                                             g["outcome"].to_numpy(int)).mean()}),
        include_groups=False).round(3).to_string())


if __name__ == "__main__":
    main()
