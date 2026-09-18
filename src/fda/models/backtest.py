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

from .calibration import Calibration
from .dc_grid import grid_markets_many, tau_grid_many
from .predict import (
    MODEL_VERSION,
    SHRINK_PRIOR,
    DixonColesModel,
    EloModel,
    ensemble,
    log_loss,
    outcome_index,
    wilson_interval,
)

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
                        "n_train": int(dc.n_matches), "model_version": MODEL_VERSION})
            rows.append(out)
    return pd.DataFrame(rows)


def calibrate_rows(df: pd.DataFrame, cal: Calibration | None) -> pd.DataFrame:
    """Copia del backtest con le probabilità ripubblicate dalla griglia calibrata.

    Perché: la pagina Accuratezza deve descrivere il modello **come viene pubblicato oggi**
    (previsioni calibrate), mentre ``backtest.parquet`` resta grezzo di proposito — è il
    campione su cui ``fda calibrate`` stima i parametri, e calibrarlo prima renderebbe la
    stima circolare (troverebbe un moltiplicatore ≈1 e le previsioni tornerebbero grezze).
    I valori grezzi restano nelle colonne ``*_raw``: la pagina può mostrarli a confronto.
    L'effetto **fuori campione** della calibrazione non è questo: è misurato walk-forward da
    ``fda calibrate`` e salvato in ``calibration.metrics``.
    """
    if df.empty or cal is None or cal.is_identity:
        return df
    out = df.copy()
    lh = pd.to_numeric(out["lambda_home"], errors="coerce").to_numpy(float)
    la = pd.to_numeric(out["lambda_away"], errors="coerce").to_numpy(float)
    rho = (np.nan_to_num(pd.to_numeric(out["dc_rho"], errors="coerce").to_numpy(float), nan=0.0)
           if "dc_rho" in out.columns else np.zeros(len(out)))
    s_lh, s_la, s_rho = cal.apply_many(lh, la, rho)
    m = grid_markets_many(tau_grid_many(s_lh, s_la, s_rho, size=11))
    for key in ("p_home", "p_draw", "p_away", "p_over15", "p_over25", "p_over35", "p_btts",
                "p_home_clean_sheet", "p_away_clean_sheet"):
        if key in out.columns:
            out[f"{key}_raw"] = out[key].to_numpy()
            out[key] = m[key]
    out["p_1x"] = m["p_home"] + m["p_draw"]
    out["p_12"] = m["p_home"] + m["p_away"]
    out["p_x2"] = m["p_draw"] + m["p_away"]
    out["lambda_home_raw"], out["lambda_away_raw"], out["rho_raw"] = lh, la, rho
    out["lambda_home"], out["lambda_away"], out["dc_rho"] = s_lh, s_la, s_rho
    out["lambda_scale"] = float(cal.lambda_scale)
    out["rho_shift"] = float(cal.rho_shift)
    out["calibration_version"] = cal.version
    return out


