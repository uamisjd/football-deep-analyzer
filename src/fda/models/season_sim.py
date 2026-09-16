"""Simulazione Monte Carlo del resto di stagione (fase 2 della roadmap, doc 01 §8).

Per ogni lega: fit Dixon-Coles + Elo su storico (datahub + risultati correnti,
stesso criterio di `fda predict`), probabilità 1X2 per ogni gara restante
(ensemble 70/30), poi N stagioni simulate campionando i punteggi dalla griglia DC
→ distribuzione finale di posizione: % titolo, % accesso UCL ordinario (top N configurato),
% retrocessione, punti attesi. Squadre senza storico DC (es. neopromosse) usano parametri neutri
(λ = medie di lega): è dichiarato nella nota della pagina del sito.
"""

from __future__ import annotations

import logging
import warnings
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .calibration import Calibration
from .dc_grid import probability_grid
from .predict import (
    MODEL_VERSION,
    NEUTRAL_LAMBDA_BOUNDS,
    DixonColesModel,
    EloModel,
    calibrated_prediction,
    ensemble,
)

log = logging.getLogger(__name__)

# Quante squadre sono a rischio retrocessione per lega (posti "rossi": dirette + playoff).
# NED1: 2 dirette + 1 playoff · FRA1: 2 dirette + 1 barrage · POR1: 2 dirette + 1 playoff (16ª)
# → tutte a 3; le altre big-5 a 3 dirette. Nota esplicita sul sito.
REL_COUNTS: dict[str, int] = {
    "ITA1": 3, "ESP1": 3, "ENG1": 3, "GER1": 3,
    "FRA1": 3, "NED1": 3, "POR1": 3,
}
DEFAULT_N_SIMS = 10_000
DEFAULT_TOP_N: int | None = 4  # fallback per fixture/test e dati storici senza metadato


def mc_se(p: float, n: int = DEFAULT_N_SIMS) -> float:
    """Errore standard Monte Carlo di una probabilità stimata su ``n`` simulazioni.

    Ritorna una quantità nella scala 0–1 (``0,005`` = 0,5 punti percentuali).
    Il conteggio è una misura di incertezza della simulazione, non un intervallo
    predittivo per la stagione reale.
    """
    if n <= 0:
        raise ValueError("il numero di simulazioni deve essere positivo")
    q = min(max(float(p), 0.0), 1.0)
    return float(np.sqrt(q * (1.0 - q) / n))


def mc_percent(p: float) -> int:
    """Probabilità Monte Carlo in percento, arrotondata all'intero più vicino.

    La pagina non pubblica decimali più fini della precisione sostenuta da 10.000
    simulazioni (massimo 0,5 punti percentuali di errore standard).
    """
    q = min(max(float(p), 0.0), 1.0)
    return int(np.floor(q * 100.0 + 0.5))


def persist_history(store: Any, hist: pd.DataFrame, league_key: str) -> int:
    """Salva lo storico usato dai modelli nella tabella ``history``.

    Perché: oggi lo storico viene riscaricato a ogni run e non resta traccia di **su quali
    partite** sono state addestrate le previsioni pubblicate. Salvarlo rende riproducibile
    ogni numero (regola B1), permette al laboratorio e alla calibrazione di girare offline
    (anche dal sandbox dell'agente, dove i mirror non sono raggiungibili) e costa poche
    decine di kB per run. È uno snapshot per lega: ``replace_by="league_key"``.
    """
    if store is None or hist is None or hist.empty:
        return 0
    df = hist.copy()
    df["league_key"] = league_key
    df["date"] = pd.to_datetime(df["date"])
    cols = [c for c in ("league_key", "date", "season", "home", "away", "home_goals", "away_goals",
                        "odds_home", "odds_draw", "odds_away") if c in df.columns]
    return int(store.upsert("history", df[cols], replace_by="league_key"))


