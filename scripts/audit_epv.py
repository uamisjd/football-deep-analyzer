"""Audit misurato della card «EPV pre-match» (docs/56).

Tre domande, tutte con numeri presi dai dati del repository — nessuna rete:

1. **sul sito di oggi**: quante schede pre-partita mostrano un verdetto EPV *diverso* dal
   favorito pubblicato dal modello?
2. **sul backtest fuori campione** (5.895 gare, `backtest.parquet`): quanto azzecca il
   verdetto EPV, quanto il modello, e — la domanda che conta — **chi ha ragione quando i
   due sono in disaccordo**;
3. **la costante di sede**: l'EPV del codice somma `0,3 × (1 × 0,5)` a chi gioca in casa
   (venue = 1 fisso). Quanto cambia il verdetto se quel termine si toglie?

L'EPV si ricostruisce con la stessa formula del codice (`analysis.py::epv_context`), dalle
posizioni e dai risultati **prima** di ogni gara (`history.parquet`, stato di stagione
ricostruito gara per gara): così il confronto è onesto, come nella pagina.

Uso: ``.venv/bin/python -m scripts.audit_epv [site_dir]`` — stampa solo riepiloghi.
"""

from __future__ import annotations

import argparse
import re
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# formula dell'indice **in uso** dalla correzione (analysis.py::classifica_forma): pesi
# dichiarati a mano e nessuna costante di sede
W_PPG, W_GD, W_POS = 0.5, 0.3, 0.2
# formula del **vecchio** EPV (analysis.py::epv_context prima della correzione), per il
# confronto prima/dopo
W_VENUE_OLD = 0.3
W_OLD = (0.4, 0.3, 0.2, 0.1)          # ppg, sede, gol, posizione
VENUE = 1.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def epv_score(ppg_diff: float, gd_diff: float, pos_diff: int) -> float:
    """Indice di contesto in uso: 50% punti/gara, 30% differenza reti delle ultime 3,
    20% posizione — **senza** il termine di sede costante del vecchio EPV."""
    n_ppg = _clamp(ppg_diff, -1.5, 1.5) / 1.5
    n_gd = _clamp(gd_diff / 3, -2, 2) / 2
    n_pos = _clamp(pos_diff / 10, -1, 1)
    return W_PPG * n_ppg + W_GD * n_gd + W_POS * n_pos


def epv_score_old(ppg_diff: float, gd_diff: float, pos_diff: int) -> float:
    """Vecchio EPV: pesi 40/30/20/10 con la sede come **costante** (+0,15 a chi gioca in casa)."""
    n_ppg = _clamp(ppg_diff, -1.5, 1.5) / 1.5
    n_gd = _clamp(gd_diff / 3, -2, 2) / 2
    n_pos = _clamp(pos_diff / 10, -1, 1)
    return W_OLD[0] * n_ppg + W_OLD[1] * (VENUE * 0.5) + W_OLD[2] * n_gd + W_OLD[3] * n_pos


def _prior_states(history: pd.DataFrame):
    """Stato di stagione **prima** di ogni gara: (squadra, stagione) → gare, punti, gol, esiti.

    Restituisce una funzione ``state(league, season, team, date)`` che legge lo stato
    accumulato fino a ``date`` esclusa (stesso principio della classifica FotMob del sito).
    """
    hist = history.copy()
    hist["date"] = pd.to_datetime(hist["date"], utc=True, errors="coerce")
    hist = hist[hist.date.notna() & hist.home_goals.notna() & hist.away_goals.notna()]
    hist = hist.sort_values(["league_key", "date"])
    timeline: dict[tuple[str, str, str], list[tuple[pd.Timestamp, dict]]] = defaultdict(list)
    running: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"g": 0, "pts": 0, "gf": 0, "ga": 0, "gd3": []})
    for r in hist.itertuples(index=False):
        season = str(getattr(r, "season", "") or "")
        for team, gf, ga in ((r.home, r.home_goals, r.away_goals), (r.away, r.away_goals, r.home_goals)):
            key = (r.league_key, season, team)
            timeline[key].append((r.date, dict(running[key])))
        for team, gf, ga, home in ((r.home, r.home_goals, r.away_goals, True),
                                   (r.away, r.away_goals, r.home_goals, False)):
            key = (r.league_key, season, team)
            st = running[key]
            st["g"] += 1
            st["pts"] += 3 if (gf > ga) else 1 if (gf == ga) else 0
            st["gf"] += int(gf)
            st["ga"] += int(ga)
            st["gd3"].append(int(gf) - int(ga))
            st["gd3"] = st["gd3"][-3:]

    def state(league: str, season: str, team: str, date: pd.Timestamp) -> dict | None:
        rows = timeline.get((league, season, team))
        if not rows:
            return None
        last = None
        for when, snap in rows:
            if when < date:
                last = snap
            else:
                break
        return last

    # classifica di lega **al giorno della gara**: punti e differenza reti di tutte le squadre
    # con almeno una gara prima di quella data. Serve per la posizione (il sito la legge dalla
    # classifica FotMob del giorno; qui si ricostruisce dallo storico, ordinando per punti e poi
    # per differenza reti come fanno i campionati).
    def standings(league: str, season: str, date: pd.Timestamp) -> dict[str, int]:
        rank: dict[str, int] = {}
        rows = []
        for (lg, se, team) in timeline:
            if lg != league or se != season:
                continue
            st = state(league, season, team, date)
            if st and st["g"]:
                rows.append((st["pts"], st["gf"] - st["ga"], st["gf"], team))
        for pos, (_p, _gd, _gf, team) in enumerate(
                sorted(rows, key=lambda x: (-x[0], -x[1], -x[2], x[3])), start=1):
            rank[team] = pos
        return rank

    state.standings = standings          # type: ignore[attr-defined]
    return state


