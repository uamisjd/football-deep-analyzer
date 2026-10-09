"""Benchmark RPS/Brier del modello contro il mercato, sulle stesse gare.

Modalità locale (docs/67): legge le quote già in history.parquet, nessuna rete né fit.
Il backtest è l'ensemble GREZZO fuori campione; non si applica una calibrazione stimata
sugli stessi esiti. Le quote si depurano del margine con la normalizzazione degli inversi.

Uso:
    python scripts/benchmark_quote.py --offline
    python scripts/benchmark_quote.py --offline --json data/cache/benchmark_history.json
    python scripts/benchmark_quote.py --offline --data percorso/processed

Senza --offline resta il benchmark mensile preesistente: scarica (o usa la cache dei)
CSV Pinnacle di chiusura, 7 leghe × 3 stagioni. Non si riduce silenziosamente quel
confronto alle sole leghe con quote locali. Le quote NON entrano nel modello o nel sito.
"""
from __future__ import annotations

import argparse
import hashlib
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


def quote_da_history(history: pd.DataFrame) -> pd.DataFrame:
    """Adattatore locale allo schema del benchmark, senza leggere o scaricare altro.

    I nomi PSCH/PSCD/PSCA qui sono solo lo schema comune: lo storico può contenere
    Pinnacle, medie o Bet365 e non conserva quale ripiego è stato usato (docs/67).
    Colonne quote assenti equivalgono a quote mancanti, mai a probabilità inventate.
    """
    names = {"league_key": "lg", "home": "HomeTeam", "away": "AwayTeam",
             "home_goals": "FTHG", "away_goals": "FTAG", "odds_home": "PSCH",
             "odds_draw": "PSCD", "odds_away": "PSCA", "date": "date"}
    return history.reindex(columns=list(names)).rename(columns=names)


def devig(h, d, a) -> np.ndarray:
    """Quote decimali valide (>1) → probabilità senza margine; altrimenti tutta la riga n.d."""
    odds = np.column_stack([pd.to_numeric(x, errors="coerce") for x in (h, d, a)]).astype(float)
    ok = np.isfinite(odds).all(1) & (odds > 1).all(1)
    out = np.full_like(odds, np.nan)
    inverses = 1 / odds[ok]
    out[ok] = inverses / inverses.sum(1, keepdims=True)
    return out


