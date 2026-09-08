"""Simulazione Monte Carlo del resto di stagione (fase 2 della roadmap, doc 01 §8).

Per ogni lega: fit Dixon-Coles + Elo su storico (datahub + risultati correnti,
stesso criterio di `fda predict`), probabilità 1X2 per ogni gara restante
(ensemble 70/30), poi N stagioni simulate campionando i punteggi dalla griglia DC
→ distribuzione finale di posizione: % titolo, % top-4, % retrocessione,
punti attesi. Squadre senza storico DC (es. neopromosse) usano parametri neutri
(λ = medie di lega): è dichiarato nella nota della pagina del sito.
"""

from __future__ import annotations

import logging
import warnings
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .predict import MODEL_VERSION, DixonColesModel, EloModel, ensemble

log = logging.getLogger(__name__)

# quante squadre retrocedono per lega (dirette + playoff: NED1 ha 2 dirette + playoff,
# FRA1 ha 2 dirette + barrage → conteggi armonizzati, nota esplicita sul sito)
REL_COUNTS: dict[str, int] = {"ITA1": 3, "ESP1": 3, "ENG1": 3, "GER1": 3, "FRA1": 3, "NED1": 3, "POR1": 2}
TOP_N = 4


def build_hist(lg: Any, fixtures: pd.DataFrame, history_client: Any,
               seasons_back: int = 3, yr: int | None = None) -> pd.DataFrame:
    """Storico di una lega: stagioni datahub + risultati correnti dal calendario FotMob.

    Nomi mappati sui canonici (come in `fda predict`): un'unica fonte di verità
    per predict e simulate.
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
    return hist


def _match_grid(dc: DixonColesModel, elo: EloModel, home: str, away: str, w_dc: float,
                neutral: tuple[float, float]) -> tuple[np.ndarray, float, float]:
    """Griglia punteggi (matrice 11×11 normalizzata) + λ per una gara restante.

    Ensemble 70/30 come le previsioni; senza storico DC per una squadra → λ neutre
    (medie gol di lega, già inclusive del fattore campo).
    """
    import penaltyblog as pb

    try:
        d = dc.predict(home, away)
    except KeyError:
        d = None
    if d is None:
        lm, la = neutral
        grid = pb.models.create_dixon_coles_grid(lm, la, rho=0.0, max_goals=10)
        m = np.asarray(grid.grid, dtype=float)
        return m / m.sum(), lm, la
    e = elo.predict(home, away) if home in elo.ratings and away in elo.ratings else None
    r = ensemble(d, e, w_dc=w_dc)
    lm, la = float(r["lambda_home"]), float(r["lambda_away"])
    rho = float(r.get("dc_rho") or 0.0)
    grid = pb.models.create_dixon_coles_grid(lm, la, rho=rho, max_goals=10)
    m = np.asarray(grid.grid, dtype=float)
    return m / m.sum(), lm, la


def simulate_league(hist: pd.DataFrame, remaining: pd.DataFrame, base_points: dict[str, float],
                    base_gd: dict[str, float], base_played: dict[str, int], w_dc: float = 0.7,
                    xi: float = 0.0018, n_sims: int = 10000, seed: int | None = None,
                    rel_count: int = 3) -> pd.DataFrame:
    """Simula `n_sims` volte il resto di stagione; ritorna una riga per squadra.

    `remaining`: colonne home/away (nomi canonici); `base_*`: stato attuale dal
    calendario; `rel_count`: quante squadre retrocedono in questa lega. Campiona i
    punteggi dalla griglia DC (ρ compreso) così i tie-break usano la differenza
    reti simulata, non una loro approssimazione.
    """
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    dc = DixonColesModel(xi=xi).fit(hist)
    elo = EloModel().fit(hist)
    neutral = (float(hist["home_goals"].mean()), float(hist["away_goals"].mean()))
    # universo simulato = le squadre della stagione corrente (con punti o con gare da giocare);
    # chi non ha storico DC viene comunque simulata con parametri neutri (nota sul sito)
    teams = sorted(set(base_points) | set(remaining["home"]) | set(remaining["away"]))
    if not teams:
        raise ValueError("nessuna squadra da simulare")
    ti = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    rng = np.random.default_rng(seed)

    pts = np.zeros((n_sims, n))
    gd = np.zeros((n_sims, n))
    for f in remaining.itertuples(index=False):
        h, a = f.home, f.away
        if h not in ti or a not in ti:
            continue  # gara fuori perimetro (squadra non simulabile): esclusa
        m, _, _ = _match_grid(dc, elo, h, a, w_dc, neutral)
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

    bp = np.array([base_points.get(t, 0.0) for t in teams])
    bg = np.array([base_gd.get(t, 0.0) for t in teams])
    total_pts = bp[None, :] + pts
    total_gd = bg[None, :] + gd
    # classifica per simulazione: punti, poi differenza reti (chiave intera stabile)
    order = np.argsort(-(total_pts * 1000 + total_gd + 400), axis=1, kind="stable")
    pos = order.argsort(axis=1) + 1  # posizione (1-based) di ogni squadra in ogni simulazione
    return pd.DataFrame({
        "team": teams,
        "played": [base_played.get(t, 0) for t in teams],
        "points": bp,
        "exp_points": total_pts.mean(0).round(1),
        "pos_mean": pos.mean(0).round(1),
        "p_title": (pos == 1).mean(0).round(4),
        "p_top4": (pos <= TOP_N).mean(0).round(4),
        "p_rel": (pos > (n - rel_count)).mean(0).round(4),
        "n_sims": n_sims, "n_train": dc.n_matches, "model_version": MODEL_VERSION,
        "made_at": datetime.now(UTC),
    })


def simulate_all(keys: list[str] | None = None, store: Any = None, n_sims: int = 10000,
                 seasons_back: int = 3, seed: int | None = None, w_dc: float = 0.7) -> pd.DataFrame:
    """Simula tutte le leghe richieste e salva la tabella `season_sim`."""
    from ..config import leagues
    from ..sources.history import HistoryClient
    from ..store import Store

    store = store or Store()
    hc = HistoryClient()
    fixtures = store.read("fixtures")
    out = []
    for lg in leagues(keys or None):
        try:
            hist = build_hist(lg, fixtures, hc, seasons_back=seasons_back)
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
            base_pts, base_gd, base_played = {}, {}, {}
            for r in fin.itertuples(index=False):
                h, a = canonical(r.home_name), canonical(r.away_name)
                hg, ag = int(r.home_goals), int(r.away_goals)
                base_pts[h] = base_pts.get(h, 0) + (3 if hg > ag else (1 if hg == ag else 0))
                base_pts[a] = base_pts.get(a, 0) + (3 if ag > hg else (1 if hg == ag else 0))
                base_gd[h] = base_gd.get(h, 0) + hg - ag
                base_gd[a] = base_gd.get(a, 0) + ag - hg
                base_played[h] = base_played.get(h, 0) + 1
                base_played[a] = base_played.get(a, 0) + 1
            df = simulate_league(hist, rem, base_pts, base_gd, base_played, w_dc=w_dc,
                                 n_sims=n_sims, seed=seed, rel_count=REL_COUNTS.get(lg.key, 3))
            df.insert(0, "league_key", lg.key)
            store.upsert("season_sim", df.to_dict("records"))
            out.append(df)
            top = df.sort_values("exp_points", ascending=False).head(3)
            log.info("%s: %d simulazioni su %d gare restanti — %s", lg.name, n_sims, len(rem),
                     " · ".join(f"{r.team} {r.exp_points:.0f}pt ({r.p_title:.0%})" for r in top.itertuples()))
        except Exception as exc:  # noqa: BLE001 — una lega senza dati non deve fermare le altre
            log.warning("%s: simulazione saltata (%s: %s)", lg.name, type(exc).__name__, exc)
    cols = ["league_key", "team", "played", "points", "exp_points", "pos_mean",
            "p_title", "p_top4", "p_rel", "n_sims", "n_train", "model_version", "made_at"]
    return pd.concat(out, ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)
