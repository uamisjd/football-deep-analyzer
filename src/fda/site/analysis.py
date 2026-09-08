"""Costruzione del contenuto analitico di una partita (in italiano) a partire dallo store.

Nessuna generazione "creativa": ogni frase deriva da un numero presente nel database, con
regole esplicite (soglie documentate nel codice). Il risultato è un dizionario che i template
Jinja2 rendono in HTML.
"""

from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..store import Store
from ..teams import canonical

POSITION_NAMES = {1: "portiere", 2: "difensore", 3: "centrocampista", 4: "attaccante"}


def _pct(p: float | None) -> str:
    return "—" if p is None or pd.isna(p) else f"{p * 100:.0f}%"


def _f(x: Any, nd: int = 2) -> str:
    """Numero per il testo narrativo: virgola decimale italiana ('3,12'; '—' se manca)."""
    return "—" if x is None or pd.isna(x) else f"{float(x):.{nd}f}".replace(".", ",")


def _first(df: pd.DataFrame) -> dict[str, Any]:
    return {} if df.empty else df.iloc[0].to_dict()


def _goals(info: dict, key: str, fixture: dict) -> int | None:
    v = _val(info, key)
    if v is None:
        v = _val(fixture, key)
    return None if v is None else int(v)


def _val(d: dict, key: str, default=None):
    v = d.get(key, default)
    return default if v is None or (isinstance(v, float) and pd.isna(v)) else v


# FotMob fornisce le condizioni meteo in inglese: mappa minima per il sito in italiano
_WEATHER_IT = {
    "sunny": "soleggiato", "clear": "sereno", "mostly clear": "per lo più sereno", "fair": "bel tempo",
    "mostly sunny": "per lo più soleggiato",
    "partly cloudy": "parzialmente nuvoloso", "mostly cloudy": "per lo più nuvoloso",
    "cloudy": "nuvoloso", "overcast": "coperto", "rain": "pioggia", "light rain": "pioggia debole",
    "heavy rain": "pioggia intensa", "drizzle": "pioggia leggera", "showers": "rovesci",
    "rain showers": "rovesci di pioggia", "showers in the vicinity": "rovesci nelle vicinanze",
    "thunderstorm": "temporale", "thunderstorms": "temporali", "thunder in the vicinity": "temporali nelle vicinanze",
    "snow": "neve", "light snow": "neve debole", "heavy snow": "neve abbondante", "sleet": "nevischio",
    "fog": "nebbia", "foggy": "nebbioso", "mist": "foschia", "haze": "foschia",
    "windy": "ventoso", "wind": "ventoso",
}


def _weather_it(desc: str | None) -> str | None:
    if not isinstance(desc, str) or not desc.strip():
        return desc
    t = desc.strip()
    low = t.lower()
    if low in _WEATHER_IT:
        return _WEATHER_IT[low]
    if "/" in low:  # varianti combinate di FotMob, es. "Partly Cloudy/Wind"
        parts = [p.strip() for p in low.split("/")]
        if all(p in _WEATHER_IT for p in parts):
            return " e ".join(_WEATHER_IT[p] for p in parts)
    return t


# Rientri previsti degli indisponibili (campo expectedReturn di FotMob, in inglese)
_MONTHS_IT = {"january": "gennaio", "february": "febbraio", "march": "marzo", "april": "aprile",
              "may": "maggio", "june": "giugno", "july": "luglio", "august": "agosto",
              "september": "settembre", "october": "ottobre", "november": "novembre", "december": "dicembre"}
_RETURN_IT = {
    "day to day": "giorno per giorno", "doubtful": "in dubbio", "unknown": "non nota",
    "about 1-2 weeks": "circa 1-2 settimane", "about 2-4 weeks": "circa 2-4 settimane",
    "about a week": "circa una settimana", "a few days": "pochi giorni", "a few weeks": "poche settimane",
    "back in training": "rientrato agli allenamenti", "out for season": "fuori per tutta la stagione",
    "out for tournament": "fuori per tutto il torneo", "suspended": "squalificato",
}
_RETURN_PART_IT = {"early": "inizio", "mid": "metà", "late": "fine"}