def rps(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    """RPS per riga, ordine 1-X-2, diviso per 2 (stessa definizione del progetto)."""
    return ((np.cumsum(P, 1) - np.cumsum(o, 1)) ** 2).sum(1) / 2.0


def brier(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    """Brier multiclasse: somma dei tre errori quadratici, scala 0–2 (non media /3)."""
    return ((P - o) ** 2).sum(1)


def _summary(r_model, r_market, b_model, b_market, draws: int, seed: int) -> dict:
    from fda.models.lab import paired_bootstrap

    def mean(values):
        return float(np.mean(values)) if len(values) else None

    def interval(values):
        lo, hi = paired_bootstrap(values, draws=draws, seed=seed)
        # <20 gare: il laboratorio non stima un intervallo. JSON valido, niente NaN o zeri.
        return [float(x) if np.isfinite(x) else None for x in (lo, hi)]

    delta, delta_brier = r_model - r_market, b_model - b_market
    return {"n": len(r_model), "rps_modello": mean(r_model), "rps_mercato": mean(r_market),
            "delta": mean(delta), "ic95": interval(delta),
            "brier_modello": mean(b_model), "brier_mercato": mean(b_market),
            "delta_brier": mean(delta_brier), "ic95_brier": interval(delta_brier)}


def misura(bt: pd.DataFrame, od: pd.DataFrame, draws: int = 4000, seed: int = 11) -> dict:
    """Join uno-a-uno per lega, giorno UTC e nomi canonici SU ENTRAMBI i lati.

    Metriche appaiate sugli stessi esiti: quote finite >1, vettori del modello validi,
    risultati coincidenti fra backtest e fonte delle quote. Duplicati → errore, non gare
    contate due volte. Copertura e scarti dichiarati anche per le leghe senza una misura.
    """
    bt, od = bt.copy(), od.copy()
    for frame, lg, home, away in ((bt, "league_key", "home", "away"),
                                  (od, "lg", "HomeTeam", "AwayTeam")):
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.normalize()
        frame[home] = frame[home].fillna("").map(canonical)
        frame[away] = frame[away].fillna("").map(canonical)
        if frame[[lg, "date"]].isna().any().any() or frame[[home, away]].eq("").any().any():
            raise ValueError("Chiavi di gara assenti: lega, data e squadre sono obbligatorie")
    keys = ["league_key", "date", "home", "away"]
    m = bt.merge(od, left_on=keys, right_on=["lg", "date", "HomeTeam", "AwayTeam"],
                 how="inner", validate="one_to_one").sort_values(keys, kind="stable")
    P = devig(m.PSCH, m.PSCD, m.PSCA)
    M = m[["p_home", "p_draw", "p_away"]].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    goals = m[["home_goals", "away_goals", "FTHG", "FTAG"]].apply(
        pd.to_numeric, errors="coerce").to_numpy(float)
    quotes_ok = np.isfinite(P).all(1)
    model_ok = (np.isfinite(M).all(1) & (M >= 0).all(1) & (M <= 1).all(1)
                & np.isclose(M.sum(1), 1, rtol=0, atol=1e-7))
    results_ok = (np.isfinite(goals).all(1) & (goals >= 0).all(1)
                  & (goals == np.floor(goals)).all(1)
                  & (goals[:, 0] == goals[:, 2]) & (goals[:, 1] == goals[:, 3]))
    if "outcome" in m:
        outcomes = np.where(goals[:, 0] > goals[:, 1], 0,
                            np.where(goals[:, 0] == goals[:, 1], 1, 2))
        results_ok &= pd.to_numeric(m.outcome, errors="coerce").to_numpy() == outcomes
    ok = quotes_ok & model_ok & results_ok
    mm = m.loc[ok]
    outcomes = np.eye(3)[[outcome_index(int(h), int(a)) for h, a in goals[ok, :2]]]
    rm, rp = rps(M[ok], outcomes), rps(P[ok], outcomes)
    bm, bp = brier(M[ok], outcomes), brier(P[ok], outcomes)
    result = _summary(rm, rp, bm, bp, draws, seed)
    result.pop("n")
    all_leagues = sorted(set(DIRS) | set(bt.league_key) | set(od.lg))
    per_league = {}
    for lg in all_leagues:
        selected = mm.league_key.to_numpy() == lg
        part = _summary(rm[selected], rp[selected], bm[selected], bp[selected], draws, seed)
        # Mantiene i nomi storici delle colonne RPS, usati nel benchmark mensile.
        part["modello"] = part.pop("rps_modello")
        part["mercato"] = part.pop("rps_mercato")
        part["n_backtest"] = int((bt.league_key == lg).sum())
        part["n_agganciate"] = int((m.league_key == lg).sum())
        per_league[lg] = part
    result.update(
        n_backtest=len(bt), n_agganciate=len(m), n_valutate=int(ok.sum()),
        n_non_agganciate=len(bt) - len(m),
        # Categorie disgiunte, in quest'ordine: somma scarti + valutate = agganciate.
        esclusioni={"quote_assenti_o_invalide": int((~quotes_ok).sum()),
                    "probabilita_modello_invalide": int((quotes_ok & ~model_ok).sum()),
                    "risultati_assenti_o_discordi": int((quotes_ok & model_ok & ~results_ok).sum())},
        leghe_valutate=sum(p["n"] > 0 for p in per_league.values()),
        leghe_vinte=sum(p["delta"] is not None and p["delta"] < 0 for p in per_league.values()),
        per_lega=per_league,
        periodo=([mm.date.min().date().isoformat(), mm.date.max().date().isoformat()]
                 if len(mm) else None),
        versioni_modello=({str(k): int(v) for k, v in mm.model_version.value_counts().items()}
                          if "model_version" in mm else {}),
        bootstrap={"draws": draws, "seed": seed, "unita": "gara appaiata", "min_gare": 20},
        modello="ensemble grezzo fuori campione; nessuna calibrazione a posteriori",
        convenzioni="delta = modello − mercato; RPS /2, Brier somma delle tre classi (0–2)")
    return result


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None, help="scrive il risultato in questo file")
    ap.add_argument("--offline", action="store_true",
                    help="usa esclusivamente history.parquet, zero richieste di rete")
    ap.add_argument("--data", type=Path, default=Path("data/processed"),
                    help="cartella dei Parquet locali")
    args = ap.parse_args(argv)
    inputs = [args.data / "backtest.parquet"]
    bt = pd.read_parquet(inputs[0])
    if args.offline:
        inputs.append(args.data / "history.parquet")
        od = quote_da_history(pd.read_parquet(inputs[1]))
    else:
        od = scarica()
    res = misura(bt, od)
    res["fonte_quote"] = ("history.parquet: priorità alla chiusura; fonte e ripiego non tracciati "
                          "per riga, non tutte certificabili come Pinnacle di chiusura"
                          if args.offline else "Pinnacle di chiusura: CSV PSCH/PSCD/PSCA")
    res["input_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    print(json.dumps({k: v for k, v in res.items() if k != "per_lega"}, indent=2,
                     ensure_ascii=False, allow_nan=False))
    table = pd.DataFrame(res["per_lega"]).T
    print(table[["n_backtest", "n", "modello", "mercato", "delta", "brier_modello",
                 "brier_mercato", "delta_brier"]].to_string())
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(res, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                          encoding="utf-8")


if __name__ == "__main__":
    main()
