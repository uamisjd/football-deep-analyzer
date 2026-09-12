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
from .advanced import score_matrix, shot_quality, style_rows, wp_path, xg_race
from .fmt import dec, it_plural

# Ruolo di FotMob ``usualPosition``: la codifica parte da **0**, non da 1. Verificato su
# 616 formazioni: il valore 0 compare 632 volte (1,03 a formazione) ed è il portiere in
# 600 formazioni su 600 che lo contengono — es. Lazio 12/09, Mandas (n. 35) = 0, Doekhi e
# Provstgaard = 1, Frattesi = 2, Zaccagni = 3. Con la vecchia mappa 1→portiere ogni riga
# della distinta era spostata di un ruolo e il portiere restava senza etichetta.
POSITION_NAMES = {0: "portiere", 1: "difensore", 2: "centrocampista", 3: "attaccante"}
# ``positionId`` tattico di FotMob (11, 34, 64, 115…) → ruolo. Tenuti solo gli id che su
# almeno 20 titolari concordano col ruolo nel 90% dei casi (misurato sull'archivio):
# 11 portiere (632/632), 33-38 difensori, 64-77 centrocampisti, 105/106/115 attaccanti.
POSITION_ID_ROLE = {11: 0, 33: 1, 34: 1, 35: 1, 36: 1, 37: 1, 38: 1, 64: 2, 66: 2, 73: 2,
                    74: 2, 75: 2, 76: 2, 77: 2, 105: 3, 106: 3, 115: 3}

# Competizioni FotMob nei precedenti (h2h) → italiano. I nomi propri restano tali (LaLiga,
# Bundesliga, KNVB Cup, DFB Pokal, Community Shield…): la stampa italiana li usa così.
# Si traducono le diciture inglesi e i suffissi ricorrenti.
_COMPETITION_IT = {
    "Club Friendlies": "Amichevoli per club",
    "League Cup": "Coppa di Lega",
    "EFL Cup": "Coppa di Lega (EFL)",
    "Super Cup": "Supercoppa",
    "Supercup": "Supercoppa",
    "German Super Cup": "Supercoppa di Germania",
    "UEFA Super Cup": "Supercoppa UEFA",
    "Ligue 1 Qualification": "spareggio Ligue 1",
    "Champions Cup": "Coppa dei Campioni",
    "Cup": "Coppa",
}
# le frasi prima delle parole singole: "Serie B Promotion Playoff" → "Serie B playoff promozione"
_COMPETITION_SUFFIX_IT = (("Promotion Playoff", "playoff promozione"), ("2nd stage", "seconda fase"),
                          ("Grp.", "girone"), ("Playoff", "playoff"))


def _competition_it(name: Any) -> str:
    """Nome della competizione in italiano; ciò che non è traducibile resta com'è."""
    if not isinstance(name, str) or not name.strip():
        return ""
    s = name.strip().replace("\xa0", " ")
    for en in sorted(_COMPETITION_IT, key=len, reverse=True):
        if s == en:
            return _COMPETITION_IT[en]
        if s.startswith(en + " "):
            s = _COMPETITION_IT[en] + s[len(en):]
            break
    for en, it in _COMPETITION_SUFFIX_IT:
        s = re.sub(rf"\b{re.escape(en)}", it, s)   # solo bordo iniziale: "Grp." finisce con un punto
    return s
XI_SIZE = 11   # giocatori in campo per squadra: oltre questa soglia il dato è ambiguo


def _pct(p: float | None) -> str:
    return "—" if p is None or pd.isna(p) else f"{p * 100:.0f}%"


def _f(x: Any, nd: int = 2) -> str:
    """Numero per il testo narrativo: virgola decimale italiana ('3,12'; '—' se manca)."""
    return "—" if x is None or pd.isna(x) else f"{float(x):.{nd}f}".replace(".", ",")


_DECIMAL_TEXT = re.compile(r"^\d+\.\d+$")


def _stat_text_it(text: Any) -> str:
    """Testo di una statistica FotMob → italiano (virgola decimale).

    FotMob pubblica gli xG come ``"1.69"``: il sito è in italiano, quindi i valori
    decimali puri diventano ``"1,69"``. Le stringhe composite (``"330 (83%)"``) e gli
    interi restano invariati.
    """
    if not isinstance(text, str):
        return "" if text is None or pd.isna(text) else str(text)
    t = text.strip()
    return t.replace(".", ",") if _DECIMAL_TEXT.match(t) else t


def _first(df: pd.DataFrame) -> dict[str, Any]:
    return {} if df.empty else df.iloc[0].to_dict()


def _goals(info: dict, key: str, fixture: dict) -> int | None:
    v = _val(info, key)
    if v is None:
        v = _val(fixture, key)
    return None if v is None else int(v)