def build_hist(lg: Any, fixtures: pd.DataFrame, history_client: Any,
               seasons_back: int = 3, yr: int | None = None, store: Any = None) -> pd.DataFrame:
    """Storico di una lega: stagioni datahub + risultati correnti dal calendario FotMob.

    Nomi mappati sui canonici (come in `fda predict`): un'unica fonte di verità
    per predict e simulate. Con ``store`` lo storico viene anche salvato in ``history``
    (vedi :func:`persist_history`).
    """
    from ..config import season, season_start_year
    from ..teams import canonical

    yr = yr or season_start_year()
    hist = history_client.seasons(lg, range(yr - seasons_back, yr))
    cur = pd.DataFrame()
    if not fixtures.empty:
        fin = fixtures[(fixtures.league_id == lg.fotmob_id) & (fixtures.status == "finished")]
        cur = pd.DataFrame({"date": pd.to_datetime(fin.utc_kickoff).dt.tz_localize(None),
                            "season": season(), "league_key": lg.key,
                            "home": fin.home_name, "away": fin.away_name,
                            "home_goals": fin.home_goals.astype(int), "away_goals": fin.away_goals.astype(int)})
    hist = pd.concat([hist, cur], ignore_index=True) if not hist.empty else cur
    if not hist.empty:
        hist["home"] = hist["home"].map(canonical)
        hist["away"] = hist["away"].map(canonical)
        if store is not None:
            try:
                persist_history(store, hist, getattr(lg, "key", str(lg)))
            except Exception as exc:                                # salvare non deve bloccare i modelli
                log.warning("storico non salvato per %s (%s: %s)", getattr(lg, "name", lg),
                            type(exc).__name__, exc)
    return hist


def _match_grid(dc: DixonColesModel, elo: EloModel, home: str, away: str, w_dc: float,
                neutral: tuple[float, float],
                calibration: Calibration | None = None) -> tuple[np.ndarray, float, float]:
    """Griglia punteggi (matrice 11×11 normalizzata) + λ per una gara restante.

    Ensemble 70/30 come le previsioni e **la stessa calibrazione**: le proiezioni di
    stagione e le schede partita devono derivare dalle identiche probabilità, altrimenti
    «Proiezioni» e «Analisi» raccontano due campionati diversi. Senza storico DC per una
    squadra → λ neutre (medie gol di lega, già inclusive del fattore campo).
    """
    try:
        d = dc.predict(home, away)
    except KeyError:
        d = None
    if d is None:
        lm, la = neutral
        grid = probability_grid(lm, la, rho=0.0, size=11)
        m = np.asarray(grid.grid, dtype=float)
        return m / m.sum(), lm, la
    e = elo.predict(home, away) if home in elo.ratings and away in elo.ratings else None
    r = calibrated_prediction(ensemble(d, e, w_dc=w_dc), calibration)
    lm, la = float(r["lambda_home"]), float(r["lambda_away"])
    rho = float(r.get("dc_rho") or 0.0)
    grid = probability_grid(lm, la, rho=rho, size=11)
    m = np.asarray(grid.grid, dtype=float)
    return m / m.sum(), lm, la