def _return_it(s: str | None) -> str | None:
    """'Mid October 2026' → 'metà ottobre 2026'; forme note tradotte, il resto invariato."""
    if not isinstance(s, str) or not s.strip():
        return s
    t = s.strip()
    if t.lower() in _RETURN_IT:
        return _RETURN_IT[t.lower()]
    m = re.match(r"^(Early|Mid|Late)\s+([A-Za-z]+)\s+(\d{4})$", t)
    if m and m.group(2).lower() in _MONTHS_IT:
        return f"{_RETURN_PART_IT[m.group(1).lower()]} {_MONTHS_IT[m.group(2).lower()]} {m.group(3)}"
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", t)
    if m and m.group(1).lower() in _MONTHS_IT:
        return f"{_MONTHS_IT[m.group(1).lower()]} {m.group(2)}"
    return t


def _it2(v: float) -> str:
    """3.5 → '3,50' (virgola decimale italiana)."""
    return f"{float(v):.2f}".replace(".", ",")


def _signed_int(v: Any) -> str:
    """+6 / -3 / 0 (differenza reti con segno)."""
    try:
        d = int(v)
    except (TypeError, ValueError):
        return "—"
    return f"+{d}" if d > 0 else str(d)


class MatchAnalysis:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.fixtures = store.read("fixtures")
        self.info = store.read("match_info")
        self.lineup = store.read("lineup")
        self.team_stats = store.read("team_stats")
        self.shots = store.read("shots")
        self.events = store.read("events")
        self.preds = store.read("predictions")
        self.us_team = store.read("understat_team_matches")
        self.fm_standings = store.read("fotmob_standings")
        self.standings = store.read("espn_standings")
        self.momentum_df = store.read("momentum")
        self.h2h_df = store.read("h2h")

    # ---- forma recente da calendario --------------------------------------------------------
    def form(self, team_id: int, before: datetime, n: int = 5) -> list[dict[str, Any]]:
        fx = self.fixtures
        if fx.empty:
            return []
        played = fx[(fx.status == "finished") & (fx.utc_kickoff < before)
                    & ((fx.home_id == team_id) | (fx.away_id == team_id))].sort_values("utc_kickoff").tail(n)
        out = []
        for r in played.itertuples(index=False):
            is_home = r.home_id == team_id
            gf, ga = (r.home_goals, r.away_goals) if is_home else (r.away_goals, r.home_goals)
            res = "V" if gf > ga else ("N" if gf == ga else "P")
            opp = r.away_name if is_home else r.home_name
            out.append({"date": r.utc_kickoff, "opponent": opp, "home": is_home, "gf": int(gf), "ga": int(ga), "res": res})
        return out

    def rest_days(self, team_id: int, kickoff: datetime) -> int | None:
        fx = self.fixtures
        if fx.empty:
            return None
        prev = fx[(fx.utc_kickoff < kickoff) & (fx.status == "finished")
                  & ((fx.home_id == team_id) | (fx.away_id == team_id))]
        if prev.empty:
            return None
        return int((kickoff - prev.utc_kickoff.max()).total_seconds() // 86400)

    # ---- xG di stagione (Understat se c'è, altrimenti FotMob) ---------------------------------
    def season_xg(self, team_name: str, team_id: int) -> dict[str, Any] | None:
        canon = canonical(team_name)
        if not self.us_team.empty:
            rows = self.us_team[self.us_team.team_name.map(canonical) == canon]
            if not rows.empty:
                n = len(rows)
                return {"source": "Understat", "played": n, "xg": rows.xg.sum(), "xga": rows.xga.sum(),
                        "xg_pm": rows.xg.mean(), "xga_pm": rows.xga.mean(), "xpts": rows.xpts.sum(),
                        "pts": rows.pts.sum(), "ppda": rows.ppda.mean()}
        if not self.info.empty:
            fin = self.info[self.info.status == "finished"]
            h = fin[fin.home_id == team_id]
            a = fin[fin.away_id == team_id]
            xg = pd.concat([h.home_xg, a.away_xg]).dropna()
            xga = pd.concat([h.away_xg, a.home_xg]).dropna()
            if len(xg):
                return {"source": "FotMob", "played": int(len(xg)), "xg": xg.sum(), "xga": xga.sum(),
                        "xg_pm": xg.mean(), "xga_pm": xga.mean(), "xpts": None, "pts": None, "ppda": None}
        return None

    def standing(self, team_name: str) -> dict[str, Any] | None:
        """Classifica: prima FotMob (fonte primaria), poi ESPN come riserva."""
        canon = canonical(team_name)
        for df in (self.fm_standings, self.standings):
            if df.empty or "team_name" not in df.columns:
                continue
            rows = df[df.team_name.map(canonical) == canon]
            if not rows.empty:
                return rows.iloc[0].to_dict()
        return None

    # ---- confronto di stagione (tabella di lega) -----------------------------------------------
    @staticmethod
    def _cmp_row(label: str, h: str, a: str, key_h: float | None = None,
                 key_a: float | None = None, higher: bool = True) -> dict[str, Any]:
        """Riga della card «Confronto di stagione»; evidenzia il lato migliore se confrontabile."""
        best = None
        if key_h is not None and key_a is not None and key_h != key_a:
            best = "h" if (key_h > key_a) == higher else "a"
        return {"label": label, "h": h, "a": a, "best": best}

    def _league_averages(self, st: dict[str, Any]) -> dict[str, float] | None:
        """Media gol fatti/subiti per gara nel campionato, dalla stessa tabella della classifica."""
        for df in (self.fm_standings, self.standings):
            if df.empty or "played" not in df.columns or "goals_for" not in df.columns:
                continue
            rows = df
            if "league_code" in df.columns:
                code = st.get("league_code")
                rows = df[df.league_code == code] if code else df.iloc[0:0]
            played = pd.to_numeric(rows["played"], errors="coerce").sum()
            if played > 0:
                return {"gf": pd.to_numeric(rows["goals_for"], errors="coerce").sum() / played,
                        "ga": pd.to_numeric(rows["goals_against"], errors="coerce").sum() / played}
        return None

    def season_compare(self, home_st: dict[str, Any] | None,
                       away_st: dict[str, Any] | None) -> dict[str, Any] | None:
        """Card «Confronto di stagione»: classifica di entrambe le squadre (FotMob, riserva ESPN).

        Renderizzata anche con una sola squadra disponibile (l'altra mostra «—»);
        None se nessuna delle due ha classifica (la card non compare).
        """
        if not home_st and not away_st:
            return None
        try:
            def side(st: dict[str, Any] | None) -> dict[str, Any] | None:
                if not st:
                    return None
                p = float(st["played"])
                if p <= 0:
                    return None
                pts, gf, ga = float(st["points"]), float(st["goals_for"]), float(st["goals_against"])
                return {"rank": int(st["rank"]), "p": p, "ppg": pts / p, "gf_pg": gf / p,
                        "ga_pg": ga / p, "diff": int(st["goal_diff"]),
                        "pts_s": f"{pts:.0f} in {p:.0f} gare", "wdl": f"{int(st['wins'])}-{int(st['draws'])}-{int(st['losses'])}"}

            dash = "—"
            h, a = side(home_st), side(away_st)
            rows = [
                self._cmp_row("Posizione", str(h["rank"]) if h else dash, str(a["rank"]) if a else dash,
                              key_h=h and h["rank"], key_a=a and a["rank"], higher=False),
                self._cmp_row("Punti", h["pts_s"] if h else dash, a["pts_s"] if a else dash,
                              key_h=h and h["ppg"], key_a=a and a["ppg"]),
                self._cmp_row("Punti/gara", _it2(h["ppg"]) if h else dash, _it2(a["ppg"]) if a else dash,
                              key_h=h and h["ppg"], key_a=a and a["ppg"]),
                self._cmp_row("Risultati (V-N-P)", h["wdl"] if h else dash, a["wdl"] if a else dash),
                self._cmp_row("Gol fatti/gara", _it2(h["gf_pg"]) if h else dash, _it2(a["gf_pg"]) if a else dash,
                              key_h=h and h["gf_pg"], key_a=a and a["gf_pg"]),
                self._cmp_row("Gol subiti/gara", _it2(h["ga_pg"]) if h else dash, _it2(a["ga_pg"]) if a else dash,
                              key_h=h and h["ga_pg"], key_a=a and a["ga_pg"], higher=False),
                self._cmp_row("Differenza reti", _signed_int(h["diff"]) if h else dash,
                              _signed_int(a["diff"]) if a else dash,
                              key_h=h and h["diff"], key_a=a and a["diff"]),
            ]
            avg = self._league_averages(home_st or away_st)
            if avg and avg["gf"] > 0 and avg["ga"] > 0:
                rows += [
                    self._cmp_row("Attacco (× media campionato)", _it2(h["gf_pg"] / avg["gf"]) if h else dash,
                                  _it2(a["gf_pg"] / avg["gf"]) if a else dash,
                                  key_h=h and h["gf_pg"] / avg["gf"], key_a=a and a["gf_pg"] / avg["gf"]),
                    self._cmp_row("Difesa (× media campionato)", _it2(h["ga_pg"] / avg["ga"]) if h else dash,
                                  _it2(a["ga_pg"] / avg["ga"]) if a else dash,
                                  key_h=h and h["ga_pg"] / avg["ga"], key_a=a and a["ga_pg"] / avg["ga"], higher=False),
                ]
                note = "Attacco e difesa rapportati alla media gol del campionato: attacco più alto e difesa più bassa è meglio."
            else:
                note = "Dalla classifica della stagione in corso."
            return {"rows": rows, "note": note}
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            return None

    # ---- assenze ------------------------------------------------------------------------------
    def unavailable(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "unavailable")]
        rows = rows.sort_values("market_value_eur", ascending=False, na_position="last")
        return [{"name": r.player_name, "type": _val(r._asdict(), "unavailability_type", "indisponibile"),
                 "ret": _return_it(_val(r._asdict(), "expected_return")), "value": _val(r._asdict(), "market_value_eur"),
                 "pos": POSITION_NAMES.get(int(r.usual_position_id) if pd.notna(r.usual_position_id) else 0, "")}
                for r in rows.itertuples(index=False)]

    def starters(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "starter")]
        return [{"name": r.player_name, "num": r.shirt_number, "rating": r.rating, "season_rating": r.season_rating,
                 "captain": bool(r.is_captain)} for r in rows.itertuples(index=False)]

    # ---- statistiche post-partita ----------------------------------------------------------------
    def key_stats(self, match_id: int, home_id: int, away_id: int) -> list[dict[str, Any]]:
        if self.team_stats.empty:
            return []
        ts = self.team_stats[(self.team_stats.match_id == match_id) & (self.team_stats.period == "All")]
        wanted = [("BallPossesion", "Possesso palla"), ("expected_goals", "xG"), ("expected_goals_on_target", "xGOT"),
                  ("total_shots", "Tiri"), ("ShotsOnTarget", "Tiri in porta"), ("big_chance", "Grandi occasioni"),
                  ("big_chance_missed_title", "Grandi occasioni fallite"), ("accurate_passes", "Passaggi riusciti"),
                  ("corners", "Calci d'angolo"), ("fouls", "Falli"), ("yellow_cards", "Ammonizioni"),
                  ("red_cards", "Espulsioni"), ("touches_opp_box", "Tocchi in area avversaria")]
        out = []
        for key, label in wanted:
            h = ts[(ts.team_id == home_id) & (ts.key == key)]
            a = ts[(ts.team_id == away_id) & (ts.key == key)]
            if not h.empty and not a.empty:
                out.append({"label": label, "home": h.iloc[0].text, "away": a.iloc[0].text})
        return out

    def timeline(self, match_id: int) -> list[dict[str, Any]]:
        if self.events.empty:
            return []
        ev = self.events[(self.events.match_id == match_id) & (self.events.type.isin(["Goal", "Card", "Substitution"]))]
        ev = ev.sort_values(["minute", "minute_added"], na_position="first")
        out = []
        for r in ev.itertuples(index=False):
            d = r._asdict()
            swap = _val(d, "swap")
            if isinstance(swap, str):
                try:
                    swap = ast.literal_eval(swap)
                except (ValueError, SyntaxError):
                    swap = None
            out.append({"type": r.type, "minute": _val(d, "minute"), "added": _val(d, "minute_added"),
                        "home": bool(_val(d, "is_home", False)), "player": _val(d, "player_name"),
                        "card": _val(d, "card"), "own_goal": bool(_val(d, "own_goal", False)),
                        "score": f"{_val(d, 'home_score', '')}-{_val(d, 'away_score', '')}" if r.type == "Goal" else None,
                        "swap_in": swap[0][1] if swap and len(swap) > 0 else None,
                        "swap_out": swap[1][1] if swap and len(swap) > 1 else None})
        return out

    def top_players(self, match_id: int, n: int = 3) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.role.isin(["starter", "sub"]))
                           & self.lineup.rating.notna()].sort_values("rating", ascending=False).head(n)
        return [{"name": r.player_name, "team_id": int(r.team_id), "rating": float(r.rating)} for r in rows.itertuples(index=False)]

    def shot_summary(self, match_id: int, team_id: int) -> dict[str, Any]:
        if self.shots.empty:
            return {}
        s = self.shots[(self.shots.match_id == match_id) & (self.shots.team_id == team_id)]
        if s.empty:
            return {}
        big = s[s.xg >= 0.3]
        return {"n": int(len(s)), "xg": float(s.xg.sum()), "on_target": int(s.is_on_target.fillna(False).sum()),
                "inside_box": int(s.is_inside_box.fillna(False).sum()), "big_chances": int(len(big)),
                "goals": int((s.event_type == "Goal").sum()),
                "best": _first(s.sort_values("xg", ascending=False)[["player_name", "xg", "minute", "event_type"]])}

    def shot_map(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        """Tiri di una squadra pronti per l'SVG: mezzo campo offensivo 105×68 m → 420×272 px (porta a destra)."""
        if self.shots.empty:
            return []
        s = self.shots[(self.shots.match_id == match_id) & (self.shots.team_id == team_id)].dropna(subset=["x", "y"])
        out = []
        for r in s.itertuples(index=False):
            xg = float(r.xg) if pd.notna(r.xg) else 0.0
            goal = r.event_type == "Goal"
            on_target = bool(r.is_on_target) if pd.notna(r.is_on_target) else False
            blocked = bool(r.is_blocked) if pd.notna(r.is_blocked) else False
            kind = "goal" if goal else "target" if on_target else "blocked" if blocked else "miss"
            out.append({"px": round(min(max((float(r.x) - 52.5) * 8.0, 4.0), 412.0), 1),
                        "py": round(min(max(float(r.y) * 4.0, 8.0), 264.0), 1),
                        "r": round(2.5 + 8.5 * xg ** 0.5, 1),
                        "xg": xg, "kind": kind, "player": r.player_name,
                        "minute": int(r.minute) if pd.notna(r.minute) else None})
        out.sort(key=lambda d: -d["xg"])  # i tiri più piccoli vengono disegnati sopra
        return out

    def momentum(self, match_id: int) -> dict[str, Any] | None:
        """Serie momentum per l'SVG: valore FotMob -100..100 (positivo = preme la squadra di casa)."""
        if self.momentum_df.empty:
            return None
        m = self.momentum_df[self.momentum_df.match_id == match_id].dropna(subset=["value"])
        if m.empty:
            return None
        m = m.sort_values("minute")
        pts = [{"minute": float(r.minute), "v": float(r.value)} for r in m.itertuples(index=False)]
        pos = sum(1 for p in pts if p["v"] > 0)
        return {"points": pts, "pos_share": pos / len(pts), "n": len(pts)}

    def _h2h_core(self, match_id: int, home_id: int, away_id: int, kickoff: pd.Timestamp,
                  n: int = 5) -> list[dict[str, Any]]:
        """Ultime n gare precedenti fra le due squadre, valide (squadre attuali, gol presenti)."""
        if self.h2h_df.empty:
            return []
        h = self.h2h_df[self.h2h_df.match_id == match_id].dropna(subset=["utc", "home_goals", "away_goals"])
        h = h[pd.to_datetime(h.utc, utc=True) < kickoff].sort_values("utc", ascending=False).head(n)
        out = []
        for r in h.itertuples(index=False):
            if int(r.home_id) not in (home_id, away_id) or int(r.away_id) not in (home_id, away_id):
                continue  # riga anomala (terza squadra): scartata
            out.append({"home_id": int(r.home_id), "away_id": int(r.away_id), "utc": pd.Timestamp(r.utc),
                        "hg": int(r.home_goals), "ag": int(r.away_goals), "league": r.league})
        return out

    def h2h_list(self, match_id: int, home_id: int, away_id: int, home_name: str, away_name: str,
                 kickoff: pd.Timestamp, n: int = 5) -> list[dict[str, Any]]:
        """Ultimi n precedenti fra le due squadre (solo gare giocate prima di questa)."""
        names = {home_id: home_name, away_id: away_name}
        out = []
        for r in self._h2h_core(match_id, home_id, away_id, kickoff, n):
            hg, ag = r["hg"], r["ag"]
            # esito dal punto di vista della squadra di casa ATTUALE (home_id del match in corso)
            if hg == ag:
                res = "N"
            else:
                # vittoria della casa attuale: se era in casa ha vinto chi ha più gol in casa,
                # se era in trasferta ha vinto chi ha più gol in trasferta
                cur_home_was_home = r["home_id"] == home_id
                res = "V" if (hg > ag) == cur_home_was_home else "P"
            out.append({"date": r["utc"].strftime("%d/%m/%Y"), "league": r["league"],
                        "home": names[r["home_id"]], "away": names[r["away_id"]],
                        "score": f"{hg}-{ag}", "res": res})
        return out

    def h2h_stats(self, match_id: int, home_id: int, away_id: int, kickoff: pd.Timestamp,
                  n: int = 5) -> dict[str, float] | None:
        """Sintesi sui precedenti mostrati: gol/gara e frequenza «entrambe a segno»."""
        rows = self._h2h_core(match_id, home_id, away_id, kickoff, n)
        if not rows:
            return None
        return {"n": len(rows),
                "gpg": sum(r["hg"] + r["ag"] for r in rows) / len(rows),
                "btts": sum(1 for r in rows if r["hg"] > 0 and r["ag"] > 0) / len(rows)}

    # ---- previsione ---------------------------------------------------------------------------------
    def prediction(self, match_id: int) -> dict[str, Any] | None:
        if self.preds.empty:
            return None
        p = self.preds[self.preds.match_id == match_id].sort_values("made_at").tail(1)
        if p.empty:
            return None
        d = p.iloc[0].to_dict()
        top = d.get("top_scores")
        if isinstance(top, str):
            try:
                top = ast.literal_eval(top)
            except (ValueError, SyntaxError):
                top = {}
        d["top_scores"] = top or {}
        return d

    # ---- testo analitico ----------------------------------------------------------------------------
    @staticmethod
    def narrative(ctx: dict[str, Any]) -> list[str]:
        """Frasi in italiano derivate dai numeri (regole esplicite)."""
        s: list[str] = []
        h, a = ctx["home_name"], ctx["away_name"]
        p = ctx.get("prediction")
        if p:
            fav = h if p["p_home"] >= p["p_away"] else a
            pf = max(p["p_home"], p["p_away"])
            if pf >= 0.60:
                s.append(f"Il modello vede {fav} nettamente favorito ({_pct(pf)}).")
            elif pf >= 0.45:
                s.append(f"Il modello indica {fav} favorito ({_pct(pf)}), ma con margine contenuto.")
            else:
                s.append(f"Partita equilibrata secondo il modello: {h} {_pct(p['p_home'])}, pareggio "
                         f"{_pct(p['p_draw'])}, {a} {_pct(p['p_away'])}.")
            tot = p["lambda_home"] + p["lambda_away"]
            if tot >= 3.0:
                s.append(f"Attesa una gara aperta: {_f(tot)} gol attesi complessivi, Over 2,5 al {_pct(p['p_over25'])}.")
            elif tot <= 2.2:
                s.append(f"Gara da pochi gol: {_f(tot)} gol attesi complessivi, Under 2,5 al {_pct(1 - p['p_over25'])}.")
            if p.get("p_btts") is not None and p["p_btts"] >= 0.58:
                s.append(f"Entrambe a segno probabile ({_pct(p['p_btts'])}).")
        for side, name in (("home", h), ("away", a)):
            f = ctx.get(f"{side}_form") or []
            if len(f) >= 3:
                pts = sum(3 if x["res"] == "V" else 1 if x["res"] == "N" else 0 for x in f)
                seq = "".join(x["res"] for x in f)
                if pts >= 2.4 * len(f):
                    s.append(f"{name} arriva in grande forma: {seq} nelle ultime {len(f)} ({pts} punti).")
                elif pts <= 0.6 * len(f):
                    s.append(f"{name} in difficoltà: {seq} nelle ultime {len(f)} ({pts} punti).")
            xg = ctx.get(f"{side}_xg")
            if xg and xg.get("xpts") is not None and xg.get("pts") is not None and xg["played"] >= 4:
                diff = xg["pts"] - xg["xpts"]
                if diff >= 3:
                    s.append(f"{name} ha raccolto {diff:+.1f} punti rispetto agli xPTS: rendimento sopra la qualità "
                             f"del gioco prodotto, possibile regressione.")
                elif diff <= -3:
                    s.append(f"{name} ha {diff:+.1f} punti rispetto agli xPTS: sta rendendo meno di quanto crea, "
                             f"segnale di sottovalutazione.")
            un = ctx.get(f"{side}_unavailable") or []
            if un:
                heavy = [u for u in un if u.get("value") and u["value"] >= 15_000_000]
                names = ", ".join(u["name"] for u in un[:4])
                extra = (" (tra cui 1 giocatore di peso)" if len(heavy) == 1
                         else f" (tra cui {len(heavy)} giocatori di peso)") if heavy else ""
                s.append(f"Assenze {name}: {len(un)}{extra} — {names}{'…' if len(un) > 4 else ''}.")
            rest = ctx.get(f"{side}_rest")
            if rest is not None and rest <= 3:
                s.append(f"{name} gioca dopo soli {rest} giorni di riposo.")
        ref = ctx.get("referee")
        if ref and ref.get("name"):
            y = ref.get("yellows")
            if y is not None:
                tone = "molto severo" if y >= 5 else "severo" if y >= 4.2 else "permissivo" if y <= 3.2 else "nella media"
                s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita ({tone})"
                         + (f", {int(ref['pens'])} rigori in {int(ref['matches'])} gare." if ref.get("pens") is not None else "."))
        w = ctx.get("weather")
        if w and w.get("desc"):
            extra = ""
            if w.get("precip") is not None and w["precip"] >= 50:
                extra = " — pioggia probabile, campo pesante"
            elif w.get("temp") is not None and w["temp"] >= 30:
                extra = " — caldo intenso, ritmi più bassi nel finale"
            s.append(f"Meteo previsto: {w['desc']}, {_f(w.get('temp'), 0)}°C{extra}.")
        if ctx.get("status") == "finished":
            hx, ax = ctx.get("home_xg_match"), ctx.get("away_xg_match")
            hg, ag = ctx.get("home_goals"), ctx.get("away_goals")
            if hx is not None and ax is not None and hg is not None and ag is not None:
                exp_w = h if hx > ax + 0.5 else a if ax > hx + 0.5 else None
                real_w = h if hg > ag else a if ag > hg else None
                if exp_w and real_w and exp_w != real_w:
                    s.append(f"Risultato contro il flusso di gioco: xG {_f(hx)}-{_f(ax)} a favore di {exp_w}, "
                             f"ma ha vinto {real_w}.")
                elif exp_w is None and real_w:
                    s.append(f"Gara equilibrata negli xG ({_f(hx)}-{_f(ax)}): {real_w} ha fatto la differenza nei dettagli.")
                else:
                    s.append(f"Risultato coerente con gli xG ({_f(hx)}-{_f(ax)}).")
            if p and hg is not None and ag is not None:
                ph = p["p_home"] if hg > ag else p["p_draw"] if hg == ag else p["p_away"]
                s.append(f"Il modello assegnava {_pct(ph)} all'esito verificatosi"
                         + (" (esito atteso)." if ph >= 0.4 else " (sorpresa)." if ph < 0.25 else "."))
            mom = ctx.get("momentum")
            if mom and mom["n"] >= 10:
                if mom["pos_share"] >= 0.60:
                    s.append(f"Momentum quasi sempre dalla parte di {h}: "
                             f"pressione a proprio favore nel {_pct(mom['pos_share'])} dei minuti.")
                elif mom["pos_share"] <= 0.40:
                    s.append(f"Momentum quasi sempre dalla parte di {a}: "
                             f"pressione a proprio favore nel {_pct(1 - mom['pos_share'])} dei minuti.")
        return s

    # ---- contesto completo ----------------------------------------------------------------------------
    def build(self, match_id: int) -> dict[str, Any] | None:
        fx = self.fixtures[self.fixtures.match_id == match_id] if not self.fixtures.empty else pd.DataFrame()
        if fx.empty:
            return None
        f = fx.iloc[0].to_dict()
        info = _first(self.info[self.info.match_id == match_id]) if not self.info.empty else {}
        kickoff = pd.Timestamp(f["utc_kickoff"])
        home_id, away_id = int(f["home_id"]), int(f["away_id"])
        status = _val(info, "status") or f["status"]
        ctx: dict[str, Any] = {
            "match_id": match_id, "league_id": int(f["league_id"]), "round": _val(f, "round"),
            "utc_kickoff": kickoff, "status": status,
            "home_id": home_id, "away_id": away_id,
            "home_name": f["home_name"], "away_name": f["away_name"],
            "home_goals": _goals(info, "home_goals", f), "away_goals": _goals(info, "away_goals", f),
            "home_form": self.form(home_id, kickoff), "away_form": self.form(away_id, kickoff),
            "home_rest": self.rest_days(home_id, kickoff), "away_rest": self.rest_days(away_id, kickoff),
            "home_xg": self.season_xg(f["home_name"], home_id), "away_xg": self.season_xg(f["away_name"], away_id),
            "home_standing": self.standing(f["home_name"]), "away_standing": self.standing(f["away_name"]),
            "season_compare": self.season_compare(self.standing(f["home_name"]), self.standing(f["away_name"])),
            "home_unavailable": self.unavailable(match_id, home_id), "away_unavailable": self.unavailable(match_id, away_id),
            "home_starters": self.starters(match_id, home_id), "away_starters": self.starters(match_id, away_id),
            "lineup_type": _val(info, "lineup_type"),
            "home_formation": _val(info, "home_formation"), "away_formation": _val(info, "away_formation"),
            "home_value": _val(info, "home_starters_value_eur"), "away_value": _val(info, "away_starters_value_eur"),
            "referee": {"name": _val(info, "referee_name"), "matches": _val(info, "referee_matches"),
                        "yellows": _val(info, "referee_yellows_per_match"), "pens": _val(info, "referee_penalties_total"),
                        "reds": _val(info, "referee_reds_total")},
            "stadium": {"name": _val(info, "stadium_name"), "city": _val(info, "stadium_city"),
                        "attendance": _val(info, "attendance")},
            "weather": {"desc": _weather_it(_val(info, "weather_desc")), "temp": _val(info, "weather_temp_c"),
                        "precip": _val(info, "weather_precip_chance")},
            "h2h": (_val(info, "h2h_home_wins"), _val(info, "h2h_draws"), _val(info, "h2h_away_wins")),
            "h2h_list": self.h2h_list(match_id, home_id, away_id, f["home_name"], f["away_name"], kickoff),
            "h2h_stats": self.h2h_stats(match_id, home_id, away_id, kickoff),
            "momentum": self.momentum(match_id) if status == "finished" else None,
            "prediction": self.prediction(match_id),
            "home_xg_match": _val(info, "home_xg"), "away_xg_match": _val(info, "away_xg"),
            "home_xgot_match": _val(info, "home_xgot"), "away_xgot_match": _val(info, "away_xgot"),
            "key_stats": self.key_stats(match_id, home_id, away_id) if status == "finished" else [],
            "timeline": self.timeline(match_id) if status == "finished" else [],
            "top_players": self.top_players(match_id) if status == "finished" else [],
            "home_shots": self.shot_summary(match_id, home_id) if status == "finished" else {},
            "away_shots": self.shot_summary(match_id, away_id) if status == "finished" else {},
            "home_shotmap": self.shot_map(match_id, home_id) if status == "finished" else [],
            "away_shotmap": self.shot_map(match_id, away_id) if status == "finished" else [],
            "generated_at": datetime.now(timezone.utc),
        }
        ctx["narrative"] = self.narrative(ctx)
        return ctx