def _on_target(s: pd.DataFrame) -> pd.Series:
    """Maschera «tiro in porta» a partire dalla lista tiri FotMob.

    Due correzioni rispetto al campo grezzo ``isOnTarget``, misurate su 478
    squadre-partita contro la statistica ufficiale ``ShotsOnTarget``:
    - FotMob mette ``isOnTarget=True`` anche sui tiri **bloccati** (1688 delle 1858 righe
      con ``isOnTarget`` lo sono): un tiro è in porta se l'esito è gol o parata **e** non
      è bloccato (Angers–Rennes 11/09: 15 «in porta» grezzi contro i 3 ufficiali);
    - gli **autogol** non contano come tiro in porta della squadra del giocatore.
    Con entrambe le regole: 476/478 (99,6%) di concordanza, contro 453/478 (94,8%) della
    sola prima regola.
    """
    return (s.event_type.isin(["Goal", "AttemptSaved"])
            & ~s.is_blocked.fillna(False) & ~s.is_own_goal.fillna(False))


def _val(d: dict, key: str, default=None):
    v = d.get(key, default)
    return default if v is None or (isinstance(v, float) and pd.isna(v)) else v


# FotMob fornisce le condizioni meteo in inglese: mappa minima per il sito in italiano
_WEATHER_IT = {
    "sunny": "soleggiato", "clear": "sereno", "clear sky": "cielo sereno",
    "mostly clear": "per lo più sereno", "mainly clear": "per lo più sereno", "fair": "bel tempo",
    "mostly sunny": "per lo più soleggiato",
    "partly cloudy": "parzialmente nuvoloso", "mostly cloudy": "per lo più nuvoloso",
    "few clouds": "poche nuvole", "scattered clouds": "nuvole sparse", "broken clouds": "nuvolosità variabile",
    "cloudy": "nuvoloso", "overcast": "coperto", "rain": "pioggia", "light rain": "pioggia debole",
    "moderate rain": "pioggia moderata", "heavy rain": "pioggia intensa",
    "drizzle": "pioggia leggera", "light drizzle": "pioggia leggera",
    "showers": "rovesci", "few showers": "qualche rovescio", "scattered showers": "rovesci sparsi",
    "rain shower": "rovescio di pioggia", "rain showers": "rovesci di pioggia",
    "light rain shower": "rovescio debole", "heavy rain shower": "rovescio intenso",
    "showers in the vicinity": "rovesci nelle vicinanze",
    "patchy rain nearby": "pioggia a tratti nelle vicinanze",
    "thunderstorm": "temporale", "thunderstorms": "temporali",
    "scattered thunderstorms": "temporali sparsi", "isolated thunderstorms": "temporali isolati",
    "thunder in the vicinity": "temporali nelle vicinanze",
    "light rain with thunder": "pioggia debole con temporali",
    "rain with thunder": "pioggia con temporali", "thunder with rain": "temporali con pioggia",
    "snow": "neve", "light snow": "neve debole", "heavy snow": "neve abbondante", "sleet": "nevischio",
    "fog": "nebbia", "foggy": "nebbioso", "mist": "foschia", "haze": "foschia",
    "windy": "ventoso", "wind": "ventoso",
}


def _weather_it(desc: str | None) -> str | None:
    """Descrizione meteo FotMob/Open-Meteo → italiano.

    Oltre alla mappa: varianti combinate con «/» o «with» (tradotte pezzo per pezzo) e
    singolare/plurale («Rain Shower»/«Rain Showers»). Se un testo resta sconosciuto viene
    mostrato com'è, mai tradotto a metà o inventato.
    """
    if not isinstance(desc, str) or not desc.strip():
        return desc
    t = desc.strip()
    low = t.lower()
    if low in _WEATHER_IT:
        return _WEATHER_IT[low]
    for sep, joiner in (("/", " e "), (" with ", " con ")):
        if sep in low:
            parts = [p.strip() for p in low.split(sep) if p.strip()]
            tr = [_weather_it(p) for p in parts]
            if len(parts) > 1 and all(x != p for x, p in zip(tr, parts, strict=True)):
                return joiner.join(tr)
    if low.endswith("s") and low[:-1] in _WEATHER_IT:   # plurale → singolare già in mappa
        return _WEATHER_IT[low[:-1]]
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

# Tipi di indisponibilità FotMob → italiano (valori reali visti nei dati:
# 'injury' 897 righe, 'suspension' 39 — verificato 2026-09-09).
_UNAVAIL_IT = {"injury": "infortunio", "suspension": "squalifica", "suspended": "squalificato",
               "doubtful": "dubbio", "illness": "malattia", "national duty": "in nazionale",
               "not in squad": "fuori rosa", "rest": "riposo"}