def simulate_league(hist: pd.DataFrame, remaining: pd.DataFrame, base_points: dict[str, float],
                    base_gd: dict[str, float], base_played: dict[str, int], w_dc: float = 0.7,
                    xi: float = 0.0018, n_sims: int = DEFAULT_N_SIMS, seed: int | None = None,
                    rel_count: int = 3, calibration: Calibration | None = None,
                    base_gf: dict[str, float] | None = None,
                    top_n: int | None = DEFAULT_TOP_N) -> pd.DataFrame:
    """Simula `n_sims` volte il resto di stagione; ritorna una riga per squadra.

    `remaining`: colonne home/away (nomi canonici); `base_*`: stato attuale dal
    calendario; `rel_count`: quante squadre retrocedono in questa lega. Campiona i
    punteggi dalla griglia DC (ρ compreso) così i tie-break usano la differenza reti
    simulata. Il secondo spareggio è sui gol fatti; gli scontri diretti non sono
    simulati e il nome alfabetico rende deterministico l'ultimo caso di parità.
    `top_n` è il numero configurato di posizioni per l'accesso UCL ordinario; ``None``
    lascia il relativo contenuto non pubblicato invece di inventare una soglia.
    """
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    dc = DixonColesModel(xi=xi).fit(hist)
    elo = EloModel().fit(hist)
    lo_neutral, hi_neutral = NEUTRAL_LAMBDA_BOUNDS
    neutral = (
        float(np.clip(hist["home_goals"].mean(), lo_neutral, hi_neutral)),
        float(np.clip(hist["away_goals"].mean(), lo_neutral, hi_neutral)),
    )
    # Universo simulato = le squadre della stagione corrente (con punti o con gare da
    # giocare); chi non ha storico DC viene comunque simulata con parametri neutri.
    teams = sorted(set(base_points) | set(remaining["home"]) | set(remaining["away"]))
    if not teams:
        raise ValueError("nessuna squadra da simulare")
    # Il numero di posti non può essere maggiore delle squadre né minore di uno: una
    # configurazione errata deve fallire prima di produrre una tabella apparentemente valida.
    if top_n is not None and not 1 <= int(top_n) <= len(teams):
        raise ValueError(f"top_n non valido: {top_n}")
    top_n = int(top_n) if top_n is not None else None
    ti = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    rng = np.random.default_rng(seed)

    pts = np.zeros((n_sims, n))
    gd = np.zeros((n_sims, n))
    gf = np.zeros((n_sims, n))
    for f in remaining.itertuples(index=False):
        h, a = f.home, f.away
        if h not in ti or a not in ti:
            continue  # gara fuori perimetro (squadra non simulabile): esclusa
        m, _, _ = _match_grid(dc, elo, h, a, w_dc, neutral, calibration)
        cum = m.ravel().cumsum()
        idx = np.searchsorted(cum, rng.random(n_sims))
        k = m.shape[1]
        hg, ag = idx // k, idx % k
        hp = np.where(hg > ag, 3.0, np.where(hg == ag, 1.0, 0.0))
        ap = np.where(ag > hg, 3.0, np.where(hg == ag, 1.0, 0.0))
        pts[:, ti[h]] += hp
        pts[:, ti[a]] += ap
        gd[:, ti[h]] += hg - ag
        gd[:, ti[a]] += ag - hg
        gf[:, ti[h]] += hg
        gf[:, ti[a]] += ag

    bp = np.array([base_points.get(t, 0.0) for t in teams])
    bg = np.array([base_gd.get(t, 0.0) for t in teams])
    bfor = np.array([(base_gf or {}).get(t, 0.0) for t in teams])
    total_pts = bp[None, :] + pts
    total_gd = bg[None, :] + gd
    total_gf = bfor[None, :] + gf
    # Classifica per simulazione: punti → differenza reti → gol fatti → nome.
    # `lexsort` usa l'ultima chiave come primaria; team è già alfabetico, quindi l'ultimo
    # spareggio resta stabile senza fingere di simulare gli scontri diretti.
    team_order = np.broadcast_to(np.arange(n, dtype=float), (n_sims, n))
    order = np.lexsort((team_order, -total_gf, -total_gd, -total_pts), axis=1)
    pos = order.argsort(axis=1) + 1  # posizione (1-based) di ogni squadra in ogni simulazione
    p_top_n = (pos <= top_n).mean(0) if top_n is not None else np.full(n, np.nan)
    return pd.DataFrame({
        "team": teams,
        "played": [base_played.get(t, 0) for t in teams],
        "points": bp,
        "exp_points": total_pts.mean(0).round(1),
        "pos_mean": pos.mean(0).round(1),
        "p_title": (pos == 1).mean(0).round(4),
        "top_n": top_n,
        "p_top_n": p_top_n.round(4),
        # Alias di compatibilità per snapshot e schede precedenti: dal primo snapshot
        # nuovo il verificatore confronta questo valore con `p_top_n`, non lo interpreta
        # più come un TOP-4 universale.
        "p_top4": p_top_n.round(4),
        "p_rel": (pos > (n - rel_count)).mean(0).round(4),
        "n_sims": n_sims, "n_train": dc.n_matches, "model_version": MODEL_VERSION,
        "made_at": datetime.now(UTC),
    })