def _rank_map(states: list[dict | None]) -> dict[int, int]:
    """Posizione (1 = migliore) per indice di squadra, ordinando per punti/gara."""
    def ppg(s):
        return (s["pts"] / s["g"]) if s and s["g"] else -1.0
    order = sorted(range(len(states)), key=lambda i: -ppg(states[i]))
    return {i: pos + 1 for pos, i in enumerate(order)}


def epv_vs_model(backtest: pd.DataFrame, history: pd.DataFrame) -> dict:
    bt = backtest.copy()
    bt["date"] = pd.to_datetime(bt["date"], utc=True, errors="coerce")
    bt = bt[bt.date.notna()]
    get = _prior_states(history)
    # la stagione non è nel backtest: si legge da `history` per la stessa partita (o, per le
    # gare non presenti lì, per la gara più vicina della stessa squadra in quella lega)
    hist_keys = (history.assign(date=pd.to_datetime(history["date"], utc=True, errors="coerce"))
                 .dropna(subset=["date"]))
    season_of: dict[tuple[str, str, str, str], str] = {}
    for r in hist_keys.itertuples(index=False):
        day = r.date.strftime("%Y-%m-%d")
        season_of[(r.league_key, r.home, r.away, day)] = str(r.season)
    rows = []
    # le partite sono valutate a coppie (casa, trasferta) della stessa lega/data/season:
    # per la posizione serve lo stato di **tutte** le squadre della lega in quel momento,
    # quindi si raccoglie prima l'insieme e si ordina per punti/gara.
    for r in bt.itertuples(index=False):
        lg, date = r.league_key, r.date
        season = season_of.get((lg, r.home, r.away, date.strftime("%Y-%m-%d")), "")
        if not season:
            # fallback: la stagione della gara più recente della squadra di casa prima di questa
            prev = hist_keys[(hist_keys.league_key == lg) & (hist_keys.home == r.home)
                             & (hist_keys.date <= date)].sort_values("date")
            season = str(prev.season.iloc[-1]) if not prev.empty else ""
        h = get(lg, season, r.home, date)
        a = get(lg, season, r.away, date)
        if not h or not a or h["g"] < 3 or a["g"] < 3:
            continue
        h_ppg, a_ppg = h["pts"] / h["g"], a["pts"] / a["g"]
        ppg_diff = h_ppg - a_ppg
        gd_diff = sum(h["gd3"]) - sum(a["gd3"])
        classifica = get.standings(lg, season, date)          # type: ignore[attr-defined]
        pos_diff = int(classifica.get(r.away, 0)) - int(classifica.get(r.home, 0))
        s = epv_score(ppg_diff, gd_diff, pos_diff)
        s_old = epv_score_old(ppg_diff, gd_diff, pos_diff)
        p_home, p_draw, p_away = float(r.p_home), float(r.p_draw), float(r.p_away)
        model_fav = max((p_home, "1"), (p_draw, "X"), (p_away, "2"))
        fav = "1" if model_fav[1] == "1" else "2" if model_fav[1] == "2" else "X"
        real = "1" if r.home_goals > r.away_goals else "2" if r.away_goals > r.home_goals else "X"
        epv_fav = "1" if s > 0.10 else "2" if s < -0.10 else "X"
        epv_no_fav = "1" if s_old > 0.10 else "2" if s_old < -0.10 else "X"
        import math
        rows.append({"league": lg, "date": date, "model_fav": fav, "epv_fav": epv_fav,
                     "epv_no_fav": epv_no_fav, "real": real, "p_max": model_fav[0],
                     "score": s, "score_no_venue": s_old,
                     "gd": int(r.home_goals) - int(r.away_goals), "p_edge": p_home - p_away,
                     "l1": math.log(max(p_home, 1e-9) / max(p_draw, 1e-9)),
                     "l2": math.log(max(p_away, 1e-9) / max(p_draw, 1e-9)),
                     "y": 0 if real == "1" else 1 if real == "X" else 2})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"n": 0}
    out: dict = {"n": len(df)}
    out["model_hit"] = float((df.model_fav == df.real).mean())
    out["epv_hit"] = float((df.epv_fav == df.real).mean())
    out["epv_no_venue_hit"] = float((df.epv_no_fav == df.real).mean())   # vecchio EPV
    out["epv_home_share"] = float((df.epv_fav == "1").mean())
    out["epv_no_venue_home_share"] = float((df.epv_no_fav == "1").mean())
    dis = df[(df.epv_fav != df.model_fav) & (df.epv_fav != "X") & (df.model_fav != "X")]
    out["disagree_n"] = len(dis)
    out["disagree_share"] = len(dis) / len(df)
    if len(dis):
        out["disagree_model_hit"] = float((dis.model_fav == dis.real).mean())
        out["disagree_epv_hit"] = float((dis.epv_fav == dis.real).mean())
    agree = df[(df.epv_fav == df.model_fav)]
    out["agree_n"] = len(agree)
    if len(agree):
        out["agree_hit"] = float((agree.model_fav == agree.real).mean())
    # correlazione (Spearman) con la differenza reti reale
    out["spearman_epv"] = float(df.score.corr(df.gd, method="spearman"))
    out["spearman_model"] = float(df.p_edge.corr(df.gd, method="spearman"))
    # per lega
    per = {}
    for lg, g in df.groupby("league"):
        per[lg] = (len(g), float((g.model_fav == g.real).mean()), float((g.epv_fav == g.real).mean()))
    out["per_league"] = per
    # --- l'EPV aggiunge qualcosa al modello? (logistica multinomiale, split temporale) ---
    out["added_value"] = _added_value(df)
    return out