def unavailability_it(value: Any) -> str:
    """'injury' → 'infortunio'; valori sconosciuti restituiti come sono (mai inventati)."""
    if not isinstance(value, str) or not value.strip():
        return "indisponibile"
    return _UNAVAIL_IT.get(value.strip().lower(), value.strip())


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
                out = {"source": "Understat", "played": n, "xg": rows.xg.sum(), "xga": rows.xga.sum(),
                       "xg_pm": rows.xg.mean(), "xga_pm": rows.xga.mean(), "xpts": rows.xpts.sum(),
                       "pts": rows.pts.sum(), "ppda": rows.ppda.mean()}
                for col, key in (("ppda_allowed", "ppda_allowed"), ("deep", "deep"),
                                 ("deep_allowed", "deep_allowed")):
                    if col in rows.columns:
                        out[key] = float(rows[col].mean())
                return out
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

    def season_style(self, team_name: str, team_id: int) -> dict[str, Any] | None:
        """Stile di stagione: xG/xGA, split azione/palle inattive (FotMob), PPDA/deep (Understat)."""
        base = dict(self.season_xg(team_name, team_id) or {})
        split = self._season_xg_split(team_id)
        if split:
            base.update(split)
        return base or None

    def _season_xg_split(self, team_id: int) -> dict[str, Any]:
        """xG azione manovrata / palle inattive per gara, dalle partite finite FotMob."""
        if self.team_stats.empty or self.info.empty:
            return {}
        fin = set(self.info.loc[self.info.status == "finished", "match_id"].astype(int))
        ts = self.team_stats[(self.team_stats.team_id == team_id)
                             & (self.team_stats.period == "All")
                             & (self.team_stats.match_id.isin(fin))]
        if ts.empty:
            return {}

        def _mean(key: str) -> float | None:
            v = pd.to_numeric(ts.loc[ts.key == key, "value"], errors="coerce").dropna()
            return float(v.mean()) if len(v) else None

        out: dict[str, Any] = {}
        op, sp = _mean("expected_goals_open_play"), _mean("expected_goals_set_play")
        if op is not None:
            out["open_pm"] = op
        if sp is not None:
            out["set_pm"] = sp
        n = ts.loc[ts.key == "expected_goals", "match_id"].nunique()
        if n:
            out["split_played"] = int(n)
        return out

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

    # ---- ruolo di un giocatore ----------------------------------------------------------------
    def _role_hist(self) -> dict[int, int]:
        """Ruolo abituale per ``player_id`` desunto dalle distinte in archivio (cache).

        Serve per gli indisponibili: FotMob non pubblica ``usualPosition`` su quelle righe
        (0/1340), quindi il ruolo si ricava dalle partite in cui il giocatore è stato
        schierato. Copre 99/248 assenti di oggi: dove non c'è, il ruolo resta vuoto.
        """
        if getattr(self, "_role_cache", None) is None:
            lu = self.lineup
            if lu.empty or "usual_position_id" not in lu.columns:
                self._role_cache = {}
            else:
                h = lu[lu.usual_position_id.notna()]
                self._role_cache = {int(k): int(v) for k, v in
                                    h.groupby("player_id").usual_position_id
                                     .agg(lambda x: x.astype(int).mode().iloc[0]).items()}
        return self._role_cache

    def _role_it(self, player_id: Any, usual: Any = None, pos: Any = None) -> str:
        """Ruolo in italiano: ``usualPosition`` → ``positionId`` mappato → storico distinte."""
        if usual is not None and pd.notna(usual) and int(usual) in POSITION_NAMES:
            return POSITION_NAMES[int(usual)]
        if pos is not None and pd.notna(pos) and int(pos) in POSITION_ID_ROLE:
            return POSITION_NAMES[POSITION_ID_ROLE[int(pos)]]
        if player_id is not None and pd.notna(player_id):
            r = self._role_hist().get(int(player_id))
            if r is not None:
                return POSITION_NAMES.get(r, "")
        return ""

    # ---- assenze ------------------------------------------------------------------------------
    def unavailable(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "unavailable")]
        rows = rows.sort_values("market_value_eur", ascending=False, na_position="last")
        return [{"name": r.player_name, "type": unavailability_it(_val(r._asdict(), "unavailability_type")),
                 "ret": _return_it(_val(r._asdict(), "expected_return")), "value": _val(r._asdict(), "market_value_eur"),
                 "pos": self._role_it(_val(r._asdict(), "player_id"), r.usual_position_id, r.position_id)}
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
        # Una squadra schiera 11 giocatori. Se ne restano di più, il dato accumulato da
        # snapshot diversi è ambiguo: il voto di partita esiste solo nello snapshot
        # ufficiale post-gara, quindi i titolari con voto sono la formazione reale
        # (verificato: 11 esatti in 472 squadre-partita su 478). Senza voti (partita non
        # ancora giocata) non c'è criterio: si mostra l'elenco della fonte, mai un taglio
        # arbitrario.
        if len(rows) > XI_SIZE:
            rated = rows[rows.rating.notna()]
            if len(rated) >= XI_SIZE:
                rows = rated.head(XI_SIZE)
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
                "id": int(r.player_id),
                "name": r.player_name,
                "pos": self._role_it(r.player_id, _val(r._asdict(), "usual_position_id"),
                                     _val(r._asdict(), "position_id")),
                "season_rating": float(r.season_rating),
                "goals": int(_season_num(int(r.player_id), "goals")),
                "assists": int(_season_num(int(r.player_id), "assists")),
            })
        return sorted(out, key=lambda p: p["season_rating"], reverse=True)[:n]


    # ---- profondità pre-partita: trend, precedenti, giocatori, assenze, arbitro ---------------
    def _season_player_stats(self, team_id: int) -> pd.DataFrame:
        """Una riga per giocatore della squadra con i totali di stagione dalle statistiche gara.

        ``player_stats`` ha una riga per (partita, giocatore, chiave): il pivot per chiave dà
        i totali senza doppioni. Fonte FotMob, presente su tutte e 7 le leghe (Understat ne
        copre 5): è la base comune per le schede giocatori, quindi niente leghe di serie B.
        ``rating_avg`` è la media dei voti sulle partite in cui il voto c'è.
        """
        if self.player_stats.empty:
            return pd.DataFrame()
        if not self.fixtures.empty:
            ids = set(self.fixtures.loc[self.fixtures.home_id == team_id, "match_id"]) \
                | set(self.fixtures.loc[self.fixtures.away_id == team_id, "match_id"])
            ps = self.player_stats[self.player_stats.match_id.isin(ids)]
        else:
            ps = self.player_stats
        ps = ps[(ps.team_id == team_id) & ps.value.notna()]
        if ps.empty:
            return pd.DataFrame()
        num = pd.to_numeric(ps.value, errors="coerce")
        ps = ps.assign(num=num)
        # unstack, non pivot_table(dropna=False): quest'ultimo espande l'indice al prodotto
        # cartesiano dei valori di ogni livello (18 giocatori → 324 righe con nomi incrociati)
        agg = ps.groupby(["player_id", "player_name", "key"]).num.sum().unstack("key")
        rated = ps[ps.key == "rating_title"].groupby(["player_id", "player_name"]).num.mean()
        games = ps[ps.key == "minutes_played"].groupby(["player_id", "player_name"]).num.count()
        out = agg.reset_index()
        key = pd.MultiIndex.from_arrays([out.player_id, out.player_name])
        out["rating_avg"] = pd.Series(rated.reindex(key).to_numpy(), index=out.index, dtype=float)
        out["games"] = pd.Series(games.reindex(key).to_numpy(), index=out.index, dtype=float)
        return out

    @staticmethod
    def _num(d: dict, key: str) -> float:
        """Valore numerico da un dizionario pivot: 0,0 se la chiave manca o non è un numero."""
        v = d.get(key)
        if v is None:
            return 0.0
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if pd.isna(f) else f

    def arrival_trend(self, team_name: str, team_id: int, n: int = 6) -> dict[str, Any] | None:
        """Come arriva la squadra: xG/xGA per gara, punti contro xPTS, PPDA, split casa/trasferta.

        Fonte primaria Understat (xG e PPDA per ogni gara, 5 leghe); dove non copre si usano
        le statistiche FotMob delle partite finite (xG su 7/7, senza PPDA). Se non si arriva
        a 3 gare con gli xG → None: la card non compare, nessun dato inventato.
        """
        rows: list[dict[str, Any]] = []
        source = None
        canon = canonical(team_name)
        # avversario per (data, casa/trasferta): serve perché Understat non lo pubblica
        opp_of: dict[tuple[str, bool], str] = {}
        if not self.fixtures.empty:
            tfx = self.fixtures[(self.fixtures.home_id == team_id) | (self.fixtures.away_id == team_id)]
            for r in tfx.itertuples(index=False):
                is_h = int(r.home_id) == team_id
                when = pd.Timestamp(r.utc_kickoff).date()
                opp_of[(str(when), is_h)] = r.home_name if not is_h else r.away_name
        if not self.us_team.empty:
            ut = self.us_team[self.us_team.team_name.map(canonical) == canon].copy()
            if not ut.empty:
                source = "Understat"
                ut["dt"] = pd.to_datetime(ut.date, utc=True, errors="coerce")
                ut = ut.dropna(subset=["dt"]).sort_values("dt").tail(n)
                for r in ut.itertuples(index=False):
                    gf, ga = int(r.goals), int(r.goals_against)
                    rows.append({"date": r.dt, "home": bool(r.is_home), "gf": gf, "ga": ga,
                                 "xg": float(r.xg), "xga": float(r.xga),
                                 "ppda": None if pd.isna(r.ppda) else float(r.ppda),
                                 "xpts": float(r.xpts), "pts": int(r.pts),
                                 "opp": opp_of.get((str(r.dt.date()), bool(r.is_home)), ""),
                                 "res": "V" if gf > ga else "N" if gf == ga else "P"})
        if not rows and not self.team_stats.empty and not self.fixtures.empty:
            source = "FotMob"
            fx = self.fixtures[(self.fixtures.status == "finished")
                               & self.fixtures.home_goals.notna()
                               & ((self.fixtures.home_id == team_id) | (self.fixtures.away_id == team_id))]
            fx = fx.sort_values("utc_kickoff").tail(n * 2)
            ts = self.team_stats[(self.team_stats.period == "All") & (self.team_stats.key == "expected_goals")]
            xg_of = {(int(m), int(t)): float(v) for m, t, v in zip(ts.match_id, ts.team_id, ts.value)}
            for r in fx.itertuples(index=False):
                is_home = int(r.home_id) == team_id
                opp = int(r.away_id) if is_home else int(r.home_id)
                gf, ga = (r.home_goals, r.away_goals) if is_home else (r.away_goals, r.home_goals)
                mine, theirs = xg_of.get((int(r.match_id), team_id)), xg_of.get((int(r.match_id), opp))
                if mine is None or theirs is None or pd.isna(mine) or pd.isna(theirs):
                    continue
                gf, ga = int(gf), int(ga)
                pts = 3 if gf > ga else 1 if gf == ga else 0
                xh, xa = self._poisson_xpts(mine, theirs)
                rows.append({"date": r.utc_kickoff, "home": is_home, "gf": gf, "ga": ga,
                             "xg": mine, "xga": theirs, "ppda": None,
                             "xpts": xh if is_home else xa, "pts": pts,
                             "opp": r.home_name if not is_home else r.away_name,
                             "res": "V" if gf > ga else "N" if gf == ga else "P"})
                if len(rows) == n:
                    break
        if len(rows) < 3:
            return None
        xg = [r["xg"] for r in rows]
        xga = [r["xga"] for r in rows]
        ppda = [r["ppda"] for r in rows if r["ppda"] is not None]
        home_rows = [r for r in rows if r["home"]]
        away_rows = [r for r in rows if not r["home"]]
        trend = None
        if len(rows) >= 6:                 # ultime 3 contro le precedenti: solo se ci sono 6 gare
            recent, before = sum(xg[-3:]) / 3, sum(xg[:-3]) / (len(xg) - 3)
            if before > 0:
                delta = recent - before
                trend = "in crescita" if delta > 0.15 else "in calo" if delta < -0.15 else "stabile"
        return {"source": source, "played": len(rows), "rows": rows,
                "xg_pm": sum(xg) / len(xg), "xga_pm": sum(xga) / len(xga),
                "pts": sum(r["pts"] for r in rows), "xpts": round(sum(r["xpts"] for r in rows), 1),
                "ppda": sum(ppda) / len(ppda) if ppda else None,
                "home_pm": sum(r["xg"] for r in home_rows) / len(home_rows) if home_rows else None,
                "away_pm": sum(r["xg"] for r in away_rows) / len(away_rows) if away_rows else None,
                "trend": trend}

    def h2h_pattern(self, match_id: int, home_id: int, away_id: int,
                    kickoff: pd.Timestamp, n: int = 60) -> dict[str, Any] | None:
        """Pattern sugli scontri diretti: tutti i precedenti disponibili, non solo gli ultimi 5.

        Esiti dal punto di vista della squadra di casa **attuale**. In archivio ci sono
        precedenti per 75/77 partite future, in media 19 a incontro (min 2, max 43):
        abbastanza per frequenze, non per conclusioni — ogni valore riporta il numero di casi.
        """
        rows = self._h2h_core(match_id, home_id, away_id, kickoff, n)
        if len(rows) < 3:
            return None
        w = d = l = 0
        margins: list[int] = []
        scorelines: dict[str, int] = {}
        btts = over25 = 0
        last_draw = None
        for i, r in enumerate(rows):
            was_home = r["home_id"] == home_id
            signed = (r["hg"] - r["ag"]) if was_home else (r["ag"] - r["hg"])
            if signed > 0:
                w += 1
            elif signed == 0:
                d += 1
                if last_draw is None:
                    last_draw = i          # 0 = l'ultimo scontro è stato un pareggio
            else:
                l += 1
            margins.append(signed)
            key = f"{r['hg']}-{r['ag']}" if was_home else f"{r['ag']}-{r['hg']}"
            scorelines[key] = scorelines.get(key, 0) + 1
            btts += int(r["hg"] > 0 and r["ag"] > 0)
            over25 += int(r["hg"] + r["ag"] > 2.5)
        total = len(rows)
        top = sorted(scorelines.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        return {"n": total, "wins": w, "draws": d, "losses": l,
                "gpg": sum(r["hg"] + r["ag"] for r in rows) / total,
                "margin": sum(margins) / total,
                "btts": btts / total, "over25": over25 / total, "draw_drought": last_draw,
                "top_scores": [{"score": s, "n": c, "share": c / total} for s, c in top],
                "last": rows[0]["utc"], "first": rows[-1]["utc"]}

    def key_players_deep(self, team_id: int, n: int = 3) -> dict[str, Any] | None:
        """Giocatori decisivi di stagione: contributo offensivo atteso per 90 minuti.

        Metrica (xG + xA) per 90: FotMob pubblica ``expected_goals`` e ``expected_assists``
        in tutte e 7 le leghe, quindi la card è identica ovunque. Due regole di qualità:
        - entrano in classifica solo i giocatori con **almeno un dato xG/xA**: chi non ha
          righe xG non è "a zero", è senza dato, e verrebbe penalizzato per errore;
        - soglia di minutaggio **relativa alla squadra** (40% dei minuti del più impiegato,
          minimo 90'): a inizio stagione una soglia assoluta (es. 270') lascerebbe fuori i
          più produttivi e premierebbe chi ha giocato tutto senza creare nulla.
        Sotto queste condizioni nessun giocatore → None, e la card non compare.
        """
        agg = self._season_player_stats(team_id)
        if agg.empty or "minutes_played" not in agg.columns:
            return None
        mins = agg.minutes_played.fillna(0.0)
        floor = max(90.0, 0.4 * float(mins.max()))
        played = agg[mins >= floor].copy()
        if played.empty:
            return None
        empty = pd.Series(index=played.index, dtype=float)
        xg = played.get("expected_goals", empty)
        xa = played.get("expected_assists", empty)
        # senza almeno una riga xG/xA il giocatore non ha un dato, non ha zero contributo
        mask = xg.notna() | xa.notna()
        played = played[mask]
        if played.empty:
            return None
        xg, xa = played.get("expected_goals", empty), played.get("expected_assists", empty)
        p90 = played.minutes_played / 90.0
        contrib = xg.fillna(0.0) + xa.fillna(0.0)
        played = played.assign(p90=p90, contrib=contrib, contrib_p90=contrib / p90)
        eligible = int(len(played))
        played = played.sort_values("contrib_p90", ascending=False).head(n)
        out = []
        for r in played.itertuples(index=False):
            d = r._asdict()
            gx, ax = d.get("expected_goals"), d.get("expected_assists")
            out.append({
                "id": int(r.player_id), "name": r.player_name,
                "pos": self._role_it(r.player_id),
                "minutes": int(self._num(d, "minutes_played")), "games": int(self._num(d, "games")),
                "goals": int(self._num(d, "goals")), "assists": int(self._num(d, "assists")),
                "xg": None if gx is None or pd.isna(gx) else round(float(gx), 2),
                "xa": None if ax is None or pd.isna(ax) else round(float(ax), 2),
                "contrib_p90": float(r.contrib_p90),
                "chances": int(self._num(d, "chances_created")),
                "big_chances": int(self._num(d, "big_chance_created_team_title")),
                "rating": None if pd.isna(r.rating_avg) else round(float(r.rating_avg), 2)})
        return {"rows": out, "floor": int(floor), "eligible": eligible}

    def absences_weight(self, match_id: int, team_id: int) -> dict[str, Any] | None:
        """Quanto pesa l'infermeria: gol, assist e xG+xA per 90 che gli assenti portano via.

        Ogni assente è pesato sui suoi numeri reali di stagione. «Titolare abituale» =
        almeno metà dei minuti medi per giocatore della squadra (minuti totali / 11).
        """
        unav = self.unavailable(match_id, team_id)
        if not unav:
            return None
        agg = self._season_player_stats(team_id)
        stats: dict[int, dict[str, float]] = {}
        team_minutes = 0.0
        if not agg.empty:
            for r in agg.itertuples(index=False):
                d = r._asdict()
                mins = self._num(d, "minutes_played")
                stats[int(r.player_id)] = {
                    "minutes": mins, "goals": self._num(d, "goals"), "assists": self._num(d, "assists"),
                    "contrib": self._num(d, "expected_goals") + self._num(d, "expected_assists")}
                team_minutes += mins
        # minuti medi per giocatore: la somma dei minuti divisa per gli 11 in campo
        per_player = team_minutes / XI_SIZE if team_minutes else 0.0
        lu = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                         & (self.lineup.role == "unavailable") & self.lineup.player_id.notna()]
        by_name = {str(r.player_name): int(r.player_id) for r in lu.itertuples(index=False)}
        players, starters_out, contrib_lost = [], 0, 0.0
        for u in unav:
            pid = by_name.get(str(u["name"]))
            s = stats.get(pid, {}) if pid is not None else {}
            mins, p90 = s.get("minutes", 0.0), s.get("minutes", 0.0) / 90.0
            contrib = s.get("contrib", 0.0) / p90 if p90 and s.get("contrib") else None
            is_starter = bool(per_player and mins >= 0.5 * per_player)
            starters_out += int(is_starter)
            contrib_lost += contrib or 0.0
            players.append({**u, "minutes": int(mins) or None, "games": None,
                            "goals": int(s.get("goals", 0.0)), "assists": int(s.get("assists", 0.0)),
                            "contrib_p90": contrib, "starter": is_starter})
        players.sort(key=lambda p: (-(p["contrib_p90"] or 0.0), -(p["minutes"] or 0)))
        return {"players": players, "n": len(players), "starters_out": starters_out,
                "contrib_lost_p90": contrib_lost or None, "has_stats": bool(stats)}

    def referee_profile(self, match_id: int) -> dict[str, Any] | None:
        """Profilo dell'arbitro con il confronto sulla media del campionato.

        Le medie di lega sono calcolate sulle designazioni FotMob in archivio
        (``match_info``): dove i dati statistici dell'arbitro mancano la card mostra solo il
        nome, senza stime.
        """
        row = self.info[self.info.match_id == match_id]
        if row.empty:
            return None
        d = row.iloc[0].to_dict()
        if not _val(d, "referee_name"):
            return None
        league_id = _val(d, "league_id")
        if league_id is None:
            lg = self.info
        else:
            lg = self.info[self.info.league_id == league_id]
        lg = lg[pd.to_numeric(lg.get("referee_yellows_per_match"), errors="coerce").notna()] \
            if "referee_yellows_per_match" in lg.columns else lg.iloc[:0]

        def _mean(col: str) -> float | None:
            if lg.empty or col not in lg.columns:
                return None
            v = pd.to_numeric(lg[col], errors="coerce").dropna()
            return float(v.mean()) if len(v) else None

        return {"name": _val(d, "referee_name"), "matches": _val(d, "referee_matches"),
                "yellows": _val(d, "referee_yellows_per_match"), "reds": _val(d, "referee_reds_total"),
                "pens": _val(d, "referee_penalties_total"), "fouls": _val(d, "referee_fouls_per_match"),
                "league_yellows": _mean("referee_yellows_per_match"),
                "league_fouls": _mean("referee_fouls_per_match"),
                "league_matches": int(len(lg)) if not lg.empty else None}

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
                out.append({"label": label, "home": _stat_text_it(h.iloc[0].text),
                            "away": _stat_text_it(a.iloc[0].text)})
        return out

    def timeline(self, match_id: int) -> list[dict[str, Any]]:
        """Cronaca essenziale (gol, cartellini, sostituzioni) con il punteggio **dopo** ogni gol.

        Semantica FotMob verificata sui dati (226 partite finite, di cui 22 con autogol):
        - ``homeScore``/``awayScore`` di un evento gol sono il punteggio **prima** del gol
          (226/226: mai quello dopo);
        - ``isHome`` indica la squadra **a cui il gol è attribuito**, già al netto degli
          autogol (22/22 partite con autogol: usando ``isHome`` tal quale il conteggio
          finale coincide col risultato; ribaltandolo sugli autogol 0/22).

        Da qui: il punteggio mostrato è ricostruito contando i gol in ordine, e un evento
        gol il cui «punteggio prima» non coincide con la sequenza viene scartato — è il
        caso dei gol duplicati dalla fonte (es. Union Berlin–Schalke 04 del 11/09: 46' e
        48' con gli stessi campi punteggio), che altrimenti finirebbero sia in cronaca sia
        nelle probabilità in-play.
        """
        if self.events.empty:
            return []
        ev = self.events[(self.events.match_id == match_id) & (self.events.type.isin(["Goal", "Card", "Substitution"]))]
        ev = ev.sort_values(["minute", "minute_added"], na_position="first")
        out = []
        hg = ag = 0
        for r in ev.itertuples(index=False):
            d = r._asdict()
            swap = _val(d, "swap")
            if isinstance(swap, str):
                try:
                    swap = ast.literal_eval(swap)
                except (ValueError, SyntaxError):
                    swap = None
            added = _val(d, "minute_added")
            scored_home = bool(_val(d, "is_home", False))   # squadra a cui il gol è attribuito
            own_goal = bool(_val(d, "own_goal", False))
            score = None
            if r.type == "Goal":
                before_h, before_a = _val(d, "home_score"), _val(d, "away_score")
                if before_h is not None and before_a is not None:
                    try:
                        if (int(before_h), int(before_a)) != (hg, ag):
                            continue   # evento duplicato o fuori sequenza: scartato
                    except (TypeError, ValueError):
                        pass
                if scored_home:
                    hg += 1
                else:
                    ag += 1
                score = f"{hg}-{ag}"
            out.append({"type": r.type, "minute": _val(d, "minute"), "added": int(added) if added is not None else None,
                        "home": scored_home, "scorer_home": scored_home != own_goal,
                        "player": _val(d, "player_name"),
                        "card": _val(d, "card"), "own_goal": own_goal, "score": score,
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
                    "id": int(r.player_id),
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
        # autogol esclusi: restano nella lista tiri FotMob ma non nei suoi aggregati di
        # squadra (tiri totali 475/478 e tiri in porta 476/478 concordano solo escludendoli)
        s = s[~s.is_own_goal.fillna(False).astype(bool)]
        if s.empty:
            return {}
        big = s[s.xg >= 0.3]
        return {"n": int(len(s)), "xg": float(s.xg.sum()), "on_target": int(_on_target(s).sum()),
                "inside_box": int(s.is_inside_box.fillna(False).sum()), "big_chances": int(len(big)),
                "goals": int((s.event_type == "Goal").sum()),
                "best": _first(s.sort_values("xg", ascending=False)[["player_name", "xg", "minute", "event_type"]])}

    def shot_map(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        """Tiri di una squadra pronti per l'SVG: mezzo campo offensivo 105×68 m → 420×272 px (porta a destra)."""
        if self.shots.empty:
            return []
        s = self.shots[(self.shots.match_id == match_id) & (self.shots.team_id == team_id)].dropna(subset=["x", "y"])
        out = []
        for r, on_tgt in zip(s.itertuples(index=False), _on_target(s), strict=True):
            xg = float(r.xg) if pd.notna(r.xg) else 0.0
            goal = r.event_type == "Goal"
            blocked = bool(r.is_blocked) if pd.notna(r.is_blocked) else False
            kind = "goal" if goal else "blocked" if blocked else "target" if on_tgt else "miss"
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
            out.append({"date": r["utc"].strftime("%d/%m/%Y"), "league": _competition_it(r["league"]),
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

    def score_matrix(self, pred: dict[str, Any] | None) -> dict[str, Any] | None:
        """Matrice 0–5 dei punteggi dalla λ e ρ della previsione (None se manca λ)."""
        if not pred or pred.get("lambda_home") is None or pred.get("lambda_away") is None:
            return None
        rho = pred.get("dc_rho") or 0.0
        try:
            rho = 0.0 if rho is None or (isinstance(rho, float) and pd.isna(rho)) else float(rho)
        except (TypeError, ValueError):
            rho = 0.0
        return score_matrix(float(pred["lambda_home"]), float(pred["lambda_away"]), rho)

    def clash(self, home_name: str, home_id: int, away_name: str, away_id: int,
              pred: dict[str, Any] | None) -> dict[str, Any] | None:
        return style_rows(self.season_style(home_name, home_id),
                          self.season_style(away_name, away_id), pred)

    def match_xg_race(self, match_id: int, home_id: int, away_id: int) -> dict[str, Any] | None:
        if self.shots.empty:
            return None
        return xg_race(self.shots[self.shots.match_id == match_id], home_id, away_id)

    def match_shot_quality(self, match_id: int, team_id: int) -> dict[str, Any] | None:
        if self.shots.empty:
            return None
        return shot_quality(self.shots[self.shots.match_id == match_id], team_id)

    def match_wp(self, pred: dict[str, Any] | None, timeline: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Traiettoria 1X2 dopo ogni gol; None senza previsione o senza gol."""
        if not pred or pred.get("lambda_home") is None or pred.get("lambda_away") is None:
            return None
        goals = [e for e in timeline if e.get("type") == "Goal"]
        if not goals:
            return None
        rho = pred.get("dc_rho") or 0.0
        try:
            rho = 0.0 if rho is None or (isinstance(rho, float) and pd.isna(rho)) else float(rho)
        except (TypeError, ValueError):
            rho = 0.0
        pts = wp_path(goals, float(pred["lambda_home"]), float(pred["lambda_away"]), rho)
        if len(pts) < 2:
            return None
        return {
            "points": pts,
            "poly_h": " ".join(f"{p['x']},{p['y_h']}" for p in pts),
            "poly_d": " ".join(f"{p['x']},{p['y_d']}" for p in pts),
            "poly_a": " ".join(f"{p['x']},{p['y_a']}" for p in pts),
        }

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
        clash = ctx.get("clash")
        if clash:
            by = {r["label"]: r for r in clash["rows"]}
            ppda = by.get("PPDA (↓ = più pressing)")
            if ppda and ppda["h"] is not None and ppda["a"] is not None:
                if ppda["h"] <= 0.75 * ppda["a"]:
                    s.append(f"{h} preme molto più di {a} (PPDA {_f(ppda['h'], 1)} vs {_f(ppda['a'], 1)}).")
                elif ppda["a"] <= 0.75 * ppda["h"]:
                    s.append(f"{a} preme molto più di {h} (PPDA {_f(ppda['a'], 1)} vs {_f(ppda['h'], 1)}).")
            op = by.get("xG azione manovrata / gara")
            st = by.get("xG palle inattive / gara")
            if op and st and op["h"] is not None and st["h"] is not None and (op["h"] + st["h"]) > 0:
                share = st["h"] / (op["h"] + st["h"])
                if share >= 0.40:
                    s.append(f"{h} crea una quota alta di xG su palla inattiva ({_pct(share)} del totale).")
            if op and st and op["a"] is not None and st["a"] is not None and (op["a"] + st["a"]) > 0:
                share = st["a"] / (op["a"] + st["a"])
                if share >= 0.40:
                    s.append(f"{a} crea una quota alta di xG su palla inattiva ({_pct(share)} del totale).")
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
                    s.append(f"{name} ha raccolto {dec(diff, 1, plus=True)} punti rispetto agli xPTS: rendimento "
                             f"sopra la qualità del gioco prodotto, possibile regressione.")
                elif diff <= -3:
                    s.append(f"{name} ha {dec(diff, 1, plus=True)} punti rispetto agli xPTS: sta rendendo meno di "
                             f"quanto crea, segnale di sottovalutazione.")
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
                         + (f", {it_plural(ref['pens'], 'rigore')} in {it_plural(ref['matches'], 'gara')}."
                            if ref.get("pens") is not None else "."))
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
                                             f["home_name"], f["away_name"], n=5)
                         if status != "finished" else []),
            "home_arrival": self.arrival_trend(f["home_name"], home_id) if status != "finished" else None,
            "away_arrival": self.arrival_trend(f["away_name"], away_id) if status != "finished" else None,
            "h2h_pattern": (self.h2h_pattern(match_id, home_id, away_id, kickoff)
                            if status != "finished" else None),
            "home_key_deep": self.key_players_deep(home_id) if status != "finished" else None,
            "away_key_deep": self.key_players_deep(away_id) if status != "finished" else None,
            "home_absences": self.absences_weight(match_id, home_id) if status != "finished" else None,
            "away_absences": self.absences_weight(match_id, away_id) if status != "finished" else None,
            "referee_profile": self.referee_profile(match_id),
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
        ctx["score_matrix"] = self.score_matrix(ctx["prediction"])
        ctx["clash"] = self.clash(f["home_name"], home_id, f["away_name"], away_id, ctx["prediction"])
        ctx["xg_race"] = self.match_xg_race(match_id, home_id, away_id) if status == "finished" else None
        ctx["home_shotq"] = self.match_shot_quality(match_id, home_id) if status == "finished" else None
        ctx["away_shotq"] = self.match_shot_quality(match_id, away_id) if status == "finished" else None
        ctx["wp_path"] = self.match_wp(ctx["prediction"], ctx["timeline"]) if status == "finished" else None
        ctx["narrative"] = self.narrative(ctx)
        return ctx