def observed_flags(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Esiti osservati dei mercati binari (bool per riga), stessa definizione della pagina."""
    tot = df["home_goals"].to_numpy(dtype=float) + df["away_goals"].to_numpy(dtype=float)
    hg = df["home_goals"].to_numpy(dtype=float)
    ag = df["away_goals"].to_numpy(dtype=float)
    return {"over15": tot > 1.5, "over25": tot > 2.5, "over35": tot > 3.5,
            "btts": (hg > 0) & (ag > 0), "d1x": hg >= ag, "d12": hg != ag, "dx2": hg <= ag,
            "cs_h": ag == 0, "cs_a": hg == 0}


def _mean_or_nan(x: Any) -> float:
    """Media senza avvisi quando non c'è niente da mediare (λ assenti, mercati non calcolati)."""
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else float("nan")


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
    n = len(df)
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
        k_mk = round(float(y.sum()))
        lo, hi = wilson_interval(k_mk, n_mk)
        prev = float(pr.mean())
        brier = float(((pr - y) ** 2).mean())
        base = float(y.mean())
        markets.append({"label": label, "n": n_mk, "k": k_mk, "prev": prev, "obs": base,
                        "lo": lo, "hi": hi,
                        "outside": bool(not (lo <= prev <= hi)), "brier": brier,
                        "brier_base": float(((base - y) ** 2).mean()),
                        "delta": brier - float(((base - y) ** 2).mean())})
    tot = df["home_goals"].to_numpy(dtype=float) + df["away_goals"].to_numpy(dtype=float)
    lam = (pd.to_numeric(df["lambda_home"], errors="coerce").to_numpy(float)
           + pd.to_numeric(df["lambda_away"], errors="coerce").to_numpy(float)) \
        if {"lambda_home", "lambda_away"} <= set(df.columns) else np.full(n, np.nan)
    w = np.array([float(m["n"]) for m in markets]) if markets else np.zeros(0)
    brier_mercati = (float(np.average([m["brier"] for m in markets], weights=w))
                     if markets else float("nan"))
    brier_mercati_base = (float(np.average([m["brier_base"] for m in markets], weights=w))
                          if markets else float("nan"))
    out = {"n": n, "leagues": int(df["league_key"].nunique()) if "league_key" in df.columns else 1,
           "rps": rps, "naive": rps_naive, "delta": rps - rps_naive,
           "brier": float(((probs - onehot) ** 2).sum(1).mean()),
           "logloss": float(np.mean([log_loss(float(x)) for x in p_real])),
           "hit": float((probs.argmax(1) == oc).mean()), "calib": calib, "markets": markets,
           "brier_mercati": brier_mercati, "brier_mercati_base": brier_mercati_base,
           "lambda_media": _mean_or_nan(lam), "gol_osservati": _mean_or_nan(tot),
           "bias_lambda": _mean_or_nan(lam - tot),
           "pareggio_previsto": float(probs[:, 1].mean()),
           "pareggio_osservato": float((oc == 1).mean())}
    if "calibration_version" in df.columns:
        out["calibration_version"] = str(df["calibration_version"].iloc[0])
        out["lambda_scale"] = float(pd.to_numeric(df["lambda_scale"], errors="coerce").iloc[0])
        out["rho_shift"] = float(pd.to_numeric(df["rho_shift"], errors="coerce").iloc[0])
    if "model_version" in df.columns:
        mix = df["model_version"].astype(str).value_counts()
        out["model_versions"] = " · ".join(f"{k}: {v} gare" for k, v in mix.items())
    return out


# ---- monitoraggio mercati binari (docs/21 P3-b) ----------------------------------------------
#: stesse terne (colonna previsione, etichetta, chiave osservata) della pagina Accuratezza
#: (``SiteBuilder.MARKETS``): se cambiano lì, cambiano qui — il monitoraggio deve leggere
#: gli stessi mercati che la pagina dichiara «compatibili» o «fuori intervallo»
BINARY_MARKETS: tuple[tuple[str, str, str], ...] = (
    ("p_over15", "Over 1,5 gol", "over15"),
    ("p_over25", "Over 2,5 gol", "over25"),
    ("p_over35", "Over 3,5 gol", "over35"),
    ("p_btts", "Gol · entrambe a segno", "btts"),
    ("p_1x", "Doppia chance 1X", "d1x"),
    ("p_12", "Doppia chance 12", "d12"),
    ("p_x2", "Doppia chance X2", "dx2"),
    ("p_home_clean_sheet", "Porta inviolata casa", "cs_h"),
    ("p_away_clean_sheet", "Porta inviolata trasferta", "cs_a"),
)

#: gare minime per lega perché il suo segnale conti nel verdetto
MIN_LEAGUE_N_MARKETS: int = 150
#: leghe con segnale coerente necessarie per dichiarare un mercato «strutturale»
MIN_STRUCTURAL_LEAGUES: int = 5


def observed_markets(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Colonne osservate dei mercati binari, derivate dai gol (stessa logica della pagina)."""
    hg = df["home_goals"].to_numpy(dtype=float)
    ag = df["away_goals"].to_numpy(dtype=float)
    tot = hg + ag
    return {"over15": tot > 1.5, "over25": tot > 2.5, "over35": tot > 3.5,
            "btts": (hg > 0) & (ag > 0),
            "d1x": hg >= ag, "d12": hg != ag, "dx2": hg <= ag,
            "cs_h": ag == 0, "cs_a": hg == 0}


def market_monitor(df: pd.DataFrame, min_league_n: int = MIN_LEAGUE_N_MARKETS,
                   min_structural_leagues: int = MIN_STRUCTURAL_LEAGUES) -> pd.DataFrame:
    """Calibrazione dei mercati binari sul backtest fuori campione, con stabilità e leghe.

    Per ogni mercato: media prevista contro frequenza osservata con IC di Wilson
    sull'osservato (stessa formula della pagina Accuratezza), più tre letture che
    distinguono il bias vero dal rumore:
    - **metà cronologiche**: il segno dello scarto osservato−previsto deve ripetersi
      nelle due metà dello storico, altrimenti è un episodio;
    - **leghe**: quante leghe (con almeno ``min_league_n`` gare) mostrano lo stesso
      segno con la previsione fuori dal proprio IC;
    - **verdetto**: «strutturale» solo se lo scarto complessivo è fuori intervallo,
      almeno ``min_structural_leagues`` leghe concordano nel segno ed entrambe le metà
      pure; altrimenti «monitora» — e il modello non si tocca (regola del piano P3).
    """
    if df.empty or "home_goals" not in df.columns:
        return pd.DataFrame()
    d = pd.to_datetime(df["date"])
    if d.dt.tz is not None:
        d = d.dt.tz_localize(None)      # il backtest salvato è tz-aware: confronto in datetime64
    dv = d.to_numpy(dtype="datetime64[ns]")
    mid = pd.Timestamp(d.median()).to_datetime64()
    lgs_all = df["league_key"].to_numpy() if "league_key" in df.columns else None
    obs = observed_markets(df)
    rows: list[dict[str, Any]] = []
    for col, label, key in BINARY_MARKETS:
        if col not in df.columns:
            continue
        pr = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        y = obs[key].astype(float)
        ok = ~np.isnan(pr)
        if ok.sum() < 20:
            continue
        pr, y, dv_k = pr[ok], y[ok], dv[ok]
        lgs = lgs_all[ok] if lgs_all is not None else np.full(int(ok.sum()), "?")
        prev, observed = float(pr.mean()), float(y.mean())
        lo, hi = wilson_interval(round(float(y.sum())), len(y))
        outside = bool(not (lo <= prev <= hi))
        sign = 1.0 if observed > prev else -1.0
        halves: list[float | None] = []
        for mask in (dv_k < mid, dv_k >= mid):
            n_h = int(mask.sum())
            if n_h < 20:
                halves.append(None)
                continue
            ph, yh = float(pr[mask].mean()), float(y[mask].mean())
            lh, hh = wilson_interval(round(float(y[mask].sum())), n_h)
            halves.append(None if lh <= ph <= hh else (1.0 if yh > ph else -1.0))
        lg_out = 0
        for lg in sorted(set(map(str, lgs))):
            m = lgs == lg
            n_l = int(m.sum())
            if n_l < min_league_n:
                continue
            pl, yl = float(pr[m].mean()), float(y[m].mean())
            ll, hl = wilson_interval(round(float(y[m].sum())), n_l)
            if not (ll <= pl <= hl) and (1.0 if yl > pl else -1.0) == sign:
                lg_out += 1
        structural = bool(outside and lg_out >= min_structural_leagues
                          and all(h == sign for h in halves if h is not None)
                          and all(h is not None for h in halves))
        rows.append({"market": key, "label": label, "n": len(y),
                     "prev": round(prev, 4), "obs": round(observed, 4),
                     "lo": round(lo, 4), "hi": round(hi, 4), "outside": outside,
                     "sign": sign, "half1": halves[0], "half2": halves[1],
                     "leagues_out": lg_out,
                     "verdict": "strutturale" if structural else "monitora"})
    return pd.DataFrame(rows)
