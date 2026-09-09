"""Catalogo giocatori per le pagine ``giocatori/`` (fase 3 — docs/07_fase3_giocatori.md).

Statistiche di stagione aggregate da ``player_stats`` (FotMob, formato lungo per
partita), anagrafica da ``lineup``, lega e calendario da ``fixtures`` (id canonico,
non quello di stagione che FotMob riporta nei matchDetails). Percentili calcolati
entro *stessa lega + stesso ruolo* con soglia minima di minuti; le statistiche
"lower is better" (es. gol subiti) sono capovolte. Nessun dato inventato: chiave
assente = 0 eventi (semantica FotMob verificata, docs/07 §1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from ..config import load_leagues_config
from ..store import Store
from .analysis import _return_it, unavailability_it
from .fmt import dec, pct_str

MIN_MINUTES = 90          # soglia per avere/entrare nei percentili (docs/07 §2.3)
MIN_PEERS = 8             # minimo pari-ruolo con dato per calcolare il percentile
SMALL_SAMPLE_MINUTES = 270  # sotto: avviso «campione ridotto»

POSITION_LABELS = {0: "Portiere", 1: "Difensore", 2: "Centrocampista", 3: "Attaccante"}

LOG_KEYS = ("minutes_played", "rating_title", "goals", "assists",
            "expected_goals", "expected_assists")


@dataclass(frozen=True)
class StatDef:
    """Definizione di una statistica aggregabile.

    kind: ``per90`` (somma → per 90 minuti), ``ratio`` (valore/totale della stessa
    chiave, es. passaggi riusciti/tentati), ``ratio2`` (chiave/chiave2, es. duelli
    vinti/vinti+persi), ``rating`` (media dei voti di partita ponderata sui minuti).
    """

    id: str
    label: str
    kind: str
    key: str = ""
    key2: str = ""
    lower: bool = False


STATS: dict[str, StatDef] = {
    s.id: s for s in (
        StatDef("rating", "Media voto", "rating", "rating_title"),
        StatDef("goals", "Gol", "per90", "goals"),
        StatDef("xg", "xG", "per90", "expected_goals"),
        StatDef("npxg", "xG senza rigori", "per90", "expected_goals_non_penalty"),
        StatDef("assists", "Assist", "per90", "assists"),
        StatDef("xa", "xA", "per90", "expected_assists"),
        StatDef("shots", "Tiri", "per90", "total_shots"),
        StatDef("sot", "Tiri nello specchio", "per90", "ShotsOnTarget"),
        StatDef("chances", "Occasioni create", "per90", "chances_created"),
        StatDef("dribbles", "Dribbling riusciti", "per90", "dribbles_succeeded"),
        StatDef("box_touches", "Tocchi in area avversaria", "per90", "touches_opp_box"),
        StatDef("passes", "Passaggi riusciti", "per90", "accurate_passes"),
        StatDef("pass_pct", "Passaggi riusciti %", "ratio", "accurate_passes"),
        StatDef("pft", "Passaggi nell'ultimo terzo", "per90", "passes_into_final_third"),
        StatDef("touches", "Tocchi palla", "per90", "touches"),
        StatDef("interceptions", "Intercessioni", "per90", "interceptions"),
        StatDef("recoveries", "Palloni recuperati", "per90", "recoveries"),
        StatDef("clearances", "Respingimenti", "per90", "clearances"),
        StatDef("aerials", "Duelli aerei vinti", "per90", "aerials_won"),
        StatDef("duels_pct", "Duelli vinti %", "ratio2", "duel_won", "duel_lost"),
        StatDef("fouls", "Falli commessi", "per90", "fouls"),
        StatDef("fouled", "Falli subiti", "per90", "was_fouled"),
        StatDef("saves", "Parate", "per90", "saves"),
        StatDef("saves_box", "Parate dentro l'area", "per90", "saves_inside_box"),
        StatDef("conceded", "Gol subiti", "per90", "goals_conceded", lower=True),
        StatDef("prevented", "Gol prevenuti", "per90", "goals_prevented"),
        StatDef("xgot_faced", "xGOT affrontato", "per90", "expected_goals_on_target_faced"),
        StatDef("claims", "Uscite alte", "per90", "keeper_high_claim"),
        StatDef("punches", "Pugni", "per90", "punches"),
    )
}

# Radar: 6 assi per ruolo (percentili). Etichette corte per la grafica.
RADAR: dict[int, list[tuple[str, str]]] = {
    0: [("rating", "Voto"), ("saves", "Parate"), ("prevented", "G. prev."),
        ("claims", "Uscite"), ("conceded", "G. subiti"), ("xgot_faced", "xGOT")],
    1: [("rating", "Voto"), ("interceptions", "Interc."), ("recoveries", "Recup."),
        ("duels_pct", "Duelli %"), ("clearances", "Resp."), ("xa", "xA")],
    2: [("rating", "Voto"), ("chances", "Occ. create"), ("xa", "xA"),
        ("passes", "Passaggi"), ("dribbles", "Dribbling"), ("recoveries", "Recup.")],
    3: [("rating", "Voto"), ("xg", "xG"), ("goals", "Gol"),
        ("sot", "Tiri specch."), ("xa", "xA"), ("chances", "Occ. create")],
}

# Barre dei percentili: radar + statistiche in più (per profondità).
PCT_EXTRA: dict[int, list[str]] = {
    0: ["saves_box", "punches", "passes"],
    1: ["aerials", "xg", "pft", "box_touches"],
    2: ["pft", "interceptions", "duels_pct", "touches"],
    3: ["npxg", "shots", "dribbles", "box_touches"],
}

# Tabella «Stagione»: (gruppo, [id statistiche]); D, C e A condividono gli stessi gruppi.
_TABLE_GK = [("Porta", ["conceded", "saves", "saves_box", "prevented", "xgot_faced"]),
             ("Uscite", ["claims", "punches"]),
             ("Costruzione", ["passes", "pass_pct", "touches", "recoveries"])]
_TABLE_FIELD = [("Attacco", ["goals", "xg", "assists", "xa", "shots", "sot", "chances",
                             "dribbles", "box_touches"]),
                ("Costruzione", ["passes", "pass_pct", "pft", "touches"]),
                ("Difesa e duelli", ["interceptions", "recoveries", "clearances", "aerials",
                                     "duels_pct", "fouls", "fouled"])]
TABLE: dict[int, list[tuple[str, list[str]]]] = {0: _TABLE_GK, 1: _TABLE_FIELD,
                                                 2: _TABLE_FIELD, 3: _TABLE_FIELD}


def _fmt_pair(stat: StatDef, total: Any, per90: Any) -> tuple[str, str]:
    """(totale, per 90) formattati in italiano; '—' quando il dato manca."""
    def _ok(v):
        return v is not None and not pd.isna(v)

    if stat.kind in ("ratio", "ratio2"):
        return (pct_str(total) if _ok(total) else "—",
                pct_str(per90, 1) if _ok(per90) else "—")
    if stat.id == "rating":
        return (dec(total, 2) if _ok(total) else "—"), ""
    return (dec(total, 2) if _ok(total) else "—",
            dec(per90, 2) if _ok(per90) else "—")


class PlayerCatalog:
    """Carica una volta tutti i giocatori visti nei lineup e le loro statistiche."""

    def __init__(self, store: Store) -> None:
        self.season = str(load_leagues_config().get("season", ""))
        self.empty = True
        self.players: pd.DataFrame = pd.DataFrame()
        self._vals: pd.DataFrame = pd.DataFrame()   # totale (o frazione per i ratio)
        self._per90: pd.DataFrame = pd.DataFrame()  # valore per 90 (o frazione)
        self._pct: pd.DataFrame = pd.DataFrame()    # percentile 0–100 (solo idonei)
        self._peers: dict[str, dict[tuple[int, int], int]] = {}
        self._ps: pd.DataFrame = pd.DataFrame()
        self._fx: pd.DataFrame = pd.DataFrame()
        self._load(store)

    # ---- caricamento ------------------------------------------------------------------
    def _load(self, store: Store) -> None:
        lu = store.read("lineup")
        ps = store.read("player_stats")
        fx = store.read("fixtures")
        if lu.empty or fx.empty:
            return
        lu = lu[lu["role"] != "coach"].dropna(subset=["player_id"]).copy()

        # nomi squadre (ultimo valore visto nel calendario) + calendario indicizzato
        names = pd.concat([
            fx[["home_id", "home_name"]].rename(columns={"home_id": "team_id", "home_name": "team"}),
            fx[["away_id", "away_name"]].rename(columns={"away_id": "team_id", "away_name": "team"}),
        ]).dropna().drop_duplicates("team_id", keep="last")
        team_names = dict(zip(names.team_id.astype(int), names.team))
        self._fx = fx[["match_id", "league_id", "utc_kickoff", "home_id", "away_id",
                       "home_name", "away_name", "home_goals", "away_goals"]].drop_duplicates("match_id")

        # identità: ultimo valore non nullo per colonna, ordinando per data di gara
        lu = lu.merge(self._fx[["match_id", "league_id", "utc_kickoff"]], on="match_id", how="left")
        lu = lu.sort_values("utc_kickoff")
        g = lu.groupby("player_id")
        ident = pd.DataFrame({
            "name": g["player_name"].last(),
            "team_id": g["team_id"].last().astype("Int64"),
            "position": g["usual_position_id"].last(),
            "age": g["age"].last(),
            "country": g["country"].last(),
            "market_value_eur": g["market_value_eur"].last(),
            "captain": g["is_captain"].max().fillna(False).astype(bool),
            "unavail_type": g["unavailability_type"].last(),
            "expected_return": g["expected_return"].last(),
            "league_id": g["league_id"].last().astype("Int64"),
        })
        self._ps = ps

        # statistiche per partita → wide (somma per chiave; chiave assente = 0 eventi)
        idx = ident.index
        if ps.empty:
            wide = pd.DataFrame(index=idx)
            totals = pd.DataFrame(index=idx)
            n_matches = pd.Series(0, index=idx, dtype=int)
            rating = pd.Series(np.nan, index=idx)
        else:
            wide = ps.pivot_table(index="player_id", columns="key", values="value",
                                  aggfunc="sum").reindex(idx)
            totals = ps.pivot_table(index="player_id", columns="key", values="total",
                                    aggfunc="sum").reindex(idx)
            n_matches = (ps.groupby("player_id")["match_id"].nunique()
                         .reindex(idx).fillna(0).astype(int))
            # media voto ponderata sui minuti giocati (docs/07 §2.7)
            rt = ps[ps["key"] == "rating_title"][["player_id", "match_id", "value"]].rename(columns={"value": "r"})
            mn = ps[ps["key"] == "minutes_played"][["player_id", "match_id", "value"]].rename(columns={"value": "m"})
            rm = rt.dropna(subset=["r"]).merge(mn.dropna(subset=["m"]), on=["player_id", "match_id"], how="inner")
            if rm.empty:
                rating = pd.Series(np.nan, index=idx)
            else:
                rm["wr"] = rm["r"] * rm["m"]
                agg = rm.groupby("player_id")[["wr", "m"]].sum()
                rating = (agg["wr"] / agg["m"].where(agg["m"] > 0)).reindex(idx)

        ident["matches"] = n_matches
        ident["minutes"] = (wide.get("minutes_played") if not wide.empty else None)
        ident["minutes"] = ident["minutes"] if ident["minutes"] is not None else pd.Series(0.0, index=idx)
        ident["minutes"] = ident["minutes"].fillna(0)
        ident["rating"] = pd.to_numeric(rating, errors="coerce")
        ident["team_name"] = ident["team_id"].map(lambda v: team_names.get(int(v)) if pd.notna(v) else None)
        ident["position_label"] = ident["position"].map(
            lambda v: POSITION_LABELS.get(int(v)) if pd.notna(v) else None)
        self.players = ident
        self._wide, self._totals = wide, totals

        # valori e per-90 di ogni statistica
        mins = ident["minutes"].where(ident["minutes"] > 0)
        vals: dict[str, pd.Series] = {}
        per90: dict[str, pd.Series] = {}
        zeros = pd.Series(0.0, index=idx)
        for s in STATS.values():
            if s.kind == "rating":
                vals[s.id] = per90[s.id] = ident["rating"]
                continue
            col = wide.get(s.key)
            col = zeros if col is None else col.fillna(0.0)
            if s.kind == "per90":
                vals[s.id], per90[s.id] = col, 90 * col / mins
            elif s.kind == "ratio":
                t = totals.get(s.key)
                t = pd.Series(np.nan, index=idx) if t is None else t
                r = col / t.where(t > 0)
                vals[s.id] = per90[s.id] = r
            elif s.kind == "ratio2":
                c2 = wide.get(s.key2)
                c2 = zeros if c2 is None else c2.fillna(0.0)
                den = col + c2
                r = col / den.where(den > 0)
                vals[s.id] = per90[s.id] = r
        self._vals = pd.DataFrame(vals)
        self._per90 = pd.DataFrame(per90)

        # percentili entro lega+ruolo (solo chi ha ≥ MIN_MINUTES e ruolo noto)
        elig = ident[(ident["minutes"] >= MIN_MINUTES) & ident["position"].notna()
                     & ident["league_id"].notna()]
        if elig.empty:
            self.empty = ident.empty
            return
        grp = [elig["league_id"].astype(int), elig["position"].astype(int)]
        pct_cols: dict[str, pd.Series] = {}
        peers: dict[str, dict[tuple[int, int], int]] = {}
        for sid in self._per90.columns:
            col = self._per90.loc[elig.index, sid]
            n_peers = col.groupby(grp).transform("count")
            r = col.groupby(grp).rank(pct=True) * 100
            if STATS[sid].lower:
                r = 100 - r
            pct_cols[sid] = r.where(n_peers >= MIN_PEERS)
            peers[sid] = {k: int(v) for k, v in col.groupby(grp).count().items()}
        self._pct = pd.DataFrame(pct_cols)
        self._peers = peers
        self.empty = ident.empty

    # ---- accesso -----------------------------------------------------------------------
    def player_ids(self) -> list[int]:
        return sorted(int(i) for i in self.players.index)

    def _peer_key(self, player_id: int) -> tuple[int, int] | None:
        if player_id not in self.players.index:
            return None
        r = self.players.loc[player_id]
        if pd.isna(r["position"]) or pd.isna(r["league_id"]):
            return None
        return int(r["league_id"]), int(r["position"])

    def _stat_row(self, sid: str, player_id: int) -> dict[str, Any]:
        s = STATS[sid]
        v = self._vals[sid].get(player_id)
        p90 = self._per90[sid].get(player_id)
        pct = self._pct[sid].get(player_id) if sid in self._pct.columns else None
        peers = self._peers.get(sid, {}).get(self._peer_key(player_id))
        tot_s, p90_s = _fmt_pair(s, v, p90)
        return {"id": sid, "label": s.label, "total": tot_s, "per90": p90_s,
                "pct": None if pct is None or pd.isna(pct) else round(float(pct)),
                "peers": peers, "lower": s.lower}

    # ---- radar SVG -------------------------------------------------------------------------
    def radar(self, player_id: int) -> dict[str, Any] | None:
        """Poligono dei percentili (6 assi). Se anche un solo asse è n.d. → None."""
        if player_id not in self.players.index:
            return None
        pos = self.players.loc[player_id, "position"]
        if pd.isna(pos) or int(pos) not in RADAR:
            return None
        pos = int(pos)
        axes, points = [], []
        n = len(RADAR[pos])
        cx, cy, r_max = 170.0, 150.0, 90.0
        for i, (sid, label) in enumerate(RADAR[pos]):
            row = self._stat_row(sid, player_id)
            pct = row["pct"]
            ang = np.deg2rad(-90 + i * 360 / n)
            ux, uy = np.cos(ang), np.sin(ang)
            if pct is not None:
                r = r_max * pct / 100
                points.append((cx + r * ux, cy + r * uy))
            lx, ly = cx + (r_max + 16) * ux, cy + (r_max + 16) * uy
            anchor = "start" if ux > 0.35 else "end" if ux < -0.35 else "middle"
            axes.append({"label": label, "pct": pct, "lower": row["lower"],
                         "lx": round(lx, 1), "ly": round(ly, 1), "anchor": anchor})
        if len(points) < n:
            return None
        rings = []
        for ring in (25, 50, 75, 100):
            pts = [f"{cx + r_max * ring / 100 * np.cos(np.deg2rad(-90 + i * 360 / n)):.1f},"
                   f"{cy + r_max * ring / 100 * np.sin(np.deg2rad(-90 + i * 360 / n)):.1f}"
                   for i in range(n)]
            rings.append(" ".join(pts))
        spokes = [(f"{cx + r_max * np.cos(np.deg2rad(-90 + i * 360 / n)):.1f}",
                   f"{cy + r_max * np.sin(np.deg2rad(-90 + i * 360 / n)):.1f}") for i in range(n)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        return {"axes": axes, "poly": poly, "rings": rings, "spokes": spokes,
                "cx": cx, "cy": cy}

    # ---- log partite ------------------------------------------------------------------------
    def match_log(self, player_id: int, built_ids: set[int]) -> list[dict[str, Any]]:
        if self._ps.empty or self._fx.empty or player_id not in self.players.index:
            return []
        ps = self._ps[self._ps["player_id"] == player_id]
        if ps.empty:
            return []
        w = ps[ps["key"].isin(LOG_KEYS)].pivot_table(
            index=["match_id", "team_id"], columns="key", values="value", aggfunc="sum")
        w = w.reindex(columns=list(LOG_KEYS)).reset_index()
        w = w.merge(self._fx, on="match_id", how="inner")
        w = w.sort_values("utc_kickoff", ascending=False)
        out = []
        for r in w.itertuples(index=False):
            is_home = int(r.team_id) == int(r.home_id)
            hg, ag = r.home_goals, r.away_goals
            res = None
            if pd.notna(hg) and pd.notna(ag):
                gf, ga = (hg, ag) if is_home else (ag, hg)
                res = "V" if gf > ga else "P" if gf < ga else "N"
            rating = getattr(r, "rating_title", None)
            mins = getattr(r, "minutes_played", None)
            out.append({
                "match_id": int(r.match_id),
                "date": pd.Timestamp(r.utc_kickoff),
                "opponent": r.away_name if is_home else r.home_name,
                "home": is_home,
                "score": None if pd.isna(hg) or pd.isna(ag) else f"{int(hg)}-{int(ag)}",
                "res": res,
                "minutes": int(mins) if mins is not None and pd.notna(mins) else 0,
                "rating": None if rating is None or pd.isna(rating) else round(float(rating), 2),
                "goals": _int_or0(getattr(r, "goals", None)),
                "assists": _int_or0(getattr(r, "assists", None)),
                "xg": _f_or_none(getattr(r, "expected_goals", None)),
                "xa": _f_or_none(getattr(r, "expected_assists", None)),
                "link": int(r.match_id) in built_ids,
            })
        return out

    # ---- pagine ------------------------------------------------------------------------------
    def player_page(self, player_id: int, built_ids: set[int]) -> dict[str, Any] | None:
        if self.empty or player_id not in self.players.index:
            return None
        r = self.players.loc[player_id]
        pos_int = int(r["position"]) if pd.notna(r["position"]) else None
        table: list[dict[str, Any]] = []
        if r["minutes"] > 0:
            # ruolo n.d. → tabella generica da outfield (nessuna statistica da portiere)
            for group, sids in TABLE.get(pos_int, _TABLE_FIELD):
                table.append({"group": group, "header": True})
                table.extend({**self._stat_row(sid, player_id), "header": False} for sid in sids)
        pct_rows: list[dict[str, Any]] = []
        if pos_int is not None and r["minutes"] >= MIN_MINUTES:
            radar_ids = {sid for sid, _ in RADAR.get(pos_int, [])}
            for sid in list(radar_ids) + PCT_EXTRA.get(pos_int, []):
                row = self._stat_row(sid, player_id)
                row["in_radar"] = sid in radar_ids
                pct_rows.append(row)
        unavail = None
        if isinstance(r["unavail_type"], str) and r["unavail_type"]:
            unavail = {"type": unavailability_it(r["unavail_type"]),
                       "return": _return_it(r["expected_return"])
                       if isinstance(r["expected_return"], str) else None}
        return {
            "id": player_id, "name": r["name"], "team_name": r["team_name"],
            "team_id": None if pd.isna(r["team_id"]) else int(r["team_id"]),
            "league_id": None if pd.isna(r["league_id"]) else int(r["league_id"]),
            "position_label": r["position_label"], "position": pos_int,
            "age": None if pd.isna(r["age"]) else int(r["age"]),
            "country": r["country"] if isinstance(r["country"], str) else None,
            "market_value_eur": (None if pd.isna(r["market_value_eur"])
                                 else float(r["market_value_eur"])),
            "captain": bool(r["captain"]), "unavail": unavail,
            "matches": int(r["matches"]), "minutes": int(r["minutes"]),
            "rating": None if pd.isna(r["rating"]) else round(float(r["rating"]), 2),
            "stats_table": table, "pct_rows": pct_rows,
            "radar": self.radar(player_id), "log": self.match_log(player_id, built_ids) if r["minutes"] > 0 else [],
            "small_sample": bool(r["minutes"] < SMALL_SAMPLE_MINUTES),
            "season": self.season, "min_minutes": MIN_MINUTES,
            "eligible": bool(r["minutes"] >= MIN_MINUTES),
            "n_players_league": self._n_league_players(r),
            "n_peers": self._n_peers(r),
            "has_lower_axis": pos_int is not None and any(
                STATS[sid].lower for sid, _ in RADAR.get(pos_int, [])),
        }

    def _n_league_players(self, r) -> int:
        if pd.isna(r["league_id"]):
            return 0
        return int((self.players["league_id"] == r["league_id"]).sum())

    def _n_peers(self, r) -> int:
        """Pari-ruolo idonei (stessa lega, stesso ruolo, ≥ MIN_MINUTES)."""
        if pd.isna(r["league_id"]) or pd.isna(r["position"]):
            return 0
        mask = ((self.players["league_id"] == r["league_id"])
                & (self.players["position"] == r["position"])
                & (self.players["minutes"] >= MIN_MINUTES))
        return int(mask.sum())

    def league_rows(self, league_id: int) -> tuple[list[dict], list[dict]]:
        """(giocatori con minuti, in rosa senza minuti) per la pagina di lega."""
        if self.empty:
            return [], []
        sub = self.players[self.players["league_id"] == league_id].copy()
        played = sub[sub["minutes"] > 0].sort_values(["rating", "minutes"], ascending=False)
        rows = [{
            "id": int(i), "name": r["name"], "team": r["team_name"],
            "pos": r["position_label"], "age": None if pd.isna(r["age"]) else int(r["age"]),
            "rating": None if pd.isna(r["rating"]) else round(float(r["rating"]), 2),
            "minutes": int(r["minutes"]), "matches": int(r["matches"]),
            "goals": _f_or0(self._vals["goals"].get(i)),
            "xg": _f_or0(self._vals["xg"].get(i)),
            "assists": _f_or0(self._vals["assists"].get(i)),
            "xa": _f_or0(self._vals["xa"].get(i)),
        } for i, r in played.iterrows()]
        bench = sub[sub["minutes"] == 0].sort_values("name")
        bench_rows = [{
            "id": int(i), "name": r["name"], "team": r["team_name"],
            "pos": r["position_label"], "age": None if pd.isna(r["age"]) else int(r["age"]),
            "unavail": isinstance(r["unavail_type"], str) and r["unavail_type"] != "",
        } for i, r in bench.iterrows()]
        return rows, bench_rows

    def hub_block(self, league_id: int, league_name: str, league_key: str,
                  top: int = 10) -> dict[str, Any]:
        rows, bench = self.league_rows(league_id)
        return {"key": league_key, "name": league_name, "league_id": league_id,
                "top": rows[:top], "n_played": len(rows), "n_bench": len(bench)}


def _int_or0(v) -> int:
    return int(v) if v is not None and pd.notna(v) else 0


def _f_or_none(v) -> float | None:
    return round(float(v), 2) if v is not None and pd.notna(v) else None


def _f_or0(v) -> float:
    return round(float(v), 2) if v is not None and pd.notna(v) else 0.0
