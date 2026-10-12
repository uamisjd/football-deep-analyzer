"""Pagina pubblica «Laboratorio»: il verdetto dei candidati, calcolato dal Parquet.

Le righe arrivano da ``model_lab.parquet`` (scritto da ``fda lab``): una riga per candidato
e campionato, più le righe riassuntive con ``league_key == "ALL"``. Il verdetto non è scritto a
mano: applica il criterio di promozione di ``docs/13`` §6.5 (IC appaiato interamente negativo e
migliore in almeno 5 campionati su 7). Un candidato che lo supera **non entra in produzione da
solo**: la promozione è una decisione a parte (``docs/86``), e la pagina lo dice.
"""

from __future__ import annotations

from typing import Any

import re

import numpy as np
import pandas as pd

#: criterio di promozione (docs/13 §6.5)
MIN_LEAGUES_BETTER = 5
#: candidato di riferimento: la ricetta in produzione
BASELINE = "dc_elo_prod"


_DOC_REF = re.compile(r",?\s*docs/\d+[^,)]*")


def public_label(label: str) -> str:
    """Etichetta per il pubblico: via i rimandi interni ai documenti del repository."""
    out = _DOC_REF.sub("", label)
    return re.sub(r"\(\s*\)", "", out).strip()


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) else x


def verdict(delta: float | None, lo: float | None, hi: float | None, leagues_better: int,
            n_leagues: int, baseline: bool) -> str:
    """Verdetto leggibile su un candidato rispetto alla produzione (testo italiano)."""
    if baseline:
        return "riferimento"
    if delta is None or lo is None or hi is None:
        return "dato insufficiente"
    if lo > 0:
        return "peggiore della produzione"
    if hi < 0 and leagues_better >= MIN_LEAGUES_BETTER:
        return "passa il criterio, non promosso"
    if hi < 0:
        unita = "campionato" if leagues_better == 1 else "campionati"
        return f"migliore in media, ma solo in {leagues_better} {unita} su {n_leagues}"
    return "non distinguibile dalla produzione"


def lab_leaderboard(lab: pd.DataFrame) -> dict[str, Any] | None:
    """Trasforma ``model_lab`` in dati per la pagina. ``None`` se il riepilogo manca."""
    if lab is None or lab.empty or "league_key" not in lab.columns:
        return None
    summ = lab[lab["league_key"] == "ALL"].drop_duplicates("candidate")
    if summ.empty or BASELINE not in set(summ["candidate"]):
        return None
    per = lab[(lab["league_key"] != "ALL") & lab["rps"].notna()]
    rps_lg = per.pivot_table(index="league_key", columns="candidate", values="rps", aggfunc="first")
    leagues = sorted(rps_lg.index.tolist())
    base_lg = rps_lg[BASELINE] if BASELINE in rps_lg.columns else None

    rows: list[dict[str, Any]] = []
    for r in summ.itertuples(index=False):
        cand = str(r.candidate)
        n_better = 0
        if base_lg is not None and cand in rps_lg.columns:
            d = rps_lg[cand] - base_lg
            n_better = int((d.dropna() < 0).sum())
        delta, lo, hi = _f(r.delta_rps), _f(r.delta_rps_lo95), _f(r.delta_rps_hi95)
        is_base = cand == BASELINE
        rows.append({
            "candidate": cand,
            "label": public_label(str(r.label)) if isinstance(r.label, str) else cand,
            "n": int(r.n) if _f(r.n) is not None else None,
            "rps": _f(r.rps),
            "logloss": _f(r.logloss),
            "delta": None if is_base else delta,
            "lo": None if is_base else lo,
            "hi": None if is_base else hi,
            "leagues_better": None if is_base else n_better,
            "n_leagues": len(leagues),
            "verdict": verdict(delta, lo, hi, n_better, len(leagues), is_base),
            "passes": (not is_base) and lo is not None and hi is not None and hi < 0
                      and n_better >= MIN_LEAGUES_BETTER,
            "baseline": is_base,
        })
    rows.sort(key=lambda x: (x["delta"] is not None, x["delta"] if x["delta"] is not None else 0.0))

    # RPS per campionato dei candidati più significativi + produzione (tabella di dettaglio)
    detail_keys = [BASELINE] + [x["candidate"] for x in rows if not x["baseline"]][:5]
    detail = []
    for lg in leagues:
        cells = {}
        for k in detail_keys:
            v = rps_lg.at[lg, k] if k in rps_lg.columns else np.nan
            cells[k] = _f(v)
        detail.append({"league": lg, "cells": cells})

    n_eval = _f(summ.loc[summ["candidate"] == BASELINE, "n"].iloc[0])
    return {
        "rows": rows,
        "detail_keys": detail_keys,
        "detail": detail,
        "leagues": leagues,
        "n_candidates": len(rows),
        "n_passes": sum(1 for x in rows if x["passes"]),
        "n_eval": int(n_eval) if n_eval is not None else None,
        "baseline_rps": _f(summ.loc[summ["candidate"] == BASELINE, "rps"].iloc[0]),
        "labels": {x["candidate"]: x["label"] for x in rows},
    }