def _added_value(df: pd.DataFrame) -> dict:
    """Il verdetto EPV, aggiunto come terza feature, migliora il modello fuori campione?

    Il modello è già una softmax su ``(l1, l2)`` (log-rapporti di probabilità vs pareggio).
    Si aggiunge la feature ``score`` con un coefficiente stimato **solo sul primo 70%
    cronologico** e si misura log-loss e RPS sul **30% più recente**: se il coefficiente è
    ~0 o il log-loss non scende, l'EPV non porta informazione che il modello non abbia già.
    """
    import numpy as np
    from scipy.optimize import minimize

    d = df.sort_values("date").reset_index(drop=True)
    cut = int(len(d) * 0.7)
    tr, te = d.iloc[:cut], d.iloc[cut:]
    if len(tr) < 200 or len(te) < 100:
        return {"n_train": len(tr), "n_test": len(te)}

    def softmax(z):
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def probs(X, theta):
        # classi 1, X, 2 con il pareggio come riferimento: z = [l1 + b1*epv, 0, l2 + b2*epv]
        b1, b2 = theta
        l1 = np.asarray(X["l1"], dtype=float)
        l2 = np.asarray(X["l2"], dtype=float)
        sc = np.asarray(X["score"], dtype=float)
        z = np.column_stack([l1 + b1 * sc, np.zeros(len(X)), l2 + b2 * sc])
        return softmax(z)

    def nll(theta, X, y):
        p = probs(X, theta)
        return -np.log(np.clip(p[np.arange(len(X)), y.to_numpy()], 1e-12, None)).mean()

    def rps(p, y):
        # RPS su 3 esiti ordinati: cumulate delle probabilità e dell'esito reale
        cum = np.cumsum(p, axis=1)[:, :2]
        real = np.zeros((len(y), 2))
        yv = y.to_numpy()
        real[yv >= 1, 0] = 1
        real[yv == 2, 1] = 1
        return float(((cum - real) ** 2).sum(axis=1).mean() / 2)

    base_te = probs(te, (1e-9, 1e-9))      # modello pubblicato, senza EPV
    res = minimize(nll, np.zeros(2), args=(tr, tr.y), method="Nelder-Mead",
                   options={"maxiter": 800, "xatol": 1e-4})
    b1, b2 = float(res.x[0]), float(res.x[1])
    fit_te = probs(te, (b1, b2))
    return {"n_train": len(tr), "n_test": len(te), "b1": b1, "b2": b2,
            "logloss_model": float(-np.log(np.clip(base_te[np.arange(len(te)), te.y.to_numpy()],
                                                   1e-12, None)).mean()),
            "logloss_epv": float(-np.log(np.clip(fit_te[np.arange(len(te)), te.y.to_numpy()],
                                                 1e-12, None)).mean()),
            "rps_model": rps(base_te, te.y), "rps_epv": rps(fit_te, te.y)}


