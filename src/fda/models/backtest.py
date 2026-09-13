"""Backtest cronologico fuori campione.

Il campione della pagina accuratezza cresce solo con i run giornalieri (~15-20 gare/giorno): per
decidere se un parametro del modello va corretto serve un campione molto più ampio, e soprattutto
serve che le stime valutate **non** abbiano visto il risultato. Qui lo storico di ogni lega viene
diviso in finestre temporali: il modello è addestrato solo sulle partite precedenti l'inizio della
finestra e valutato su quelle successive. Dixon-Coles ed Elo ricevono un sottoinsieme troncato per
data, quindi nessuna informazione futura entra nel fit e i numeri sono fuori campione.

Atteso: RPS intorno a 0,20-0,21 e log-loss intorno a 1,0 su un campionato europeo
di prima divisione.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from .predict import (SHRINK_PRIOR, DixonColesModel, EloModel, ensemble, log_loss, outcome_index,
                      wilson_interval)

log = logging.getLogger("fda.backtest")

#: (colonna di probabilità, chiave dell'esito osservato, etichetta italiana) dei mercati binari
MARKET_KEYS: tuple[tuple[str, str, str], ...] = (
    ("p_over15", "over15", "Over 1,5 gol"), ("p_over25", "over25", "Over 2,5 gol"),
    ("p_over35", "over35", "Over 3,5 gol"), ("p_btts", "btts", "Gol · entrambe a segno"),
    ("p_1x", "d1x", "Doppia chance 1X"), ("p_12", "d12", "Doppia chance 12"),
    ("p_x2", "dx2", "Doppia chance X2"), ("p_home_clean_sheet", "cs_h", "Porta inviolata casa"),
    ("p_away_clean_sheet", "cs_a", "Porta inviolata trasferta"),
)

#: probabilità di riferimento di chi non ha un modello (1X2 medio dei campionati europei)
NAIVE_1X2: tuple[float, float, float] = (0.45, 0.27, 0.28)

OUTCOME_LABELS: tuple[str, str, str] = ("1 · vittoria in casa", "X · pareggio",
                                          "2 · vittoria in trasferta")


def chronological_backtest(hist: pd.DataFrame, step_days: int = 14, min_train: int = 200,
                           xi: float = 0.0018, w_dc: float = 0.7,
                           shrink_prior: float = SHRINK_PRIOR,
                           leagues: list[str] | None = None) -> pd.DataFrame:
    """Cammina sullo storico a finestre di ``step_days`` e restituisce una riga per gara valutata.

    ``hist`` deve avere ``date``, ``home``, ``away``, ``home_goals``, ``away_goals`` e, se presente,
    ``league_key`` (una lega alla volta: attacco/difesa e fattore campo sono stimati per lega).
    ``min_train`` è il numero minimo di partite di storico richieste prima di iniziare a valutare.
    """
    df = hist.dropna(subset=["home_goals", "away_goals"]).copy()
    if df.empty:
        return pd.DataFrame()
    d = pd.to_datetime(df["date"])
    df["date"] = d.dt.tz_localize(None) if d.dt.tz is not None else d
    df = df.sort_values("date").reset_index(drop=True)
    frames = []
    if "league_key" in df.columns:
        groups = [(str(lg), g.reset_index(drop=True)) for lg, g in df.groupby("league_key")]
    else:
        groups = [("?", df)]
    for lg, g in groups:
        if leagues and lg not in leagues:
            continue
        try:
            part = _walk(g, lg, step_days=step_days, min_train=min_train, xi=xi, w_dc=w_dc,
                         shrink_prior=shrink_prior)
        except Exception as exc:   # una lega problematica non ferma le altre
            log.warning("backtest %s saltato: %s: %s", lg, type(exc).__name__, exc)
            continue
        if not part.empty:
            frames.append(part)
            log.info("backtest %s: %d gare valutate su %d di storico", lg, len(part), len(g))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _walk(g: pd.DataFrame, league_key: str, step_days: int, min_train: int, xi: float,
          w_dc: float, shrink_prior: float) -> pd.DataFrame:
    d = g["date"]
    if len(g) <= min_train:
        return pd.DataFrame()
    step = pd.Timedelta(days=step_days)
    cutoff = d.iloc[min_train].normalize()
    last = d.max()
    rows: list[dict[str, Any]] = []
    while cutoff <= last:
        window_end = cutoff + step
        train = g[d < cutoff]
        test = g[(d >= cutoff) & (d < window_end)]
        cutoff = window_end
        if len(train) < min_train or test.empty:
            continue
        dc = DixonColesModel(xi=xi, shrink_prior=shrink_prior).fit(train)
        elo = EloModel().fit(train)
        for r in test.itertuples(index=False):
            try:
                pr = dc.predict(r.home, r.away)
            except KeyError:
                continue        # squadra mai vista nello storico (promozione a stagione in corso)
            note = r.home in elo.ratings and r.away in elo.ratings
            e = elo.predict(r.home, r.away) if note else None
            out = ensemble(pr, e, w_dc=w_dc)
            out.pop("top_scores", None)
            out.update({"date": r.date, "league_key": league_key, "home": r.home, "away": r.away,
                        "home_goals": int(r.home_goals), "away_goals": int(r.away_goals),
                        "outcome": outcome_index(int(r.home_goals), int(r.away_goals)),
                        "n_train": int(dc.n_matches)})
            rows.append(out)
    return pd.DataFrame(rows)


def observed_flags(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Esiti osservati dei mercati binari (bool per riga), stessa definizione della pagina."""
    tot = df["home_goals"].to_numpy(dtype=float) + df["away_goals"].to_numpy(dtype=float)
    hg = df["home_goals"].to_numpy(dtype=float)
    ag = df["away_goals"].to_numpy(dtype=float)
    return {"over15": tot > 1.5, "over25": tot > 2.5, "over35": tot > 3.5,
            "btts": (hg > 0) & (ag > 0), "d1x": hg >= ag, "d12": hg != ag, "dx2": hg <= ag,
            "cs_h": ag == 0, "cs_a": hg == 0}


