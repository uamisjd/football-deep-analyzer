"""Audit dei «Fattori che spostano la partita»: quanto pesa davvero ogni fattore.

Nasce con la revisione della card del 2026-10-08 (`docs/58`). Regola del progetto
(`docs/00` B.8, «prima si dimostra, poi si integra»): nessun fattore entra nella scheda senza
una misura sui nostri archivi. Qui si misura **ogni** candidato — quelli già in card e quelli
proposti — con lo stesso schema: campione, effetto sull'esito, e (dove i dati lo permettono)
se l'effetto resta dopo aver tolto quello che le quote dicono già.

Fonti, tutte già raccolte (nessuna richiesta di rete):

* ``history.parquet`` — 7.467 gare di campionato su 3 stagioni (2023/24 → 2026/27) con esito e
  quote: riposo, split di sede, distanza «per procura» non c'è (mancano gli stadi) ma c'è
  l'ancora delle quote;
* ``match_info.parquet`` — 442 gare con dettagli (375 finite): stadio (lat/lon, città,
  capienza), valore dei titolari, età media, arbitro e sue medie, meteo;
* ``team_stats.parquet`` — cartellini, falli e xG delle 375 finite;
* ``shots.parquet`` — i rigori tirati (``situation == "Penalty"``) per contare i rigori concessi;
* ``understat_team_matches.parquet`` — PPDA per squadra;
* ``fixtures.parquet`` + ``cup_fixtures.parquet`` — calendario con le coppe (impegno ravvicinato).

Uso::

    .venv/bin/python scripts/audit_fattori.py            # riepilogo a schermo
    .venv/bin/python scripts/audit_fattori.py --json out.json

Stampa solo riepiloghi (mai dati grezzi: `docs/00` A.3) e chiude con il verdetto per fattore.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DATA = Path("data/processed")

# Soglie già in produzione (importate, non riscritte: la misura deve parlare del codice vero)
from fda.site.analysis import MatchAnalysis

FACTOR_REST = MatchAnalysis.FACTOR_REST_SHORT
FACTOR_MARKET = MatchAnalysis.FACTOR_MARKET_RATIO
FACTOR_PRESS = MatchAnalysis.FACTOR_PRESS_RATIO


def _load(name: str) -> pd.DataFrame:
    p = DATA / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def _quota_impl(g: pd.DataFrame, col: str = "odds_home") -> float | None:
    """Probabilità implicita **normalizzata**: 1/quota diviso la somma dei tre 1/quota.

    Senza normalizzare, la somma dei tre esiti supera 1 dell'overround del bookmaker (5-8%) e
    ogni confronto «esito reale contro quota implicita» è sbilanciato verso il basso: è l'errore
    che la prima stesura di questo audit faceva sul Δ di riposo (`docs/58` §2).
    """
    o = g[["odds_home", "odds_draw", "odds_away"]].apply(pd.to_numeric, errors="coerce").dropna()
    if o.empty:
        return None
    inv = 1 / o
    return float((inv[col] / inv.sum(axis=1)).mean())


def _pts(gf: float, ga: float, casa: bool) -> int:
    d = (gf - ga) if casa else (ga - gf)
    return 3 if d > 0 else 1 if d == 0 else 0


def _wilson(k: int, n: int) -> tuple[float, float]:
    """Intervallo di Wilson al 95%: con campioni piccoli la percentuale da sola mente."""
    if n == 0:
        return (0.0, 0.0)
    z, p = 1.96, k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


# --------------------------------------------------------------------------- 1. riposo
def riposo(hist: pd.DataFrame) -> dict[str, Any]:
    """Riposo in giorni e punti fatti, su 3 stagioni di campionato (coppe escluse).

    Il calendario di ``history`` è solo campionato: il riposo «vero» (coppe incluse) è quello di
    ``rest_days()``, ma su 3 stagioni il campionato è la componente dominante e il confronto
    relativo resta leggibile. Misurato anche il Δ di riposo fra le due squadre, che è ciò che
    la card può dire: due riposi uguali non spostano niente.
    """
    if hist.empty:
        return {"n": 0}
    h = hist.copy()
    h["date"] = pd.to_datetime(h["date"], utc=True)
    h["esito"] = np.where(h.home_goals > h.away_goals, "1",
                          np.where(h.home_goals == h.away_goals, "X", "2"))
    h["punti_casa"] = np.where(h.esito == "1", 3, np.where(h.esito == "X", 1, 0))
    h["gol"] = h.home_goals + h.away_goals
    # riposo di ciascuna squadra: giorni dalla sua gara di campionato precedente
    rest_h = h.sort_values(["home", "date"]).groupby("home")["date"].diff().dt.days
    rest_a = h.sort_values(["away", "date"]).groupby("away")["date"].diff().dt.days
    h["rh"] = rest_h.sort_index()
    h["ra"] = rest_a.sort_index()
    h["punti_ospite"] = np.where(h.esito == "2", 3, np.where(h.esito == "X", 1, 0))
    long = pd.concat([
        h.dropna(subset=["rh"])[["rh", "punti_casa", "home_goals", "away_goals"]]
        .rename(columns={"rh": "rest", "punti_casa": "punti", "home_goals": "gf",
                         "away_goals": "ga"})[["rest", "punti", "gf", "ga"]],
        h.dropna(subset=["ra"])[["ra", "punti_ospite", "home_goals", "away_goals"]]
        .rename(columns={"ra": "rest", "punti_ospite": "punti", "away_goals": "gf",
                         "home_goals": "ga"})[["rest", "punti", "gf", "ga"]],
    ], ignore_index=True)
    long["bucket"] = pd.cut(long.rest, [0, 2, 3, 4, 5, 6, 7, 9, 14, 400],
                            labels=["≤2", "3", "4", "5", "6", "7", "8-9", "10-14", "≥15"],
                            right=True)
    out: dict[str, Any] = {"n_osservazioni": len(long), "per_bucket": []}
    for b, g in long.groupby("bucket", observed=True):
        out["per_bucket"].append({"riposo": str(b), "n": len(g),
                                  "punti_gara": round(float(g.punti.mean()), 3),
                                  "gol_fatti": round(float(g.gf.mean()), 3),
                                  "gol_subiti": round(float(g.ga.mean()), 3)})
    # Δ di riposo: la squadra con più riposo fa più punti? (ancora: la quota implicita)
    a = h.dropna(subset=["rh", "ra"]).copy()
    a["delta"] = a.rh - a.ra
    a["db"] = pd.cut(a.delta, [-99, -3, -1, 1, 3, 99],
                     labels=["casa ≥4 gg in meno", "casa 2-3 in meno", "pari",
                             "casa 2-3 in più", "casa ≥4 gg in più"])
    righe_d = []
    for b, g in a.groupby("db", observed=True):
        qi = _quota_impl(g)
        righe_d.append({"delta_riposo": str(b), "n": len(g),
                        "vittorie_casa": round(float((g.esito == "1").mean()), 3),
                        "quota_impl_casa": round(qi, 3) if qi else None})
    out["delta_riposo"] = righe_d
    out["n_delta"] = len(a)
    return out


# ------------------------------------------------------------------- 2. valore di mercato
def mercato(mi: pd.DataFrame) -> dict[str, Any]:
    """Rapporto del valore dei titolari ed esito, sulle 375 gare finite con i valori."""
    d = mi[(mi.status == "finished") & mi.home_starters_value_eur.notna()
           & mi.away_starters_value_eur.notna()].copy()
    if d.empty:
        return {"n": 0}
    d["ratio"] = d.home_starters_value_eur / d.away_starters_value_eur
    d["fav"] = np.where(d.ratio >= 1, "h", "a")
    d["r_fav"] = np.where(d.fav == "h", d.ratio, 1 / d.ratio)
    d["esito"] = np.where(d.home_goals > d.away_goals, "h",
                          np.where(d.home_goals == d.away_goals, "d", "a"))
    d["punti_fav"] = np.where(d.esito == d.fav, 3.0, np.where(d.esito == "d", 1.0, 0.0))
    d["b"] = pd.cut(d.r_fav, [0, 1 / FACTOR_MARKET, 2, 3, 5, 1e6],
                    labels=[f"<{FACTOR_MARKET}×", f"{FACTOR_MARKET}-2×", "2-3×", "3-5×", "≥5×"])
    out = {"n": len(d), "per_bucket": []}
    for b, g in d.groupby("b", observed=True):
        k = int((g.punti_fav == 3).sum())
        lo, hi = _wilson(k, len(g))
        out["per_bucket"].append({"rapporto": str(b), "n": len(g),
                                  "vittorie_favorita": round(k / len(g), 3),
                                  "ic95": [round(lo, 3), round(hi, 3)],
                                  "punti_gara_favorita": round(float(g.punti_fav.mean()), 3)})
    sopra = d[d.r_fav >= FACTOR_MARKET]
    out["sopra_soglia"] = {"n": len(sopra),
                           "punti_gara_favorita": round(float(sopra.punti_fav.mean()), 3),
                           "vittorie_favorita": round(float((sopra.punti_fav == 3).mean()), 3)}
    sotto = d[d.r_fav < FACTOR_MARKET]
    out["sotto_soglia"] = {"n": len(sotto),
                           "punti_gara_favorita": round(float(sotto.punti_fav.mean()), 3),
                           "vittorie_favorita": round(float((sotto.punti_fav == 3).mean()), 3)}
    return out


# ---------------------------------------------------------------------- 3. distanza
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distanza(mi: pd.DataFrame) -> dict[str, Any]:
    """Trasferta in km (stadio di casa dell'ospite → stadio della gara) ed esito.

    Le coordinate arrivano dagli stadi visti in ``match_info``: per ogni squadra si prende lo
    stadio più frequente delle sue gare interne (una squadra può cambiarlo, e la fonte a volte
    lo scrive in modo diverso). Unico limite dichiarato: la distanza è **in linea d'aria**,
    non i km stradali o le ore di viaggio.
    """
    if mi.empty or "stadium_lat" not in mi.columns:
        return {"n": 0}
    casa = mi[mi.stadium_lat.notna() & mi.stadium_city.notna()]
    stadi: dict[int, tuple[float, float, str]] = {}
    for tid, g in casa.groupby("home_id"):
        s = g.groupby(["stadium_lat", "stadium_lon", "stadium_city"]).size().idxmax()
        stadi[int(tid)] = (float(s[0]), float(s[1]), str(s[2]))
    fin = mi[(mi.status == "finished") & mi.stadium_lat.notna()].copy()
    fin["lat_h"], fin["lon_h"], fin["citta_h"] = zip(*[
        stadi.get(int(t), (float("nan"), float("nan"), "")) for t in fin.home_id])
    fin["lat_a"], fin["lon_a"], fin["citta_a"] = zip(*[
        stadi.get(int(t), (float("nan"), float("nan"), "")) for t in fin.away_id])
    fin = fin.dropna(subset=["lat_a", "lon_a"])
    fin["km"] = [_haversine(a, b, c, d) for a, b, c, d in
                 zip(fin.lat_a, fin.lon_a, fin.lat_h, fin.lon_h)]
    fin["esito"] = np.where(fin.home_goals > fin.away_goals, "h",
                            np.where(fin.home_goals == fin.away_goals, "d", "a"))
    fin["b"] = pd.cut(fin.km, [-1, 50, 150, 300, 600, 1e6],
                      labels=["≤50 (derby/regione)", "50-150", "150-300", "300-600", ">600"])
    out: dict[str, Any] = {"n": len(fin), "km_medio": round(float(fin.km.mean()), 1),
                           "per_bucket": []}
    for b, g in fin.groupby("b", observed=True):
        out["per_bucket"].append({
            "distanza_km": str(b), "n": len(g),
            "punti_ospite_gara": round(float(np.where(g.esito == "a", 3,
                                                      np.where(g.esito == "d", 1, 0)).mean()), 3),
            "gol_ospite": round(float(g.away_goals.mean()), 3),
            "xg_ospite": (round(float(g.away_xg.mean()), 3) if g.away_xg.notna().any() else None),
            "vittorie_casa": round(float((g.esito == "h").mean()), 3)})
    # stesso Comune: derby cittadino
    der = fin[fin.citta_h.str.lower() == fin.citta_a.str.lower()]
    out["stessa_citta"] = {
        "n": len(der),
        "punti_ospite_gara": (round(float(np.where(der.esito == "a", 3,
                                                   np.where(der.esito == "d", 1, 0)).mean()), 3)
                              if len(der) else None),
        "gol_totali": round(float((der.home_goals + der.away_goals).mean()), 3) if len(der) else None}
    altre = fin[fin.citta_h.str.lower() != fin.citta_a.str.lower()]
    out["citta_diversa"] = {
        "n": len(altre),
        "punti_ospite_gara": round(float(np.where(altre.esito == "a", 3,
                                                  np.where(altre.esito == "d", 1, 0)).mean()), 3),
        "gol_totali": round(float((altre.home_goals + altre.away_goals).mean()), 3)}
    return out


# ---------------------------------------------------------------- 4. split di sede
def sede(hist: pd.DataFrame) -> dict[str, Any]:
    """Rendimento in casa dell'una contro quello in trasferta dell'altra (stagioni precedenti).

    Per ogni gara si calcola il PPG **casalingo** della squadra di casa e il PPG **esterno**
    dell'ospite sulle gare dei 365 giorni precedenti (solo campionato, dallo stesso archivio):
    è il confronto che la scheda non pubblica da nessuna parte. L'ancora è la quota, così
    l'effetto si legge al netto di quello che il mercato sa già.
    """
    if hist.empty:
        return {"n": 0}
    h = hist.copy()
    h["date"] = pd.to_datetime(h["date"], utc=True)
    h["esito"] = np.where(h.home_goals > h.away_goals, "h",
                          np.where(h.home_goals == h.away_goals, "d", "a"))
    righe = []
    for team_col, casa in (("home", True), ("away", False)):
        g = h[["league_key", "date", team_col, "esito"]].rename(columns={team_col: "team"})
        g["punti"] = [3 if (e == ("h" if casa else "a")) else 1 if e == "d" else 0 for e in g.esito]
        g["sede"] = "casa" if casa else "trasferta"
        righe.append(g)
    long = pd.concat(righe, ignore_index=True).sort_values(["team", "date"])
    # PPG per sede sui 365 giorni precedenti, con conteggio gare (niente numeri su 2 partite)
    cache = {k: v[["date", "punti"]] for k, v in long.groupby(["team", "sede"])}
    out_rows = []
    for r in h.itertuples(index=False):
        righe_cal = []
        for team, sede_ in ((r.home, "casa"), (r.away, "trasferta")):
            df = cache.get((team, sede_))
            if df is None:
                righe_cal.append((None, 0))
                continue
            lo = r.date - pd.Timedelta(days=365)
            w = df[(df.date >= lo) & (df.date < r.date)]
            righe_cal.append((float(w.punti.mean()) if len(w) else None, len(w)))
        out_rows.append((*righe_cal[0], *righe_cal[1], r.esito,
                         r.odds_home, r.odds_draw, r.odds_away))
    m = pd.DataFrame(out_rows, columns=["ppg_casa_h", "n_h", "ppg_trasf_a", "n_a", "esito",
                                        "odds_home", "odds_draw", "odds_away"])
    m = m[(m.n_h >= 5) & (m.n_a >= 5)].dropna(subset=["ppg_casa_h", "ppg_trasf_a"])
    if m.empty:
        return {"n": 0, "nota": "nessuna gara con ≥5 gare per sede nella finestra"}
    m["delta"] = m.ppg_casa_h - m.ppg_trasf_a
    m["b"] = pd.cut(m.delta, [-9, -1, -0.34, 0.34, 1, 9],
                    labels=["ospite ≥1 pt migliore", "ospite 0,3-1 migliore", "pari (±0,33)",
                            "casa 0,3-1 migliore", "casa ≥1 pt migliore"])
    out: dict[str, Any] = {"n": len(m), "per_bucket": []}
    for b, g in m.groupby("b", observed=True):
        k = int((g.esito == "h").sum())
        lo, hi = _wilson(k, len(g))
        qi = _quota_impl(g)
        out["per_bucket"].append({
            "delta_ppg_sede": str(b), "n": len(g),
            "vittorie_casa": round(k / len(g), 3), "ic95": [round(lo, 3), round(hi, 3)],
            "quota_impl_casa": round(qi, 3) if qi else None})
    # vantaggio di sede medio, per dare la scala del numero
    long2 = long[long.date >= long.date.max() - pd.Timedelta(days=365)]
    out["ppg_casa_ultima_stagione"] = round(
        float(long2.loc[long2.sede == "casa", "punti"].mean()), 3)
    out["ppg_trasferta_ultima_stagione"] = round(
        float(long2.loc[long2.sede == "trasferta", "punti"].mean()), 3)
    return out


# ------------------------------------------------------------------- 5. età media
def eta(mi: pd.DataFrame) -> dict[str, Any]:
    """Età media dei titolari e differenza di età: la squadra più esperta fa più punti?"""
    d = mi[(mi.status == "finished") & mi.home_avg_starter_age.notna()
           & mi.away_avg_starter_age.notna()].copy()
    if d.empty:
        return {"n": 0}
    d["delta"] = d.home_avg_starter_age - d.away_avg_starter_age
    d["esito"] = np.where(d.home_goals > d.away_goals, "h",
                          np.where(d.home_goals == d.away_goals, "d", "a"))
    d["punti_casa"] = np.where(d.esito == "h", 3, np.where(d.esito == "d", 1, 0))
    d["b"] = pd.cut(d.delta, [-9, -2, -1, 1, 2, 9],
                    labels=["casa ≥2 anni più giovane", "casa 1-2 più giovane", "pari (±1)",
                            "casa 1-2 più esperta", "casa ≥2 anni più esperta"])
    out = {"n": len(d), "eta_media": round(float(d.home_avg_starter_age.mean()), 2),
           "per_bucket": []}
    for b, g in d.groupby("b", observed=True):
        out["per_bucket"].append({"delta_eta": str(b), "n": len(g),
                                  "punti_casa_gara": round(float(g.punti_casa.mean()), 3),
                                  "gol_totali": round(float((g.home_goals + g.away_goals).mean()), 3)})
    corr = float(np.corrcoef(d.delta, d.punti_casa)[0, 1])
    out["correlazione_delta_eta_punti_casa"] = round(corr, 4)
    return out


# ------------------------------------------------------------------- 6. arbitro
def arbitro(mi: pd.DataFrame, ts: pd.DataFrame, shots: pd.DataFrame) -> dict[str, Any]:
    """Quanto pesa l'arbitro su cartellini e rigori, e quanto lo annuncia la sua media.

    Tre misure: (1) la **dispersione** fra arbitri (quota di varianza dei cartellini di gara
    spiegata da chi arbitra, sugli arbitri con ≥5 gare in archivio); (2) se la media dichiarata
    dalla fonte **predice** i cartellini della gara; (3) i rigori concessi per gara contro la
    media di carriera. I rigori contano: un rigore è ~0,79 xG, quindi un arbitro che ne fischia
    il doppio cambia i gol attesi della partita.
    """
    if mi.empty or ts.empty:
        return {"n": 0}
    cards = ts[(ts.period == "All") & ts.key.isin(["yellow_cards", "red_cards", "fouls"])]
    cards = cards.assign(value=pd.to_numeric(cards.value, errors="coerce"))
    per_gara = cards.pivot_table(index="match_id", columns="key", values="value", aggfunc="sum")
    d = mi[(mi.status == "finished") & mi.referee_name.notna()].copy()
    d = d.join(per_gara, on="match_id")
    d["gialli"] = d.get("yellow_cards")
    d = d.dropna(subset=["gialli"])
    d["gialli_gara"] = d.gialli
    out: dict[str, Any] = {"n_gare": len(d), "gialli_per_gara": round(float(d.gialli_gara.mean()), 2)}
    counts = d.groupby("referee_name").size()
    ab = counts[counts >= 5]
    out["arbitri_con_almeno_5_gare"] = len(ab)
    out["gare_coperte_da_quegli_arbitri"] = int(ab.sum())
    if len(ab):
        sub = d[d.referee_name.isin(ab.index)]
        medie = sub.groupby("referee_name").gialli_gara.agg(["mean", "count"])
        # varianza fra arbitri / varianza totale (eta-quadrato di una ANOVA a un fattore)
        gran = sub.gialli_gara.mean()
        ss_b = float((medie["count"] * (medie["mean"] - gran) ** 2).sum())
        ss_t = float(((sub.gialli_gara - gran) ** 2).sum())
        out["quota_varianza_gialli_spiegata_dall_arbitro"] = round(ss_b / ss_t, 4) if ss_t else None
        out["arbitro_piu_severo"] = {"nome": medie["mean"].idxmax(),
                                     "gialli_gara": round(float(medie["mean"].max()), 2),
                                     "gare": int(medie["count"].max())}
        out["arbitro_meno_severo"] = {"nome": medie["mean"].idxmin(),
                                      "gialli_gara": round(float(medie["mean"].min()), 2),
                                      "gare": int(medie["count"].min())}
    dd = d.dropna(subset=["referee_yellows_per_match"])
    if len(dd) > 10:
        out["predizione_dalla_media_dichiarata"] = {
            "n": len(dd),
            "correlazione": round(float(np.corrcoef(dd.referee_yellows_per_match,
                                                    dd.gialli_gara)[0, 1]), 4),
            "pendenza": round(float(np.polyfit(dd.referee_yellows_per_match, dd.gialli_gara, 1)[0]), 4),
            "media_dichiarata": round(float(dd.referee_yellows_per_match.mean()), 2),
            "media_reale": round(float(dd.gialli_gara.mean()), 2)}
        # la media dichiarata divide davvero le gare in due?
        med = dd.referee_yellows_per_match.median()
        hi, lo = dd[dd.referee_yellows_per_match > med], dd[dd.referee_yellows_per_match <= med]
        out["sopra_mediana_dichiarata"] = {
            "n": len(hi), "gialli_gara": round(float(hi.gialli_gara.mean()), 2),
            "contro_n": len(lo), "contro_gialli_gara": round(float(lo.gialli_gara.mean()), 2)}
    # rigori: tirati dalle squadre di casa/trasferta, contati dagli shot con situation=Penalty
    if not shots.empty and "situation" in shots.columns:
        pen = shots[shots.situation == "Penalty"].groupby("match_id").size().rename("rigori")
        dp = d.join(pen, on="match_id")
        dp["rigori"] = dp.rigori.fillna(0)
        out["rigori_per_gara"] = round(float(dp.rigori.mean()), 3)
        dr = dp.dropna(subset=["referee_matches", "referee_penalties_total"])
        dr = dr[pd.to_numeric(dr.referee_matches, errors="coerce") > 0]
        if len(dr) > 10:
            dr = dr.assign(pens_career=pd.to_numeric(dr.referee_penalties_total, errors="coerce")
                           / pd.to_numeric(dr.referee_matches, errors="coerce"))
            med = dr.pens_career.median()
            hi, lo = dr[dr.pens_career > med], dr[dr.pens_career <= med]
            out["rigori_per_arbitro"] = {
                "n": len(dr), "mediana_career": round(float(med), 3),
                "sopra_mediana": {"n": len(hi),
                                  "rigori_gara": round(float(hi.rigori.mean()), 3)},
                "sotto_mediana": {"n": len(lo),
                                  "rigori_gara": round(float(lo.rigori.mean()), 3)},
                "correlazione": round(float(np.corrcoef(dr.pens_career, dr.rigori)[0, 1]), 4)}
    return out


# ------------------------------------------------------- 7. impegno ravvicinato
def impegno(mi: pd.DataFrame) -> dict[str, Any]:
    """Gare giocate con un altro impegno entro 3 giorni: la squadra rende meno?

    Il meccanismo non è la stanchezza (quella è il riposo **prima**), è il turnover: chi ha una
    coppa o un turno infrasettimanale subito dopo cambia gli uomini. Si misura sulle 375 gare
    finite con dettagli, calendario di campionato + coppe.
    """
    fx = _load("fixtures")
    cup = _load("cup_fixtures")
    if mi.empty or fx.empty:
        return {"n": 0}
    src = pd.concat([fx, cup], ignore_index=True) if not cup.empty else fx
    src["utc_kickoff"] = pd.to_datetime(src.utc_kickoff, utc=True)
    fin = mi[(mi.status == "finished") & mi.home_xg.notna()].copy()
    fin["ko"] = pd.to_datetime(fin.utc_kickoff, utc=True)
    righe = []
    for r in fin.itertuples(index=False):
        for tid, is_home in ((r.home_id, True), (r.away_id, False)):
            nxt = src[(src.utc_kickoff > r.ko) & (src.status != "cancelled")
                      & ((src.home_id == tid) | (src.away_id == tid))]
            if nxt.empty:
                continue
            gap = float((nxt.utc_kickoff.min() - r.ko).total_seconds() / 86400)
            gf = r.home_goals if is_home else r.away_goals
            ga = r.away_goals if is_home else r.home_goals
            xg = r.home_xg if is_home else r.away_xg
            righe.append({"gap": gap, "punti": _pts(gf, ga, True), "xg": xg,
                          "gf": gf, "ga": ga, "cup": "cup_name" in nxt.columns
                          and bool(pd.notna(nxt.iloc[0].get("cup_name"))
                                   and str(nxt.iloc[0].get("cup_name")).strip())})
    if not righe:
        return {"n": 0}
    m = pd.DataFrame(righe).dropna(subset=["gap"])
    m["b"] = pd.cut(m.gap, [0, 3, 4, 6, 100],
                    labels=["prossima gara ≤3 giorni", "4 giorni", "5-6 giorni", "≥7 giorni"])
    out: dict[str, Any] = {"n": len(m), "per_bucket": []}
    for b, g in m.groupby("b", observed=True):
        out["per_bucket"].append({"prossimo_impegno": str(b), "n": len(g),
                                  "punti_gara": round(float(g.punti.mean()), 3),
                                  "xg_gara": round(float(g.xg.mean()), 3),
                                  "gol_fatti": round(float(g.gf.mean()), 3)})
    return out


# ------------------------------------------------------------------- 8. meteo
def meteo(mi: pd.DataFrame, ts: pd.DataFrame) -> dict[str, Any]:
    """Temperatura e vento delle 375 gare finite contro gol e cartellini.

    La probabilità di pioggia la fonte la pubblica **solo per le gare future** (67 righe su
    442): sulle finite non si può misurare, e la misura va dichiarata non fatta invece di
    citare una soglia che nessuno ha verificato.
    """
    d = mi[(mi.status == "finished") & mi.weather_temp_c.notna()].copy()
    if d.empty:
        return {"n": 0}
    cards = ts[(ts.period == "All") & (ts.key == "yellow_cards")].assign(
        value=lambda x: pd.to_numeric(x.value, errors="coerce"))
    gialli = cards.groupby("match_id").value.sum().rename("gialli")
    d = d.join(gialli, on="match_id")
    d["gol"] = d.home_goals + d.away_goals
    out: dict[str, Any] = {"n": len(d), "temp_min": float(d.weather_temp_c.min()),
                           "temp_max": float(d.weather_temp_c.max()),
                           "vento_max": (float(pd.to_numeric(d.weather_wind, errors="coerce").max())
                                         if "weather_wind" in d.columns else None)}
    d["b"] = pd.cut(d.weather_temp_c, [-50, 5, 15, 25, 30, 60],
                    labels=["≤5 °C", "6-15 °C", "16-25 °C", "26-30 °C", ">30 °C"])
    out["per_temperatura"] = []
    for b, g in d.groupby("b", observed=True):
        out["per_temperatura"].append({"temp": str(b), "n": len(g),
                                       "gol_gara": round(float(g.gol.mean()), 3),
                                       "gialli_gara": (round(float(g.gialli.mean()), 2)
                                                       if g.gialli.notna().any() else None)})
    w = pd.to_numeric(d.weather_wind, errors="coerce")
    d["w"] = w
    d["bw"] = pd.cut(d.w, [-1, 8, 12, 20, 500], labels=["≤8", "9-12", "13-20", ">20 km/h"])
    out["per_vento"] = []
    for b, g in d.groupby("bw", observed=True):
        out["per_vento"].append({"vento": str(b), "n": len(g),
                                 "gol_gara": round(float(g.gol.mean()), 3)})
    return out


# ------------------------------------------------------------------- 9. pressing
def pressing(us: pd.DataFrame, mi: pd.DataFrame) -> dict[str, Any]:
    """Rapporto di PPDA e gol: la soglia ≤0,75× separa qualcosa?

    Il PPDA arriva solo da Understat, quindi copre le leghe che Understat copre: la misura è su
    quel perimetro e la scheda deve dirlo (su NED1/POR1 la riga è «non calcolabile»).
    """
    if us.empty or mi.empty:
        return {"n": 0}
    pp = us.groupby("team_name").ppda.mean()
    d = mi[(mi.status == "finished") & mi.home_xg.notna()].copy()
    # i nomi di FotMob e di Understat non sono identici: si passa per il nome del calendario
    fx = _load("fixtures")
    map_id = dict(zip(fx.home_id, fx.home_name)) | dict(zip(fx.away_id, fx.away_name)) if not fx.empty else {}
    d["ppda_h"] = [pp.get(map_id.get(int(t), ""), np.nan) for t in d.home_id]
    d["ppda_a"] = [pp.get(map_id.get(int(t), ""), np.nan) for t in d.away_id]
    d = d.dropna(subset=["ppda_h", "ppda_a"])
    if d.empty:
        return {"n": 0, "nota": "nessuna gara con PPDA per entrambe le squadre"}
    d["ratio"] = d.ppda_h / d.ppda_a
    d["gol"] = d.home_goals + d.away_goals
    d["esito"] = np.where(d.home_goals > d.away_goals, "h",
                          np.where(d.home_goals == d.away_goals, "d", "a"))
    d["punti_casa"] = np.where(d.esito == "h", 3, np.where(d.esito == "d", 1, 0))
    d["b"] = pd.cut(d.ratio, [0, FACTOR_PRESS, 0.9, 1.1, 1 / FACTOR_PRESS, 9],
                    labels=[f"≤{FACTOR_PRESS}× (casa pressa molto)", f"{FACTOR_PRESS}-0,90×",
                            "0,90-1,10× (pari)", f"1,10-{1 / FACTOR_PRESS:.2f}×",
                            f"≥{1 / FACTOR_PRESS:.2f}× (ospite pressa molto)"])
    out: dict[str, Any] = {"n": len(d), "per_bucket": []}
    for b, g in d.groupby("b", observed=True):
        out["per_bucket"].append({"rapporto_ppda": str(b), "n": len(g),
                                  "gol_gara": round(float(g.gol.mean()), 3),
                                  "xg_gara": round(float((g.home_xg + g.away_xg).mean()), 3),
                                  "punti_casa_gara": round(float(g.punti_casa.mean()), 3)})
    return out


def _fmt(d: Any, ind: int = 0) -> str:
    pad = "  " * ind
    if isinstance(d, dict):
        righe = []
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                righe.append(f"{pad}{k}:")
                righe.append(_fmt(v, ind + 1))
            else:
                righe.append(f"{pad}{k}: {v}")
        return "\n".join(r for r in righe if r)
    if isinstance(d, list):
        return "\n".join(f"{pad}- " + " · ".join(f"{k}={v}" for k, v in x.items())
                         if isinstance(x, dict) else f"{pad}- {x}" for x in d)
    return f"{pad}{d}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="scrive il riepilogo anche in JSON")
    a = ap.parse_args()
    mi, ts, shots = _load("match_info"), _load("team_stats"), _load("shots")
    hist, us = _load("history"), _load("understat_team_matches")
    res = {"riposo": riposo(hist), "mercato": mercato(mi), "distanza": distanza(mi),
           "sede": sede(hist), "eta": eta(mi), "arbitro": arbitro(mi, ts, shots),
           "impegno": impegno(mi), "meteo": meteo(mi, ts), "pressing": pressing(us, mi)}
    for k, v in res.items():
        print(f"\n=== {k} ===")
        print(_fmt(v, 1))
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nscritto {a.json}")


if __name__ == "__main__":
    main()
