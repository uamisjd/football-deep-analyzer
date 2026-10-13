"""Esperimento dc_xg v1, isolato dal Parquet pubblico e dalla produzione (docs/92)."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import lab
from .calibration import Calibration
from .xg import FALLBACK_LEAGUES

log = logging.getLogger(__name__)
PROTOCOL = "dc_xg_v1"
CUTOFF = pd.Timestamp("2026-10-12T13:10:00Z")
STEP_DAYS = 90
MIN_TRAIN = 800
MIN_EVAL = 200
MIN_LEAGUES = 5
BOOT_DRAWS = 2000
BOOT_SEED = 11
LEAGUE_KEYS = {"EPL": "ENG1", "La_Liga": "ESP1", "Serie_A": "ITA1",
               "Bundesliga": "GER1", "Ligue_1": "FRA1"}
MATCH_KEYS = ["date", "league_key", "home", "away"]
PROB_COLS = ["p_home", "p_draw", "p_away"]
INPUT_HASHES = {
    "understat_matches.parquet": "687d76830e96ff9dea6672764aa1e20e326ca679361114071ff03af798bb5047",
    "history.parquet": "3927c7dfdfefdf1ff8d703524949659cfead26385871b1952522250811a4174c",
}


def _check_goals(frame: pd.DataFrame) -> None:
    goals = frame[["home_goals", "away_goals"]].to_numpy(float, na_value=np.nan)
    if not np.isfinite(goals).all() or (goals < 0).any() or not np.equal(goals, np.round(goals)).all():
        raise ValueError("storico: gol mancanti, non finiti, negativi o non interi")


def prepare_history(understat: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Stesso campione per entrambi: ID Understat per cinque leghe, storico per NED/POR."""
    u = understat.copy()
    if not u["is_result"].isin([True, False]).all():
        raise ValueError("Understat: flag risultato non valido")
    u["date"] = pd.to_datetime(u["utc_kickoff"], utc=True, errors="raise")
    u = u[u["is_result"].eq(True) & u["season"].between(2021, 2026)].copy()
    if u["date"].isna().any():
        raise ValueError("Understat: gara finita senza data")
    u = u[u["date"] < CUTOFF].copy()
    if u["understat_id"].isna().any() or u["understat_id"].duplicated().any():
        raise ValueError("Understat: ID gara mancanti o duplicati")
    if not set(u["league_slug"]) <= set(LEAGUE_KEYS):
        raise ValueError("Understat: campionati fuori protocollo")
    for side in ("home", "away"):
        ids = pd.to_numeric(u[f"{side}_id"], errors="coerce").to_numpy(float, na_value=np.nan)
        if not np.isfinite(ids).all() or not np.equal(ids, np.round(ids)).all():
            raise ValueError("Understat: ID squadra non validi")
        u[side] = "understat:" + u[f"{side}_id"].astype(int).astype(str)
    xg = u[["home_xg", "away_xg"]].to_numpy(float, na_value=np.nan)
    if not np.isfinite(xg).all() or (xg < 0).any():
        raise ValueError("Understat: xG mancanti o non validi")
    u["league_key"] = u["league_slug"].map(LEAGUE_KEYS)
    u["source"] = "understat"
    _check_goals(u)

    h = history[history["league_key"].isin(FALLBACK_LEAGUES)].copy()
    h["date"] = pd.to_datetime(h["date"], utc=True, errors="raise")
    if h["date"].isna().any():
        raise ValueError("storico fallback: date mancanti")
    h["season"] = h["season"].astype(str).str[:4].astype(int)
    h = h[h["season"].between(2021, 2026) & (h["date"] < CUTOFF)].copy()
    h["home_xg"], h["away_xg"] = np.nan, np.nan
    h["source"] = "history"
    _check_goals(h)
    cols = MATCH_KEYS + ["season", "home_goals", "away_goals", "home_xg", "away_xg", "source"]
    out = pd.concat([u[cols], h[cols]], ignore_index=True)
    if out[MATCH_KEYS].isna().any().any() or out["home"].eq(out["away"]).any():
        raise ValueError("storico: chiavi mancanti o una squadra contro se stessa")
    if out.assign(day=out["date"].dt.normalize()).duplicated(["day", *MATCH_KEYS[1:]]).any():
        raise ValueError("storico: gara duplicata (anche con orari diversi)")
    return out.sort_values(MATCH_KEYS).reset_index(drop=True)


