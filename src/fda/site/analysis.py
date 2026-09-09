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

import numpy as np
import pandas as pd
from scipy.stats import poisson

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


# Fatti FotMob (`insights`): testi inglesi a template. Si traducono SOLO i pattern
# oggettivi (streak, gol recenti, testa-a-testa, capocannoniere). Qualsiasi altra
# frase — hype («most shots on target»), marketing, o forma sconosciuta — viene
# scartata: sul sito non compare mai un testo non tradotto.
_INSIGHT_EN_LEAK = re.compile(
    r"\b(haven't|have scored|have (won|lost|kept|been|conceded)|clean sheet|"
    r"their last|matches|meetings|attempts|competition|ranked|average)\b",
    re.I,
)


def _n_partite(n: int) -> str:
    return "1 partita" if n == 1 else f"{n} partite"


def _n_incontri(n: int) -> str:
    return "1 incontro" if n == 1 else f"{n} incontri"


def _n_confronti(n: int) -> str:
    return "1 confronto" if n == 1 else f"{n} confronti"


def translate_insight(text: str) -> dict[str, Any] | None:
    """Traduce un fatto FotMob. ``None`` = non mostrare (niente inglese a schermo).

    Il testo restituito è il predicato (minuscolo): il template antepone la squadra.
    """
    if not isinstance(text, str):
        return None
    t = text.strip()
    if not t:
        return None

    m = re.fullmatch(r"Have scored (\d+) goals in their last (\d+) matches", t)
    if m:
        n, k = int(m.group(1)), int(m.group(2))
        if k == 1:
            body = f"ha segnato {n} gol nell'ultima partita"
        else:
            body = f"ha segnato {n} gol nelle ultime {k} partite"
        return {"text": body, "kind": "goals", "priority": 80}

    m = re.fullmatch(r"Haven't scored in their last (\d+) matches", t)
    if m:
        n = int(m.group(1))
        return {"text": f"non segna da {_n_partite(n)}", "kind": "goals", "priority": 82}

    m = re.fullmatch(r"Haven't lost in (\d+) matches", t)
    if m:
        n = int(m.group(1))
        return {"text": f"imbattuta da {_n_partite(n)}", "kind": "streak", "priority": 90}

    m = re.fullmatch(r"Haven't won a match in (\d+) attempts", t)
    if m:
        n = int(m.group(1))
        return {"text": f"non vince da {_n_partite(n)}", "kind": "streak", "priority": 88}

    m = re.fullmatch(r"Have lost their last (\d+) matches", t)
    if m:
        n = int(m.group(1))
        if n == 1:
            body = "ha perso l'ultima partita"
        else:
            body = f"ha perso le ultime {n} partite"
        return {"text": body, "kind": "streak", "priority": 89}

    m = re.fullmatch(r"Have won their last (\d+) matches", t)
    if m:
        n = int(m.group(1))
        if n == 1:
            body = "ha vinto l'ultima partita"
        else:
            body = f"ha vinto le ultime {n} partite"
        return {"text": body, "kind": "streak", "priority": 91}

    m = re.fullmatch(r"Haven't kept a clean sheet in (\d+) matches", t)
    if m:
        n = int(m.group(1))
        return {"text": f"non tiene la porta inviolata da {_n_partite(n)}",
                "kind": "clean_sheet", "priority": 70}

    m = re.fullmatch(
        r"(.+) haven't lost to (.+) in their last (\d+) meetings \((\d+)W, (\d+)D\)\.", t)
    if m:
        opp, n, w, d = m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5))
        return {"text": f"non perde contro {opp} da {_n_incontri(n)} ({w}V, {d}N)",
                "kind": "h2h", "priority": 100}

    m = re.fullmatch(r"(.+) have won the previous (\d+) matches against (.+)\.", t)
    if m:
        n, opp = int(m.group(2)), m.group(3)
        if n == 1:
            body = f"ha vinto la precedente partita contro {opp}"
        else:
            body = f"ha vinto le precedenti {n} partite contro {opp}"
        return {"text": body, "kind": "h2h", "priority": 98}

    m = re.fullmatch(
        r"(.+) and (.+) have not drawn any of their last (\d+) matches against each other\.", t)
    if m:
        n = int(m.group(3))
        return {"text": f"nessun pareggio negli ultimi {_n_confronti(n)} diretti",
                "kind": "h2h", "priority": 92}

    m = re.fullmatch(
        r"(.+) and (.+) have drawn their last (\d+) matches against each other\.", t)
    if m:
        n = int(m.group(3))
        if n == 1:
            body = "ha pareggiato l'ultimo confronto diretto"
        else:
            body = f"ha pareggiato gli ultimi {n} confronti diretti"
        return {"text": body, "kind": "h2h", "priority": 93}

    m = re.fullmatch(r"(.+) is the competition's top scorer \((\d+)\)", t)
    if m:
        name, n = m.group(1).strip(), int(m.group(2))
        if not name:
            return None
        return {"text": f"{name} è il capocannoniere del campionato ({n} gol)",
                "kind": "scorer", "priority": 55}

    return None