def backtest_summary(df: pd.DataFrame,
                     naive: tuple[float, float, float] = NAIVE_1X2) -> dict[str, Any]:
    """Riepilogo, calibrazione 1X2 e mercati del backtest, con intervalli di Wilson al 95%."""
    if df.empty:
        return {}
    probs = df[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
    oc = df["outcome"].to_numpy(dtype=int)
    onehot = np.eye(3)[oc]
    naive_arr = np.tile(np.asarray(naive, dtype=float), (len(df), 1))
    rps = float((((probs.cumsum(1) - onehot.cumsum(1)) ** 2).sum(1) / 2).mean())
    rps_naive = float((((naive_arr.cumsum(1) - onehot.cumsum(1)) ** 2).sum(1) / 2).mean())
    p_real = probs[np.arange(len(df)), oc]
    n = int(len(df))
    calib = []
    for i, label in enumerate(OUTCOME_LABELS):
        k = int((oc == i).sum())
        lo, hi = wilson_interval(k, n)
        prev = float(probs[:, i].mean())
        calib.append({"label": label, "prev": prev, "obs": k / n, "k": k, "n": n,
                      "lo": lo, "hi": hi, "outside": bool(not (lo <= prev <= hi))})
    flags = observed_flags(df)
    markets = []
    for col, key, label in MARKET_KEYS:
        if col not in df.columns:
            continue
        pr = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        y = flags[key].astype(float)
        ok = ~np.isnan(pr)
        if ok.sum() < 5:
            continue
        pr, y = pr[ok], y[ok]
        n_mk = int(ok.sum())
        k_mk = int(round(float(y.sum())))
        lo, hi = wilson_interval(k_mk, n_mk)
        prev = float(pr.mean())
        brier = float(((pr - y) ** 2).mean())
        base = float(y.mean())
        markets.append({"label": label, "n": n_mk, "prev": prev, "obs": base, "lo": lo, "hi": hi,
                        "outside": bool(not (lo <= prev <= hi)), "brier": brier,
                        "brier_base": float(((base - y) ** 2).mean()),
                        "delta": brier - float(((base - y) ** 2).mean())})
    return {"n": n, "leagues": int(df["league_key"].nunique()) if "league_key" in df.columns else 1,
            "rps": rps, "naive": rps_naive, "delta": rps - rps_naive,
            "brier": float(((probs - onehot) ** 2).sum(1).mean()),
            "logloss": float(np.mean([log_loss(float(x)) for x in p_real])),
            "hit": float((probs.argmax(1) == oc).mean()), "calib": calib, "markets": markets}
