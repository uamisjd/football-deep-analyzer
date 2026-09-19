"""Analisi avanzate derivate — nessun dato inventato.

Funzioni pure (griglia Dixon-Coles, probabilità in-play, corsa xG, qualità tiri,
scontro di stili). Ogni numero è una funzione esplicita di λ/ρ del modello, dei
tiri FotMob o delle medie di stagione già nello store.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from ..models.dc_grid import tau_grid
from .fmt import dec as _dec
from .fmt import int_it as _int_it
from .fmt import it_plural as _it_plural

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


GOALS_CAP = 6          # barre 0–6 gol; il resto è dichiarato come «7+»
GOAL_DOTS = 20         # quantile dotplot: 1 punto = 5 partite su 100


def goals_view(lh: float, la: float, rho: float = 0.0, cap: int = GOALS_CAP,
               dots: int = GOAL_DOTS) -> dict[str, Any]:
    """Distribuzione dei gol totali e quantile dotplot, dalla stessa griglia dei mercati.

    Due viste dello stesso oggetto (la matrice Dixon-Coles già pubblicata), perché la
    ricerca sulla comunicazione dell'incertezza (Hullman/Kay) mostra che le frequenze
    discrete — «1 punto = 5 partite su 100» — si leggono meglio di una densità continua
    e non invitano a cercare un valore «vero» dove c'è solo una distribuzione.

    ``cap`` è l'ultimo totale mostrato come barra; la massa oltre finisce in «7+».

    ``copertura`` è la massa che cade davvero fra ``q10`` e ``q90``: sempre > 80% per costruzione,
    ma non esattamente 80% né 90%, quindi è quella che va scritta in didascalia.
    """
    g = dixon_coles_grid(lh, la, rho, max_goals=max(cap + 9, 15))
    ii, jj = np.indices(g.shape)
    tot = ii + jj
    p = np.array([float(g[tot == t].sum()) for t in range(cap + 1)])
    tail = max(0.0, 1.0 - float(p.sum()))
    coda = f"{cap + 1}+"
    # La scala dell'istogramma deve essere il massimo DELLE barre che si disegnano, coda compresa.
    # Con pmax calcolato solo sui totali 0..cap la barra «7+» superava il 100% del contenitore —
    # 9 previsioni su 2.152, fino a height:183% con λ totale 4,7-5,5 — e invadeva il titolo della
    # card o veniva tagliata (docs/19 §3.4). Nessuna barra viene "schiacciata": le altezze restano
    # proporzionali alle probabilità, cambia solo quale barra occupa il 100% del riquadro.
    scala = float(max(p.max(), tail, 1e-9))
    moda = int(p.argmax())
    per100 = _per_cento(np.append(p, tail))
    bars = [{"g": t, "label": str(t), "p": round(float(p[t]), 4), "per100": int(per100[t]),
             "h": round(float(p[t]) / scala, 4), "mode": bool(t == moda)} for t in range(cap + 1)]
    bars.append({"g": cap + 1, "label": coda, "p": round(tail, 4),
                 "per100": int(per100[cap + 1]), "h": round(tail / scala, 4),
                 "mode": False, "tail": True})
    # quantili: il k-esimo punto sta a metà del k-esimo ventesimo di massa
    masses = np.append(p, tail)
    cdf = np.cumsum(masses)

    def _q(u: float) -> int:
        """Primo totale di gol la cui cumulata raggiunge ``u`` (mai oltre la coda)."""
        return int(min(cap + 1, np.searchsorted(cdf, u, side="left")))

    quantiles = [_q((k - 0.5) / dots) for k in range(1, dots + 1)]
    counts = {t: quantiles.count(t) for t in range(cap + 2)}
    # Intervallo centrale 10°-90° percentile, con la copertura **reale** pubblicata accanto.
    # La didascalia dichiarava «nel 90% dei casi il totale resta fra q10 e q90»: falso, perché
    # con F(q90) ≥ 0,90 e F(q10 − 1) < 0,10 la copertura garantita è > 80%, e la discretizzazione
    # la porta tipicamente a 85-93%. Allargarlo a 5°-95° renderebbe vera la frase «90%» ma
    # svuoterebbe l'informazione (l'intervallo diventa quasi sempre «fra 0 e 6», cioè tutto l'asse).
    # Si tiene quindi l'intervallo informativo e si pubblica il numero vero di quella gara:
    # nessun tondo dichiarato a priori, e la lettura resta verificabile.
    q10, q90 = _q(0.10), _q(0.90)
    copertura = float(cdf[q90] - (cdf[q10 - 1] if q10 > 0 else 0.0)) * 100.0
    # tutte le colonne, anche vuote: l'asse dei gol resta allineato con l'istogramma
    columns = [{"g": t, "n": counts[t], "label": f"{t}" if t <= cap else f"{cap + 1}+"}
               for t in range(cap + 2)]
    return {
        "bars": bars, "cap": cap, "moda": moda, "media": round(float((g * tot).sum()), 2),
        "mediana": _q(0.5), "q10": q10, "q90": q90,
        # l'estremo superiore è la coda quando il 90° percentile cade oltre l'ultimo totale
        # disegnato: va scritto «7+», non «7», altrimenti si legge come intervallo chiuso
        "q90_label": coda if q90 == cap + 1 else str(q90),
        "copertura": round(copertura, 1),
        "dots": quantiles, "columns": columns, "n_dots": dots,
        "per_dot": round(100.0 / dots), "p_coda": round(tail, 4), "coda_label": coda,
        "lambda_home": round(float(lh), 3), "lambda_away": round(float(la), 3),
        "rho": round(float(rho or 0.0), 4),
    }


def _per_cento(masse: np.ndarray) -> np.ndarray:
    """«Partite su 100» intere la cui somma è esattamente 100 (metodo del resto massimo).

    Arrotondare ogni valore per conto suo darebbe somme da 99 o 101 su 100 partite, e la
    scheda deve restare verificabile a occhio (regola B1: ogni numero mostrato torna).
    """
    raw = np.nan_to_num(np.asarray(masse, dtype=float), nan=0.0, posinf=0.0, neginf=0.0) * 100.0
    base = np.floor(raw).astype(int)
    resto = round(100.0 - base.sum())
    if resto > 0:
        ordine = np.argsort(-(raw - base), kind="stable")
        for i in ordine[:resto]:
            base[int(i)] += 1
    return base


def probability_steps(pred: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Scomposizione della probabilità pubblicata: modello sui gol → rating → calibrazione.

    Ogni passo è un vettore 1X2 realmente calcolato e salvato nella riga di previsione
    (``dc_p_*`` dal modello Dixon-Coles, ``blend_p_*`` dalla media pesata con l'Elo,
    ``p_*`` pubblicato dopo la calibrazione): niente viene ricostruito a posteriori.
    I passi di cui non c'è traccia nei dati non compaiono (degradazione onesta).
    """
    if not pred:
        return []

    def _vec(prefix: str) -> tuple[float, float, float] | None:
        vals = [pred.get(f"{prefix}home"), pred.get(f"{prefix}draw"), pred.get(f"{prefix}away")]
        try:
            out = [float(v) for v in vals]
        except (TypeError, ValueError):
            return None
        if any(pd.isna(v) for v in out) or abs(sum(out) - 1.0) > 0.02:
            return None
        return (out[0], out[1], out[2])

    steps: list[dict[str, Any]] = []

    def _append(label: str, note: str, v: tuple[float, float, float]) -> None:
        # % mostrate = metodo del resto massimo a 0,1 (stessa resa di |pct3 nel template):
        # il Δ stampato è per costruzione la differenza fra i valori stampati dei due passi,
        # quindi la catena è ricalcolabile a occhio (regola «ogni numero mostrato torna»).
        from .fmt import pct_triple

        disp = pct_triple(v, 1)
        top_disp = float(max(disp))
        prev = steps[-1]["top_disp"] if steps else None
        steps.append({"label": label, "note": note, "p_home": v[0], "p_draw": v[1], "p_away": v[2],
                      "top": _top_name(v), "top_disp": top_disp,
                      "delta_pp": None if prev is None else round(top_disp - prev, 1)})

    dc = _vec("dc_p_")
    elo = _vec("elo_p_")
    if dc is not None:
        _append("Modello sui gol (Dixon-Coles)",
                "attacco/difesa pesati nel tempo, senza rating", dc)
    # passo 2: la media pesata VERA, ricalcolabile dalle colonne salvate (dc_p_*, elo_p_*, w_dc)
    w = pred.get("w_dc")
    if dc is not None and elo is not None and w is not None and not pd.isna(w):
        wf = float(w)
        media = (wf * dc[0] + (1 - wf) * elo[0],
                 wf * dc[1] + (1 - wf) * elo[1],
                 wf * dc[2] + (1 - wf) * elo[2])
        _append("Media pesata con i rating Elo",
                f"peso Dixon-Coles {wf:.0%}, Elo {1 - wf:.0%}", media)
    # passo 3: il vettore che le λ pubblicate producono, prima della calibrazione
    blend = _vec("blend_p_")
    if blend is not None:
        mode = str(pred.get("ensemble_mode") or "")
        if mode == "tilt":
            tilt = pred.get("tilt")
            note = "l'Elo inclina il rapporto casa/trasferta a totale dei gol invariato"
            if tilt is not None and not pd.isna(tilt) and abs(float(tilt) - 1.0) > 1e-6:
                note += f" (×{_dec(float(tilt), 3)}): la griglia arriva a questo vettore"
            else:
                note += ": qui l'Elo non sposta (inclinazione ≈ 1), il vettore coincide con la media"
            _append("Griglia sulle λ inclinate dall'Elo", note, blend)
        else:
            # previsioni storiche della ricetta precedente: blend_p_* è il vettore obiettivo
            # 70/30 che le due λ cercate raggiungevano (goal_expectancy, «inverti»)
            _append("Media con i rating Elo",
                    "vettore obiettivo dei due rating (previsione precedente alla ricetta attuale)",
                    blend)
    pub = _vec("p_")
    if pub and steps and max(abs(pub[i] - steps[-1][k]) for i, k in
                             enumerate(("p_home", "p_draw", "p_away"))) > 5e-4:
        cal_v = pred.get("calibration_version")
        calibrated = bool(cal_v) and str(cal_v) not in {"", "identity", "nan"}
        scale = pred.get("lambda_scale")
        note = "nessuna correzione applicata"
        if calibrated:
            try:
                come = ""
                est = str(pred.get("calibration_estimator") or "")
                win = pred.get("calibration_window_days")
                if est and win and not pd.isna(win) and float(win) > 0:
                    come = f" ({est}, ultimi {_int_it(float(win))} giorni)"
                elif est:
                    come = f" ({est})"
                note = (f"λ × {_dec(scale, 2)}{come} stimata su "
                        f"{_int_it(pred.get('calibration_n_fit'))} gare fuori campione")
            except (TypeError, ValueError):
                note = "correzione storica delle λ"
        _append("Calibrazione" if calibrated else "Pubblicato (nessuna calibrazione)", note, pub)
    # un solo passo non è una scomposizione: la scheda non mostra un blocco vuoto
    return steps if len(steps) >= 2 else []