def select_insights(rows: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    """Sceglie al più ``n`` fatti: priorità alta, al più uno per (kind, squadra)."""
    ranked = sorted(rows, key=lambda r: (-int(r["priority"]), r["team"], r["text"]))
    picked: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for r in ranked:
        key = (str(r["kind"]), int(r["team_id"]))
        if key in seen:
            continue
        seen.add(key)
        picked.append(r)
        if len(picked) >= n:
            break
    return picked


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
        self.player_stats = store.read("player_stats")
        self.shots = store.read("shots")
        self.events = store.read("events")
        self.preds = store.read("predictions")
        self.us_team = store.read("understat_team_matches")
        self.fm_standings = store.read("fotmob_standings")
        self.standings = store.read("espn_standings")
        self.momentum_df = store.read("momentum")
        self.h2h_df = store.read("h2h")
        self.insights_df = store.read("insights")
        self.weather_forecast = store.read("weather_forecast")

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
    @staticmethod
    def _poisson_xpts(lh: float, la: float) -> tuple[float, float]:
        """xPTS attesi di una partita dai soli xG (Poisson indipendente): (xPTS casa, trasferta).

        Probabilità P(vittoria casa), P(pareggio), P(vittoria trasferta) dalle λ = xG delle due
        squadre; xPTS = 3×P(vittoria) + P(pareggio). La coda oltre λ+12 gol è trascurabile.
        """
        g = np.arange(int(max(lh, la)) + 13)                 # gol possibili: 0..λ+12
        pa = poisson.pmf(g, la)                             # gol della squadra in trasferta
        p_draw = float((poisson.pmf(g, lh) * pa).sum())
        p_home = float((poisson.sf(g, lh) * pa).sum())      # la casa segna più di k
        p_away = float((poisson.cdf(g - 1, lh) * pa).sum()) # gol casa < k (cdf(-1) = 0)
        return 3 * p_home + p_draw, 3 * p_away + p_draw

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
                xpts = pts = None
                # xPTS e punti reali solo dalle partite finite con xG completo (entrambe le λ);
                # senza i gol reali la riga xPTS resta assente (None) come prima.
                if {"home_goals", "away_goals"} <= set(self.info.columns):
                    ok = fin[(fin.home_id == team_id) | (fin.away_id == team_id)]
                    ok = ok.dropna(subset=["home_xg", "away_xg", "home_goals", "away_goals"])
                    if not ok.empty:
                        xpts_total = pts_total = 0
                        for r in ok.itertuples(index=False):
                            xh, xa = self._poisson_xpts(float(r.home_xg), float(r.away_xg))
                            team_home = int(r.home_id) == team_id
                            xpts_total += xh if team_home else xa
                            hg, ag = int(r.home_goals), int(r.away_goals)
                            signed = hg - ag if team_home else ag - hg
                            pts_total += 3 if signed > 0 else 1 if signed == 0 else 0
                        xpts, pts = round(xpts_total, 1), int(pts_total)
                return {"source": "FotMob", "played": int(len(xg)), "xg": xg.sum(),
                        "xga": xga.sum(), "xg_pm": xg.mean(), "xga_pm": xga.mean(),
                        "xpts": xpts, "pts": pts, "ppda": None}
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
        # FotMob elenca a volte lo stesso giocatore sia come titolare sia come
        # indisponibile: lo escludiamo dai titolari per non contraddire l'infermeria.
        unav = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "unavailable")]
        unav_ids = set(unav.player_id.dropna())
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "starter")
                           & (~self.lineup.player_id.isin(unav_ids))]
        out = []
        for r in rows.itertuples(index=False):
            rating = r.rating if not pd.isna(r.rating) else None
            season_rating = r.season_rating if not pd.isna(r.season_rating) else None
            num = r.shirt_number if not pd.isna(r.shirt_number) else None
            out.append({"name": r.player_name, "num": num, "rating": rating,
                        "season_rating": season_rating, "captain": bool(r.is_captain)})
        return out

    def team_key_players(self, team_id: int, n: int = 3) -> list[dict[str, Any]]:
        """Giocatori da tenere d'occhio di una squadra (card pre-partita).

        Top ``n`` per rating di stagione (FotMob ``season_rating``, media stagionale
        del ruolo), deduplicati per ``player_id``; arricchiti con gol/assist stagionali
        sommati dalle statistiche partita (``player_stats``, una riga per partita/giocatore/
        chiave: nessun doppione) e con la posizione. Nessun dato inventato: solo giocatori
        con ``season_rating`` disponibile; se manca la lista resta vuota.
        """
        if self.lineup.empty:
            return []
        # Una riga per giocatore: prendi il season_rating più recente/rappresentativo.
        rows = self.lineup[(self.lineup.team_id == team_id)
                           & (self.lineup.role.isin(["starter", "sub"]))
                           & self.lineup.season_rating.notna()]
        if rows.empty:
            return []
        rows = rows.sort_values("season_rating").drop_duplicates(subset=["player_id"], keep="last")
        # Statistiche di stagione per giocatore (gol/assist) su TUTTE le partite della squadra.
        season_stats: dict[tuple[int, str], float] = {}
        if not self.player_stats.empty:
            team_matches = None
            if not self.fixtures.empty:
                team_matches = set(self.fixtures[self.fixtures.home_id == team_id].match_id) \
                    | set(self.fixtures[self.fixtures.away_id == team_id].match_id)
            ps = self.player_stats if team_matches is None else \
                self.player_stats[self.player_stats.match_id.isin(team_matches)]
            for row in ps.itertuples(index=False):
                if int(row.team_id) != team_id:
                    continue
                v = row.value
                if v is None or pd.isna(v):
                    continue
                k = (int(row.player_id), str(row.key))
                season_stats[k] = season_stats.get(k, 0.0) + float(v)

        def _season_num(player_id: int, key: str) -> float:
            v = season_stats.get((player_id, key))
            return float(v) if v is not None and pd.notna(v) else 0.0

        out = []
        for r in rows.itertuples(index=False):
            out.append({
                "name": r.player_name,
                "pos": POSITION_NAMES.get(int(r.position_id) if pd.notna(r.position_id) else 0, ""),
                "season_rating": float(r.season_rating),
                "goals": int(_season_num(int(r.player_id), "goals")),
                "assists": int(_season_num(int(r.player_id), "assists")),
            })
        return sorted(out, key=lambda p: p["season_rating"], reverse=True)[:n]


    def _weather(self, match_id: int, desc: Any, temp: Any, precip: Any) -> dict[str, Any]:
        """Meteo della gara: FotMob primario, Open-Meteo (previsionale) come fallback."""
        if desc:
            return {"desc": _weather_it(desc), "temp": temp, "precip": precip, "source": "FotMob"}
        if not self.weather_forecast.empty:
            row = self.weather_forecast[self.weather_forecast.match_id == match_id]
            if not row.empty:
                d = row.iloc[0].to_dict()
                return {"desc": _val(d, "desc"), "temp": _val(d, "temp_c"),
                        "precip": _val(d, "precip_prob"), "source": "Open-Meteo"}
        return {"desc": None, "temp": None, "precip": None, "source": None}

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
            added = _val(d, "minute_added")
            out.append({"type": r.type, "minute": _val(d, "minute"), "added": int(added) if added is not None else None,
                        "home": bool(_val(d, "is_home", False)), "player": _val(d, "player_name"),
                        "card": _val(d, "card"), "own_goal": bool(_val(d, "own_goal", False)),
                        "score": f"{_val(d, 'home_score', '')}-{_val(d, 'away_score', '')}" if r.type == "Goal" else None,
                        "swap_in": swap[0][1] if swap and len(swap) > 0 else None,
                        "swap_out": swap[1][1] if swap and len(swap) > 1 else None})
        return out

    def top_players(self, match_id: int, home_id: int, away_id: int,
                    n: int = 3) -> dict[str, list[dict[str, Any]]]:
        """Top giocatori per squadra (rating partita FotMob) con gol, assist e minuti della gara.

        Restituisce ``{"home": [...], "away": [...]}``: per ciascuna squadra i migliori ``n``
        titolari/subentrati per rating, arricchiti con gol/assist/minuti dalle statistiche
        partita (``player_stats``). I giocatori non scesi in campo (ruolo diverso da
        starter/sub) sono esclusi; se il rating manca la lista resta vuota (nessun dato inventato).
        """
        out: dict[str, list[dict[str, Any]]] = {"home": [], "away": []}
        if self.lineup.empty:
            return out
        rated = self.lineup[(self.lineup.match_id == match_id)
                            & (self.lineup.role.isin(["starter", "sub"]))
                            & self.lineup.rating.notna()]
        if rated.empty:
            return out

        stat_of: dict[tuple[int, str], float] = {}
        if not self.player_stats.empty:
            ps = self.player_stats[self.player_stats.match_id == match_id]
            for row in ps.itertuples(index=False):
                stat_of[(int(row.player_id), str(row.key))] = row.value

        def _num(player_id: int, key: str) -> float | None:
            v = stat_of.get((player_id, key))
            return float(v) if v is not None and pd.notna(v) else None

        def _rows(team_id: int) -> list[dict[str, Any]]:
            sel = rated[rated.team_id == team_id].sort_values("rating", ascending=False).head(n)
            players = []
            for r in sel.itertuples(index=False):
                minutes = _num(int(r.player_id), "minutes_played")
                players.append({
                    "name": r.player_name,
                    "rating": float(r.rating),
                    "goals": int(_num(int(r.player_id), "goals") or 0),
                    "assists": int(_num(int(r.player_id), "assists") or 0),
                    "minutes": int(minutes) if minutes is not None else None,
                    "season_rating": float(r.season_rating) if pd.notna(r.season_rating) else None,
                })
            return players

        out["home"] = _rows(home_id)
        out["away"] = _rows(away_id)
        return out

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

    def match_insights(self, match_id: int, home_id: int, away_id: int,
                       home_name: str, away_name: str, n: int = 3) -> list[dict[str, Any]]:
        """Fatti pre-partita: tradotti, filtrati, al più ``n``, mai in inglese.

        Fonte: tabella ``insights`` (FotMob ``matchFacts.insights``). Si tengono
        solo streak / gol recenti / testa-a-testa / capocannoniere. I testi non
        traducibili e i fatti «hype» (most X in the competition) sono scartati.
        """
        if self.insights_df.empty or "text" not in self.insights_df.columns:
            return []
        rows = self.insights_df[self.insights_df.match_id == match_id]
        if rows.empty:
            return []
        names = {int(home_id): home_name, int(away_id): away_name}
        out: list[dict[str, Any]] = []
        seen_text: set[str] = set()
        for r in rows.itertuples(index=False):
            d = r._asdict()
            tid = _val(d, "team_id")
            if tid is None or pd.isna(tid):
                continue
            try:
                team_id = int(tid)
            except (TypeError, ValueError):
                continue
            if team_id not in names:
                continue
            raw = _val(d, "text")
            tr = translate_insight(raw if isinstance(raw, str) else "")
            if not tr:
                continue
            body = tr["text"]
            if _INSIGHT_EN_LEAK.search(body):
                continue  # rete di sicurezza: mai inglese a schermo
            if body in seen_text:
                continue
            seen_text.add(body)
            out.append({"team": names[team_id], "team_id": team_id,
                        "side": "home" if team_id == home_id else "away",
                        "text": body, "kind": tr["kind"], "priority": tr["priority"]})
        return select_insights(out, n=n)

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
            "home_key_players": self.team_key_players(home_id),
            "away_key_players": self.team_key_players(away_id),
            "insights": (self.match_insights(match_id, home_id, away_id,
                                             f["home_name"], f["away_name"])
                         if status != "finished" else []),
            "lineup_type": _val(info, "lineup_type"),
            "home_formation": _val(info, "home_formation"), "away_formation": _val(info, "away_formation"),
            "home_value": _val(info, "home_starters_value_eur"), "away_value": _val(info, "away_starters_value_eur"),
            "referee": {"name": _val(info, "referee_name"), "matches": _val(info, "referee_matches"),
                        "yellows": _val(info, "referee_yellows_per_match"), "pens": _val(info, "referee_penalties_total"),
                        "reds": _val(info, "referee_reds_total")},
            "stadium": {"name": _val(info, "stadium_name"), "city": _val(info, "stadium_city"),
                        "attendance": _val(info, "attendance")},
            "weather": self._weather(match_id, _val(info, "weather_desc"),
                                     _val(info, "weather_temp_c"), _val(info, "weather_precip_chance")),
            "h2h": (_val(info, "h2h_home_wins"), _val(info, "h2h_draws"), _val(info, "h2h_away_wins")),
            "h2h_list": self.h2h_list(match_id, home_id, away_id, f["home_name"], f["away_name"], kickoff),
            "h2h_stats": self.h2h_stats(match_id, home_id, away_id, kickoff),
            "momentum": self.momentum(match_id) if status == "finished" else None,
            "prediction": self.prediction(match_id),
            "home_xg_match": _val(info, "home_xg"), "away_xg_match": _val(info, "away_xg"),
            "home_xgot_match": _val(info, "home_xgot"), "away_xgot_match": _val(info, "away_xgot"),
            "key_stats": self.key_stats(match_id, home_id, away_id) if status == "finished" else [],
            "timeline": self.timeline(match_id) if status == "finished" else [],
            "top_players": self.top_players(match_id, home_id, away_id) if status == "finished"
                           else {"home": [], "away": []},
            "home_shots": self.shot_summary(match_id, home_id) if status == "finished" else {},
            "away_shots": self.shot_summary(match_id, away_id) if status == "finished" else {},
            "home_shotmap": self.shot_map(match_id, home_id) if status == "finished" else [],
            "away_shotmap": self.shot_map(match_id, away_id) if status == "finished" else [],
            "generated_at": datetime.now(timezone.utc),
        }
        ctx["narrative"] = self.narrative(ctx)
        return ctx
