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
from .fmt import dec, int_it, pct_str
from .rates import (
    MIN_DEN_FOR_RATE,
    SMALL_SAMPLE_MINUTES,
    Pool,
    group_label,
    lookup,
    player_pools,
)

MIN_MINUTES = 90          # soglia per avere/entrare nei percentili (docs/07 §2.3)
MIN_PEERS = 8             # minimo pari-ruolo con dato per calcolare il percentile

POSITION_LABELS = {0: "Portiere", 1: "Difensore", 2: "Centrocampista", 3: "Attaccante"}


def _label_or_none(v: Any) -> str | None:
    """Etichetta testuale o ``None``.

    Con pandas 3 le colonne di stringhe sono Arrow-backed: un ``None`` assegnato a una
    colonna diventa ``nan`` (che nei template Jinja è *truthy* → «Amad Diallonan»).
    Ogni etichetta che esce dal DataFrame passa da qui, così il template riceve sempre
    ``str`` oppure ``None``.
    """
    return v if isinstance(v, str) and v else None

LOG_KEYS = ("minutes_played", "rating_title", "goals", "assists",
            "expected_goals", "expected_assists")


@dataclass(frozen=True)
class StatDef:
    """Definizione di una statistica aggregabile.

    kind: ``per90`` (somma → per 90 minuti), ``ratio`` (valore/totale della stessa
    chiave, es. passaggi riusciti/tentati), ``ratio2`` (chiave/chiave2, es. duelli
    vinti/vinti+persi), ``rating`` (media dei voti di partita ponderata sui minuti).

    ``count=True`` per le statistiche che sono conteggi interi (gol, tiri, passaggi…):
    il totale viene mostrato senza decimali («4», non «4,00»); il per-90 resta a due
    decimali perché è una media.

    Per le quote (``ratio``/``ratio2``) ``num_label``/``den_label``/``unita_den`` descrivono la
    frazione pubblicata («58 passaggi riusciti su 65 tentati») e l'unità del peso della stima
    (in eventi, non in minuti: docs/23 §2).
    """

    id: str
    label: str
    kind: str
    key: str = ""
    key2: str = ""
    lower: bool = False
    count: bool = False
    num_label: str = ""
    den_label: str = ""
    unita_den: str = ""


STATS: dict[str, StatDef] = {
    s.id: s for s in (
        StatDef("rating", "Media voto", "rating", "rating_title"),
        StatDef("goals", "Gol", "per90", "goals", count=True),
        StatDef("xg", "xG", "per90", "expected_goals"),
        StatDef("npxg", "xG senza rigori", "per90", "expected_goals_non_penalty"),
        StatDef("assists", "Assist", "per90", "assists", count=True),
        StatDef("xa", "xA", "per90", "expected_assists"),
        StatDef("shots", "Tiri", "per90", "total_shots", count=True),
        StatDef("sot", "Tiri nello specchio", "per90", "ShotsOnTarget", count=True),
        StatDef("chances", "Occasioni create", "per90", "chances_created", count=True),
        StatDef("dribbles", "Dribbling riusciti", "per90", "dribbles_succeeded", count=True),
        StatDef("box_touches", "Tocchi in area avversaria", "per90", "touches_opp_box", count=True),
        StatDef("passes", "Passaggi riusciti", "per90", "accurate_passes", count=True),
        StatDef("pass_pct", "Passaggi riusciti %", "ratio", "accurate_passes",
                num_label="passaggi riusciti", den_label="tentati", unita_den="tentativi"),
        StatDef("pft", "Passaggi ultimo terzo", "per90", "passes_into_final_third", count=True),
        StatDef("touches", "Tocchi palla", "per90", "touches", count=True),
        StatDef("interceptions", "Intercessioni", "per90", "interceptions", count=True),
        StatDef("recoveries", "Palloni recuperati", "per90", "recoveries", count=True),
        StatDef("clearances", "Respingimenti", "per90", "clearances", count=True),
        StatDef("aerials", "Duelli aerei vinti", "per90", "aerials_won", count=True),
        StatDef("duels_pct", "Duelli vinti %", "ratio2", "duel_won", "duel_lost",
                num_label="duelli vinti", den_label="disputati", unita_den="duelli"),
        StatDef("fouls", "Falli commessi", "per90", "fouls", count=True),
        StatDef("fouled", "Falli subiti", "per90", "was_fouled", count=True),
        StatDef("saves", "Parate", "per90", "saves", count=True),
        StatDef("saves_box", "Parate dentro l'area", "per90", "saves_inside_box", count=True),
        StatDef("conceded", "Gol subiti", "per90", "goals_conceded", lower=True, count=True),
        StatDef("prevented", "Gol prevenuti", "per90", "goals_prevented"),
        StatDef("xgot_faced", "xGOT affrontato", "per90", "expected_goals_on_target_faced"),
        StatDef("claims", "Uscite alte", "per90", "keeper_high_claim", count=True),
        StatDef("punches", "Pugni", "per90", "punches", count=True),
    )
}