def epv_on_site(site: Path) -> dict:
    """Sul sito generato: etichette EPV e disaccordo col favorito della previsione pubblicata."""
    preds = pd.read_parquet(ROOT / "data" / "processed" / "predictions.parquet")
    preds["made_at"] = pd.to_datetime(preds["made_at"], utc=True, errors="coerce")
    latest = preds.sort_values("made_at").drop_duplicates("match_id", keep="last").set_index("match_id")
    labels: dict[str, int] = defaultdict(int)
    agree = disagree = tot = 0
    scores: list[float] = []
    for pg in sorted((site / "partite").glob("*.html")):
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or 'id="epv"' not in html:
            continue
        m = re.search(r"EPV pre-match — (.+?) \(score (-?[\d,]+)\)", html)
        if not m:
            continue
        score = float(m.group(2).replace(",", "."))
        labels[m.group(1)] += 1
        scores.append(score)
        mid = int(pg.stem)
        if mid not in latest.index:
            continue
        p = latest.loc[mid]
        fav = max((float(p.p_home), "1"), (float(p.p_draw), "X"), (float(p.p_away), "2"))[1]
        epv_fav = "1" if score > 0.10 else "2" if score < -0.10 else "X"
        tot += 1
        if epv_fav == fav or (epv_fav == "X" and fav == "X"):
            agree += 1
        else:
            disagree += 1
    return {"pagine": tot, "etichette": dict(labels), "accordo": agree, "disaccordo": disagree,
            "mediana_score": round(statistics.median(scores), 3) if scores else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("site_dir", nargs="?", default=str(ROOT / "site"))
    args = ap.parse_args(argv)
    site = Path(args.site_dir)
    print("=== 1. sul sito generato (le schede pre-partita di oggi) ===")
    if (site / "partite").is_dir():
        r = epv_on_site(site)
        print(f"schede con card EPV: {r['pagine']} · etichette {r['etichette']}")
        print(f"accordo col favorito del modello: {r['accordo']} · DISACCORDO: {r['disaccordo']}"
              f" ({(r['disaccordo'] / max(r['pagine'], 1)) * 100:.0f}%) · mediana score {r['mediana_score']}")
    else:
        print(f"nessuna build in {site}/partite: esegui `fda build` per le misure sul sito")
    print("\n=== 2. sul backtest fuori campione (stessa formula del codice, stato ricostruito) ===")
    bt = pd.read_parquet(ROOT / "data" / "processed" / "backtest.parquet")
    hist = pd.read_parquet(ROOT / "data" / "processed" / "history.parquet")
    m = epv_vs_model(bt, hist)
    if not m.get("n"):
        print("nessuna gara utilizzabile (history/backtest insufficienti)")
        return 0
    print(f"gare valutate: {m['n']}")
    print(f"favorito azzeccato — modello: {m['model_hit']:.3f} · indice in uso: {m['epv_hit']:.3f} "
          f"· vecchio EPV (sede costante): {m['epv_no_venue_hit']:.3f}")
    print(f"quota di verdetti «casa» — indice in uso: {m['epv_home_share']:.3f} "
          f"· vecchio EPV: {m['epv_no_venue_home_share']:.3f}")
    print(f"disaccordi indice↔modello (esclusi i pareggi): {m['disagree_n']} "
          f"({m['disagree_share']:.1%} delle gare)")
    if "disagree_model_hit" in m:
        print(f"  quando sono in disaccordo, azzecca — modello: {m['disagree_model_hit']:.3f} "
              f"· indice: {m['disagree_epv_hit']:.3f}")
    if "agree_hit" in m:
        print(f"  quando sono d'accordo ({m['agree_n']} gare), azzecca: {m['agree_hit']:.3f}")
    print(f"correlazione (Spearman) con la differenza reti reale — indice: {m['spearman_epv']:.3f} "
          f"· modello: {m['spearman_model']:.3f}")
    print("per lega (n · modello · indice): " + " · ".join(
        f"{lg} {n} {hi:.3f}/{he:.3f}" for lg, (n, hi, he) in sorted(m["per_league"].items())))
    av = m.get("added_value") or {}
    if av.get("n_test"):
        print("\n=== 3. l'EPV aggiunge informazione al modello? (coeff. stimati sul primo 70%, "
              "misure sul 30% più recente) ===")
        print(f"train {av['n_train']} gare · test {av['n_test']} gare · coefficienti EPV "
              f"b1 {av['b1']:+.3f} (casa) · b2 {av['b2']:+.3f} (trasferta)")
        print(f"log-loss — modello pubblicato: {av['logloss_model']:.4f} · "
              f"modello+EPV: {av['logloss_epv']:.4f} (Δ {av['logloss_epv'] - av['logloss_model']:+.4f})")
        print(f"RPS      — modello pubblicato: {av['rps_model']:.4f} · "
              f"modello+EPV: {av['rps_epv']:.4f} (Δ {av['rps_epv'] - av['rps_model']:+.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
