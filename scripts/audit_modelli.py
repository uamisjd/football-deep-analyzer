"""Audit quantitativo dei modelli di previsione (2026-09-20).

Tutto offline, sui Parquet versionati in ``data/processed``: nessuna richiesta di rete.
Ogni sezione risponde a una domanda precisa e stampa solo numeri ricalcolabili:

1. **Quanto vale ogni pezzo della ricetta** (backtest fuori campione, 5.891 gare):
   RPS / log-loss / Brier di Dixon-Coles puro, Elo puro, ensemble grezzo e ensemble calibrato,
   con IC 95% appaiato (bootstrap) sulle differenze.
2. **Affidabilità (reliability) dell'1X2**: per ogni esito, probabilità dichiarata per decile
   contro frequenza osservata con intervallo di Wilson; scomposizione di Brier
   (affidabilità / risoluzione / incertezza); prova della temperatura (il vettore è troppo
   piatto o troppo appuntito?) stimata walk-forward.
3. **Distanza dal mercato** dove le quote di chiusura sono nello storico (NED1/POR1).
4. **Riposo**: gol segnati / λ per fascia di giorni di riposo (solo campionato) e ΔRPS del
   fattore di riposo oggi in produzione applicato al backtest.
5. **Valore di mercato dei titolari**: sulle gare finite con `match_info` (unico campione
   disponibile), Δlog-loss dell'inclinazione per una griglia di k.
6. **Assenze**: stesso campione, effetto dell'inclinazione oggi in produzione.

Uso: ``python scripts/audit_modelli.py [--json docs/_audit_modelli.json]``
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fda.models.backtest import calibrate_rows
from fda.models.calibration import from_store
from fda.models.dc_grid import GRID_SIZE, grid_markets_many, tau_grid_many
from fda.models.lab import paired_bootstrap
from fda.models.predict import (
    absences_tilt,
    market_value_tilt,
    rest_tilt,
    wilson_interval,
)
from fda.store import Store
from fda.teams import canonical

DATA = Path("data/processed")


# ----------------------------------------------------------------------------- metriche
def rps_rows(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    O = np.zeros_like(P)
    O[np.arange(len(o)), o] = 1.0
    return ((np.cumsum(P, 1) - np.cumsum(O, 1)) ** 2).sum(1) / 2.0


def logloss_rows(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(P[np.arange(len(o)), o], 1e-12, 1.0))


def brier_rows(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    O = np.zeros_like(P)
    O[np.arange(len(o)), o] = 1.0
    return ((P - O) ** 2).sum(1)


def vec(df: pd.DataFrame, prefix: str) -> np.ndarray:
    P = df[[f"{prefix}home", f"{prefix}draw", f"{prefix}away"]].to_numpy(float)
    return P / P.sum(1, keepdims=True)


def fmt(x: float, nd: int = 4) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def confronto(nome: str, P: np.ndarray, o: np.ndarray, ref: np.ndarray | None) -> dict:
    r, ll, b = rps_rows(P, o), logloss_rows(P, o), brier_rows(P, o)
    row = {"nome": nome, "n": len(o), "rps": float(r.mean()), "logloss": float(ll.mean()),
           "brier": float(b.mean()), "pareggio_previsto": float(P[:, 1].mean())}
    if ref is not None:
        d = r - rps_rows(ref, o)
        lo, hi = paired_bootstrap(d, draws=3000)
        row.update({"delta_rps": float(d.mean()), "ci_lo": lo, "ci_hi": hi})
    return row


# ----------------------------------------------------------------------------- 1 + 2
def sezione_ricetta(bt: pd.DataFrame, cal) -> dict:
    o = bt["outcome"].to_numpy(int)
    P_pub = vec(bt, "p_")                     # calibrata (come pubblicata oggi)
    P_raw = vec(bt, "p_") if "p_home_raw" not in bt else vec(bt.rename(columns={
        "p_home_raw": "raw_home", "p_draw_raw": "raw_draw", "p_away_raw": "raw_away"}), "raw_")
    P_dc = vec(bt, "dc_p_")
    P_elo = vec(bt, "elo_p_")
    naive = np.tile(np.bincount(o, minlength=3) / len(o), (len(o), 1))
    rows = [confronto("pubblicato (DC+Elo tilt, calibrato)", P_pub, o, None)]
    ref = P_pub
    rows.append(confronto("DC+Elo tilt grezzo (senza calibrazione)", P_raw, o, ref))
    rows.append(confronto("Dixon-Coles puro (dc_p_*)", P_dc, o, ref))
    rows.append(confronto("Elo puro (elo_p_*)", P_elo, o, ref))
    rows.append(confronto("naive: frequenze del campione", naive, o, ref))
    print("\n== 1. Quanto vale ogni pezzo (backtest fuori campione, stessa gare) ==")
    print(f"{'ricetta':44s} {'n':>5s} {'RPS':>7s} {'logloss':>8s} {'Brier':>7s} {'X prev':>7s} {'ΔRPS vs pubbl.':>16s} {'IC 95%':>22s}")
    for r in rows:
        ci = f"[{fmt(r['ci_lo'], 5)}; {fmt(r['ci_hi'], 5)}]" if "ci_lo" in r else ""
        d = fmt(r["delta_rps"], 5) if "delta_rps" in r else ""
        print(f"{r['nome']:44s} {r['n']:5d} {fmt(r['rps']):>7s} {fmt(r['logloss']):>8s} {fmt(r['brier']):>7s} "
              f"{fmt(r['pareggio_previsto'], 3):>7s} {d:>16s} {ci:>22s}")
    print(f"pareggio osservato: {fmt((o == 1).mean(), 3)} · 1 osservato {fmt((o == 0).mean(), 3)} · 2 osservato {fmt((o == 2).mean(), 3)}")

    # per lega, pubblicato
    per_lega = []
    for lg, g in bt.groupby("league_key"):
        og = g["outcome"].to_numpy(int)
        Pg = vec(g, "p_")
        nv = np.tile(np.bincount(og, minlength=3) / len(og), (len(og), 1))
        per_lega.append({"lega": lg, "n": len(g), "rps": float(rps_rows(Pg, og).mean()),
                         "rps_naive": float(rps_rows(nv, og).mean()),
                         "rps_dc": float(rps_rows(vec(g, "dc_p_"), og).mean()),
                         "rps_elo": float(rps_rows(vec(g, "elo_p_"), og).mean())})
    print("\nper lega (RPS): pubblicato · DC puro · Elo puro · naive")
    for r in per_lega:
        print(f"  {r['lega']}: n={r['n']:4d}  {fmt(r['rps'])} · {fmt(r['rps_dc'])} · {fmt(r['rps_elo'])} · naive {fmt(r['rps_naive'])}")

    # ---- reliability per esito, decili
    print("\n== 2. Affidabilità dell'1X2 pubblicato (decili di probabilità dichiarata) ==")
    rel = {}
    for k, nome in enumerate(("1 casa", "X pareggio", "2 trasferta")):
        p = P_pub[:, k]
        y = (o == k).astype(float)
        edges = np.quantile(p, np.linspace(0, 1, 11))
        idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, 9)
        righe = []
        print(f"  {nome}:  dichiarata → osservata [Wilson 95%]  (n)")
        for b in range(10):
            m = idx == b
            if m.sum() < 30:
                continue
            lo, hi = wilson_interval(int(y[m].sum()), int(m.sum()))
            flag = "" if lo <= p[m].mean() <= hi else "  ← fuori"
            righe.append({"bin": b, "n": int(m.sum()), "prev": float(p[m].mean()), "oss": float(y[m].mean()), "lo": lo, "hi": hi})
            print(f"    {fmt(p[m].mean(), 3)} → {fmt(y[m].mean(), 3)} [{fmt(lo, 3)}; {fmt(hi, 3)}]  ({int(m.sum())}){flag}")
        rel[nome] = righe

    # ---- scomposizione di Brier (multiclasse, su 10 bin per esito) e temperatura
    unc = float(sum(pk * (1 - pk) for pk in np.bincount(o, minlength=3) / len(o)))
    reliab = 0.0
    resol = 0.0
    for k in range(3):
        p = P_pub[:, k]
        y = (o == k).astype(float)
        edges = np.quantile(p, np.linspace(0, 1, 11))
        idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, 9)
        ybar = y.mean()
        for b in range(10):
            m = idx == b
            if not m.any():
                continue
            reliab += m.sum() * (p[m].mean() - y[m].mean()) ** 2 / len(o)
            resol += m.sum() * (y[m].mean() - ybar) ** 2 / len(o)
    print(f"\n  Brier multiclasse = {fmt(brier_rows(P_pub, o).mean())} ≈ affidabilità {fmt(reliab)} − risoluzione {fmt(resol)} + incertezza {fmt(unc)}")
    print("  (affidabilità → 0 = ben calibrato; la risoluzione è ciò che distingue le partite: lì si guadagna)")

    # temperatura: p_T ∝ p^(1/T); T<1 = più appuntito, T>1 = più piatto. Stima walk-forward:
    # metà cronologica per stimare, l'altra metà per misurare.
    bt_sorted = bt.sort_values("date")
    Ps = vec(bt_sorted, "p_")
    os_ = bt_sorted["outcome"].to_numpy(int)
    half = len(bt_sorted) // 2
    Ts = np.round(np.arange(0.80, 1.31, 0.02), 2)

    def temp(P, T):
        q = np.power(np.clip(P, 1e-9, 1), 1.0 / T)
        return q / q.sum(1, keepdims=True)

    best = min(Ts, key=lambda T: logloss_rows(temp(Ps[:half], T), os_[:half]).mean())
    ll_before = logloss_rows(Ps[half:], os_[half:]).mean()
    ll_after = logloss_rows(temp(Ps[half:], best), os_[half:]).mean()
    rps_before = rps_rows(Ps[half:], os_[half:]).mean()
    rps_after = rps_rows(temp(Ps[half:], best), os_[half:]).mean()
    print(f"  temperatura stimata sulla prima metà cronologica: T = {fmt(best, 2)} "
          f"(1,00 = nessuna correzione; <1 = il modello è troppo prudente)")
    print(f"  seconda metà: log-loss {fmt(ll_before)} → {fmt(ll_after)} · RPS {fmt(rps_before)} → {fmt(rps_after)}")
    return {"ricette": rows, "per_lega": per_lega, "reliability": rel,
            "brier_decomp": {"affidabilita": reliab, "risoluzione": resol, "incertezza": unc},
            "temperatura": {"T": float(best), "logloss_prima": float(ll_before), "logloss_dopo": float(ll_after),
                            "rps_prima": float(rps_before), "rps_dopo": float(rps_after)}}


# ----------------------------------------------------------------------------- 3
def sezione_mercato(bt: pd.DataFrame, hist: pd.DataFrame) -> dict:
    print("\n== 3. Distanza dal mercato (quote di chiusura presenti nello storico: NED1/POR1) ==")
    h = hist.dropna(subset=["odds_home", "odds_draw", "odds_away"]).copy()
    if h.empty:
        print("  nessuna quota nello storico")
        return {}
    h["d"] = pd.to_datetime(h["date"], utc=True).dt.tz_convert(None).dt.normalize()
    b = bt.copy()
    b["d"] = pd.to_datetime(b["date"]).dt.tz_localize(None).dt.normalize() if getattr(pd.to_datetime(b["date"]).dt, "tz", None) is not None else pd.to_datetime(b["date"]).dt.normalize()
    m = b.merge(h[["league_key", "d", "home", "away", "odds_home", "odds_draw", "odds_away"]],
                on=["league_key", "d", "home", "away"], how="inner")
    if m.empty:
        print("  nessun aggancio backtest ↔ quote")
        return {}
    inv = 1.0 / m[["odds_home", "odds_draw", "odds_away"]].to_numpy(float)
    P_mkt = inv / inv.sum(1, keepdims=True)
    o = m["outcome"].to_numpy(int)
    P_mod = vec(m, "p_")
    r_mod, r_mkt = rps_rows(P_mod, o), rps_rows(P_mkt, o)
    lo, hi = paired_bootstrap(r_mod - r_mkt, draws=3000)
    out = {"n": len(m), "rps_modello": float(r_mod.mean()), "rps_mercato": float(r_mkt.mean()),
           "delta": float((r_mod - r_mkt).mean()), "ci_lo": lo, "ci_hi": hi,
           "logloss_modello": float(logloss_rows(P_mod, o).mean()), "logloss_mercato": float(logloss_rows(P_mkt, o).mean())}
    print(f"  n = {out['n']} gare agganciate · RPS modello {fmt(out['rps_modello'])} · mercato {fmt(out['rps_mercato'])} · "
          f"Δ = {fmt(out['delta'], 5)} IC95 [{fmt(lo, 5)}; {fmt(hi, 5)}] · log-loss {fmt(out['logloss_modello'])} vs {fmt(out['logloss_mercato'])}")
    # miscela modello/mercato: quanto del divario chiude una media?
    for w in (0.25, 0.5, 0.75):
        Pm = w * P_mkt + (1 - w) * P_mod
        print(f"  miscela {int(w*100)}% mercato: RPS {fmt(rps_rows(Pm, o).mean())}")
    for lg, g in m.groupby("league_key"):
        og = g["outcome"].to_numpy(int)
        invg = 1.0 / g[["odds_home", "odds_draw", "odds_away"]].to_numpy(float)
        print(f"  {lg}: n={len(g)} modello {fmt(rps_rows(vec(g, 'p_'), og).mean())} · mercato {fmt(rps_rows(invg / invg.sum(1, keepdims=True), og).mean())}")
    return out


# ----------------------------------------------------------------------------- 4
def sezione_riposo(bt: pd.DataFrame, hist: pd.DataFrame) -> dict:
    print("\n== 4. Riposo (giorni dall'ultima gara di campionato) ==")
    h = hist.dropna(subset=["home_goals", "away_goals"]).copy()
    h["dt"] = pd.to_datetime(h["date"], utc=True).dt.tz_convert(None)
    long = pd.concat([h[["league_key", "dt", "home"]].rename(columns={"home": "team"}),
                      h[["league_key", "dt", "away"]].rename(columns={"away": "team"})]).sort_values("dt")
    long["prev"] = long.groupby(["league_key", "team"])["dt"].shift(1)
    long["rest"] = ((long["dt"] - long["prev"]).dt.total_seconds() // 86400)
    rest = long.dropna(subset=["rest"]).set_index(["league_key", "dt", "team"])["rest"]
    b = bt.copy()
    b["dt"] = pd.to_datetime(b["date"]).dt.tz_localize(None) if getattr(pd.to_datetime(b["date"]).dt, "tz", None) is not None else pd.to_datetime(b["date"])
    b["rest_h"] = [rest.get((lg, dt, t), np.nan) for lg, dt, t in zip(b.league_key, b.dt, b.home)]
    b["rest_a"] = [rest.get((lg, dt, t), np.nan) for lg, dt, t in zip(b.league_key, b.dt, b.away)]
    lh = pd.to_numeric(b["lambda_home"]).to_numpy(float)
    la = pd.to_numeric(b["lambda_away"]).to_numpy(float)
    hg = b["home_goals"].to_numpy(float)
    ag = b["away_goals"].to_numpy(float)
    # rapporto gol/λ per fascia (casa e trasferta insieme, per squadra)
    fasce = [("≤2", 0, 2), ("3", 3, 3), ("4-5", 4, 5), ("6-7", 6, 7), ("8-13", 8, 13), ("≥14", 14, 999)]
    out = []
    print("  fascia   n squadre-gara   gol/λ (IC ~95% Poisson)   fattore in produzione")
    fattori = {"≤2": 0.95, "3": 0.98, "4-5": 0.98, "6-7": 1.00, "8-13": 1.02, "≥14": 1.02}
    for nome, lo_, hi_ in fasce:
        mh = (b.rest_h >= lo_) & (b.rest_h <= hi_)
        ma = (b.rest_a >= lo_) & (b.rest_a <= hi_)
        g = np.concatenate([hg[mh.to_numpy()], ag[ma.to_numpy()]])
        l = np.concatenate([lh[mh.to_numpy()], la[ma.to_numpy()]])
        if len(g) < 30:
            continue
        ratio = g.sum() / l.sum()
        se = math.sqrt(g.sum()) / l.sum()
        out.append({"fascia": nome, "n": len(g), "ratio": float(ratio), "lo": ratio - 1.96 * se, "hi": ratio + 1.96 * se})
        print(f"  {nome:6s}  {len(g):6d}          {fmt(ratio, 3)} [{fmt(ratio - 1.96*se, 3)}; {fmt(ratio + 1.96*se, 3)}]        {fattori[nome]:.2f}")
    # ΔRPS del rest_tilt di produzione applicato alle λ del backtest
    ok = b.rest_h.notna() & b.rest_a.notna()
    idx = np.where(ok.to_numpy())[0]
    lh2 = lh.copy(); la2 = la.copy()
    for i in idx:
        lh2[i], la2[i], *_ = rest_tilt(lh[i], la[i], int(b.rest_h.iloc[i]), int(b.rest_a.iloc[i]))
    rho = np.nan_to_num(pd.to_numeric(b["dc_rho"]).to_numpy(float))
    o = b["outcome"].to_numpy(int)
    m0 = grid_markets_many(tau_grid_many(lh, la, rho, size=GRID_SIZE))
    m1 = grid_markets_many(tau_grid_many(lh2, la2, rho, size=GRID_SIZE))
    P0 = np.column_stack([m0["p_home"], m0["p_draw"], m0["p_away"]])
    P1 = np.column_stack([m1["p_home"], m1["p_draw"], m1["p_away"]])
    d = rps_rows(P1, o)[idx] - rps_rows(P0, o)[idx]
    lo, hi = paired_bootstrap(d, draws=3000)
    toccate = int((np.abs(lh2 - lh) > 1e-9).sum())
    print(f"  fattore di riposo di produzione applicato al backtest: gare con riposo noto {len(idx)}, λ modificate {toccate}, "
          f"ΔRPS {fmt(d.mean(), 6)} IC95 [{fmt(lo, 6)}; {fmt(hi, 6)}]")
    return {"fasce": out, "delta_rps": float(d.mean()), "ci_lo": lo, "ci_hi": hi, "n": len(idx), "toccate": toccate}


# ----------------------------------------------------------------------------- 5 + 6
def _aggancia_finite(bt: pd.DataFrame, fixtures: pd.DataFrame) -> pd.DataFrame:
    fx = fixtures[fixtures.status == "finished"].copy()
    fx["home"] = fx.home_name.map(canonical)
    fx["away"] = fx.away_name.map(canonical)
    fx["d"] = pd.to_datetime(fx.utc_kickoff, utc=True).dt.tz_convert(None).dt.normalize()
    b = bt.copy()
    bd = pd.to_datetime(b["date"])
    b["d"] = (bd.dt.tz_localize(None) if getattr(bd.dt, "tz", None) is not None else bd).dt.normalize()
    return b.merge(fx[["match_id", "home_id", "away_id", "d", "home", "away"]], on=["d", "home", "away"], how="inner")


def sezione_valore(bt: pd.DataFrame, fixtures: pd.DataFrame, mi: pd.DataFrame) -> dict:
    print("\n== 5. Valore di mercato dei titolari (unico campione con il dato: gare finite di questa stagione) ==")
    m = _aggancia_finite(bt, fixtures).merge(
        mi[["match_id", "home_starters_value_eur", "away_starters_value_eur"]], on="match_id", how="inner")
    m = m.dropna(subset=["home_starters_value_eur", "away_starters_value_eur"])
    m = m[(m.home_starters_value_eur > 0) & (m.away_starters_value_eur > 0)]
    if len(m) < 50:
        print(f"  campione insufficiente: {len(m)} gare")
        return {"n": len(m)}
    o = m["outcome"].to_numpy(int)
    lh = pd.to_numeric(m["lambda_home"]).to_numpy(float)
    la = pd.to_numeric(m["lambda_away"]).to_numpy(float)
    rho = np.nan_to_num(pd.to_numeric(m["dc_rho"]).to_numpy(float))
    ratio = (m.home_starters_value_eur / m.away_starters_value_eur).to_numpy(float)
    print(f"  n = {len(m)} gare · rapporto valore casa/trasferta: mediana {fmt(np.median(ratio), 2)}, p10 {fmt(np.quantile(ratio, .1), 2)}, p90 {fmt(np.quantile(ratio, .9), 2)}")
    # correlazione fra log-rapporto di valore e il residuo del modello (esito − p_casa + p_trasferta)
    P0 = vec(m, "p_")
    resid = ((o == 0).astype(float) - P0[:, 0]) - ((o == 2).astype(float) - P0[:, 2])
    lr = np.log(ratio)
    corr = float(np.corrcoef(lr, resid)[0, 1])
    corr_dc = float(np.corrcoef(lr, P0[:, 0] - P0[:, 2])[0, 1])
    print(f"  correlazione log(rapporto valore) con (p_casa − p_trasferta) del modello: {fmt(corr_dc, 3)} → il modello lo sa già")
    print(f"  correlazione log(rapporto valore) con il residuo del modello: {fmt(corr, 3)} (≈0 = nessuna informazione residua)")
    righe = []
    base_ll = logloss_rows(P0, o).mean()
    base_rps = rps_rows(P0, o).mean()
    print("  k      log-loss   RPS       Δlog-loss  IC95 (bootstrap appaiato)")
    for k in (0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.25):
        lh2 = lh.copy(); la2 = la.copy()
        for i in range(len(m)):
            lh2[i], la2[i], *_ = market_value_tilt(lh[i], la[i], m.home_starters_value_eur.iloc[i], m.away_starters_value_eur.iloc[i], k=k)
        mk = grid_markets_many(tau_grid_many(lh2, la2, rho, size=GRID_SIZE))
        P = np.column_stack([mk["p_home"], mk["p_draw"], mk["p_away"]])
        ll = logloss_rows(P, o); d = ll - logloss_rows(P0, o)
        lo, hi = paired_bootstrap(d, draws=3000)
        righe.append({"k": k, "logloss": float(ll.mean()), "rps": float(rps_rows(P, o).mean()), "delta_ll": float(d.mean()), "lo": lo, "hi": hi})
        print(f"  {k:.2f}   {fmt(ll.mean())}     {fmt(rps_rows(P, o).mean())}    {fmt(d.mean(), 5):>9s}  [{fmt(lo, 5)}; {fmt(hi, 5)}]")
    print(f"  (riferimento k=0: log-loss {fmt(base_ll)}, RPS {fmt(base_rps)}; k in produzione = 0,12 con clip del rapporto a [0,2; 5])")
    return {"n": len(m), "corr_residuo": corr, "corr_modello": corr_dc, "griglia": righe}


def sezione_assenze(bt: pd.DataFrame, fixtures: pd.DataFrame, store: Store) -> dict:
    print("\n== 6. Assenze (contributo xG+xA/90 perso, come lo calcola la scheda) ==")
    from fda.site.analysis import MatchAnalysis
    ma = MatchAnalysis(store)
    m = _aggancia_finite(bt, fixtures)
    ch, ca = [], []
    for r in m.itertuples(index=False):
        try:
            ah = ma.absences_weight(int(r.match_id), int(r.home_id))
            aa = ma.absences_weight(int(r.match_id), int(r.away_id))
        except (KeyError, ValueError, TypeError, IndexError):   # scheda senza dati: si salta
            ah, aa = None, None
        ch.append(float(ah["contrib_lost_p90"]) if ah and ah.get("contrib_lost_p90") else None)
        ca.append(float(aa["contrib_lost_p90"]) if aa and aa.get("contrib_lost_p90") else None)
    m["ch"] = ch; m["ca"] = ca
    has = m.ch.notna() | m.ca.notna()
    print(f"  gare finite agganciate {len(m)} · con almeno un'infermeria pesata {int(has.sum())}")
    if has.sum() < 40:
        print("  campione insufficiente")
        return {"n": int(has.sum())}
    vals = pd.concat([m.ch, m.ca]).dropna()
    print(f"  contributo perso per squadra: mediana {fmt(vals.median(), 2)}, p90 {fmt(vals.quantile(.9), 2)}, max {fmt(vals.max(), 2)} xG+xA/90 "
          f"→ fattore λ in produzione (1 − 0,3·c/2): mediana {fmt(1 - 0.3*vals.median()/2, 3)}, p90 {fmt(1 - 0.3*vals.quantile(.9)/2, 3)}, min {fmt(max(0.7, 1 - 0.3*vals.max()/2), 3)}")
    o = m["outcome"].to_numpy(int)
    lh = pd.to_numeric(m["lambda_home"]).to_numpy(float)
    la = pd.to_numeric(m["lambda_away"]).to_numpy(float)
    rho = np.nan_to_num(pd.to_numeric(m["dc_rho"]).to_numpy(float))
    # gol segnati / λ per squadre con infermeria pesante vs leggera (senza toccare il modello)
    hg = m["home_goals"].to_numpy(float); ag = m["away_goals"].to_numpy(float)
    c_all = np.concatenate([np.nan_to_num(m.ch.to_numpy(float)), np.nan_to_num(m.ca.to_numpy(float))])
    g_all = np.concatenate([hg, ag]); l_all = np.concatenate([lh, la])
    for nome, lo_, hi_ in (("nessuna (0)", -1, 0.0), ("0-0,5", 0.0, 0.5), ("0,5-1", 0.5, 1.0), (">1", 1.0, 99)):
        sel = (c_all > lo_) & (c_all <= hi_)
        if sel.sum() >= 20:
            ratio = g_all[sel].sum() / l_all[sel].sum(); se = math.sqrt(g_all[sel].sum()) / l_all[sel].sum()
            print(f"  contributo perso {nome:12s}: n={int(sel.sum()):4d} squadre-gara · gol/λ {fmt(ratio, 3)} [{fmt(ratio-1.96*se, 3)}; {fmt(ratio+1.96*se, 3)}]")
    mk0 = grid_markets_many(tau_grid_many(lh, la, rho, size=GRID_SIZE))
    P0 = np.column_stack([mk0["p_home"], mk0["p_draw"], mk0["p_away"]])
    righe = []
    print("  k (produzione 0,30)   log-loss    RPS      Δlog-loss   IC95")
    for k in (0.0, 0.1, 0.2, 0.3, 0.5):
        lh2 = lh.copy(); la2 = la.copy()
        for i in range(len(m)):
            lh2[i], la2[i], *_ = absences_tilt(lh[i], la[i], m.ch.iloc[i], m.ca.iloc[i], k=k)
        mk = grid_markets_many(tau_grid_many(lh2, la2, rho, size=GRID_SIZE))
        P = np.column_stack([mk["p_home"], mk["p_draw"], mk["p_away"]])
        d = logloss_rows(P, o) - logloss_rows(P0, o)
        lo, hi = paired_bootstrap(d[has.to_numpy()], draws=3000)
        righe.append({"k": k, "logloss": float(logloss_rows(P, o).mean()), "rps": float(rps_rows(P, o).mean()), "delta_ll": float(d[has.to_numpy()].mean()), "lo": lo, "hi": hi})
        print(f"  {k:.2f}                  {fmt(logloss_rows(P, o).mean())}      {fmt(rps_rows(P, o).mean())}   {fmt(d[has.to_numpy()].mean(), 5):>9s}   [{fmt(lo, 5)}; {fmt(hi, 5)}]")
    return {"n": int(has.sum()), "griglia": righe}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--salta-assenze", action="store_true")
    args = ap.parse_args()
    store = Store(DATA)
    bt_raw = store.read("backtest")
    cal = from_store(store)
    bt = calibrate_rows(bt_raw, cal)
    hist = store.read("history")
    fixtures = store.read("fixtures")
    mi = store.read("match_info")
    print(f"backtest: {len(bt)} gare fuori campione {pd.to_datetime(bt.date).min():%Y-%m-%d} → {pd.to_datetime(bt.date).max():%Y-%m-%d} · "
          f"calibrazione {cal.version} λ×{cal.lambda_scale:.4f} ρ{cal.rho_shift:+.2f} (stimata {cal.fitted_at:%Y-%m-%d} su {cal.n_fit} gare)")
    out = {"n_backtest": len(bt), "calibrazione": {"version": cal.version, "lambda_scale": cal.lambda_scale,
                                                        "rho_shift": cal.rho_shift, "fitted_at": str(cal.fitted_at), "n_fit": cal.n_fit}}
    out["ricetta"] = sezione_ricetta(bt, cal)
    out["mercato"] = sezione_mercato(bt, hist)
    out["riposo"] = sezione_riposo(bt, hist)
    out["valore"] = sezione_valore(bt, fixtures, mi)
    if not args.salta_assenze:
        out["assenze"] = sezione_assenze(bt, fixtures, store)
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
        print(f"\nJSON salvato in {args.json}")


if __name__ == "__main__":
    main()