#: Tipi di statistica che pubblicano una **quota** (percentuale) e non una rata per 90.
KIND_QUOTA = ("ratio", "ratio2")

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
    # conteggi interi senza decimali nel totale («4», non «4,00»); il per-90 resta decimale
    tot = (int_it(total) if stat.count else dec(total, 2)) if _ok(total) else "—"
    return tot, (dec(per90, 2) if _ok(per90) else "—")


def _titolo_cella(stat: StatDef, *, quota: bool, minuti: int, per90: str,
                  grezzo: str | None, stima: str | None, nota: str | None,
                  insufficient: bool, est_visibile: bool, num: int | None,
                  den: int | None) -> str:
    """Testo del tooltip della cella «Per 90′»: dichiara sempre **cos'è** il numero mostrato.

    Una cella senza il suo significato è un numero che il lettore deve indovinare. Qui la quota
    dice la frazione esatta («58 passaggi riusciti su 65 tentati»), la rata per 90 dice il calcolo
    e la stima dice da quale gruppo arriva (docs/19 §1.10, docs/23 §2). Il testo sta qui e non nel
    template perché è una frase verificabile: i test la interrogano come dato, non come HTML.
    """
    unita = "" if quota else "/90"
    cosa = "la percentuale grezza" if quota else "la rata per 90"
    if stima is not None and insufficient:
        return (f"Campione di {minuti}′ (sotto i 90′): {cosa} non si pubblica, sarebbe rumore. "
                f"Stima stabilizzata {stima}{unita} — {nota}")
    if stima is not None and est_visibile:
        return f"grezzo {grezzo or per90}{unita} · stima stabilizzata {stima}{unita} — {nota}"
    if quota:
        if num is not None and den is not None:
            return (f"{num} {stat.num_label} su {den} {stat.den_label} (totale stagionale): "
                    f"la percentuale non è una rata per 90 minuti")
        return "percentuale di stagione: non è una rata per 90 minuti"
    # qui non c'è né una stima né una quota: la cella porta la rata grezza, oppure niente
    if per90 in ("", "—"):
        if stima is None and minuti < SMALL_SAMPLE_MINUTES:
            return (f"campione di {minuti}′ (sotto i 90′): la rata per 90 non si pubblica, "
                    "sarebbe rumore; stima non disponibile (gruppo di pari insufficiente)")
        return ""
    testo = f"{per90}/90′"
    if stima is None and minuti < SMALL_SAMPLE_MINUTES:
        testo += (f" — campione di {minuti}′: stima non disponibile "
                  "(gruppo di pari insufficiente)")
    return testo


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

        # Stime stabilizzate (docs/19 §1.10, docs/23 §2): gruppi dei pari e peso misurati dal run,
        # non costanti nel codice. `_est` contiene la rata stabilizzata dove la rata ha un
        # denominatore: per-90 (denominatore = minuti) e quote (denominatore = eventi). Per il voto
        # resta la rata grezza: una media di voti non è un conteggio da contrarre.
        # Per le quote servono i **tentativi** (colonna `total` della chiave), non i riusciti: il
        # numeratore resta `value`. Si passa un solo frame ai pool, quindi i tentativi entrano con
        # un nome esplicito (es. ``accurate_passes__tentati``).
        pool_frame = wide.copy()
        for s2 in STATS.values():
            if s2.kind == "ratio" and not totals.empty and s2.key in totals.columns:
                pool_frame[f"{s2.key}__tentati"] = (
                    pd.to_numeric(totals[s2.key], errors="coerce")
                    .reindex(pool_frame.index).fillna(0.0))
        chiavi = {s2.id: [s2.key] for s2 in STATS.values() if s2.kind == "per90"}
        denominatori: dict[str, list[str]] = {}
        num_quota: dict[str, pd.Series] = {}
        den_quota: dict[str, pd.Series] = {}
        for s2 in STATS.values():
            if s2.kind not in KIND_QUOTA:
                continue
            chiavi[s2.id] = [s2.key]
            num_quota[s2.id] = pd.to_numeric(wide.get(s2.key, zeros), errors="coerce").fillna(0.0)
            if s2.kind == "ratio":
                denominatori[s2.id] = [f"{s2.key}__tentati"]
                den_quota[s2.id] = pd.to_numeric(totals.get(s2.key, zeros),
                                                 errors="coerce").fillna(0.0)
            else:
                denominatori[s2.id] = [s2.key, s2.key2]
                den_quota[s2.id] = (num_quota[s2.id]
                                    + pd.to_numeric(wide.get(s2.key2, zeros),
                                                    errors="coerce").fillna(0.0))
        self._num_pct = pd.DataFrame(num_quota)
        self._den_pct = pd.DataFrame(den_quota)
        self._pools = player_pools(pool_frame.reindex(idx),
                                   ident[["league_id", "position", "minutes"]],
                                   chiavi, dens=denominatori)
        est = dict(per90)
        for s2 in STATS.values():
            if s2.kind == "per90":
                est[s2.id] = self._stime(s2.id, vals[s2.id], ident["minutes"])
            elif s2.kind in KIND_QUOTA:
                est[s2.id] = self._stime_quota(s2.id, num_quota[s2.id], den_quota[s2.id])
        self._est = pd.DataFrame(est)

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
            # percentili sulle rate stabilizzate: un 100° percentile su 96 minuti non è una
            # classifica, è rumore (docs/19 §1.10). Per le percentuali e il voto: rata grezza.
            col = (self._est[sid] if sid in self._est.columns else self._per90[sid]).loc[elig.index]
            n_peers = col.groupby(grp).transform("count")
            r = col.groupby(grp).rank(pct=True) * 100
            if STATS[sid].lower:
                r = 100 - r
            pct_cols[sid] = r.where(n_peers >= MIN_PEERS)
            peers[sid] = {k: int(v) for k, v in col.groupby(grp).count().items()}
        self._pct = pd.DataFrame(pct_cols)
        self._peers = peers
        self.empty = ident.empty

    # ---- stime stabilizzate (docs/19 §1.10) ----------------------------------------------
    def _chiave_gruppo(self, player_id: int) -> tuple[int | None, int | None]:
        """(lega, ruolo) del giocatore, o ``None`` dove il dato manca (il pool ripiega)."""
        if player_id not in self.players.index:
            return None, None
        r = self.players.loc[player_id]
        lega = int(r["league_id"]) if pd.notna(r["league_id"]) else None
        ruolo = int(r["position"]) if pd.notna(r["position"]) else None
        return lega, ruolo

    def _pool(self, sid: str, player_id: int) -> tuple[Pool, str] | None:
        """Media dei pari per la statistica e il gruppo d'origine, o ``None`` se non c'è."""
        lega, ruolo = self._chiave_gruppo(player_id)
        trovato = lookup(self._pools, lega, ruolo, sid)
        if trovato is None:
            return None
        pool, (lg, rl) = trovato
        return pool, group_label(lg, rl)

    def _stime(self, sid: str, num: pd.Series, mins: pd.Series) -> pd.Series:
        """Valore stabilizzato per giocatore (una serie allineata a ``num``)."""
        out = pd.Series(np.nan, index=num.index, dtype=float)
        for pid in num.index:
            trovato = self._pool(sid, int(pid))
            if trovato is None:
                continue
            pool, _gruppo = trovato
            den = float(mins.get(pid, 0.0) or 0.0)
            if den <= 0:
                continue
            out[pid] = pool.per90(float(num.get(pid, 0.0) or 0.0), den)
        return out

    def _stime_quota(self, sid: str, num: pd.Series, den: pd.Series) -> pd.Series:
        """Quota stabilizzata (0-1) di una statistica percentuale, ``NaN`` dove il gruppo manca.

        Il denominatore è il numero di **eventi** (tentativi di passaggio, duelli): è quello a
        rendere piccola una quota, non il minuto giocato — un difensore con 300′ e 4 duelli non ha
        una «quota dei duelli», ha quattro duelli (docs/23 §2).
        """
        out = pd.Series(np.nan, index=num.index, dtype=float)
        for pid in num.index:
            trovato = self._pool(sid, int(pid))
            if trovato is None:
                continue
            pool, _gruppo = trovato
            d = float(den.get(pid, 0.0) or 0.0)
            if d <= 0:
                continue
            out[pid] = pool.shrink(float(num.get(pid, 0.0) or 0.0), d)
        return out

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
        """Una riga della tabella «Stagione», con la regola di pubblicazione delle rate.

        - campione pieno (≥ 270′ di gioco): si pubblica il valore grezzo;
        - campione ridotto (90′ ≤ minuti < 270′): valore grezzo **con** la stima stabilizzata
          accanto (marcatore ◎);
        - minuti < 90′: il grezzo **non si pubblica** (sarebbe «90,00 tiri/90» su un minuto di
          gioco, o una percentuale su tre duelli): si pubblica la stima, dichiarata come stima (◇).

        Vale per le rate per 90 **e** per le quote (docs/23 §2): la differenza è il denominatore
        della stima — minuti per le prime, eventi (tentativi, duelli) per le seconde — e il fatto
        che una quota non è mai una rata per 90, quindi il suo tooltip dice la frazione esatta.
        """
        s = STATS[sid]
        quota = s.kind in KIND_QUOTA
        mins = float(self.players.loc[player_id, "minutes"]) if player_id in self.players.index else 0.0
        v = self._vals[sid].get(player_id)
        p90 = self._per90[sid].get(player_id)
        pct = self._pct[sid].get(player_id) if sid in self._pct.columns else None
        peers = self._peers.get(sid, {}).get(self._peer_key(player_id))
        est = self._est[sid].get(player_id) if sid in self._est.columns else None
        num = den = None
        if quota and sid in self._den_pct.columns:
            n_q, d_q = self._num_pct[sid].get(player_id), self._den_pct[sid].get(player_id)
            if None not in (n_q, d_q) and not pd.isna(n_q) and not pd.isna(d_q) and float(d_q) > 0:
                num, den = int(n_q), int(d_q)
        grezzo_s = (pct_str(p90, 1) if quota else dec(p90, 2)) if p90 is not None and not pd.isna(p90) else None
        est_s, est_note = None, None
        insufficient = est_visibile = False
        ha_stima = est is not None and not pd.isna(est) and s.kind != "rating"
        if ha_stima:
            trovato = self._pool(sid, player_id)
            est_s = pct_str(est, 1) if quota else dec(est, 2)
            if trovato is not None:
                est_note = (trovato[0].note_pct(trovato[1], unit=s.unita_den) if quota
                            else trovato[0].note(trovato[1]))
            insufficient = mins < MIN_DEN_FOR_RATE
            # sopra i 270′ la stima è a un soffio dalla rata: mostrarla confonderebbe senza dire nulla
            est_visibile = mins < SMALL_SAMPLE_MINUTES
        pubblicata = None if insufficient else p90
        tot_s, p90_s = _fmt_pair(s, v, pubblicata)
        return {"id": sid, "label": s.label, "total": tot_s, "per90": p90_s,
                "per90_raw": grezzo_s,
                "per90_titolo": _titolo_cella(s, quota=quota, minuti=int(mins), per90=p90_s,
                                              grezzo=grezzo_s, stima=est_s, nota=est_note,
                                              insufficient=insufficient,
                                              est_visibile=est_visibile, num=num, den=den),
                "quota": quota, "num": num, "den": den, "minutes": int(mins),
                "est": None if est is None or pd.isna(est) else float(est), "est_s": est_s,
                "est_note": est_note, "insufficient": insufficient,
                "est_visibile": bool(est_s and est_visibile),
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
            "position_label": _label_or_none(r["position_label"]), "position": pos_int,
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
            "pos": _label_or_none(r["position_label"]),
            "age": None if pd.isna(r["age"]) else int(r["age"]),
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
            "pos": _label_or_none(r["position_label"]),
            "age": None if pd.isna(r["age"]) else int(r["age"]),
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
