"""Previsioni partita: Dixon-Coles (penaltyblog) + Elo + ensemble → mercati.

Input: DataFrame storico normalizzato (date, home, away, home_goals, away_goals) con nomi
canonici. Output: per ogni partita richiesta un dict con λ attese, 1X2, risultati esatti,
Over/Under, BTTS, doppia chance, e i contributi dei singoli modelli.

Nota tecnica: penaltyblog richiede array NumPy scrivibili (con pandas 3 copy-on-write le Series
sono read-only) → `.to_numpy().copy()`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import penaltyblog as pb

from ..config import PROCESSED_DIR
from .calibration import Calibration
from .dc_grid import GRID_SIZE, probability_grid, tau_grid

log = logging.getLogger(__name__)

# 0.2: shrinkage dei parametri DC verso la media di lega.
# 0.3: calibrazione fuori campione della griglia (λ×m, ρ+Δ) stimata da `fda calibrate` sul
#      backtest: rimuove il bias misurato di +8,6% sui gol totali e la sottostima del pareggio.
# 0.4: l'Elo entra nella griglia per **inclinazione** e non più invertendo due λ libere
#      dall'1X2 mediato (`ENSEMBLE_MODE = "tilt"`, candidato `dc_elo_tilt` promosso dopo il
#      verdetto del laboratorio). I gol attesi tornano quelli del modello sui gol: la
#      calibrazione è stata ristimata su questa ricetta, non riutilizzata dalla precedente.
MODEL_VERSION = "dc-elo-tilt-0.4"

# Pseudo-partite del prior sui parametri attacco/difesa (shrinkage verso la media di lega).
SHRINK_PRIOR = 8.0

# Limiti condivisi per il prior di lega usato quando una squadra non compare nello storico.
# La simulazione di stagione deve usare gli stessi limiti di `predict_matches`: due percorsi
# diversi non possono trasformare la stessa media osservata in λ diverse (docs/19 §1.8d).
NEUTRAL_LAMBDA_BOUNDS: tuple[float, float] = (0.6, 2.2)


def _grid_markets(grid: Any) -> dict[str, float]:
    """Estrae i mercati principali da un FootballProbabilityGrid di penaltyblog."""
    hda = grid.home_draw_away
    top = {}
    m = np.asarray(grid.grid)
    flat = [(int(i), int(j), float(m[i, j])) for i in range(min(m.shape[0], 8)) for j in range(min(m.shape[1], 8))]
    flat.sort(key=lambda t: -t[2])
    for i, j, p in flat[:6]:
        top[f"{i}-{j}"] = round(p, 4)
    return {
        "p_home": float(hda[0]), "p_draw": float(hda[1]), "p_away": float(hda[2]),
        "lambda_home": float(grid.home_goal_expectation),
        "lambda_away": float(grid.away_goal_expectation),
        "p_over15": float(grid.total_goals("over", 1.5)),
        "p_over25": float(grid.total_goals("over", 2.5)),
        "p_over35": float(grid.total_goals("over", 3.5)),
        "p_btts": float(grid.btts_yes),
        "p_1x": float(grid.double_chance_1x), "p_12": float(grid.double_chance_12),
        "p_x2": float(grid.double_chance_x2),
        "p_home_clean_sheet": float(np.asarray(grid.grid)[:, 0].sum()),
        "p_away_clean_sheet": float(np.asarray(grid.grid)[0, :].sum()),
        "top_scores": top,
    }


@dataclass
class DixonColesModel:
    xi: float = 0.0018             # decadimento temporale (Dixon & Coles 1997: ~0.0065/settimana ≈ 0.0009/giorno)
    max_goals: int = 10
    # Shrinkage dei parametri attacco/difesa verso la media di lega. A inizio stagione una
    # neopromossa ha 2-3 partite: il suo stimatore finisce al bordo dell'ottimizzazione
    # (attacco −2,5) e la rende "incapace di segnare" (Dortmund–Paderborn λ 1,02–0,19 con
    # Over 2,5 al 12%, contro 0,71 xG/gara reali del Paderborn). Il parametro viene
    # contratto di f = w/(w+shrink_prior), dove w è il peso temporale delle sue partite.
    # shrink_prior = 0 disattiva la contrazione (comportamento penaltyblog puro).
    shrink_prior: float = SHRINK_PRIOR
    model: Any = field(default=None, init=False, repr=False)
    teams: set[str] = field(default_factory=set, init=False)
    team_weight: dict[str, float] = field(default_factory=dict, init=False)
    fitted_at: datetime | None = field(default=None, init=False)
    n_matches: int = field(default=0, init=False)

    def fit(self, hist: pd.DataFrame, as_of: datetime | None = None) -> "DixonColesModel":
        df = hist.dropna(subset=["home_goals", "away_goals"]).copy()
        if as_of is not None:
            df = df[df["date"] <= pd.Timestamp(as_of).tz_localize(None) if df["date"].dt.tz is None
                    else df["date"] <= pd.Timestamp(as_of)]
        if len(df) < 50:
            raise ValueError(f"storico insufficiente per Dixon-Coles: {len(df)} partite")
        dates = pd.to_datetime(df["date"]).dt.tz_localize(None) if df["date"].dt.tz is not None else df["date"]
        weights = pb.models.dixon_coles_weights(dates, xi=self.xi)
        self.model = pb.models.DixonColesGoalModel(
            df["home_goals"].to_numpy(dtype=float).copy(),
            df["away_goals"].to_numpy(dtype=float).copy(),
            df["home"].to_numpy().copy(),
            df["away"].to_numpy().copy(),
            weights=np.asarray(weights, dtype=float).copy(),
        )
        self.model.fit()
        self.teams = set(df["home"]) | set(df["away"])
        w = pd.Series(np.asarray(weights, dtype=float), index=df.index)
        per_team = w.groupby(df["home"]).sum().add(w.groupby(df["away"]).sum(), fill_value=0.0)
        self.team_weight = {str(t): float(v) for t, v in per_team.items()}
        self.n_matches = int(len(df))
        self.fitted_at = datetime.now(timezone.utc)
        return self

    def shrunk_params(self, params: dict[str, float] | Any) -> dict[str, float]:
        """Parametri attacco/difesa contratti verso la media di lega, in proporzione ai dati.

        ``f = w / (w + shrink_prior)`` con ``w`` = peso temporale accumulato dalla squadra
        (una squadra presente da 3 stagioni pesa ~130 con xi=0.0018, una neopromossa ~2).

        Poiché ``f`` cambia da squadra a squadra, la contrazione sposterebbe le medie di
        lega e con esse il gauge scelto dall'ottimizzatore (λ = exp(attacco + difesa +
        hfa)): le due medie vengono quindi riportate al valore del fit. Restano intatte
        graduatorie e differenze relative, che sono ciò che determina λ.
        """
        params = dict(params)
        if self.shrink_prior <= 0 or not self.teams:
            return params
        att = {t: float(params.get(f"attack_{t}", 0.0)) for t in self.teams}
        dfn = {t: float(params.get(f"defence_{t}", 0.0)) for t in self.teams}
        mean_att = sum(att.values()) / len(att)
        mean_dfn = sum(dfn.values()) / len(dfn)
        shrunk_att, shrunk_dfn = {}, {}
        for t in self.teams:
            w = self.team_weight.get(t, 0.0)
            f = w / (w + self.shrink_prior)
            shrunk_att[t] = mean_att + (att[t] - mean_att) * f
            shrunk_dfn[t] = mean_dfn + (dfn[t] - mean_dfn) * f
        shift_att = sum(shrunk_att.values()) / len(shrunk_att) - mean_att
        shift_dfn = sum(shrunk_dfn.values()) / len(shrunk_dfn) - mean_dfn
        for t in self.teams:
            params[f"attack_{t}"] = shrunk_att[t] - shift_att
            params[f"defence_{t}"] = shrunk_dfn[t] - shift_dfn
        return params

    def lambdas(self, home: str, away: str, params: dict[str, float]) -> tuple[float, float]:
        """λ attese dalla parametrizzazione moltiplicativa di penaltyblog (exp di att+dif+hfa)."""
        hfa = float(params.get("home_advantage", 0.0))
        att_h = float(params.get(f"attack_{home}", 0.0))
        att_a = float(params.get(f"attack_{away}", 0.0))
        dfn_h = float(params.get(f"defence_{home}", 0.0))
        dfn_a = float(params.get(f"defence_{away}", 0.0))
        return math.exp(att_h + dfn_a + hfa), math.exp(att_a + dfn_h)

    def predict(self, home: str, away: str) -> dict[str, Any]:
        if home not in self.teams or away not in self.teams:
            missing = [t for t in (home, away) if t not in self.teams]
            raise KeyError(f"squadre non nello storico DC: {missing}")
        params = self.shrunk_params(self.model.get_params())
        lh, la = self.lambdas(home, away, params)
        # griglia ricostruita sui parametri contratti (stessa τ del modello addestrato)
        grid = probability_grid(lh, la, params.get("rho", 0.0) or 0.0, size=self.max_goals)
        out = _grid_markets(grid)
        out["dc_attack_home"] = float(params.get(f"attack_{home}", float("nan")))
        out["dc_defence_home"] = float(params.get(f"defence_{home}", float("nan")))
        out["dc_attack_away"] = float(params.get(f"attack_{away}", float("nan")))
        out["dc_defence_away"] = float(params.get(f"defence_{away}", float("nan")))
        out["dc_home_advantage"] = float(params.get("home_advantage", float("nan")))
        out["dc_rho"] = float(params.get("rho", float("nan")))
        return out

    def strength_table(self) -> pd.DataFrame:
        p = self.shrunk_params(self.model.get_params())
        rows = [{"team": t, "attack": p[f"attack_{t}"], "defence": p[f"defence_{t}"],
                 "matches_weight": round(self.team_weight.get(t, 0.0), 1)} for t in sorted(self.teams)]
        df = pd.DataFrame(rows)
        # più alto = meglio, per entrambi (attack alto = segna di più; defence basso = subisce meno)
        df["rating"] = df["attack"] - df["defence"]
        return df.sort_values("rating", ascending=False).reset_index(drop=True)


@dataclass
class EloModel:
    k: float = 20.0
    home_field_advantage: float = 60.0
    ratings: dict[str, float] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list, init=False)

    def fit(self, hist: pd.DataFrame) -> "EloModel":
        elo = pb.ratings.Elo(k=self.k, home_field_advantage=self.home_field_advantage)
        df = hist.dropna(subset=["home_goals", "away_goals"]).sort_values("date")
        # 0 = vittoria casa, 1 = pareggio, 2 = vittoria trasferta (convenzione penaltyblog)
        for r in df.itertuples(index=False):
            result = 0 if r.home_goals > r.away_goals else (1 if r.home_goals == r.away_goals else 2)
            elo.update_ratings(r.home, r.away, result)
        self._elo = elo
        teams = set(df["home"]) | set(df["away"])
        self.ratings = {t: float(elo.get_team_rating(t)) for t in teams}
        return self

    def predict(self, home: str, away: str) -> dict[str, float]:
        p = self._elo.calculate_match_probabilities(home, away)
        # penaltyblog restituisce un oggetto/dict con home_win, draw, away_win
        ph, pd_, pa = (p["home_win"], p["draw"], p["away_win"]) if isinstance(p, dict) \
            else (p.home_win, p.draw, p.away_win)
        return {"elo_home": self.ratings.get(home, 1500.0), "elo_away": self.ratings.get(away, 1500.0),
                "elo_p_home": float(ph), "elo_p_draw": float(pd_), "elo_p_away": float(pa)}


#: limiti di sicurezza sulle λ ricavate dall'1X2 mediato (vedi :func:`_clamp_lambda`).
#: Tarati sul backtest reale (5.791 gare fuori campione, 7 leghe): il modello sui gol da solo
#: non supera mai λ 3,84 per squadra né 4,73 totali, mentre l'inversione dell'1X2 mediato
#: arriva a 5,09 e 6,77 (rapporto medio 1,14, p99 1,35, max 1,55) e sulle previsioni
#: pubblicate anche a 8,4 gol attesi. Con questi valori i limiti toccano l'1,2% delle gare.
LAMBDA_MAX = 4.0                 # gol attesi massimi per una singola squadra
LAMBDA_TOTAL_MAX_REL = 1.35      # totale al massimo +35% rispetto al modello sui gol
LAMBDA_TOTAL_MIN_REL = 0.70      # e non sotto il 70%
LAMBDA_TOTAL_MAX_ABS = 5.5       # tetto assoluto: oltre non è una partita di calcio reale
LAMBDA_TOTAL_ABS = (1.0, LAMBDA_TOTAL_MAX_ABS)   # se le λ del modello sui gol non sono note


#: ricetta con cui l'Elo entra nella griglia pubblicata.
#:
#: * ``"tilt"`` (produzione dal 2026-09-13): l'Elo **inclina** il rapporto casa/trasferta e il
#:   totale dei gol attesi resta quello stimato dal modello sui gol. Promossa dopo il verdetto
#:   del laboratorio in Actions (`model_lab.parquet`, 1.527 gare walk-forward, 7 leghe):
#:   ΔRPS −0,000406 con IC 95% appaiato [−0,000773; −0,000041] interamente negativo e RPS più
#:   basso in 5 leghe su 7 — le due condizioni di `docs/13` §6.5. Dettagli in `docs/15`;
#: * ``"inverti"``: la ricetta precedente, due λ libere cercate da ``goal_expectancy`` per
#:   riprodurre l'1X2 mediato. Gonfia i gol attesi (bias +0,24 gol sul backtest) ed è ciò che
#:   la calibrazione doveva correggere a valle. Resta disponibile al laboratorio come
#:   candidato ``dc_elo_ge``, così il confronto che ha deciso la promozione è ripetibile.
ENSEMBLE_MODE = "tilt"
ENSEMBLE_MODES = ("tilt", "inverti")

#: inclinazioni casa/trasferta provate da :func:`_tilt_lambdas` (1,00 = λ del modello sui gol)
TILT_GRID: tuple[float, ...] = tuple(round(0.85 + 0.01 * i, 3) for i in range(31))


def _one_x_two(grid: np.ndarray) -> tuple[float, float, float]:
    """1X2 della griglia (stessa convenzione di penaltyblog: casa, pareggio, trasferta)."""
    i, j = np.indices(grid.shape)
    return float(grid[i > j].sum()), float(grid[i == j].sum()), float(grid[i < j].sum())


def _tilt_pair(lh: float, la: float, t: float) -> tuple[float, float]:
    """λ inclinate di ``t`` (rapporto casa/trasferta × t²) a **totale invariato**."""
    totale = float(lh) + float(la)
    lh_t, la_t = float(lh) * t, float(la) / max(t, 1e-9)
    s = totale / (lh_t + la_t) if (lh_t + la_t) > 0 else 1.0
    return lh_t * s, la_t * s


def _tilt_lambdas(lh: float, la: float, rho: float,
                  target: tuple[float, float, float]) -> tuple[float, float, float]:
    """λ che avvicinano l'1X2 della griglia al vettore mediato **senza toccare il totale**.

    È l'alternativa strutturale a ``goal_expectancy`` misurata dal laboratorio: l'Elo sposta
    il rapporto casa/trasferta, il totale dei gol attesi resta quello del modello sui gol, e
    il vettore 1X2 pubblicato è quello della griglia risultante (mercati e 1X2 coerenti fra
    loro, senza bisogno di correggere a valle). La ricerca è su :data:`TILT_GRID`
    (0,85…1,15 a passi di 0,01) e non su un'ottimizzazione continua: 31 griglie sono ~1 ms e
    l'intervallo è quello entro cui il candidato è stato misurato.

    Restituisce (λ casa, λ trasferta, inclinazione scelta).
    """
    if not (np.isfinite(lh) and np.isfinite(la)):
        return float(lh), float(la), 1.0        # λ non calcolabili: niente da inclinare
    # griglia discreta primaria + raffinamento parabolico ±0,015 a passo 0,002 (audit 1.2)
    best_err: float | None = None
    best_t: float = 1.0
    for t in TILT_GRID:
        lh_t, la_t = _tilt_pair(lh, la, t)
        p = _one_x_two(tau_grid(lh_t, la_t, rho, size=GRID_SIZE))
        err = sum((float(a) - float(b)) ** 2 for a, b in zip(p, target))
        if best_err is None or err < best_err:
            best_err, best_t = err, float(t)
    # raffinamento: 15 punti extra attorno al minimo (±0,015), costo <0,4 ms
    lo_ref = max(TILT_GRID[0] - 0.15, best_t - 0.015)
    hi_ref = min(TILT_GRID[-1] + 0.15, best_t + 0.015)
    for t in np.arange(lo_ref, hi_ref + 1e-9, 0.002):
        t = round(float(t), 4)
        if t in TILT_GRID:
            continue
        lh_t, la_t = _tilt_pair(lh, la, t)
        p = _one_x_two(tau_grid(lh_t, la_t, rho, size=GRID_SIZE))
        err = sum((float(a) - float(b)) ** 2 for a, b in zip(p, target))
        if err < best_err:  # type: ignore[operator]
            best_err, best_t = err, float(t)
    if best_t in (TILT_GRID[0], TILT_GRID[-1]):
        log.debug("tilt al bordo %.3f (target %.2f/%.2f/%.2f)", best_t, *target)
    lh_t, la_t = _tilt_pair(lh, la, best_t)
    return lh_t, la_t, float(best_t)


def _clamp_lambda(lh: float, la: float, dc_lh: float, dc_la: float) -> tuple[float, float] | None:
    """Riporta le λ invertite entro limiti di sicurezza; ``None`` se non ce n'è bisogno.

    ``goal_expectancy`` risolve le λ che riproducono un vettore 1X2 **senza alcun vincolo**:
    quando l'Elo spinge l'1X2 verso esiti estremi (pareggio al 5-6%) l'unico modo di
    riprodurlo è gonfiare i gol attesi, e la griglia descrive partite che nel calcio reale non
    esistono. Sulle previsioni pubblicate il caso limite misurato è Barcellona-Racing Santander
    con λ 6,17+2,25 = 8,4 gol attesi (Over 2,5 al 99%, risultati esatti centrati sul 5-1):
    numeri che un lettore riconosce come assurdi e che trascinano con sé ogni mercato derivato.

    Qui il totale resta fra il 70% e il 135% di quello stimato dal modello sui gol — che i gol
    li modellerà pure male, ma non inventa partite da otto reti — e ogni λ resta sotto 4,0.
    Il rapporto casa/trasferta si conserva (si scala il totale, non si tocca l'inclinazione);
    il vecchio ``min(lh*scala, LAMBDA_MAX)`` per singola λ rompeva il rapporto quando entrambe
    toccavano il tetto (audit 1.3).
    """
    tot = float(lh) + float(la)
    if not np.isfinite(tot) or tot <= 0:
        return None
    # ρ sane anche quando il caller passa un NaN (audit 1.7)
    # (qui non serve: sanity già in probability_grid/clamp_rho, ma clamp lambda non deve esplodere)
    tot_dc = float(dc_lh) + float(dc_la)
    lo, hi = ((tot_dc * LAMBDA_TOTAL_MIN_REL, tot_dc * LAMBDA_TOTAL_MAX_REL)
              if np.isfinite(tot_dc) and tot_dc > 0 else LAMBDA_TOTAL_ABS)
    hi = min(hi, LAMBDA_TOTAL_MAX_ABS)          # il tetto assoluto vale anche se il modello esagera
    if lo > hi:  # invariante di guardia (tot_dc esterno a scala)
        lo, hi = hi, lo
    # scala totale che riporta tot dentro [lo, hi]
    lo = float(lo); hi = float(hi)
    tot_clamped = float(min(max(tot, lo), hi))
    s_tot = tot_clamped / tot if tot else 1.0
    # applica la stessa scala al rapporto: preserva lh/la esattamente
    lh_s, la_s = float(lh) * s_tot, float(la) * s_tot
    # se una  (dopo scala totale) eccede LAMBDA_MAX, riduci **uniformemente** il totale
    # così il rapporto resta identico invece di troncare una sola gamba
    m = max(lh_s, la_s)
    if m > LAMBDA_MAX:
        s_cap = LAMBDA_MAX / m
        lh_s *= s_cap
        la_s *= s_cap
        # rispetta anche il tetto totale assoluto dopo il cap per-team
        tot2 = lh_s + la_s
        if tot2 > LAMBDA_TOTAL_MAX_ABS:
            s2 = LAMBDA_TOTAL_MAX_ABS / tot2
            lh_s *= s2; la_s *= s2
    if abs(lh_s - float(lh)) < 1e-9 and abs(la_s - float(la)) < 1e-9:
        return None
    # invariante: rapporto preservato a meno del cap per-team intenzionale
    # (verificato da test_... quando m <= LAMBDA_MAX)
    return lh_s, la_s


def ensemble(dc: dict[str, Any], elo: dict[str, float] | None, w_dc: float = 0.7,
             mode: str = ENSEMBLE_MODE) -> dict[str, Any]:
    """Media pesata 1X2 tra Dixon-Coles ed Elo, ripubblicata **da una sola griglia**.

    L'Elo non ha λ, quindi l'1X2 mediato va riportato su una matrice di punteggi da cui
    derivare tutti i mercati. Due modi di farlo (:data:`ENSEMBLE_MODE`):

    * ``mode="tilt"`` (produzione): il totale dei gol attesi **resta** quello del modello sui
      gol e l'Elo inclina solo il rapporto casa/trasferta (:func:`_tilt_lambdas`). Non c'è
      nulla da correggere a valle, perché la media pesata non gonfia le λ — è il difetto
      misurato (bias +0,24 gol) che la ricetta ``"inverti"`` introduceva e la calibrazione
      doveva tamponare;
    * ``mode="inverti"``: due λ libere cercate da ``goal_expectancy`` per riprodurre il
      vettore mediato (ricetta precedente, rimasta come candidato del laboratorio).

    Con ``mode="tilt"`` l'1X2 pubblicato è quello della griglia inclinata (non il vettore
    mediato, che una griglia a totale fissato non è detta sappia riprodurre: la differenza è
    misurata entro ~1 punto nei casi ordinari). In entrambi i modi, quando i limiti di
    sicurezza legano, l'1X2 è quello della griglia limitata: mai un 1X2 estremo accanto a
    mercati prudenti.
    """
    out = dict(dc)
    out["dc_p_home"] = float(dc["p_home"])
    out["dc_p_draw"] = float(dc["p_draw"])
    out["dc_p_away"] = float(dc["p_away"])
    # λ del solo modello sui gol: sono il riferimento dei limiti di sicurezza e restano
    # utili anche dopo la calibrazione, che le moltiplica insieme a quelle pubblicate
    out["dc_lambda_home"] = float(dc.get("lambda_home", float("nan")))
    out["dc_lambda_away"] = float(dc.get("lambda_away", float("nan")))
    out["lambda_limitata"] = False
    out["ensemble_mode"] = mode
    if not elo:
        out["model"] = "dc"
        return out
    ph = w_dc * dc["p_home"] + (1 - w_dc) * elo["elo_p_home"]
    pdw = w_dc * dc["p_draw"] + (1 - w_dc) * elo["elo_p_draw"]
    pa = w_dc * dc["p_away"] + (1 - w_dc) * elo["elo_p_away"]
    s = ph + pdw + pa
    ph, pdw, pa = ph / s, pdw / s, pa / s
    try:
        _rho_raw = dc.get("dc_rho", 0.0)
        rho = float(_rho_raw) if _rho_raw is not None else 0.0
        if not np.isfinite(rho):
            rho = 0.0
        rho = float(np.clip(rho, -0.3, 0.3))
        lh_dc = float(dc.get("lambda_home", float("nan")))
        la_dc = float(dc.get("lambda_away", float("nan")))
        if mode == "tilt":
            lh, la, tilt = _tilt_lambdas(lh_dc, la_dc, rho, (ph, pdw, pa))
            out["tilt"] = tilt
        else:
            ge = pb.models.goal_expectancy(ph, pdw, pa, dc_adj=True, rho=rho)
            lh, la = float(ge["home_exp"]), float(ge["away_exp"])
        limitato = _clamp_lambda(lh, la, lh_dc, la_dc)
        if limitato is not None:
            # dettaglio a DEBUG: su un calendario intero sarebbero decine di righe di log;
            # il riepilogo con il tasso di intervento lo scrive predict_matches
            log.debug("λ fuori dai limiti: %.2f+%.2f → %.2f+%.2f (1X2 ripubblicato dalla griglia)",
                      lh, la, limitato[0], limitato[1])
            lh, la = limitato
        grid = probability_grid(lh, la, rho, size=GRID_SIZE)
        markets = _grid_markets(grid)
        if mode != "tilt" and limitato is None:
            # la ricetta "inverti" riproduce il vettore mediato per costruzione: l'1X2 resta
            # quello della media pesata (comportamento storico, su cui il laboratorio misura)
            markets.update({"p_home": ph, "p_draw": pdw, "p_away": pa})
        # la doppia chance è per definizione una somma di esiti 1X2: va ricalcolata sull'1X2
        # pubblicato, altrimenti la scheda mostra «1X 73%» accanto a «1X2 48/27/26» (100−26=74).
        # Sui dati pubblicati lo scarto arrivava a 1,1 punti e l'intero a schermo era
        # incoerente nel 14,3% delle partite.
        markets.update({"p_1x": markets["p_home"] + markets["p_draw"],
                        "p_12": markets["p_home"] + markets["p_away"],
                        "p_x2": markets["p_draw"] + markets["p_away"]})
        out.update(markets)
        out["lambda_limitata"] = bool(limitato is not None)
    except Exception as exc:  # fallback: solo 1X2 mediato
        log.debug("ensemble %s fallita (%s): uso 1X2 mediato e mercati DC", mode, exc)
        out.update({"p_home": ph, "p_draw": pdw, "p_away": pa})
    out.update(elo)
    out["model"] = "ensemble"
    out["w_dc"] = w_dc
    # primo passo della scomposizione mostrata in scheda: le probabilità del solo modello
    # sui gol, prima della media con i rating (la media è già in p_* qui sopra)
    out["dc_p_home"] = float(dc["p_home"])
    out["dc_p_draw"] = float(dc["p_draw"])
    out["dc_p_away"] = float(dc["p_away"])
    return out


def calibrated_prediction(out: dict[str, Any], cal: Calibration | None) -> dict[str, Any]:
    """Applica la calibrazione e ripubblica **tutta** la previsione dalla griglia calibrata.

    La calibrazione agisce su λ e ρ, cioè sugli unici due ingressi della matrice: 1X2,
    doppia chance, risultati esatti, Over/Under, BTTS, porte inviolate e λ restano quindi
    coerenti fra loro e con la matrice mostrata nella scheda (una sola superficie di
    probabilità). Il vettore 1X2 precedente (media pesata DC+Elo prima della calibrazione)
    viene conservato in ``blend_p_*`` per trasparenza, non sostituito di nascosto.
    """
    cal = cal or Calibration()
    res = dict(out)
    res["lambda_home_raw"] = float(out.get("lambda_home", 0.0) or 0.0)
    res["lambda_away_raw"] = float(out.get("lambda_away", 0.0) or 0.0)
    res["rho_raw"] = float(out.get("dc_rho", 0.0) or 0.0)
    if cal.is_identity:
        return res
    lh, la, rho = cal.apply(res["lambda_home_raw"], res["lambda_away_raw"], res["rho_raw"])
    # i limiti di sicurezza valgono sui gol attesi **pubblicati**, non su quelli grezzi: con un
    # moltiplicatore sopra 1 (1,0401 dal 2026-09-13, quando il tilt ha riportato le λ al livello
    # del modello sui gol) la correzione può spingere una λ già limitata poco sopra il tetto
    # (misurato sulle previsioni rigenerate: 2 partite su 2.071 con λ per squadra a 4,16).
    # Il vincolo *relativo* è invariante alla scala — se il totale grezzo sta fra il 70% e il
    # 135% di quello del modello sui gol, lo resta dopo aver moltiplicato entrambi — quindi qui
    # possono legare solo i tetti assoluti (λ ≤ 4,0 per squadra, totale ≤ 5,5).
    limite = _clamp_lambda(lh, la, float(out.get("dc_lambda_home", float("nan"))) * cal.lambda_scale,
                           float(out.get("dc_lambda_away", float("nan"))) * cal.lambda_scale)
    if limite is not None:
        lh, la = limite
        res["lambda_limitata"] = True
    grid = probability_grid(lh, la, rho, size=GRID_SIZE)
    markets = _grid_markets(grid)
    res["blend_p_home"] = float(out.get("p_home", 0.0))
    res["blend_p_draw"] = float(out.get("p_draw", 0.0))
    res["blend_p_away"] = float(out.get("p_away", 0.0))
    res.update(markets)
    res.update({"lambda_home": lh, "lambda_away": la, "dc_rho": rho})
    return res


def latest_per_match(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per (partita, modello): l'ultima previsione, cioè quella che l'utente ha visto.

    Serve due volte: come **migrazione** delle righe accumulate con la chiave vecchia
    (`match_id`, `model`, `made_at`) e come garanzia che una partita riprevista a ogni run
    non si moltiplichi. Le previsioni restano tutte *pre-partita*: `fda predict` lavora solo
    sulle gare con `status == "scheduled"`, quindi l'ultima riga è per costruzione quella
    pubblicata prima del calcio d'inizio.
    """
    if df.empty or "match_id" not in df.columns:
        return df
    keys = ["match_id"] + (["model"] if "model" in df.columns else [])
    out = df.copy()
    if "made_at" in out.columns:
        sort_cols = ["made_at"] + (["model_version"] if "model_version" in out.columns else [])
        out = out.sort_values(sort_cols, kind="stable")
    return out.drop_duplicates(subset=keys, keep="last").reset_index(drop=True)