def eligible_matches(hist: pd.DataFrame, *, step_days: int = STEP_DAYS,
                     min_train: int = MIN_TRAIN) -> pd.DataFrame:
    """Calendario atteso indipendente dai fit: un fit fallito non può cambiare il campione."""
    h = hist.copy()
    h["date"] = pd.to_datetime(h["date"], utc=True).dt.tz_localize(None)
    expected = []
    for _, group in h.groupby("league_key"):
        g = group.sort_values("date").reset_index(drop=True)
        if len(g) <= min_train:
            continue
        start = g["date"].iloc[min_train].normalize()
        while start <= g["date"].max():
            before = g[g["date"] < start]
            after = g[(g["date"] >= start) & (g["date"] < start + pd.Timedelta(days=step_days))]
            if len(before) >= min_train and not after.empty:
                known = set(before["home"]) | set(before["away"])
                after = after[after["home"].isin(known) & after["away"].isin(known)]
                expected.append(after[MATCH_KEYS].assign(expected_train=len(before),
                                                        expected_train_max=before["date"].max(),
                                                        expected_window_start=start))
            start += pd.Timedelta(days=step_days)
    columns = MATCH_KEYS + ["expected_train", "expected_train_max", "expected_window_start"]
    return pd.concat(expected, ignore_index=True) if expected else pd.DataFrame(columns=columns)


def validate_pairs(rows: pd.DataFrame, expected: pd.DataFrame) -> pd.DataFrame:
    """Boccia dati/campioni ambigui e torna il confronto esatto, con la baseline a fianco."""
    keys = (lab.BASELINE, lab.XG_CANDIDATE.key)
    if rows.empty or set(rows["candidate"]) != set(keys):
        raise ValueError("esperimento: mancano il riferimento o il candidato")
    if rows.duplicated(["candidate", *MATCH_KEYS]).any():
        raise ValueError("esperimento: previsioni duplicate")
    probabilities = rows[PROB_COLS].to_numpy(float, na_value=np.nan)
    if (not np.isfinite(probabilities).all() or (probabilities < 0).any()
            or (probabilities > 1).any()
            or not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-9, rtol=0)):
        raise ValueError("esperimento: probabilità non valide")
    expected_keys = pd.MultiIndex.from_frame(expected[MATCH_KEYS])
    for key in keys:
        r = rows[rows["candidate"].eq(key)]
        actual_keys = pd.MultiIndex.from_frame(r[MATCH_KEYS])
        if len(actual_keys) != len(expected_keys) or set(actual_keys) != set(expected_keys):
            raise ValueError(f"esperimento: campione incompleto o extra per {key}")
        check = r.merge(expected, on=MATCH_KEYS, validate="one_to_one")
        if (not check["n_train"].eq(check["expected_train"]).all()
                or not check["train_max"].eq(check["expected_train_max"]).all()
                or not check["window_start"].eq(check["expected_window_start"]).all()
                or not check["train_max"].lt(check["window_start"]).all()
                or not check["window_start"].le(check["date"]).all()):
            raise ValueError("esperimento: prefisso temporale del fit non valido")
        for _, league in r.groupby("league_key"):
            windows = league.groupby("window_start", sort=True)
            n_before = 0
            for _, window in windows:
                if not window["calibration_n"].eq(n_before).all():
                    raise ValueError("esperimento: calibrazione non dalle sole finestre precedenti")
                n_before += len(window)
    ref = rows[rows["candidate"].eq(lab.BASELINE)]
    cand = rows[rows["candidate"].eq(lab.XG_CANDIDATE.key)]
    joined = cand.merge(ref, on=MATCH_KEYS, suffixes=("", "_ref"), validate="one_to_one")
    if not joined["outcome"].eq(joined["outcome_ref"]).all():
        raise ValueError("esperimento: esiti non appaiati")
    fallback = joined["league_key"].isin(FALLBACK_LEAGUES)
    if not joined["uses_xg"].eq(~fallback).all() or joined["uses_xg_ref"].any():
        raise ValueError("esperimento: copertura xG o fallback non conforme")
    fallback_cols = PROB_COLS + ["lambda_home", "lambda_away", "rho", "lambda_scale"]
    if not np.allclose(joined.loc[fallback, fallback_cols].to_numpy(float),
                       joined.loc[fallback, [c + "_ref" for c in fallback_cols]].to_numpy(float),
                       atol=1e-12, rtol=0):
        raise ValueError("esperimento: il fallback ha cambiato il riferimento")
    return joined


def promotion(n: int, n_xg: int, hi: float, better: int) -> bool:
    """La regola 5/7 non diventa 5/5; i fallback non gonfiano l'evidenza xG minima."""
    return bool(n >= MIN_EVAL and n_xg >= MIN_EVAL and np.isfinite(hi)
                and hi < 0 and better >= MIN_LEAGUES)


