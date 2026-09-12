"""Analisi avanzate derivate — nessun dato inventato.

Funzioni pure (griglia Dixon-Coles, probabilità in-play, corsa xG, qualità tiri,
scontro di stili). Ogni numero è una funzione esplicita di λ/ρ del modello, dei
tiri FotMob o delle medie di stagione già nello store.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..models.dc_grid import clamp_rho as _clamp_rho  # noqa: F401  (riesportato per i test)
from ..models.dc_grid import tau_grid

# Situazioni FotMob → italiano (valori reali in shots.parquet, 2026-09-11).
SITUATION_IT = {
    "RegularPlay": "azione manovrata",
    "FastBreak": "contropiede",
    "IndividualPlay": "azione individuale",
    "FromCorner": "calcio d'angolo",
    "SetPiece": "palla inattiva",
    "FreeKick": "punizione",
    "ThrowInSetPiece": "rimessa laterale",
    "Penalty": "rigore",
}
OPEN_PLAY = frozenset({"RegularPlay", "FastBreak", "IndividualPlay"})
SET_PLAY = frozenset({"FromCorner", "SetPiece", "FreeKick", "ThrowInSetPiece"})
PENALTY = "Penalty"

# Display della matrice: 0–5 gol per lato; la coda 6+ è dichiarata a parte.
MATRIX_CAP = 5


def dixon_coles_grid(lh: float, la: float, rho: float = 0.0, max_goals: int = 12) -> np.ndarray:
    """Matrice P(casa=i, trasferta=j) Dixon-Coles, troncata e rinormalizzata.

    τ(0,0)=1−λh λa ρ; τ(0,1)=1+λh ρ; τ(1,0)=1+λa ρ; τ(1,1)=1−ρ; altrimenti 1.
    È l'implementazione condivisa con i modelli (:mod:`fda.models.dc_grid`): la matrice
    mostrata sul sito e le probabilità pubblicate devono derivare dalla stessa formula.
    ``max_goals`` è il numero massimo di gol rappresentato (matrice di lato max_goals+1).
    λ ≤ 0 vengono trattate come ~0 (partita già chiusa / tempo residuo nullo);
    ρ fuori dai bound matematici viene clampato, mai scartato.
    """
    return tau_grid(lh, la, rho, size=int(max_goals) + 1)


def grid_1x2(grid: np.ndarray) -> tuple[float, float, float]:
    """Somme 1 / X / 2 su una griglia (righe = gol casa, colonne = gol trasferta)."""
    ii, jj = np.indices(grid.shape)
    p_home = float(grid[ii > jj].sum())
    p_draw = float(grid[ii == jj].sum())
    p_away = float(grid[ii < jj].sum())
    return p_home, p_draw, p_away


def score_matrix(lh: float, la: float, rho: float = 0.0, cap: int = MATRIX_CAP) -> dict[str, Any]:
    """Vista 0–``cap`` della griglia, con coda e cella modale."""
    g = dixon_coles_grid(lh, la, rho, max_goals=max(cap + 8, 12))
    block = g[: cap + 1, : cap + 1]
    p_tail = round(max(0.0, 1.0 - float(block.sum())), 4)
    mode = tuple(int(x) for x in np.unravel_index(int(block.argmax()), block.shape))
    max_p = float(block.max())
    cells = []
    for i in range(cap + 1):
        row = []
        for j in range(cap + 1):
            p = float(g[i, j])
            row.append({"i": i, "j": j, "p": round(p, 4), "op": heat_opacity(p, max_p),
                        "mode": i == mode[0] and j == mode[1]})
        cells.append(row)
    ph, pd_, pa = grid_1x2(g)
    return {
        "cells": cells, "cap": cap, "p_tail": p_tail, "max_p": max_p,
        "mode": f"{mode[0]}-{mode[1]}", "mode_i": mode[0], "mode_j": mode[1],
        "p_home": ph, "p_draw": pd_, "p_away": pa,
        "lambda_home": float(lh), "lambda_away": float(la), "rho": float(rho or 0.0),
    }


def heat_opacity(p: float, max_p: float) -> float:
    """Opacità 0,12–1,00 della cella, relativa al massimo della matrice visibile."""
    if max_p <= 0:
        return 0.12
    return round(0.12 + 0.88 * min(max(p / max_p, 0.0), 1.0), 3)


def state_probs(hg: int, ag: int, lh: float, la: float, minute: float,
                rho: float = 0.0) -> tuple[float, float, float]:
    """P(1/X/2) a un minuto dato il punteggio corrente.

    Tempo residuo ∝ (90 − min(minuto, 90))/90. Al calcio d'inizio si usa la
    griglia Dixon-Coles completa (con ρ). Nei minuti successivi il residuo è
    Poisson indipendente (ρ=0): ρ è una correzione da partita intera, non
    scalabile al residuo senza una stima dedicata.
    """
    t = float(minute)
    rem = max(0.0, (90.0 - min(max(t, 0.0), 90.0)) / 90.0)
    if rem <= 1e-9:
        if hg > ag:
            return 1.0, 0.0, 0.0
        if hg == ag:
            return 0.0, 1.0, 0.0
        return 0.0, 0.0, 1.0
    use_rho = float(rho or 0.0) if t <= 0.0 else 0.0
    add = dixon_coles_grid(lh * rem, la * rem, use_rho, max_goals=12)
    ii, jj = np.indices(add.shape)
    fh, fa = hg + ii, ag + jj
    p_home = float(add[fh > fa].sum())
    p_draw = float(add[fh == fa].sum())
    p_away = float(add[fh < fa].sum())
    return p_home, p_draw, p_away


def wp_path(goals: list[dict[str, Any]], lh: float, la: float,
            rho: float = 0.0) -> list[dict[str, Any]]:
    """Traiettoria 1X2: calcio d'inizio + un punto dopo ogni gol.

    ``goals`` ordinati: ``minute``, ``home`` (squadra **a cui il gol è attribuito**),
    ``player``. Gli autogol sono già contabilizzati dalla fonte (vedi
    :meth:`MatchAnalysis.timeline`): qui ``home`` si usa tal quale, senza ribaltamenti.
    """
    pts = []
    hg = ag = 0
    ph, pd_, pa = state_probs(0, 0, lh, la, 0.0, rho)
    pts.append({"minute": 0.0, "hg": 0, "ag": 0, "p_home": ph, "p_draw": pd_, "p_away": pa,
                "event": None, "player": None, "scorer_home": None})
    for g in goals:
        minute = g.get("minute")
        if minute is None or (isinstance(minute, float) and pd.isna(minute)):
            continue
        added = g.get("added") or 0
        t = float(minute) + float(added)
        scored_home = bool(g.get("home"))
        if scored_home:
            hg += 1
        else:
            ag += 1
        ph, pd_, pa = state_probs(hg, ag, lh, la, t, rho)
        pts.append({"minute": t, "hg": hg, "ag": ag, "p_home": ph, "p_draw": pd_, "p_away": pa,
                    "event": "goal", "player": g.get("player"), "scorer_home": scored_home})
    max_t = max(90.0, max(p["minute"] for p in pts))
    for p in pts:
        x = round(6 + min(max(p["minute"], 0.0), max_t) / max_t * 408, 1)
        p["x"] = x
        p["y_h"] = round(8 + (1.0 - p["p_home"]) * 108, 1)
        p["y_d"] = round(8 + (1.0 - p["p_draw"]) * 108, 1)
        p["y_a"] = round(8 + (1.0 - p["p_away"]) * 108, 1)
    return pts


def _shot_minute(r: Any) -> float | None:
    m = getattr(r, "minute", None)
    if m is None or (isinstance(m, float) and pd.isna(m)):
        return None
    added = getattr(r, "minute_added", None)
    extra = 0.0 if added is None or (isinstance(added, float) and pd.isna(added)) else float(added)
    return float(m) + extra


def xg_race(shots: pd.DataFrame, home_id: int, away_id: int) -> dict[str, Any] | None:
    """Corsa xG: cumulativo per minuto, autogol esclusi (non sono tiri della squadra)."""
    if shots is None or shots.empty:
        return None
    s = shots.dropna(subset=["xg"]).copy()
    if "is_own_goal" in s.columns:
        s = s[~s.is_own_goal.fillna(False)]
    rows = []
    for r in s.itertuples(index=False):
        t = _shot_minute(r)
        if t is None:
            continue
        tid = int(r.team_id)
        if tid not in (home_id, away_id):
            continue
        rows.append((t, tid, float(r.xg),
                    bool(getattr(r, "event_type", None) == "Goal"),
                    getattr(r, "player_name", None)))
    if not rows:
        return None
    rows.sort(key=lambda x: x[0])
    ch = ca = 0.0
    pts: list[dict[str, Any]] = [{"minute": 0.0, "home": 0.0, "away": 0.0}]
    goals: list[dict[str, Any]] = []
    for t, tid, xg, is_goal, player in rows:
        if tid == home_id:
            ch += xg
        else:
            ca += xg
        pts.append({"minute": t, "home": round(ch, 4), "away": round(ca, 4)})
        if is_goal:
            goals.append({"minute": t, "home": tid == home_id, "player": player,
                          "home_cum": round(ch, 4), "away_cum": round(ca, 4)})
    max_t = max(90.0, max(p["minute"] for p in pts))
    max_xg = max(ch, ca, 0.5)

    def _xy(minute: float, value: float) -> tuple[float, float]:
        x = round(6 + min(max(minute, 0.0), max_t) / max_t * 408, 1)
        y = round(148 - min(max(value, 0.0), max_xg) / max_xg * 128, 1)
        return x, y

    for p in pts:
        p["x"], p["y_h"] = _xy(p["minute"], p["home"])
        _, p["y_a"] = _xy(p["minute"], p["away"])
    for g in goals:
        g["x"], g["y"] = _xy(g["minute"], g["home_cum"] if g["home"] else g["away_cum"])
    poly_h = " ".join(f"{p['x']},{p['y_h']}" for p in pts)
    poly_a = " ".join(f"{p['x']},{p['y_a']}" for p in pts)
    return {"points": pts, "goals": goals, "home_xg": round(ch, 3), "away_xg": round(ca, 3),
            "n": len(rows), "poly_h": poly_h, "poly_a": poly_a, "max_xg": round(max_xg, 2)}


def _bucket(situation: Any) -> str:
    if not isinstance(situation, str):
        return "other"
    if situation in OPEN_PLAY:
        return "open"
    if situation in SET_PLAY:
        return "set"
    if situation == PENALTY:
        return "pen"
    return "other"


def shot_quality(shots: pd.DataFrame, team_id: int) -> dict[str, Any] | None:
    """Profilo tiri di una squadra: volume, qualità, palle inattive, xGOT.

    Autogol esclusi. ``finishing`` = gol − xGOT (positivo = ha superato il
    portiere rispetto alla qualità dei tiri in porta). ``over_xg`` = gol − xG.
    """
    if shots is None or shots.empty:
        return None
    s = shots[shots.team_id == team_id]
    if "is_own_goal" in s.columns:
        s = s[~s.is_own_goal.fillna(False)]
    s = s.dropna(subset=["xg"])
    if s.empty:
        return None
    n = int(len(s))
    xg = float(s.xg.sum())
    xgot = float(s.xgot.fillna(0).sum()) if "xgot" in s.columns else 0.0
    goals = int((s.event_type == "Goal").sum()) if "event_type" in s.columns else 0
    buckets: dict[str, dict[str, float]] = {}
    for name in ("open", "set", "pen", "other"):
        sub = s[s.situation.map(_bucket) == name] if "situation" in s.columns else s.iloc[0:0]
        buckets[name] = {"n": int(len(sub)), "xg": float(sub.xg.sum()) if len(sub) else 0.0}
    best = s.sort_values("xg", ascending=False).iloc[0]
    return {
        "n": n, "xg": xg, "xgot": xgot, "goals": goals,
        "xg_per_shot": xg / n,
        "inside": int(s.is_inside_box.fillna(False).sum()) if "is_inside_box" in s.columns else 0,
        "on_target": int(s.is_on_target.fillna(False).sum()) if "is_on_target" in s.columns else 0,
        "open": buckets["open"], "set": buckets["set"], "pen": buckets["pen"],
        "over_xg": goals - xg, "finishing": goals - xgot,
        "best": {
            "player": best.player_name if "player_name" in s.columns else None,
            "xg": float(best.xg),
            "minute": (int(best.minute)
                       if "minute" in s.columns and pd.notna(best.minute) else None),
            "situation": (SITUATION_IT.get(str(best.situation), None)
                          if "situation" in s.columns else None),
        },
    }


def style_rows(home: dict[str, Any] | None, away: dict[str, Any] | None,
               pred: dict[str, Any] | None) -> dict[str, Any] | None:
    """Card «Scontro tattico»: λ, DC attacco/difesa, xG split, PPDA, deep.

    Una riga compare solo se almeno un lato ha il dato. None se non c'è nulla
    di confrontabile (niente previsione e niente stile di stagione).
    """
    h, a = home or {}, away or {}
    pred = pred or {}
    rows: list[dict[str, Any]] = []

    def add(label: str, hv, av, higher: bool | None = True, nd: int = 2) -> None:
        if hv is None and av is None:
            return
        best = None
        if hv is not None and av is not None and higher is not None and hv != av:
            best = "h" if (hv > av) == higher else "a"
        rows.append({"label": label, "h": hv, "a": av, "best": best, "nd": nd})

    add("Gol attesi (λ)", pred.get("lambda_home"), pred.get("lambda_away"), True)
    add("Attacco DC", pred.get("dc_attack_home"), pred.get("dc_attack_away"), True)
    add("Difesa DC (↓ meglio)", pred.get("dc_defence_home"), pred.get("dc_defence_away"), False)
    add("xG / gara", h.get("xg_pm"), a.get("xg_pm"), True)
    add("xGA / gara", h.get("xga_pm"), a.get("xga_pm"), False)
    add("xG azione manovrata / gara", h.get("open_pm"), a.get("open_pm"), True)
    add("xG palle inattive / gara", h.get("set_pm"), a.get("set_pm"), True)
    add("PPDA (↓ = più pressing)", h.get("ppda"), a.get("ppda"), False, 1)
    add("PPDA concesso", h.get("ppda_allowed"), a.get("ppda_allowed"), True, 1)
    add("Passaggi profondi / gara", h.get("deep"), a.get("deep"), True, 1)
    add("Passaggi profondi subiti / gara", h.get("deep_allowed"), a.get("deep_allowed"), False, 1)
    if not rows:
        return None
    notes = [
        "Attacco/difesa DC: parametri Dixon-Coles. Difesa più bassa = subisce meno.",
        "PPDA: passaggi concessi per azione difensiva (basso = più pressing).",
        "Passaggi profondi: completamenti negli ultimi ~20 m (Understat).",
        "xG azione / palle inattive: media sulle finite FotMob.",
    ]
    return {"rows": rows, "notes": notes}