def fair_odds(p: float) -> float | None:
    return None if not p or p <= 0 else round(1.0 / p, 2)


def predict_matches(hist: pd.DataFrame, fixtures: pd.DataFrame, xi: float = 0.0018,
                    w_dc: float = 0.7,
                    shrink_prior: float = SHRINK_PRIOR,
                    calibration: Calibration | None = None,
                    ) -> tuple[pd.DataFrame, DixonColesModel, EloModel]:
    """Addestra DC+Elo su `hist` e prevede le righe di `fixtures` (colonne: match_id, home, away, ...).

    ``calibration`` (vedi :mod:`fda.models.calibration`) è opzionale: se assente la previsione
    è quella non calibrata, identica al comportamento precedente. I parametri applicati sono
    sempre scritti nelle righe di output, così ogni numero pubblicato è riconducibile alla
    versione che lo ha prodotto.
    """
    cal = calibration or Calibration()
    dc = DixonColesModel(xi=xi, shrink_prior=shrink_prior).fit(hist)
    elo = EloModel().fit(hist)
    made_at = datetime.now(timezone.utc)
    # neutre di lega per il fallback neopromosse (audit 1.7): medie gol osservate
    neutral_lh = float(hist["home_goals"].mean()) if not hist.empty and "home_goals" in hist.columns else 1.35
    neutral_la = float(hist["away_goals"].mean()) if not hist.empty and "away_goals" in hist.columns else 1.15
    # sanity clamp (in caso di storico degenere)
    neutral_lh = float(np.clip(neutral_lh, *NEUTRAL_LAMBDA_BOUNDS))
    neutral_la = float(np.clip(neutral_la, *NEUTRAL_LAMBDA_BOUNDS))
    rows = []
    for f in fixtures.itertuples(index=False):
        is_prior = False
        try:
            d = dc.predict(f.home, f.away)
        except KeyError as exc:
            # squadra non nello storico DC (neopromossa): prior di lega invece di saltare la gara
            log.info("prior di lega per %s (%s vs %s): %s", getattr(f, "match_id", "?"), f.home, f.away, exc)
            # griglia neutra (attack=0, defence=0, hfa neutra) → λ di lega, ρ 0
            grid_neutral = probability_grid(neutral_lh, neutral_la, rho=0.0, size=GRID_SIZE)
            d = _grid_markets(grid_neutral)
            d["dc_attack_home"] = 0.0; d["dc_defence_home"] = 0.0
            d["dc_attack_away"] = 0.0; d["dc_defence_away"] = 0.0
            d["dc_home_advantage"] = 0.0; d["dc_rho"] = 0.0
            is_prior = True
        # Elo: se manca una squadra, usa 1500 invece di saltare (simula come prior)
        e = None
        try:
            if f.home in elo.ratings and f.away in elo.ratings:
                e = elo.predict(f.home, f.away)
            elif hasattr(elo, "_elo"):
                # una delle due manca: fallback Elo a 1500, ma mantieni il tilt se possibile
                e = elo.predict(f.home, f.away)
        except Exception:
            e = None
        r = calibrated_prediction(ensemble(d, e, w_dc=w_dc), cal)
        if is_prior:
            r["prior_di_lega"] = True
            # il modello resta dc/ensemble ma la scheda può dichiarare \"storico insufficiente, prior di lega\"
        r.update({
            "lambda_scale": float(cal.lambda_scale), "rho_shift": float(cal.rho_shift),
            "calibration_version": cal.version if not cal.is_identity else "identity",
            "calibration_n_fit": int(cal.n_fit),
            # come è stata stimata la correzione: la scheda lo dice invece di lasciarlo intuire
            "calibration_estimator": str(getattr(cal, "estimator", "") or ""),
            "calibration_window_days": int(getattr(cal, "window_days", 0) or 0),
            "match_id": getattr(f, "match_id", None), "home": f.home, "away": f.away,
            "utc_kickoff": getattr(f, "utc_kickoff", None), "league_key": getattr(f, "league_key", None),
            "made_at": made_at, "model_version": MODEL_VERSION, "n_train": dc.n_matches,
            "fair_home": fair_odds(r["p_home"]), "fair_draw": fair_odds(r["p_draw"]),
            "fair_away": fair_odds(r["p_away"]),
            "top_scores": str(r.get("top_scores")),
        })
        rows.append(r)
    cols_first = ["match_id", "league_key", "utc_kickoff", "home", "away", "model", "p_home", "p_draw", "p_away",
                  "lambda_home", "lambda_away", "p_over25", "p_btts"]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[[c for c in cols_first if c in df.columns] + [c for c in df.columns if c not in cols_first]]
        if "lambda_limitata" in df.columns:
            lim = int(pd.Series(df["lambda_limitata"]).fillna(False).astype(bool).sum())
            log.info("limiti di sicurezza su lambda: toccate %d partite su %d (%.2f%%)",
                     lim, len(df), 100.0 * lim / max(len(df), 1))
    return df, dc, elo


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di Wilson al 95% per una frequenza osservata ``k`` su ``n``.

    Serve a distinguere una distorsione reale dal rumore di campionamento: su 50 gare una
    differenza di 10 punti fra previsto e osservato può essere del tutto compatibile con il
    caso, e non giustifica una correzione del modello. L'intervallo di Wilson resta sensato
    anche per ``k = 0`` o ``k = n`` (a differenza dell'approssimazione normale).
    """
    if n <= 0:
        return (0.0, 1.0)
    p_hat = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = p_hat + z2 / (2 * n)
    half = z * float(np.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n)))
    return ((centre - half) / den, (centre + half) / den)


def rps(probs: list[list[float]], outcomes: list[int]) -> float:
    """Ranked Probability Score medio (0 = perfetto; ~0.2 tipico per il calcio)."""
    return float(pb.metrics.rps_average(np.asarray(probs, dtype=float), np.asarray(outcomes, dtype=int)))


def outcome_index(hg: int, ag: int) -> int:
    return 0 if hg > ag else (1 if hg == ag else 2)


def log_loss(p: float) -> float:
    return -math.log(max(p, 1e-12))


def xi_for_league(league_key: str, path: Path | None = None,
                  xi_default: float = 0.0018) -> float:
    """ξ per lega adottato dal laboratorio (docs/21 P3-a); altrimenti quello globale.

    Legge ``xi_league.parquet`` se esiste (lo scrive ``fda lab-xi``, nel workflow lab):
    cambia ξ solo per le leghe con ``adopt=True``, cioè IC 95% del ΔRPS interamente
    negativo e almeno ``lab.MIN_XI_LEAGUE_N`` gare fuori campione. File assente, lega
    non adottata o valore non positivo → ξ globale: il default resta la scelta prudente.
    """
    p = path or (PROCESSED_DIR / "xi_league.parquet")
    try:
        df = pd.read_parquet(p)
    except (FileNotFoundError, OSError):
        return xi_default
    if "adopt" not in df.columns or "xi_best" not in df.columns:
        return xi_default
    row = df[(df.league_key == league_key) & df.adopt.fillna(False).astype(bool)]
    if row.empty:
        return xi_default
    v = float(row.iloc[0]["xi_best"])
    return v if v > 0 else xi_default