def report_results(hist: pd.DataFrame, rows: pd.DataFrame, paired: pd.DataFrame) -> dict[str, Any]:
    """RPS indipendente per lega e controllo del riepilogo comune del laboratorio."""
    def rps(frame: pd.DataFrame, suffix: str = "") -> np.ndarray:
        p1 = frame[f"p_home{suffix}"].to_numpy(float)
        p1x = p1 + frame[f"p_draw{suffix}"].to_numpy(float)
        outcome = frame["outcome"].to_numpy(int)
        return ((p1 - (outcome == 0)) ** 2 + (p1x - (outcome <= 1)) ** 2) / 2

    paired = paired.copy()
    paired["rps_xg"] = rps(paired)
    paired["rps_ref"] = rps(paired, "_ref")
    paired["delta"] = paired["rps_xg"] - paired["rps_ref"]
    per = []
    for key, g in paired.groupby("league_key"):
        per.append({"league_key": key, "n": len(g), "xg_used": bool(g["uses_xg"].all()),
                    "rps_ref": float(g["rps_ref"].mean()), "rps_xg": float(g["rps_xg"].mean()),
                    "delta_rps": float(g["delta"].mean())})
    summary = lab.summarize(rows, baseline=lab.BASELINE, draws=BOOT_DRAWS)
    candidate = summary[summary["candidate"].eq(lab.XG_CANDIDATE.key)].iloc[0]
    if not np.isclose(candidate["delta_rps"], paired["delta"].mean(), atol=1e-12, rtol=0):
        raise ValueError("RPS indipendente e laboratorio discordano")
    n_xg = int(paired["uses_xg"].sum())
    better = sum(r["xg_used"] and r["delta_rps"] < 0 for r in per)
    passes = promotion(len(paired), n_xg, float(candidate["delta_rps_hi95"]), better)
    counts = hist.groupby(["league_key", "season"]).size().rename("n").reset_index()
    return {
        "protocol": PROTOCOL, "cutoff_utc": CUTOFF.isoformat(),
        "settings": {"step_days": STEP_DAYS, "min_train": MIN_TRAIN,
                     "bootstrap_draws": BOOT_DRAWS, "bootstrap_seed": BOOT_SEED,
                     "rho_shift": 0.0, "self_calibrate": True, "strict_fits": True,
                     "min_eval": MIN_EVAL, "min_leagues_better": MIN_LEAGUES,
                     "xi": 0.0018, "shrink": 8.0, "w_dc": 0.7},
        "input_games": len(hist), "input_by_season": counts.to_dict("records"),
        "n": len(paired), "n_xg": n_xg, "n_fallback": len(paired) - n_xg,
        "excluded_burnin_or_unseen": len(hist) - len(paired),
        "eval_from_utc": str(paired["date"].min()), "eval_to_utc": str(paired["date"].max()),
        "summary": json.loads(summary.to_json(orient="records", double_precision=15)),
        "per_league": per, "leagues_better": better, "leagues_required": 7,
        "passes": passes, "promoted": False,
    }


def run(data_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Esegue una sola volta la ricetta fissa; scrive esclusivamente nell'area esperimento."""
    data_dir, output_dir = Path(data_dir).resolve(), Path(output_dir).resolve()
    if output_dir == data_dir or output_dir.is_relative_to(data_dir):
        raise ValueError("output esperimento vietato dentro la cartella dei dati di produzione")
    hashes = {name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest() for name in INPUT_HASHES}
    if hashes != INPUT_HASHES:
        raise ValueError("snapshot diverso da docs/92: recuperare i due input dal commit 514309d; "
                         "non si cambia il campione dopo averne visto l'esito")
    hist = prepare_history(pd.read_parquet(data_dir / "understat_matches.parquet"),
                           pd.read_parquet(data_dir / "history.parquet"))
    if len(hist) != 11179 or set(hist["league_key"]) != set(LEAGUE_KEYS.values()) | FALLBACK_LEAGUES:
        raise ValueError("campione diverso dalle 11.179 gare / sette leghe preregistrate")
    expected = eligible_matches(hist)
    baseline = next(c for c in lab.CANDIDATES if c.key == lab.BASELINE)
    log.info("%s: %d gare, %d eleggibili, due ricette fisse", PROTOCOL, len(hist), len(expected))
    frames = []
    for key, group in hist.groupby("league_key"):
        log.info("%s: inizio walk-forward su %d gare", key, len(group))
        frames.append(lab.walk_forward(group, (baseline, lab.XG_CANDIDATE), step_days=STEP_DAYS,
                                       min_train=MIN_TRAIN, calibration=Calibration(),
                                       self_calibrate=True, strict_fits=True))
        log.info("%s: %d previsioni prodotte", key, len(frames[-1]))
    rows = pd.concat(frames, ignore_index=True)
    paired = validate_pairs(rows, expected)
    report = report_results(hist, rows, paired)
    report["input_sha256"] = hashes
    report["versions"] = {name: version(name) for name in ("numpy", "pandas", "scipy", "penaltyblog")}
    report["versions"]["python"] = platform.python_version()
    report["code_sha256"] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                             for name in ("xg.py", "lab_xg.py", "lab.py", "predict.py",
                                          "calibration.py", "dc_grid.py")}
    # Serializzare prima dei file: un NaN/Inf nel verdetto fa fallire il run.
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    hist.to_parquet(output_dir / "history.parquet", index=False, compression="zstd")
    rows.to_parquet(output_dir / "rows.parquet", index=False, compression="zstd")
    paired.to_parquet(output_dir / "paired.parquet", index=False, compression="zstd")
    (output_dir / "report.json").write_text(payload)
    return report
