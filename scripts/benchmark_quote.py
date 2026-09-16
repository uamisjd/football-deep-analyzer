"""Benchmark modello vs quote di chiusura Pinnacle (7 leghe × 3 stagioni).

Scarica i CSV dal mirror già usato per NED1/POR1 e li confronta con le previsioni
fuori campione salvate in ``data/processed/backtest.parquet``. Le quote NON entrano
nel modello (decisione A, docs/19 §1.1): sono solo il riferimento esterno con cui
misurare la distanza del progetto dal mercato — la base naive è un avversario debole,
il mercato di chiusura è il metro più forte disponibile a costo zero.

Uso:
    python scripts/benchmark_quote.py                  # riepilogo a schermo
    python scripts/benchmark_quote.py --json out.json  # salva anche il JSON (artifact CI)
Esito atteso (misura 2026-09-14): n_valutate ≈ 4.372, delta ≈ +0,0096, IC95 interamente
positivo (il modello perde col mercato in 7/7 leghe: è il riferimento da chiudere).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from fda.models.predict import outcome_index
from fda.teams import canonical

BASE = "https://raw.githubusercontent.com/huhao930422-debug/football-odds-mirror/main/data"
DIRS = {"ENG1": "premier-league", "ESP1": "la-liga", "FRA1": "ligue-1", "GER1": "bundesliga",
        "ITA1": "serie-a", "NED1": "eredivisie", "POR1": "primeira-liga"}
SEASONS = ("2324", "2425", "2526")
CACHE = Path("data/cache/odds")


def scarica(http=None) -> pd.DataFrame:
    """Scarica (con cache 30 giorni) i CSV football-data del mirror con le quote di chiusura."""
    from fda.http import HttpClient
    http = http or HttpClient(name="odds-mirror", rate_limit_s=1.0, max_requests=40)
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for lg, d in DIRS.items():
        for s in SEASONS:
            url = f"{BASE}/{d}/season-{s}.csv"
            f = CACHE / f"{d}-{s}.csv"
            if not f.exists():
                f.write_bytes(http.get_bytes(url, ttl_h=24 * 30))
            c = pd.read_csv(f, encoding="latin-1", low_memory=False)
            if not {"PSCH", "PSCD", "PSCA"}.issubset(c.columns):
                continue
            keep = [x for x in ("HomeTeam", "AwayTeam", "FTHG", "FTAG", "PSCH", "PSCD", "PSCA",
                                "B365>2.5", "B365<2.5") if x in c.columns]
            c = c[["Date"] + keep].copy()
            c["lg"] = lg
            c["date"] = pd.to_datetime(c["Date"], dayfirst=True, errors="coerce")
            out.append(c.drop(columns=["Date"]))
    return pd.concat(out, ignore_index=True)


def devig(h, d, a) -> np.ndarray:
    """Quote decimali → probabilità senza margine (normalizzazione semplice)."""
    p = np.column_stack([1 / pd.to_numeric(h, errors="coerce"),
                         1 / pd.to_numeric(d, errors="coerce"),
                         1 / pd.to_numeric(a, errors="coerce")])
    ok = np.isfinite(p).all(1) & (p > 0).all(1)
    out = np.full_like(p, np.nan)
    out[ok] = p[ok] / p[ok].sum(1, keepdims=True)
    return out


def rps(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    """RPS per riga (stessa definizione del progetto, vettorializzata per il benchmark)."""
    return ((np.cumsum(P, 1) - np.cumsum(o, 1)) ** 2).sum(1) / 2.0


def misura(bt: pd.DataFrame, od: pd.DataFrame, draws: int = 4000, seed: int = 11) -> dict:
    """Aggancia backtest e quote (nomi canonici + lega + data) e misura modello vs mercato."""
    from fda.models.lab import paired_bootstrap

    bt = bt.copy()
    btd = pd.to_datetime(bt["date"])
    bt["date"] = (btd.dt.tz_localize(None) if getattr(btd.dt, "tz", None) else btd).dt.normalize()
    od = od.copy()
    od["HomeTeam"] = od["HomeTeam"].map(canonical).str.strip()
    od["AwayTeam"] = od["AwayTeam"].map(canonical).str.strip()
    m = bt.merge(od, left_on=["league_key", "date", "home", "away"],
                 right_on=["lg", "date", "HomeTeam", "AwayTeam"], how="inner")
    P = devig(m.PSCH, m.PSCD, m.PSCA)
    M = np.column_stack([m.p_home, m.p_draw, m.p_away]).astype(float)
    o = np.eye(3)[[outcome_index(int(h), int(a)) for h, a in zip(m.FTHG, m.FTAG)]]
    ok = np.isfinite(P).all(1)
    P, M, o, mm = P[ok], M[ok], o[ok], m[ok]
    d = rps(M, o) - rps(P, o)
    lo, hi = paired_bootstrap(np.asarray(d, float), draws=draws, seed=seed)
    per_lega = (pd.DataFrame({"lg": mm["league_key"].values, "d": d, "m": rps(M, o), "p": rps(P, o)})
                .groupby("lg").agg(n=("d", "size"), modello=("m", "mean"),
                                   mercato=("p", "mean"), delta=("d", "mean")).round(5))
    return {"n_agganciate": len(m), "n_valutate": int(np.count_nonzero(ok)),
            "rps_modello": float(rps(M, o).mean()), "rps_mercato": float(rps(P, o).mean()),
            "delta": float(d.mean()), "ic95": [float(lo), float(hi)],
            "leghe_vinte": int((per_lega["delta"] < 0).sum()), "per_lega": per_lega.to_dict("index")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None, help="scrive il risultato in questo file")
    args = ap.parse_args()
    bt = pd.read_parquet("data/processed/backtest.parquet")
    od = scarica()
    res = misura(bt, od)
    print(json.dumps({k: v for k, v in res.items() if k != "per_lega"}, indent=2))
    print(pd.DataFrame(res["per_lega"]).T.to_string())
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