def _top_name(v: tuple[float, float, float]) -> str:
    names = ("1", "X", "2")
    return names[int(np.argmax(v))]


def _top_value(v: tuple[float, float, float]) -> float:
    return float(max(v))


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
    n = len(s)
    xg = float(s.xg.sum())
    xgot = float(s.xgot.fillna(0).sum()) if "xgot" in s.columns else 0.0
    goals = int((s.event_type == "Goal").sum()) if "event_type" in s.columns else 0
    buckets: dict[str, dict[str, float]] = {}
    for name in ("open", "set", "pen", "other"):
        sub = s[s.situation.map(_bucket) == name] if "situation" in s.columns else s.iloc[0:0]
        buckets[name] = {"n": len(sub), "xg": float(sub.xg.sum()) if len(sub) else 0.0}
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


def _n_gare(v, singolare: str = "gara", plurale: str = "gare") -> str:
    """Contatore di gare concordato: 1 → «1 gara», 4 → «4 gare».

    Perché non basta :func:`fda.site.fmt.it_plural`: i tooltip dello «Scontro tattico»
    dichiarano su quante gare è calcolata la media, e quando il dato manca il valore è il
    trattino «—», non un numero — quello va passato attraverso tale e quale (seguito dal
    plurale, come prima). Con una sola gara in archivio (prima giornata, o una neopromossa
    con un solo turno raccolto) le due frasi stampavano «su 1 gare» e «1 gare finite»
    (docs/40 §1, punti 4 e 5).
    """
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return f"{v} {plurale}"
    return _it_plural(n, singolare, plurale)