def simulate_all(keys: list[str] | None = None, store: Any = None, n_sims: int = DEFAULT_N_SIMS,
                 seasons_back: int = 3, seed: int | None = None, w_dc: float = 0.7,
                 calibration: Calibration | None = None) -> pd.DataFrame:
    """Simula tutte le leghe richieste e salva la tabella `season_sim`."""
    from ..config import leagues
    from ..sources.history import HistoryClient
    from ..store import Store

    store = store or Store()
    hc = HistoryClient()
    fixtures = store.read("fixtures")
    if calibration is None:
        from .calibration import from_store

        calibration = from_store(store)
    out = []
    for lg in leagues(keys or None):
        try:
            hist = build_hist(lg, fixtures, hc, seasons_back=seasons_back, store=store)
            if hist.empty or len(hist) < 50:
                log.warning("%s: storico insufficiente (%s), simulazione saltata", lg.name, len(hist))
                continue
            fin = fixtures[(fixtures.league_id == lg.fotmob_id) & (fixtures.status == "finished")]
            rem = fixtures[(fixtures.league_id == lg.fotmob_id) & (fixtures.status == "scheduled")]
            if rem.empty:
                log.warning("%s: nessuna gara restante, simulazione saltata", lg.name)
                continue
            from ..teams import canonical
            rem = pd.DataFrame({"home": rem.home_name.map(canonical), "away": rem.away_name.map(canonical)})
            base_pts, base_gd, base_gf, base_played = {}, {}, {}, {}
            for r in fin.itertuples(index=False):
                h, a = canonical(r.home_name), canonical(r.away_name)
                hg, ag = int(r.home_goals), int(r.away_goals)
                base_pts[h] = base_pts.get(h, 0) + (3 if hg > ag else (1 if hg == ag else 0))
                base_pts[a] = base_pts.get(a, 0) + (3 if ag > hg else (1 if hg == ag else 0))
                base_gd[h] = base_gd.get(h, 0) + hg - ag
                base_gd[a] = base_gd.get(a, 0) + ag - hg
                base_gf[h] = base_gf.get(h, 0) + hg
                base_gf[a] = base_gf.get(a, 0) + ag
                base_played[h] = base_played.get(h, 0) + 1
                base_played[a] = base_played.get(a, 0) + 1
            df = simulate_league(
                hist, rem, base_pts, base_gd, base_played, w_dc=w_dc,
                n_sims=n_sims, seed=seed, rel_count=REL_COUNTS.get(lg.key, 3),
                calibration=calibration, base_gf=base_gf,
                top_n=getattr(lg, "ucl_spots", DEFAULT_TOP_N),
            )
            df.insert(0, "league_key", lg.key)
            # È uno snapshot per lega: rimuove anche eventuali righe con una vecchia grafia
            # della squadra (es. «Nottm Forest» → «Nottingham Forest») rimaste da un run
            # precedente, invece di lasciarle concorrere alla somma delle probabilità.
            store.upsert("season_sim", df.to_dict("records"), replace_by="league_key")
            out.append(df)
            top = df.sort_values("exp_points", ascending=False).head(3)
            log.info("%s: %d simulazioni su %d gare restanti — %s", lg.name, n_sims, len(rem),
                     " · ".join(f"{r.team} {r.exp_points:.0f}pt ({r.p_title:.0%})" for r in top.itertuples()))
        except Exception as exc:  # noqa: BLE001 — una lega senza dati non deve fermare le altre
            log.warning("%s: simulazione saltata (%s: %s)", lg.name, type(exc).__name__, exc)
    cols = ["league_key", "team", "played", "points", "exp_points", "pos_mean",
            "p_title", "top_n", "p_top_n", "p_top4", "p_rel", "n_sims", "n_train",
            "model_version", "made_at"]
    return pd.concat(out, ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)