def _quota_split(side: dict[str, Any]) -> tuple[float | None, float | None]:
    """Quote xG azione / palle inattive (somma 100) da un'unica fonte — mai sommabili a un
    totale calcolato da un'altra fonte (docs/20 §4): è l'unica scomposizione coerente
    per costruzione e confrontabile in parità fra tutte e 7 le leghe."""
    op, sp = side.get("open_pm"), side.get("set_pm")
    if op is None or sp is None:
        return None, None
    tot = float(op) + float(sp)
    if tot <= 0:
        return None, None
    return (round(100.0 * float(op) / tot, 1), round(100.0 * float(sp) / tot, 1))


def style_rows(home: dict[str, Any] | None, away: dict[str, Any] | None,
               pred: dict[str, Any] | None) -> dict[str, Any] | None:
    """Card «Scontro tattico»: λ, DC attacco/difesa, xG split, PPDA, deep.

    Una riga compare solo se almeno un lato ha il dato. None se non c'è nulla
    di confrontabile (niente previsione e niente stile di stagione). Ogni riga
    dichiara la **sua** fonte nel tooltip (``help``): nella stessa tabella possono
    convivere modello (λ/DC), Understat (xG/PPDA nelle 5 leghe coperte) e FotMob
    (xG in NED1/POR1 e sempre per le quote azione/palle inattive) — i due fornitori
    di xG divergono di ~0,15 a gara su 92 squadre (docs/20 §3), quindi la
    scomposizione è pubblicata come quota interna a una sola fonte.
    """
    h, a = home or {}, away or {}
    pred = pred or {}
    rows: list[dict[str, Any]] = []

    def add(label: str, hv, av, higher: bool | None = True, nd: int = 2,
            help: str | None = None, suffix: str | None = None) -> None:
        if hv is None and av is None:
            return
        best = None
        if hv is not None and av is not None and higher is not None and hv != av:
            best = "h" if (hv > av) == higher else "a"
        rows.append({"label": label, "h": hv, "a": av, "best": best, "nd": nd,
                     "help": help, "suffix": suffix})

    def _xg_help(base: str, hs: dict[str, Any], as_: dict[str, Any]) -> str:
        """Fonte esplicita per lato della stessa riga: qui (e solo qui) le due colonne
        possono venire da fornitori diversi."""
        hsrc, asrc = hs.get("source") or "n.d.", as_.get("source") or "n.d."
        hn, an = _n_gare(hs.get("played") or "—"), _n_gare(as_.get("played") or "—")
        if hsrc == asrc:
            return f"{base}, media stagionale {hsrc} su {hn}"
        return (f"{base}, media stagionale: colonna a sinistra {hsrc} su {hn}, "
                f"colonna a destra {asrc} su {an} — i due fornitori non sono identici")

    add("Gol attesi (λ)", pred.get("lambda_home"), pred.get("lambda_away"), True,
        help="Media Poisson Dixon-Coles+Elo calibrata, non media delle ultime gare")
    add("Attacco DC", pred.get("dc_attack_home"), pred.get("dc_attack_away"), True,
        help="Parametro d'attacco del modello (gol attesi contro una difesa media)")
    add("Difesa DC (↓ meglio)", pred.get("dc_defence_home"), pred.get("dc_defence_away"), False,
        help="Parametro di difesa del modello: più basso = subisce meno")
    add("xG / gara", h.get("xg_pm"), a.get("xg_pm"), True, help=_xg_help("Gol attesi", h, a))
    add("xGA / gara", h.get("xga_pm"), a.get("xga_pm"), False,
        help=_xg_help("Gol attesi concessi", h, a))
    qo_h, qs_h = _quota_split(h)
    qo_a, qs_a = _quota_split(a)

    def _quota_help(hv, av) -> str:
        def _one(side, qo, qs) -> str:
            if side.get("open_pm") is None or side.get("set_pm") is None:
                return "n.d."
            n = side.get("split_played") or "—"
            return (f"{_dec(side['open_pm'], 2)} + {_dec(side['set_pm'], 2)} xG a gara "
                    f"(FotMob, {_n_gare(n, 'gara finita', 'gare finite')})")
        return (f"Quota del totale xG della squadra, unica fonte FotMob: le due quote sommano "
                f"sempre 100 e NON si sommano alla riga «xG / gara» se quella viene da "
                f"Understat. Valori a gara — sinistra {_one(h, qo_h, qs_h)}, "
                f"destra {_one(a, qo_a, qs_a)}")

    add("xG da azione manovrata (quota)", qo_h, qo_a, None, 0, _quota_help(qo_h, qo_a), "%")
    add("xG da palle inattive (quota)", qs_h, qs_a, None, 0, _quota_help(qs_h, qs_a), "%")
    add("PPDA (↓ = più pressing)", h.get("ppda"), a.get("ppda"), False, 1,
        help="Passaggi concessi prima di un intervento difensivo (Understat): 8 = pressing alto, 18 = blocco basso")
    add("PPDA concesso", h.get("ppda_allowed"), a.get("ppda_allowed"), True, 1,
        help="Pressing subito: passaggi che gli avversari completano prima di un intervento (Understat)")
    add("Passaggi profondi / gara", h.get("deep"), a.get("deep"), True, 1,
        help="Completamenti negli ultimi ~20 m di campo (Understat): quanto una squadra arriva vicino all'area")
    add("Passaggi profondi subiti / gara", h.get("deep_allowed"), a.get("deep_allowed"), False, 1,
        help="Completamenti negli ultimi ~20 m concessi (Understat): più basso = difesa più protetta")
    if not rows:
        return None
    notes = [
        "Attacco/difesa DC: parametri del modello. Difesa più bassa = subisce meno.",
        "PPDA e passaggi profondi: Understat (nelle leghe coperte).",
        "Quote azione/palle inattive: FotMob; sommano 100 e non si sommano al totale.",
    ]
    # le due colonne hanno fornitori xG diversi? Il lettore deve saperlo senza
    # dover aprire il tooltip (docs/20 §3)
    hsrc, asrc = h.get("source"), a.get("source")
    mixed = bool(hsrc and asrc and hsrc != asrc)
    if mixed:
        notes.append(f"xG / gara da due fornitori diversi in questa gara: "
                     f"sinistra {hsrc}, destra {asrc} — confronto indicativo.")
    # dedup con pattern lasco (case/punteggiatura/spazi) — evita nota globale duplicata per variazioni minime
    def _norm(s: str) -> str:
        return re.sub(r"\W+", " ", s.lower().strip()).strip()
    seen: set[str] = set()
    uniq: list[str] = []
    for n in notes:
        k = _norm(n)
        if k not in seen:
            seen.add(k)
            uniq.append(n)
    # nota globale singola (pattern lasco già applicato) + lista per retro-compatibilità
    global_note = " ".join(uniq[:2])
    return {"rows": rows, "notes": uniq, "global_note": global_note, "mixed_sources": mixed}
