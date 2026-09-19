"""Costruzione del contenuto analitico di una partita (in italiano) a partire dallo store.

Nessuna generazione "creativa": ogni frase deriva da un numero presente nel database, con
regole esplicite (soglie documentate nel codice). Il risultato è un dizionario che i template
Jinja2 rendono in HTML.
"""

from __future__ import annotations

import ast
import itertools
import re
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.stats import poisson

from ..config import leagues, load_leagues_config
from ..models.predict import wilson_interval
from ..sources.news import TOPIC_LABELS, TOPIC_WEIGHTS, classify_news, is_italian_news, news_value
from ..store import Store
from ..teams import canonical, soft_key
from .advanced import (
    goals_view,
    probability_steps,
    score_matrix,
    shot_quality,
    style_rows,
    wp_path,
    xg_race,
)
from .fmt import dec, displayed_sum, it_day_time, it_plural, pct_triple
from .rates import (
    MIN_DEN_FOR_RATE,
    Pool,
    group_label,
    player_pools,
)
from .rates import (
    lookup as pool_lookup,
)

# Ruolo di FotMob ``usualPosition``: la codifica parte da **0**, non da 1. Verificato su
# 616 formazioni: il valore 0 compare 632 volte (1,03 a formazione) ed è il portiere in
# 600 formazioni su 600 che lo contengono — es. Lazio 12/09, Mandas (n. 35) = 0, Doekhi e
# Provstgaard = 1, Frattesi = 2, Zaccagni = 3. Con la vecchia mappa 1→portiere ogni riga
# della distinta era spostata di un ruolo e il portiere restava senza etichetta.
# ``goal_description`` di FotMob → italiano. Tenuti solo i valori presenti nei dati
# (166/753 gol): per gli altri non si inventa nulla, la riga resta senza specifica.
GOAL_KIND_IT = {"Header": "di testa", "Penalty": "rigore", "Own goal": "autogol",
                "Direct freekick": "punizione diretta", "Overhead kick": "rovesciata",
                "Tap-in": "sotto misura", "Deflected": "deviato"}

POSITION_NAMES = {0: "portiere", 1: "difensore", 2: "centrocampista", 3: "attaccante"}

# Le medie dei pari per stabilizzare le rate su campioni piccoli non sono costanti qui:
# si misurano dal run in ``fda.site.rates`` (docs/19 §1.10), perché una costante scritta a
# mano non conosce né la stagione né la statistica a cui viene applicata.
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


def _elenco_it(items: list[str], max_items: int = 4) -> str:
    """Elenco in italiano corrente: «A», «A e B», «A, B e C» (P2.4, `docs/19` §2.8).

    La congiunzione prima dell'ultimo nome è ciò che distingue una frase da un elenco di
    dati separati da virgole. Se i nomi mostrati sono già stati troncati a ``max_items``
    il chiamante aggiunge «…»: qui non si inventa nulla sul resto.
    """
    nomi = [str(x) for x in items if str(x).strip()]
    if not nomi:
        return ""
    if len(nomi) == 1:
        return nomi[0]
    return f"{', '.join(nomi[:-1])} e {nomi[-1]}"


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


def _no_news() -> dict[str, Any]:
    """Bollettino vuoto per le partite finite (la card non si stampa, il contesto resta tipato)."""
    return {"notizie": [], "riserva": [], "esaminate": 0, "pubblicate": 0, "scartate": 0,
            "oltre": 0, "annunci": 0, "piatti": 0, "altre": 0, "doppioni": 0,
            "vecchie": 0, "pertinenti": 0, "lingua": 0,
            "finestra": 0, "limite": 0, "categoria_limite": 0, "riserva_limite": 0}


#: Voci dell'imbuto della card «Vita del club» che entrano nella riga unica quando non c'è
#: niente da pubblicare (`docs/28` §2 P1.1). L'ordine mette per primo il cesto generico —
#: «servizio o cronaca», cioè quello che non è notizia — e poi i motivi specifici, nello
#: stesso ordine in cui la riga dell'imbuto li legge per esteso. Un motivo a zero non si
#: stampa: la riga non deve suggerire scarti che non ci sono stati.
NEWS_FUNNEL_ORDER: tuple[tuple[str, str], ...] = (
    ("scartate", "servizio o cronaca"),
    ("lingua", "in un'altra lingua"),
    ("annunci", "annunci o logistica"),
    ("piatti", "non spostano nulla"),
    ("altre", "su un'altra squadra"),
    ("doppioni", "già raccontati da un'altra voce"),
    ("oltre", "oltre il limite dei tre"),
)


def news_quiet_line(home: dict[str, Any], away: dict[str, Any], home_name: str,
                    away_name: str) -> dict[str, Any] | None:
    """Una riga sola quando **nessuna** delle due squadre ha un titolo pubblicabile.

    Perché esiste (misurato il 2026-09-18, `docs/28` §2 P1.1): su **42 schede su 66** la card
    «Vita del club» non aveva nulla da pubblicare e restava comunque il blocco più pesante
    della pagina — 3.054 caratteri mediani, di cui il **99%** prosa metodologica — mentre
    tutta l'analisi numerica stava in un decimo del testo. Qui si costruisce il fatto in una
    riga («nessun titolo pubblicabile: N esaminati e scartati, con i motivi») e i conteggi
    restano tutti: il template li mostra in una tendina, insieme ai criteri. Nessun numero
    viene tolto dalla pagina, cambia solo *dove* sta: nel primo schermo il risultato, sotto
    il lavoro fatto per arrivarci.

    Ritorna ``None`` quando una delle due squadre ha qualcosa da pubblicare (o in riserva):
    in quel caso la card resta quella completa, colonna per colonna.

    I conteggi sono gli stessi che il verificatore ricalcola con :meth:`MatchAnalysis.team_news`
    (``scripts/verify_site.py [20]``): la riga non introduce numeri nuovi, somma quelli
    dell'imbuto già pubblicato per squadra.
    """
    def _vuoto(nw: dict[str, Any]) -> bool:
        return not nw.get("notizie") and not nw.get("riserva")

    if not (_vuoto(home) and _vuoto(away)):
        return None

    def _somma(chiave: str) -> int:
        return int(home.get(chiave) or 0) + int(away.get(chiave) or 0)

    esaminate = _somma("esaminate")
    vecchie = _somma("vecchie")
    finestra = int(home.get("finestra") or away.get("finestra") or 0)
    giorni = it_plural(finestra, "giorno")
    squadre = f"{home_name} e {away_name}"
    if not esaminate:
        riga = f"Nessun titolo in lingua italiana raccolto su {squadre} negli ultimi {giorni}"
        if vecchie:
            riga += (f" ({it_plural(vecchie, 'titolo più vecchio', 'titoli più vecchi')} oltre la "
                     "finestra: guardati e lasciati fuori)")
        riga += "."
    else:
        motivi = [f"{_somma(chiave)} {etichetta}" for chiave, etichetta in NEWS_FUNNEL_ORDER
                  if _somma(chiave)]
        esam = it_plural(esaminate, "titolo esaminato", "titoli esaminati")
        scartati = "scartato" if esaminate == 1 else "scartati"
        riga = (f"Nessun titolo pubblicabile su {squadre} negli ultimi {giorni}: {esam} e "
                f"{scartati} con criterio — {' · '.join(motivi)}")
        if vecchie:
            riga += f" · {it_plural(vecchie, 'troppo vecchio', 'troppo vecchi')}"
        riga += "."
    return {"riga": riga, "esaminate": esaminate, "vecchie": vecchie, "finestra": finestra,
            "motivi": [{"chiave": chiave, "etichetta": etichetta, "n": _somma(chiave)}
                       for chiave, etichetta in NEWS_FUNNEL_ORDER if _somma(chiave)]}


def news_freshness(hours: float) -> float:
    """Punteggio di freschezza di una notizia (docs/24 §3.5).

    Non basta «dentro la settimana»: dentro la settimana conta **quanto** è vicina al
    calcio d'inizio. Una voce di ieri sera pesa più di una di lunedì, e una di tre giorni
    fa più di una di sei. Le soglie sono le stesse misurate sul prototipo approvato.
    """
    if hours <= 12:
        return 6.0
    if hours <= 24:
        return 5.0
    if hours <= 36:
        return 4.0
    if hours <= 48:
        return 3.0
    if hours <= 72:
        return 1.5
    return 0.0


def news_substance(text: str) -> float:
    """Fatti sopra dichiarazioni: +2 con un numero o una decisione, −2 con una frase.

    Serve all'ordinamento della card (docs/24 §3.5): a parità di freschezza e rilevanza,
    «il tetto di spesa è 142,8 M€» viene prima di «il tecnico ha parlato della rosa».
    """
    p = 0.0
    if re.search(r"\d", text or "") or re.search(
            r"ricorso|respinge|respinto|limita|rinnovo|firmato|cantiere|lavori|sanzione|"
            r"indagine|esclusi|tetto|limite|divario|priorit[aà]|"
            r"rechaza|rechaz|aprueba|desestima|denuncia|multa|deuda|l[ií]mite|"
            r"protesta|amenaza|insulto|comunicado|renueva|acuerdo|recurso|sentencia|"
            r"reject|sanction|fine|debt|cap|protest|abuse|threat|"
            r"ablehnt|kritik|streik|rejette|afwijst|rejeita", text or "", re.IGNORECASE):
        p += 2
    if re.search(r"dichiarazion|conferenza stampa|intervista|ha detto|le parole di|"
                 r"declaracion|dijo|asegur|se[ñn]al[oó]|explic[oó]|palabras|"
                 r"quotes|said|says|erkl[aä]rt|d[eé]clar|zegt|disse", text or "", re.IGNORECASE):
        p -= 2
    return p


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
    """3.5 → '3,50' (virgola decimale italiana). Alias di :func:`fda.site.fmt.dec`."""
    return dec(v, 2)


# Fatti FotMob (`insights`): testi inglesi a template. Si traducono SOLO i pattern
# oggettivi (streak, gol recenti, testa-a-testa, capocannoniere). Qualsiasi altra
# frase — hype («most shots on target»), marketing, o forma sconosciuta — viene
# scartata: sul sito non compare mai un testo non tradotto.
_INSIGHT_EN_LEAK = re.compile(
    r"\b(haven't|have scored|have (won|lost|kept|been|conceded)|clean sheet|"
    r"their last|matches|meetings|attempts|competition|ranked|average)\b",
    re.IGNORECASE,
)

# Sotto questa soglia la media gialli/partita di un arbitro ha un errore standard grande
# (su 6 partite ~0,6): si pubblicano i numeri, mai l'aggettivo (P1.2, docs/19 §2.6).
MIN_REFEREE_MATCHES = 15


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

    # Template oggettivi recuperati (P1.4, docs/19 §2.5): i 5 più frequenti fra gli scarti
    # (685 fatti scartati su 2.014, 34%) — tutti dati, nessun giudizio/hype.
    m = re.fullmatch(r"Have kept the most clean sheets in the competition \((\d+)\)", t)
    if m:
        n = int(m.group(1))
        return {"text": f"ha il maggior numero di porte inviolate del campionato ({n})",
                "kind": "clean_sheet", "priority": 74}

    m = re.fullmatch(r"Have conceded the most penalties this season \((\d+)\)", t)
    if m:
        n = int(m.group(1))
        return {"text": f"ha concesso più rigori in questa stagione ({n})",
                "kind": "penalty", "priority": 72}

    m = re.fullmatch(r"Have been awarded the most penalties this season \((\d+)\)", t)
    if m:
        n = int(m.group(1))
        return {"text": f"ha ottenuto più rigori in questa stagione ({n})",
                "kind": "penalty", "priority": 72}

    m = re.fullmatch(r"Average (\d+(?:\.\d+)?) goals per match", t)
    if m:
        v = f"{float(m.group(1)):.1f}".replace(".", ",")   # FotMob pubblica 1 decimale
        return {"text": f"media {v} gol a partita", "kind": "goals", "priority": 50}

    m = re.fullmatch(r"Ranked (\d+) at home this season", t)
    if m:
        n = int(m.group(1))
        return {"text": f"{n}° in classifica nelle gare interne", "kind": "rank", "priority": 48}

    m = re.fullmatch(r"Ranked (\d+) away from home this season", t)
    if m:
        n = int(m.group(1))
        return {"text": f"{n}° in classifica nelle gare in trasferta", "kind": "rank", "priority": 48}

    insight_dropped(t)
    return None


# Osservabilità degli scarti (P1.4, docs/19 §2.5): il 34% dei fatti FotMob veniva scartato
# in silenzio. Il conteggio per forma canonica (numeri → «N») distingue un template nuovo
# (centinaia di occorrenze identiche) dal caso singolo; il build lo pubblica in stato.html.
INSIGHT_DROP_LOG: dict[str, int] = {}
INSIGHT_SEEN: dict[str, int] = {"tradotti": 0, "scartati": 0}


def insight_dropped(text: str) -> None:
    """Registra un fatto non tradotto, per forma canonica. Mai in pagina come testo inglese."""
    key = re.sub(r"\d+", "N", str(text))[:80]
    INSIGHT_DROP_LOG[key] = INSIGHT_DROP_LOG.get(key, 0) + 1


def insight_drop_stats() -> dict[str, Any] | None:
    """Riepilogo per stato.html: fatti visti dal build, tradotti, scartati, forma top."""
    tot_seen = INSIGHT_SEEN["tradotti"] + INSIGHT_SEEN["scartati"]
    if not tot_seen and not INSIGHT_DROP_LOG:
        return None
    top_key, top_n = (max(INSIGHT_DROP_LOG.items(), key=lambda kv: kv[1])
                      if INSIGHT_DROP_LOG else (None, 0))
    return {"tradotti": INSIGHT_SEEN["tradotti"], "scartati": INSIGHT_SEEN["scartati"],
            "n_shapes": len(INSIGHT_DROP_LOG), "top_shape": top_key, "top_n": top_n}


def reset_insight_stats() -> None:
    """Azzera i contatori (per i test e per build multipli nello stesso processo)."""
    INSIGHT_DROP_LOG.clear()
    INSIGHT_SEEN["tradotti"] = 0
    INSIGHT_SEEN["scartati"] = 0


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


def prediction_meta(pred: dict[str, Any] | None, home_name: str | None = None,
                    away_name: str | None = None) -> dict[str, Any] | None:
    """Riassunto leggibile della previsione, senza trasformare una probabilità in un pronostico.

    La scheda pubblica tre cose verificabili: esito più probabile, margine sul secondo esito
    e concordanza (o divergenza) fra Dixon-Coles ed Elo. Il margine non viene chiamato
    «confidenza»: una probabilità del 57% resta un evento incerto. ``None`` viene restituito
    se il vettore 1X2 non è completo, così il template non stampa valori inventati.
    """
    if not pred:
        return None

    def _prob(key: str) -> float | None:
        try:
            value = float(pred.get(key))
        except (TypeError, ValueError):
            return None
        return None if pd.isna(value) else value

    names = {"1": home_name or "Casa", "X": "Pareggio", "2": away_name or "Trasferta"}
    values = {key: _prob(f"p_{suffix}") for key, suffix in (("1", "home"), ("X", "draw"), ("2", "away"))}
    if any(v is None for v in values.values()):
        return None
    ordered = sorted(values.items(), key=lambda item: (-float(item[1]), ("1", "X", "2").index(item[0])))
    top_key, top_probability = ordered[0]
    second_probability = float(ordered[1][1])

    elo_keys = (("1", "elo_p_home"), ("X", "elo_p_draw"), ("2", "elo_p_away"))
    elo_values = {key: _prob(field) for key, field in elo_keys}
    has_elo = all(v is not None for v in elo_values.values())
    elo_top = None
    elo_gap_pp = None
    if has_elo:
        elo_ordered = sorted(elo_values.items(), key=lambda item: (-float(item[1]), ("1", "X", "2").index(item[0])))
        elo_top = elo_ordered[0][0]
        elo_gap_pp = round(max(abs(float(values[k]) - float(elo_values[k])) for k in values) * 100, 1)

    second_key, _second_prob = ordered[1]
    # probabilità DC ed Elo per tooltip dettagliato
    dc_keys = (("1", "dc_p_home"), ("X", "dc_p_draw"), ("2", "dc_p_away"))
    dc_values = {k: _prob(f) for k, f in dc_keys}
    has_dc = all(v is not None for v in dc_values.values())
    dc_top = None
    dc_top_prob = None
    if has_dc:
        dc_ordered = sorted(dc_values.items(), key=lambda item: (-float(item[1]), ("1", "X", "2").index(item[0])))
        dc_top, dc_top_prob = dc_ordered[0][0], float(dc_ordered[0][1])
    elo_top_prob = None
    if has_elo and elo_top:
        elo_top_prob = float(elo_values[elo_top])
    # distanza DC–Elo **sul preferito pubblicato**, fra i due modelli (non fra blend ed Elo):
    # è il numero che rende leggibile «quanto sono d'accordo i due motori» (docs/20 §7)
    elo_gap_top_pp = None
    if has_dc and has_elo:
        elo_gap_top_pp = round(abs(float(dc_values[top_key]) - float(elo_values[top_key])) * 100, 1)

    def _comma(x: float | None, nd: int = 1) -> str:
        return "" if x is None else f"{float(x):.{nd}f}".replace(".", ",")

    # Segnale di (dis)accordo con i due soggetti espliciti e le percentuali ricalcolabili
    # dai vettori salvati: mai uno «scarto» senza dire fra chi (docs/20 §7)
    if has_dc and has_elo and dc_top is not None and elo_top is not None:
        if dc_top == elo_top:
            signal_label = (f"DC ed Elo sullo stesso preferito ({names[dc_top]}): "
                            f"DC {_comma(float(dc_values[dc_top]) * 100)}% · "
                            f"Elo {_comma(float(elo_values[elo_top]) * 100)}% · "
                            f"distanza {_comma(elo_gap_top_pp)} punti")
            signal_tone = "agree"
        else:
            signal_label = (f"Preferiti diversi: DC {names[dc_top]} "
                            f"{_comma(float(dc_values[dc_top]) * 100)}% · "
                            f"Elo {names[elo_top]} {_comma(float(elo_values[elo_top]) * 100)}%")
            signal_tone = "split"
    elif has_elo and top_key != elo_top:
        signal_label = "DC ed Elo divergono"
        signal_tone = "split"
    elif has_elo:
        signal_label = "Stesso preferito per DC ed Elo"
        signal_tone = "agree"
    elif has_dc:
        signal_label = "Solo modello sui gol"
        signal_tone = "single"
    else:
        signal_label = "Segnale unico"
        signal_tone = "single"

    # percentuali intere coerenti (resto massimo, somma 100): il margine pubblicato è la
    # differenza fra le percentuali STAMPATE, così il lettore può rifare il conto (docs/20 §5)
    pct = pct_triple((float(values["1"]), float(values["X"]), float(values["2"])))
    idx = {"1": 0, "X": 1, "2": 2}

    return {
        "top_key": top_key,
        "top_name": names[top_key],
        "top_probability": float(top_probability),
        "pct": pct,
        "top_pct": pct[idx[top_key]],
        "second_key": second_key,
        "second_name": names[second_key],
        "second_probability": float(second_probability),
        "second_pct": pct[idx[second_key]],
        "margin_pp": pct[idx[top_key]] - pct[idx[second_key]],
        "signal_label": signal_label,
        "signal_tone": signal_tone,
        "elo_top": elo_top,
        "elo_top_name": names[elo_top] if elo_top else None,
        "elo_top_prob": elo_top_prob,
        "dc_top": dc_top,
        "dc_top_name": names[dc_top] if dc_top else None,
        "dc_top_prob": dc_top_prob,
        "elo_gap_pp": elo_gap_pp,
        "elo_gap_top_pp": elo_gap_top_pp,
        "has_dc": has_dc,
        "has_elo": has_elo,
    }


#: Parole tutte maiuscole che non sono nomi propri. I titoli di agenzia («UFFICIALE –
#: BOLOGNA, ESONERATO TEDESCO…») sono scritti in maiuscolo e senza questa lista i soggetti
#: diventavano «esonerato» o «allenatore», quindi il dedup non riconosceva lo stesso fatto
#: raccontato due volte (misurato il 2026-09-17 sulla colonna del Bologna: due titoli
#: sull'esonero di Tedesco pubblicati insieme).
_MAIUSCOLE_NON_NOMI = frozenset({
    "ufficiale", "ufficialmente", "ufficializzata", "esonero", "esonerato", "esonerati",
    "allenatore", "panchina", "calcio", "calciomercato", "mercato", "nuovo", "nuova",
    "scelto", "ultimora", "ultime", "live", "video", "foto", "pagelle", "probabili",
    "formazioni", "convocati", "infortunio", "squalifica", "rifiuta", "accordo",
    "contratto", "presidente", "società", "squadra", "partita", "gara", "campionato",
})


def news_subjects(title: str, club_tokens: set[str] | None = None) -> set[str]:
    """Nomi propri di un titolo (persone, città, enti) esclusi i nomi dei club.

    Serve al bollettino stampa per non pubblicare due volte la stessa notizia: due titoli
    della stessa categoria che citano lo stesso nome proprio (Calhanoglu, Idzes, Tedesco)
    raccontano lo stesso fatto. Il nome del club non conta — compare in qualunque titolo.
    Un titolo scritto **tutto in maiuscolo** (agenzie, siti locali) non ha iniziali
    minuscole: lì i nomi si prendono dalle parole maiuscole, tolte quelle di servizio
    (``_MAIUSCOLE_NON_NOMI``).
    """
    drop = club_tokens or set()
    testo = title or ""
    nomi = re.findall(r"\b[A-ZÀ-Ý][a-zà-ÿ']{3,}\b", testo)
    if len(re.findall(r"[a-zà-ÿ]", testo)) < 4:
        nomi += [w for w in re.findall(r"\b[A-ZÀ-Ý][A-ZÀ-Ý']{3,}\b", testo)
                 if soft_key(w) not in _MAIUSCOLE_NON_NOMI]
    out: set[str] = set()
    for w in nomi:
        k = soft_key(w)
        if len(k) >= 4 and k not in drop:
            out.add(k)
    return out


# Mappa storicamente verificata dei club allenati in precedenza dai tecnici attivi nelle 7 leghe:
# serve a rilevare gli «Ex di turno», un fatto di contorno cruciale nella vita del club.
COACH_FORMER_CLUBS: dict[str, set[str]] = {
    "Gian Piero Gasperini": {"inter", "genoa", "palermo", "crotone"},
    "Massimiliano Allegri": {"milan", "juventus", "cagliari", "sassuolo"},
    "Antonio Conte": {"juventus", "inter", "chelsea", "tottenham", "atalanta", "bari", "siena"},
    "Luciano Spalletti": {"roma", "inter", "napoli", "udinese", "empoli", "sampdoria"},
    "Maurizio Sarri": {"napoli", "juventus", "chelsea", "lazio", "empoli"},
    "Daniele De Rossi": {"roma", "spal"},
    "Raffaele Palladino": {"monza"},
    "Stefano Pioli": {"milan", "fiorentina", "inter", "lazio", "bologna", "chievo", "parma"},
    "Paulo Fonseca": {"roma", "milan", "lille", "porto", "braga"},
    "José Mourinho": {"inter", "roma", "real madrid", "chelsea", "tottenham", "manchester united", "porto"},
    "Manuel Pellegrini": {"real madrid", "villarreal", "malaga", "manchester city", "west ham"},
    "José Bordalás": {"valencia", "alaves", "elche"},
    "Marcelino": {"villarreal", "valencia", "athletic club", "sevilla", "marseille"},
    "Pep Guardiola": {"barcelona", "bayern munchen"},
    "Luis Enrique": {"roma", "barcelona", "celta vigo"},
    "Carlo Ancelotti": {"milan", "real madrid", "chelsea", "paris saint germain", "bayern munchen", "juventus", "napoli", "everton", "parma"},
    "Marco Rose": {"borussia dortmund", "borussia monchengladbach", "rb leipzig"},
    "Niko Kovac": {"eintracht frankfurt", "bayern munchen", "monaco", "vfl wolfsburg"},
    "Graham Potter": {"brighton and hove albion", "chelsea"},
    "Enzo Maresca": {"leicester city", "parma"},
    "Michael Carrick": {"manchester united"},
    "Thomas Frank": {"brentford"},
    "Ruben Amorim": {"sporting cp", "braga", "casa pia"},
    "Sérgio Conceição": {"porto", "nantes", "braga", "vitoria sc"},
    "Roger Schmidt": {"benfica", "bayer leverkusen", "psv eindhoven"},
    "Peter Bosz": {"ajax", "borussia dortmund", "bayer leverkusen", "lyon", "psv eindhoven"},
    "Francesco Farioli": {"nice", "ajax"},
    "Roberto De Zerbi": {"brighton and hove albion", "sassuolo"},
    "Igor Tudor": {"lazio", "marseille", "hellas verona", "udinese"},
    "Alberto Gilardino": {"genoa"},
    "Claudio Ranieri": {"roma", "cagliari", "juventus", "inter", "leicester city", "chelsea", "monaco", "valencia", "atletico madrid", "fiorentina", "napoli", "sampdoria"},
    "Ivan Juric": {"torino", "hellas verona", "genoa", "crotone"},
    "Thiago Motta": {"bologna", "spezia", "genoa"},
    "Vincenzo Italiano": {"fiorentina", "spezia", "trapani"},
    "Paolo Vanoli": {"torino", "venezia"},
    "Marco Baroni": {"lazio", "hellas verona", "lecce", "frosinone"},
    "Davide Nicola": {"cagliari", "empoli", "salernitana", "torino", "genoa", "udinese", "crotone"},
    "Roberto D'Aversa": {"empoli", "lecce", "sampdoria", "parma"},
    "Fabio Pecchia": {"parma", "cremonese", "hellas verona"},
    "Patrick Vieira": {"genoa", "crystal palace", "nice", "strasbourg"},
}


class MatchAnalysis:
    def __init__(self, store: Store) -> None:
        self.store = store
        # token dei nomi di club, calcolati una volta sola (servono al bollettino per non
        # scambiare il nome di una squadra per il soggetto di una notizia)
        self._club_tokens: set[str] | None = None
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
        self.backtest = store.read("backtest")
        self.season_sim = store.read("season_sim")
        self.cup_fixtures = store.read("cup_fixtures")
        self.news_df = store.read("news")
        self.transfers = store.read("transfers")
        self._pools_cache: dict[tuple[int | None, int | None], dict[str, Pool]] | None = None

    # ---- quando arriva il primo gol (ritmo a due tempi calibrato sullo storico) -------------
    def first_goal_clock(self, prediction: dict[str, Any] | None) -> dict[str, Any] | None:
        """Minuti attesi del primo gol, da un ritmo a due tempi MISURATO, non da Poisson puro.

        Il Poisson a tasso costante sbaglia sistematicamente: i gol osservati arrivano più
        tardi (sullo storico di stagione solo il 42,8% cade nel 1° tempo). Qui il tasso è
        r1 = s·λ/45 nel 1° tempo e r2 = (1-s)·λ/45 nel 2°, con s = quota dei gol di 1°
        tempo misurata su events.parquet a ogni build (regola: minuto ≤ 45 vale 1° tempo,
        i 45+x' recupero del 1°). I quartili arrivano in forma chiusa da
        S(t) = e^{-r1 t} (t≤45) e S(t) = e^{-r1·45}e^{-r2 (t-45)} dopo; il verificatore
        ricalcola numeri pubblici dalla stessa formula e dagli stessi eventi, e la card
        dichiara i conteggi (gol, partite) con cui s è stata misurata. Minuti oltre il 90°
        non esistono: un quartile oltre il fischio finale diventa «dopo il 90'», mai un
        numero inventato.
        """
        lam = self._lambdas(prediction)
        if lam is None or self.events.empty or "type" not in self.events.columns:
            return None
        g = self.events[self.events.type == "Goal"]
        if len(g) < 60 or not g.minute.notna().all():
            return None
        s = float((g.minute <= 45).mean())                    # misura, non ipotesi
        lam_tot = float(lam[0] + lam[1])
        r1, r2 = s * lam_tot / 45.0, (1.0 - s) * lam_tot / 45.0
        if r1 <= 0 or r2 <= 0:
            return None
        s_ht = float(np.exp(-r1 * 45.0))                      # P(0-0 all'intervallo)

        def _q(p: float) -> float | None:
            tail = 1.0 - p
            if tail >= s_ht:                                  # il quartile cade nel 1° tempo
                t = -np.log(tail) / r1
            else:
                t = 45.0 + (-np.log(tail) - r1 * 45.0) / r2
            return None if t > 90.0 else float(t)

        # P2.3 (`docs/28` §3): la card era di solo testo. Il micro-visivo è una distribuzione
        # **osservata** (quando è arrivato il primo gol nella stagione, in quarti d'ora) più la
        # banda del modello per QUESTA partita: due cose diverse, etichettate come tali. I
        # conteggi vengono dagli stessi eventi di `s`, quindi il lettore può rifarli.
        first = g.dropna(subset=["minute"]).groupby("match_id").minute.min().clip(lower=1)
        n_first = len(first)
        confini = (0, 15, 30, 45, 60, 75, 10_000)
        etichette = ("1–15'", "16–30'", "31–45'", "46–60'", "61–75'", "76–90'")
        conteggi = [int(((first > lo) & (first <= hi)).sum())
                    for lo, hi in itertools.pairwise(confini)]
        massimo = max(conteggi) or 1
        bins = [{"label": lab, "n": c,
                 "per100": round(100.0 * c / n_first) if n_first else 0,
                 "h": round(100.0 * c / massimo)}
                for lab, c in zip(etichette, conteggi)]
        # quante partite degli stessi eventi sono finite 0-0 (osservato, non modello)
        n_partite_eventi = int(self.events.match_id.nunique())
        senza_gol = (1.0 - n_first / n_partite_eventi) if n_partite_eventi else None
        q = [(p, _q(p)) for p in (0.25, 0.50, 0.75)]

        def _pct(t: float | None) -> float:
            """Posizione sulla scala 0–90 dell'asse del grafico (oltre il 90' = fondo scala)."""
            return 100.0 if t is None else round(min(100.0, 100.0 * t / 90.0), 2)

        return {"q": q,
                "s_half": s, "s_ht": s_ht, "lam": lam_tot,
                "n_goals": len(g), "n_matches": int(g.match_id.nunique()),
                "zero": float(np.exp(-lam_tot)),
                "bins": bins, "n_first": n_first,
                "senza_gol_oss": senza_gol,
                "band": {"from": _pct(q[0][1]), "to": _pct(q[2][1]), "med": _pct(q[1][1]),
                         "q1_oltre": q[0][1] is None, "q3_oltre": q[2][1] is None,
                         "med_oltre": q[1][1] is None},
                "fmt": {0.25: "25°", 0.50: "50°", 0.75: "75°"}}

    # ---- quanto valgono i gol attesi nel suo campionato -------------------------------------
    def league_goals_percentile(self, prediction: dict[str, Any] | None) -> dict[str, Any] | None:
        """Su che scala leggere i gol attesi totali della scheda: il percentile di lega.

        Un λ totale di 3,0 non significa lo stesso ovunque (media stagionale misurata:
        2,6 in ENG1 ma 3,4 in NED1). Qui il λ della scheda viene ordinato dentro la
        distribuzione della stessa quantità su tutte le partite della STESSA lega
        previste dal modello in stagione — così il lettore ottiene «tanto o poco per la
        sua serie» da un conteggio rifaicibile, non da un giudizio. Numeri e frazione
        sono ricalcolati a ogni build da predictions.parquet e verificati pagina per pagina.
        """
        lam = self._lambdas(prediction)
        if lam is None or self.preds.empty or "league_key" not in self.preds.columns:
            return None
        lg = prediction.get("league_key")
        if not lg:
            return None
        p = self.preds[self.preds.league_key == lg].sort_values("made_at").groupby("match_id").tail(1)
        tot = (p.lambda_home.astype(float) + p.lambda_away.astype(float))
        tot = tot[np.isfinite(tot)]
        n = len(tot)
        if n < 30:
            return None
        here = displayed_sum(lam[0], lam[1])   # la somma dei due λ stampati, non dei grezzi
        below = float((tot < here).mean())
        if below >= 0.75:
            label = "fra le partite che promettono più gol"
        elif below <= 0.25:
            label = "fra le partite più chiuse del campionato"
        else:
            label = "nella media del campionato"
        name = {x.key: x.name for x in leagues()}.get(str(lg), str(lg))
        # P2.3 (`docs/28` §3): la barra della posizione. La scala va dal 2° al 98° percentile
        # della distribuzione di lega (gli estremi veri sono code che schiaccerebbero tutto al
        # centro), il riempimento è il percentile già pubblicato in prosa e la tacca è la
        # mediana di lega: si vede a colpo d'occhio da che parte sta questa partita.
        lo_q, hi_q = float(tot.quantile(0.02)), float(tot.quantile(0.98))
        med = float(tot.median())

        def _pos(v: float) -> float:
            return round(min(100.0, max(0.0, 100.0 * (v - lo_q) / (hi_q - lo_q))), 2)

        # La barra è un extra della card, non la card: se la distribuzione di lega è troppo
        # stretta (nessuno spazio fra 2° e 98° percentile) il grafico non direbbe nulla e la
        # card resta com'era — la frase, che è il contenuto, non sparisce mai per un grafico.
        viz = ({"lo": round(lo_q, 2), "hi": round(hi_q, 2), "pct": _pos(here),
                "med_pct": _pos(med), "mean_pct": _pos(float(tot.mean()))}
               if hi_q - lo_q >= 0.2 else None)
        return {"here": here, "n": n, "below": below, "mean": float(tot.mean()),
                "median": med, "label": label, "league": name, "league_key": str(lg),
                "viz": viz}

    # ---- fascia storica del pronostico (backtest fuori campione) ---------------------------
    #: fasce di probabilità del favorito usate per dire «quando il favorito aveva questa
    #: forza, poi ha vinto così spesso». Bordi scelti una volta: 1/3 è il minimo possibile
    #: (tre esiti equiprobabili) e oltre 0,4 il favorito definisce il tipo di partita.
    FAVORITE_BANDS: tuple[tuple[float, float, str], ...] = (
        (0.33, 0.40, "fino al 40%"),
        (0.40, 0.50, "fra 40% e 50%"),
        (0.50, 0.60, "fra 50% e 60%"),
        (0.60, 0.75, "fra 60% e 75%"),
        (0.75, 1.001, "oltre il 75%"),
    )

    def favorite_track_record(self, prediction: dict[str, Any] | None) -> list[dict[str, Any]] | None:
        """Come è andata ogni fascia di pronostico nel backtest: tabella per la scheda.

        Per le 5 fasce di probabilità del favorito pubblica media prevista, frequenza
        osservata del favorito vincente, intervallo di Wilson 95% e numerosità — sempre
        dalla tabella ``backtest`` (previsioni fuori campione, nessun risultato visto).
        Riga ``current=True`` sulla fascia in cui cade QUESTA partita. La frequenza passata
        non è una promessa: il lettore vede numeri e numerosità e può rifare i conti.
        """
        if prediction is None or self.backtest.empty or "outcome" not in self.backtest.columns:
            return None
        p = self.backtest[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
        fav = p.max(axis=1)
        hit = p.argmax(axis=1) == self.backtest["outcome"].to_numpy()
        here = float(max(prediction["p_home"], prediction["p_draw"], prediction["p_away"]))
        out = []
        for lo, hi, label in self.FAVORITE_BANDS:
            m = (fav >= lo) & (fav < hi)
            n = int(m.sum())
            if n < 30:
                continue
            k = int(hit[m].sum())
            wl, wh = wilson_interval(k, n)
            out.append({"lo": lo, "hi": hi, "label": label, "n": n, "k": k,
                        "obs": k / n, "wil_lo": wl, "wil_hi": wh,
                        "pred_mean": float(fav[m].mean()),
                        "current": bool(lo <= here < hi)})
        if not any(r["current"] for r in out):
            return None
        return {"rows": out, "n_tot": len(fav), "fav": here}

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
        fx = self._rest_source()
        if fx.empty:
            return None
        prev = fx[(fx.utc_kickoff < kickoff) & (fx.status == "finished")
                  & ((fx.home_id == team_id) | (fx.away_id == team_id))]
        if prev.empty:
            return None
        return int((kickoff - prev.utc_kickoff.max()).total_seconds() // 86400)

    def _rest_source(self) -> pd.DataFrame:
        """Gare di campionato + coppe europee: il riposo vero conta anche i turni europei.

        Prima (docs/21 Q4) contava solo il campionato: una squadra in campo il martedì
        di Champions mostrava «6 giorni di riposo» nella scheda del sabato. Le coppe
        vivono in ``cup_fixtures`` (calendario raccolto da ``collect_cups``); se la
        tabella non esiste ancora (run precedenti) si degrada al solo campionato.
        """
        fx = self.fixtures
        if fx.empty or self.cup_fixtures.empty:
            return fx if not fx.empty else (self.cup_fixtures if not self.cup_fixtures.empty else fx)
        cup = self.cup_fixtures.copy()
        for col in fx.columns:
            if col not in cup.columns:
                cup[col] = pd.NA
        keep = [c for c in fx.columns] + (["cup_name"] if "cup_name" in cup.columns else [])
        cup = cup[keep]
        return pd.concat([fx, cup], ignore_index=True, sort=False)

    def rest_cup(self, team_id: int, kickoff: datetime) -> str | None:
        """Nome della coppa se l'ultima gara giocata dalla squadra era europea, altrimenti None."""
        src = self._rest_source()
        if src.empty or "cup_name" not in src.columns:
            return None
        prev = src[(src.utc_kickoff < kickoff) & (src.status == "finished")
                   & ((src.home_id == team_id) | (src.away_id == team_id))]
        if prev.empty:
            return None
        last = prev.loc[prev.utc_kickoff.idxmax()]
        name = last["cup_name"]
        return None if pd.isna(name) or not str(name) else str(name)

    def next_commitment(self, team_id: int, after: datetime) -> dict[str, Any] | None:
        """Prima gara ufficiale dopo ``after`` (campionato + coppe): card post-partita.

        Principio di utilità (docs/21 §9): a fine gara la prima domanda è «quando si
        rigioca e con quanto riposo». Il calendario è lo stesso di ``rest_days``
        (``_rest_source``: campionato + coppe europee); contano solo le gare
        ``scheduled`` — rinviate e annullate non danno un prossimo impegno certo.
        """
        src = self._rest_source()
        if src.empty:
            return None
        fut = src[(src.utc_kickoff > after) & (src.status == "scheduled")
                  & ((src.home_id == team_id) | (src.away_id == team_id))]
        if fut.empty:
            return None
        nxt = fut.loc[fut.utc_kickoff.idxmin()]
        is_home = int(nxt.home_id) == team_id
        opp = str(nxt.away_name if is_home else nxt.home_name)
        cup = nxt["cup_name"] if "cup_name" in src.columns else None
        comp = _competition_it(cup) if cup is not None and not pd.isna(cup) and str(cup).strip() else "Campionato"
        rest = int((pd.Timestamp(nxt.utc_kickoff) - pd.Timestamp(after)).total_seconds() // 86400)
        tz = ZoneInfo(load_leagues_config().get("timezone_display", "Europe/Rome"))
        line = (f"{comp} · {opp} {'in casa' if is_home else 'in trasferta'} · "
                f"{it_day_time(nxt.utc_kickoff, tz)} · {rest} {'giorni' if rest != 1 else 'giorno'} di riposo")
        return {"line": line, "rest": rest, "is_cup": comp != "Campionato", "opponent": opp}

    # ---- panchina e posta in gioco (docs/21, P0-1) ------------------------------------------
    def coach(self, team_id: int, kickoff: datetime | None = None) -> dict[str, Any] | None:
        """Allenatore in panchina e da quanto, dagli snapshot FotMob già raccolti.

        Il coach arriva dalla distinta (``role="coach"``): non serve nessuna fonte nuova.
        Il **cambio di panchina** si rileva dalla storia: se negli snapshot raccolti la
        squadra ha avuto due id allenatore diversi, quello corrente è subentrato e
        ``matches`` conta le gare da calendario giocate/disputande da allora fino a
        ``kickoff``. ``prev_name`` è il nome di chi è stato sostituito. Nessun dato
        inventato: se la squadra non ha righe coach, si ritorna ``None`` e la scheda
        mostra un segnaposto onesto.
        """
        if self.lineup.empty or self.fixtures.empty:
            return None
        co = self.lineup[(self.lineup.team_id == team_id) & (self.lineup.role == "coach")]
        if co.empty:
            return None
        ko = self.fixtures.drop_duplicates("match_id").set_index("match_id")["utc_kickoff"]
        co = co[co.match_id.isin(ko.index)].copy()
        if co.empty:
            return None
        co["ko"] = pd.to_datetime(co.match_id.map(ko), utc=True)
        co = co.sort_values("ko", kind="stable")
        if kickoff is not None:
            co = co[co.ko <= pd.Timestamp(kickoff)]
            if co.empty:
                return None
        last = co.iloc[-1]
        cur_id = last.player_id
        if pd.isna(cur_id):
            return {"id": None, "name": str(last.player_name), "matches": 1,
                    "prev_name": None, "first_seen": last.ko}
        streak, prev_name = 0, None
        for pid, name in zip(co.player_id.iloc[::-1], co.player_name.iloc[::-1]):
            if pid == cur_id:
                streak += 1
            else:
                prev_name = str(name)
                break
        return {"id": int(cur_id), "name": str(last.player_name), "matches": int(streak),
                "prev_name": prev_name, "first_seen": co[co.player_id == cur_id].ko.min()}

    def stakes(self, team_name: str) -> dict[str, Any] | None:
        """Cosa vale la stagione della squadra: Monte Carlo di ``season_sim``.

        Gli snapshot P1.7 portano ``p_top_n`` e ``top_n`` dalla configurazione della
        lega. Quelli storici con ``p_top4`` restano leggibili come migrazione, ma non
        vengono più interpretati come soglia universale per tutte le competizioni.
        """
        if self.season_sim.empty or "team" not in self.season_sim.columns:
            return None
        canon = canonical(team_name)
        rows = self.season_sim[self.season_sim.team.map(canonical) == canon]
        if rows.empty:
            return None
        r = rows.iloc[0]
        p_t = float(r.p_title)
        p_r = float(r.p_rel)
        raw_top = r.get("p_top_n")
        legacy_top = raw_top is None or pd.isna(raw_top)
        if legacy_top:
            raw_top = r.get("p_top4")
        if raw_top is None or pd.isna(raw_top):
            p_e = None
            legacy_top = False
        else:
            p_e = float(raw_top)
        raw_n = r.get("top_n")
        top_n = None if raw_n is None or pd.isna(raw_n) else int(raw_n)
        if top_n is None and p_e is not None:
            top_n = 4  # vecchio snapshot: il nome p_top4 documenta la soglia
        if p_t >= 0.15:
            label = "corsa al titolo"
        elif p_e is not None and p_e >= 0.35:
            label = "corsa alla Champions" if top_n and top_n < 4 else "corsa all'Europa"
        elif p_r >= 0.35:
            label = "lotta salvezza"
        elif p_r >= 0.15:
            label = "zona salvezza non lontana"
        else:
            label = "stagione di metà classifica"
        p_e_pct = None if p_e is None else round(p_e * 100)
        return {"p_title": p_t, "p_top_n": p_e, "p_top4": p_e, "p_rel": p_r,
                "ucl_spots": top_n, "ucl_legacy": legacy_top,
                "p_title_pct": round(p_t * 100),
                "p_top_n_pct": p_e_pct, "p_top4_pct": p_e_pct,
                "p_rel_pct": round(p_r * 100),
                "pos_mean": float(r.pos_mean), "exp_points": float(r.exp_points),
                "label": label, "played": int(r.played)}

    def bench_side(self, team_id: int, team_name: str,
                   avg_age: Any = None) -> dict[str, Any] | None:
        """Blocco «Panchina e posta in gioco» di una squadra (coach + stakes + età media)."""
        coach = self.coach(team_id)
        stakes = self.stakes(team_name)
        age = None if avg_age is None or pd.isna(avg_age) else float(avg_age)
        if coach is None and stakes is None and age is None:
            return None
        return {"coach": coach, "stakes": stakes, "avg_age": age}

    # Nazionalità degli allenatori → italiano (i codici ISO grezzi non vanno a schermo).
    _COUNTRY_IT: ClassVar[dict[str, str]] = {"ITA": "Italia", "ESP": "Spagna", "GER": "Germania", "FRA": "Francia",
                   "ENG": "Inghilterra", "NED": "Paesi Bassi", "POR": "Portogallo",
                   "BEL": "Belgio", "SCO": "Scozia", "ARG": "Argentina", "BRA": "Brasile",
                   "CRO": "Croazia", "SRB": "Serbia", "DNK": "Danimarca",
                   "AUT": "Austria", "SUI": "Svizzera", "URU": "Uruguay", "MEX": "Messico",
                   "JPN": "Giappone", "KOR": "Corea del Sud", "POL": "Polonia", "SWE": "Svezia",
                   "NOR": "Norvegia", "TUR": "Turchia", "GRE": "Grecia", "IRL": "Irlanda",
                   "WAL": "Galles", "NIR": "Irlanda del Nord", "MAR": "Marocco", "ALG": "Algeria",
                   "SEN": "Senegal", "GHA": "Ghana", "NGA": "Nigeria", "AUS": "Australia"}

    def bench_deep(self, team_id: int, team_name: str, opp_id: int, opp_name: str,
                   kickoff: datetime, avg_age: Any = None) -> dict[str, Any] | None:
        """La panchina e la posta in gioco come informazioni *utili*, non anagrafica.

        Tutto derivato dai Parquet già raccolti (nessuna fonte nuova, nessun numero
        inventato); ogni riga dichiara il proprio campione:

        - **profilo allenatore**: età e nazionalità dalla distinta, frase di permanenza
          (subentro rilevato dal cambio di id, mai da voci);
        - **rendimento**: punti/gara sulle partite *finite* con l'allenatore corrente
          (le future non contano);
        - **precedenti mirati**: bilancio dell'allenatore corrente contro la squadra
          avversaria (da 3 gare in su) e contro l'allenatore avversario (da 2 in su);
        - **posta in gioco di classifica**: distacco reale dalla zona retrocessione
          (retrocessioni dirette: 18ª posizione su 20 squadre, 17ª su 18) e dal 4º posto
          (linea Europa minima in tutte e 7 le leghe), dalla classifica FotMob viva;
        - **cosa succede**: posizione virtuale in caso di vittoria/sconfitta, per punti e
          differenza reti con le altre partite in sospeso (etichettato «virtuale»);
        - **probabilità di stagione** da ``season_sim`` (Monte Carlo) come prima.
        """
        coach = self.coach(team_id, kickoff)
        stakes = self.stakes(team_name)
        age = None if avg_age is None or pd.isna(avg_age) else float(avg_age)
        out: dict[str, Any] = {"coach": coach, "stakes": stakes, "avg_age": age,
                               "coach_age": None, "coach_country_it": None,
                               "coach_ppg_line": None, "coach_vs_opp_line": None,
                               "coach_vs_coach_line": None, "tenure_line": None,
                               "table_line": None, "virtual_line": None}
        # ---- profilo e rendimento dell'allenatore -------------------------------------------
        if coach is not None and not self.lineup.empty:
            ko = self.fixtures.drop_duplicates("match_id").set_index("match_id")["utc_kickoff"] \
                if not self.fixtures.empty else pd.Series(dtype="datetime64[ns, UTC]")
            ct = self.lineup[(self.lineup.team_id == team_id) & (self.lineup.role == "coach")]
            if not ct.empty and not ko.empty:
                ct = ct[ct.match_id.isin(ko.index)].copy()
                ct["ko"] = pd.to_datetime(ct.match_id.map(ko), utc=True)
                ct = ct[(ct.ko <= pd.Timestamp(kickoff))].sort_values("ko", kind="stable")
                if not ct.empty:
                    last = ct.iloc[-1]
                    age_v, country_v = last.get("age"), last.get("country")
                    if age_v is not None and not pd.isna(age_v):
                        out["coach_age"] = int(age_v)
                    if isinstance(country_v, str) and country_v.strip():
                        out["coach_country_it"] = self._COUNTRY_IT.get(country_v.strip().upper(),
                                                                       country_v.strip().upper())
                    cur = last.player_id
                    fin = self.fixtures[(self.fixtures.status == "finished")
                                        & ((self.fixtures.home_id == team_id)
                                           | (self.fixtures.away_id == team_id))].copy()
                    fin["ko"] = pd.to_datetime(fin.utc_kickoff, utc=True)
                    fin = fin[fin.ko <= pd.Timestamp(kickoff)]
                    ids = set(ct.loc[ct.player_id == cur, "match_id"])
                    mine = fin[fin.match_id.isin(ids)]
                    if not mine.empty:
                        pts = sum(
                            3 if ((r.home_id == team_id and r.home_goals > r.away_goals)
                                  or (r.away_id == team_id and r.away_goals > r.home_goals))
                            else 1 if r.home_goals == r.away_goals else 0
                            for r in mine.itertuples(index=False))
                        ppg = pts / len(mine)
                        out["coach_ppg_line"] = (
                            f"{ppg:.1f}".replace(".", ",") +
                            (" punti/gara su 1 gara finita" if len(mine) == 1
                             else f" punti/gara su {len(mine)} gare finite"))
                    # precedenti contro l'avversaria e contro l'allenatore avversario
                    if pd.notna(cur):
                        vs = mine[((mine.home_id == opp_id) | (mine.away_id == opp_id))]
                        if len(vs) >= 3:
                            w = sum(1 for r in vs.itertuples(index=False)
                                    if (r.home_id == team_id and r.home_goals > r.away_goals)
                                    or (r.away_id == team_id and r.away_goals > r.home_goals))
                            d = sum(1 for r in vs.itertuples(index=False) if r.home_goals == r.away_goals)
                            l = len(vs) - w - d
                            out["coach_vs_opp_line"] = (
                                f"bilancio contro {opp_name}: {w}V {d}N {l}P su {len(vs)} gare")
                        opp_coach = self.coach(opp_id, kickoff)
                        if opp_coach and opp_coach.get("id") is not None:
                            occ = self.lineup[(self.lineup.role == "coach")
                                              & (self.lineup.player_id == opp_coach["id"])]
                            hv = mine[mine.match_id.isin(set(occ.match_id))]
                            if len(hv) >= 2:
                                w = sum(1 for r in hv.itertuples(index=False)
                                        if (r.home_id == team_id and r.home_goals > r.away_goals)
                                        or (r.away_id == team_id and r.away_goals > r.home_goals))
                                d = sum(1 for r in hv.itertuples(index=False)
                                        if r.home_goals == r.away_goals)
                                l = len(hv) - w - d
                                out["coach_vs_coach_line"] = (
                                    f"scontro diretto con {opp_coach['name']}: "
                                    f"{w}V {d}N {l}P su {len(hv)} gare")
            if coach.get("prev_name"):
                out["tenure_line"] = (f"panchina nuova: {coach['matches']}ª gara dal subentro "
                                      f"a {coach['prev_name']}")
            else:
                out["tenure_line"] = (f"panchina invariata da {coach['matches']} "
                                      f"{'gara' if coach['matches'] == 1 else 'gare'} "
                                      f"nel nostro archivio")
        # ---- posta in gioco di classifica + posizione virtuale -------------------------------
        st = self.standing(team_name)
        if st and not self.fm_standings.empty:
            code = st.get("league_code")
            tab = self.fm_standings[self.fm_standings.league_code == code] if code else self.fm_standings
            tab = tab.drop_duplicates("team_id")
            n_teams = len(tab)
            if n_teams >= 4 and st.get("points") is not None and not pd.isna(st["points"]):
                pts, gd, rank = int(st["points"]), int(st.get("goal_diff") or 0), int(st["rank"])
                releg_start = n_teams - 2 if n_teams == 20 else n_teams - 1
                by_rank = tab.set_index("rank")
                if releg_start in by_rank.index and rank < releg_start:
                    marg = pts - int(by_rank.loc[releg_start, "points"])
                    gap_rel = (f"{marg} {'punto' if marg == 1 else 'punti'} sopra la zona "
                               f"retrocessione" if marg > 0 else "a pari punti con la zona retrocessione")
                elif releg_start - 1 in by_rank.index:
                    need = int(by_rank.loc[releg_start - 1, "points"]) - pts
                    gap_rel = (f"{need} {'punto' if need == 1 else 'punti'} dalla salvezza diretta"
                               if need > 0 else "in zona salvezza diretta")
                else:
                    gap_rel = None
                ucl_n = self.ucl_spots(code)
                if ucl_n is not None and ucl_n in by_rank.index:
                    if rank <= ucl_n:
                        # Manteniamo «Europa» per la frase storica della scheda; il
                        # numero di posizione è quello ufficiale configurato per lega.
                        gap_eur = (f"in zona Europa ({ucl_n}º posto o meglio)"
                                   if ucl_n == 4 else
                                   f"in zona Champions ({ucl_n}º posto o meglio)")
                    else:
                        ge = int(by_rank.loc[ucl_n, "points"]) - pts
                        gap_eur = (
                            f"{ge} {'punto' if ge == 1 else 'punti'} dal {ucl_n}º posto"
                            if ge > 0 else f"a pari punti col {ucl_n}º posto"
                        )
                else:
                    gap_eur = None
                # concordanza: «1º con 1 punti» non è italiano; due righe più sopra lo stesso
                # file concordava già «1 punto / 2 punti dal Nº posto» (audit 18/09/2026)
                parts = [f"{rank}º con {it_plural(pts, 'punto', 'punti')}"]
                if gap_rel:
                    parts.append(gap_rel)
                if gap_eur:
                    parts.append(gap_eur)
                out["table_line"] = " · ".join(parts)

                def _virtual(my_pts: int) -> int:
                    better = 0
                    for r in tab.itertuples(index=False):
                        if int(r.team_id) == int(st.get("team_id", -1)):
                            continue
                        op, og = int(r.points), int(r.goal_diff or 0)
                        if op > my_pts or (op == my_pts and og > gd):
                            better += 1
                    return better + 1

                pw, pl = _virtual(pts + 3), _virtual(pts)
                out["virtual_line"] = (f"con una vittoria {pw}º · con una sconfitta {pl}º "
                                       f"(classifica virtuale, altre gare in sospeso)")
        if all(out[k] is None for k in ("coach", "stakes", "avg_age", "table_line", "virtual_line")):
            return None
        return out

    # ---- clima del club (docs/21 P2-6, direttiva «sezioni utilissime») ------------------------
    # Soglie dichiarate e pubblicate nella nota della card: niente punteggio sintetico,
    # ogni riga è un fatto misurato col proprio criterio (regola B8: prima si dimostra).
    MOOD_LOSS_STREAK = 3        # perse consecutive → «crisi di risultati»
    MOOD_NOWIN = 4              # gare senza vittoria → «non vince da»
    MOOD_UNBEATEN = 5           # gare senza sconfitte → clima sereno
    MOOD_DRY = 3                # gare consecutive senza segnare
    MOOD_XPTS_GAP = 2.0         # punti di scarto fra fatti e attesi (xPTS)
    MOOD_ABSENT_N = 4           # assenti → infermeria pesante
    MOOD_ABSENT_STARTERS = 2    # titolari abituali fuori → infermeria pesante
    MOOD_ABSENT_CONTRIB = 0.5   # xG+xA/gara portati via dagli assenti
    MOOD_REST_SHORT = 3         # giorni di riposo → corto
    MOOD_CONGEST_DAYS = 10      # finestra di congestione
    MOOD_CONGEST_N = 3          # gare giocate nella finestra → congestione

    def club_mood(self, match_id: int, team_id: int, team_name: str,
                  kickoff: datetime) -> list[dict[str, Any]]:
        """Il «clima del club» come fatti misurati, non come aggettivi.

        Segnali derivati solo da dati già raccolti (forma, xPTS, panchina, infermeria,
        riposo e congestione anche coppe), ognuno con la propria soglia dichiarata nella
        nota della card; toni: ``bad`` (allarme), ``warn`` (attenzione), ``good`` (sereno).
        Se nessun segnale supera le soglie la squadra resta senza righe: la card lo dice
        («nessun segnale anomalo») invece di inventare un clima neutro a parole.
        """
        out: list[dict[str, Any]] = []
        f = self.form(team_id, kickoff)
        seq = [r["res"] for r in f]
        lose = nowin = unbeaten = dry = 0
        for r in reversed(seq):
            if r == "P":
                lose += 1
            else:
                break
        for r in reversed(seq):
            if r == "V":
                break
            nowin += 1
        for r in reversed(seq):
            if r == "P":
                break
            unbeaten += 1
        for r in reversed(f):
            if r["gf"] == 0:
                dry += 1
            else:
                break
        if lose >= self.MOOD_LOSS_STREAK:
            out.append({"tone": "bad", "text": f"crisi di risultati: {lose} sconfitte consecutive"})
        elif nowin >= self.MOOD_NOWIN:
            nd = sum(1 for r in seq[-nowin:] if r == "N")
            out.append({"tone": "warn",
                        "text": f"non vince da {nowin} gare ({nd} N, {nowin - nd} P)"})
        elif unbeaten >= self.MOOD_UNBEATEN:
            out.append({"tone": "good",
                        "text": f"imbattuta da {unbeaten} gare: clima di fiducia"})
        if dry >= self.MOOD_DRY:
            out.append({"tone": "bad", "text": f"attacco a secco: {dry} gare senza segnare"})
        xg = self.season_xg(team_name, team_id)
        if xg and xg.get("xpts") is not None and xg.get("pts") is not None:
            d = float(xg["pts"]) - float(xg["xpts"])
            if d <= -self.MOOD_XPTS_GAP:
                out.append({"tone": "warn",
                            "text": f"raccoglie {str(round(abs(d), 1)).replace('.', ',')} punti "
                                    f"meno di quanto crea (xPTS): calo di concretezza o sfortuna"})
            elif d >= self.MOOD_XPTS_GAP:
                out.append({"tone": "warn",
                            "text": f"{str(round(d, 1)).replace('.', ',')} punti più di quanto "
                                    f"crea: rendimento sopra la qualità del gioco, regressione "
                                    f"possibile"})
        coach = self.coach(team_id, kickoff)
        if coach and coach.get("prev_name"):
            out.append({"tone": "warn",
                        "text": f"{coach['matches']}ª gara dal subentro a {coach['prev_name']}: "
                                f"il cambio panchina è una variabile di shock"})
        ab = self.absences_weight(match_id, team_id)
        if ab and (ab["n"] >= self.MOOD_ABSENT_N
                   or ab["starters_out"] >= self.MOOD_ABSENT_STARTERS
                   or (ab.get("contrib_lost_p90") or 0) >= self.MOOD_ABSENT_CONTRIB):
            bits = [f"infermeria pesante: {ab['n']} assenti"]
            if ab["starters_out"]:
                # concordanza: con un solo titolare «di cui 1 titolari abituali» non è italiano
                # (25 occorrenze su 22 schede, audit 18/09). it_plural è lo stesso helper che
                # match.html:284 e _sapere_assenze usano già per la stessa frase.
                bits.append("di cui " + it_plural(ab["starters_out"], "titolare abituale",
                                                  "titolari abituali"))
            if ab.get("contrib_lost_p90"):
                bits.append(f"≈ {str(round(ab['contrib_lost_p90'], 1)).replace('.', ',')} "
                            f"xG+xA a partita in meno")
            value = sum(u.get("value") or 0 for u in self.unavailable(match_id, team_id))
            if value >= 30_000_000:
                bits.append(f"≈ {round(value / 1_000_000)} M€ di mercato ai box")
            out.append({"tone": "warn", "text": ", ".join(bits)})
        rest = self.rest_days(team_id, kickoff)
        if rest is not None and rest <= self.MOOD_REST_SHORT:
            cup = self.rest_cup(team_id, kickoff)
            out.append({"tone": "warn",
                        "text": f"riposo corto: {rest} {'giorno' if rest == 1 else 'giorni'}"
                                + (f", con un turno di {cup} in mezzo" if cup else "")})
        src = self._rest_source()
        if not src.empty:
            lo = pd.Timestamp(kickoff) - pd.Timedelta(days=self.MOOD_CONGEST_DAYS)
            rec = src[(src.status == "finished")
                      & (pd.to_datetime(src.utc_kickoff, utc=True) >= lo)
                      & (pd.to_datetime(src.utc_kickoff, utc=True) < pd.Timestamp(kickoff))
                      & ((src.home_id == team_id) | (src.away_id == team_id))]
            if len(rec) >= self.MOOD_CONGEST_N:
                out.append({"tone": "warn",
                            "text": f"congestione: {len(rec)} gare giocate negli ultimi "
                                    f"{self.MOOD_CONGEST_DAYS} giorni"})
        return out

    # ---- notizie per partita (docs/21 P1-5, rifatte in docs/24 §3 e §3.5) -------------------
    # Card «Vita del club»: le regole approvate il 2026-09-17 valgono per **ogni** partita in
    # programma, non per l'esempio su cui sono nate. Finestra di 7 giorni pesata sulle ore al
    # fischio d'inizio, rilevanza per questa partita, gate «il fatto deve poter spostare
    # qualcosa», diversità e trasparenza sui conteggi.
    NEWS_WINDOW_DAYS: ClassVar[int] = 7          # finestra vera: una settimana
    NEWS_OLD_HORIZON_DAYS: ClassVar[int] = 45    # quanto indietro si contano i «troppo vecchi»
    NEWS_LIMIT: ClassVar[int] = 3                # fatti pubblicati per squadra
    NEWS_CATEGORY_LIMIT: ClassVar[int] = 2       # non più di due fatti della stessa categoria
    NEWS_RESERVE_LIMIT: ClassVar[int] = 2        # «in riserva»: i primi che non entrano nei tre
    # «Da sapere»: tetto alle righe derivate dai nostri dati. Oltre questa soglia la card
    # smette di essere un riassunto e diventa un elenco (docs/25 §5).
    SAPERE_MAX: ClassVar[int] = 8
    # temi che la scheda copre già altrove: ripeterli nella card non aggiunge nulla
    NEWS_ALTROVE: ClassVar[frozenset[str]] = frozenset({"infortuni", "squalifiche", "mercato"})

    def team_tokens(self, team_name: str) -> set[str]:
        """Token distintivi del nome squadra (per capire di chi parla un titolo)."""
        key = soft_key(team_name or "")
        drop = {"calcio", "club", "fc", "ac", "as", "ss", "ssc", "us", "sc", "cf", "afc",
                "cp", "cd", "sv", "vfl", "vfb", "tsg", "bsc", "de", "del"}
        return {t for t in key.split() if len(t) >= 4 and t not in drop}

    def team_news(self, team_id: int, team_name: str, kickoff: datetime,
                  days: int | None = None, limit: int | None = None,
                  squad: list[dict[str, Any]] | None = None,
                  seen: set[str] | None = None,
                  opponent: str | None = None,
                  coach: str | None = None) -> dict[str, Any]:
        """Bollettino stampa della squadra: solo i fatti che possono spostare qualcosa.

        Rifatto in ``docs/24`` §3 e poi in §3.5 dopo il confronto con l'utente del
        2026-09-16/17. Difetti misurati nella versione precedente, tutti corretti qui:
        pubblicava per il 38% dirette, pronostici e «dove vederla»; non aveva un limite per
        categoria; non distingueva un fatto da un annuncio; e quando non c'era nulla non lo
        diceva con i numeri.

        Regole (deterministiche e verificabili):

        1. **finestra vera**: ``kickoff − 7 giorni ≤ data ≤ kickoff``, senza recupero. Una
           notizia di tre settimane prima non entra: l'utente l'ha rifiutata due volte. Le
           righe più vecchie della finestra si **contano** (``vecchie``), così la card può
           dichiararle invece di far credere di non averle viste;
        2. **filtro e categoria** da :func:`fda.sources.news.classify_news` (dirette,
           pronostici, pagelle, biglietti e cronaca fuori), nelle lingue delle due edizioni;
        3. **già altrove**: infortuni, squalifiche e mercato hanno la loro card in questa
           pagina e qui non si ripetono (``NEWS_ALTROVE``);
        4. **gate del valore** da :func:`fda.sources.news.news_value`: annunci e logistica
           (``annunci``) e fatti senza frizione né decisione (``piatti``) restano fuori e
           vengono contati — è la correzione chiesta dall'utente («info non recentissime o
           non inerenti», «con queste notizie non ci faccio nulla»);
        5. **gate di soggetto**: il titolo deve parlare della squadra o citare un suo
           giocatore/allenatore;
        6. **punteggio**: categoria + sostanza (numeri e decisioni sopra le dichiarazioni) +
           freschezza (ore al calcio d'inizio) + rilevanza per questa partita (avversario,
           allenatore, giocatori della distinta di oggi; penalità se il titolo parla di
           un'altra squadra). Si ordina per punteggio, poi per data — la versione vecchia
           ordinava a parità di peso per data **crescente**;
        7. **diversità**: al massimo 3 fatti per squadra, 2 per categoria, 1 per soggetto;
           chi resta fuori per il limite dei tre non si perde: i primi due restano «in
           riserva» e la card li mostra come tali;
        8. **dedup**: per titolo normalizzato, con l'insieme condiviso fra le due squadre
           della stessa partita, così lo stesso pezzo non compare due volte in pagina.

        Ritorna le voci e i conteggi dell'imbuto (esaminate, pubblicate, annunci, servizio o
        cronaca, non spostano nulla, troppo vecchi, oltre il limite, in riserva).
        """
        days = self.NEWS_WINDOW_DAYS if days is None else days
        limit = self.NEWS_LIMIT if limit is None else limit
        out: dict[str, Any] = {"notizie": [], "riserva": [], "esaminate": 0, "pubblicate": 0,
                               "scartate": 0, "oltre": 0, "annunci": 0, "piatti": 0,
                               "altre": 0, "doppioni": 0, "vecchie": 0, "pertinenti": 0,
                               "lingua": 0,
                               "finestra": days, "limite": limit,
                               "categoria_limite": self.NEWS_CATEGORY_LIMIT,
                               "riserva_limite": self.NEWS_RESERVE_LIMIT}
        if self.news_df.empty:
            return out
        ko = pd.Timestamp(kickoff)
        pa = pd.to_datetime(self.news_df.published_at, utc=True)
        miei = self.news_df.team_id == team_id
        df = self.news_df[miei & (pa >= ko - pd.Timedelta(days=days)) & (pa <= ko)]
        out["esaminate"] = len(df)
        # le righe più vecchie della finestra non si pubblicano ma si contano (fino a un
        # orizzonte utile): la card dice quante ne ha lasciate indietro, e il lettore sa che
        # non è che non le abbiamo viste
        fuori = self.news_df[miei & (pa >= ko - pd.Timedelta(days=self.NEWS_OLD_HORIZON_DAYS))
                             & (pa < ko - pd.Timedelta(days=days))]
        out["vecchie"] = len(fuori)
        tokens = self.team_tokens(team_name)
        avversario = self.team_tokens(opponent or "")
        # entità della squadra citabili in un titolo: nomi della distinta di questa partita
        # (titolari, panchina, indisponibili, allenatore) più i giocatori con presenze in
        # stagione: bastano per riconoscere «Zirkzee», «Abde», «Bordalás» in un titolo.
        squad = squad or []
        entities: dict[str, str] = {}
        for r in squad:
            full = str(r.get("name") or "").strip()
            if full:
                entities[full.lower()] = str(r.get("status") or "")
        for full in self.team_player_names(team_id):
            entities.setdefault(full.lower(), "")
        for full, status in list(entities.items()):
            last = full.split()[-1]
            if len(last) >= 5:
                entities.setdefault(last, status)
        if coach:
            entities.setdefault(str(coach).lower(), "coach")
            for part in soft_key(str(coach)).split():
                if len(part) >= 5:
                    entities.setdefault(part, "coach")

        # nomi propri di club: «Milan» in un titolo di Inter non è un soggetto interessante
        # (il club lo si cita sempre), i nomi di persona sì
        if self._club_tokens is None:
            self._club_tokens = set()
            if not self.fixtures.empty:
                for nm in pd.concat([self.fixtures.home_name, self.fixtures.away_name]).dropna():
                    self._club_tokens |= self.team_tokens(str(nm))

        def soggetti(title: str) -> set[str]:
            """Soggetto della notizia (vedi :func:`news_subjects`).

            Fra i nomi esclusi ci sono quelli dei club — tutti, non solo i due di questa
            partita: «Inter» apre qualunque titolo della colonna di Inter e non distingue
            una notizia dall'altra.
            """
            return news_subjects(title, set(self._club_tokens or ()) | tokens)

        def subject_ok(title: str) -> bool:
            key = soft_key(title or "")
            if tokens and any(t in key for t in tokens):
                return True
            low = (title or "").lower()
            return any(nm in low for nm in entities if len(nm) >= 5)

        def nota(title: str) -> str:
            """Collegamento con i nostri dati: a chi si riferisce la notizia, e come stava."""
            low = (title or "").lower()
            for nm, status in sorted(entities.items(), key=lambda kv: -len(kv[0])):
                if len(nm) < 5 or nm not in low:
                    continue
                nome = nm if nm[0].isupper() else nm.title()
                if status == "unavailable":
                    return f"«{nome}» è nella lista indisponibili di FotMob per questa gara"
                if status == "starter":
                    return f"«{nome}» è in distinta come titolare: la notizia può essere più fresca del dato"
                if status == "sub":
                    return f"«{nome}» è in distinta fra i giocatori a disposizione"
                if status == "coach":
                    return f"«{nome}» è l'allenatore di questa squadra"
                return ""
            return ""

        def altra_squadra(title: str) -> str | None:
            """Il titolo parla di **un'altra** squadra del nostro archivio, non di questa.

            Misurato il 2026-09-17: «Indagine a Roma: pressioni su Lotito a cedere la
            Lazio» finiva nella colonna della Roma (Roma è la città, la procura e il club
            insieme). Se manca l'avversario, un nostro tesserato (allenatore o giocatore
            della distinta) e un token distintivo della squadra, l'unico aggancio è un
            altro club: la voce non riguarda questa gara e si conta a parte.
            """
            key = soft_key(title or "")
            if avversario and any(t in key for t in avversario):
                return None
            if coach and soft_key(str(coach)) in key:
                return None
            if any(soft_key(str(nm)) in key for nm in entities if len(nm) >= 5):
                return None
            if any(t in key for t in tokens if len(t) >= 5):
                return None
            for c in sorted(self._club_tokens or ()):
                if len(c) >= 5 and c not in tokens and c not in avversario and c in key:
                    return c
            return None

        def rilevanza(title: str) -> float:
            """Quanto la notizia riguarda **questa** partita (docs/24 §3.5).

            +5 avversario o vigilia, +4 allenatore, +3 un giocatore della distinta, +2 la
            squadra; **−4** se il titolo nomina un altro club: una dichiarazione su
            un'altra squadra non è informazione per questa gara.
            """
            key = soft_key(title or "")
            low = (title or "").lower()
            p = 0.0
            if avversario and any(t in key for t in avversario):
                p += 5
            if re.search(r"previa|ante el |ante la |jornada \d|vigilia|vespera|preview|"
                         r"vorbericht|avant-?match|voorbeschouwing|pr[eé]via|partidazo",
                         title or "", re.IGNORECASE):
                p += 5
            if coach and (soft_key(str(coach)) in key or str(coach).lower() in low
                          or any(len(t) >= 5 and t in key
                                 for t in soft_key(str(coach)).split())):
                p += 4
            if any(nm in low for nm in entities if len(nm) >= 5):
                p += 3
            if tokens and any(t in key for t in tokens):
                p += 2
            altri = {c for c in (self._club_tokens or ())
                     if len(c) >= 5 and c not in tokens and c not in avversario}
            if any(c in key for c in altri):
                p -= 4
            return p

        rows = [r._asdict() for r in df.itertuples(index=False)]
        visti: set[str] = seen if seen is not None else set()
        scelte: list[dict[str, Any]] = []
        for r in rows:
            title = str(r.get("title") or "").strip()
            key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
            # La lingua viene **prima** di tutto (docs/25 §5): se il titolo non è
            # italiano, dire «servizio o cronaca» è falso — su Málaga-Villarreal la card
            # diceva «132 titoli esaminati · 131 servizio o cronaca» quando 116 di
            # quelli erano semplicemente in spagnolo o in inglese. Il motivo dello
            # scarto deve essere quello vero, e in italiano.
            if not title or not is_italian_news(title, r.get("description") or ""):
                out["lingua"] += 1
                continue
            topic, _evidence = classify_news(title, r.get("description"), r.get("source"))
            if topic is None:
                out["scartate"] += 1
                continue
            if not key or key in visti or not subject_ok(title):
                out["scartate"] += 1
                continue
            if topic in self.NEWS_ALTROVE:
                # infortuni, squalifiche e mercato hanno già la loro card in questa pagina:
                # ripeterli qui era una delle cose che l'utente non voleva più leggere
                out["scartate"] += 1
                continue
            motivo = news_value(title, r.get("description"), r.get("source"))
            if motivo is not None:
                out["annunci" if motivo == "annuncio" else "piatti"] += 1
                continue
            if altra_squadra(title):
                out["altre"] += 1
                continue
            # la chiave entra subito nell'insieme condiviso: il feed ripubblica lo stesso
            # articolo con data aggiornata (misurato: 231 coppie (squadra, url) con più righe)
            visti.add(key)
            branch = self._news_branch(r)
            # «sintesi» solo se aggiunge qualcosa al titolo: per Google News il brano È il
            # titolo con la testata appiccicata, e ripeterlo era il difetto della vecchia card
            sintesi = branch if len(branch) >= 60 and title[:40].lower() not in branch.lower() else ""
            if sintesi and not is_italian_news(sintesi):
                sintesi = ""
            published = pd.to_datetime(r.get("published_at"), utc=True)
            ore = max(0.0, (ko - published).total_seconds() / 3600.0)
            punteggio = (TOPIC_WEIGHTS.get(topic, 0)
                         + news_substance(f"{title} {branch}")
                         + news_freshness(ore)
                         + rilevanza(title))
            scelte.append({"title": title, "source": str(r.get("source") or ""),
                           "url": str(r.get("url") or ""), "published_at": published,
                           "topic": topic, "topic_label": TOPIC_LABELS.get(topic, topic),
                           "sintesi": sintesi, "why": nota(title), "ore": ore,
                           "punteggio": punteggio, "_key": key})

        def un_soggetto(voci: list[dict[str, Any]]) -> list[dict[str, Any]]:
            """Una voce per categoria e soggetto, nell'ordine in cui arrivano.

            Due voci della stessa categoria sullo stesso nome proprio sono lo stesso fatto
            raccontato due volte. Il filtro va applicato **dopo** l'ordinamento per
            (punteggio, data): le righe del Parquet arrivano in ordine di data crescente e
            filtrando in lettura restava la voce più vecchia.
            """
            tenute: list[dict[str, Any]] = []
            visti_sog: dict[str, set[str]] = {}
            for v in voci:
                sog = soggetti(v["title"])
                if sog and sog & visti_sog.get(v["topic"], set()):
                    continue
                visti_sog.setdefault(v["topic"], set()).update(sog)
                tenute.append(v)
            return tenute

        def un_evento(voci: list[dict[str, Any]]) -> list[dict[str, Any]]:
            """Un fatto per evento, anche fra categorie diverse (docs/24 §3, regola 8).

            `un_soggetto` guarda dentro la stessa categoria; ma lo stesso episodio può
            arrivare con due categorie diverse — misurato il 2026-09-17 sui titoli della
            seconda edizione: per il Betis la difesa di Pellegrini su Abde compariva due
            volte, come «Dichiarazioni» e come «Club». Qui la chiave è la **persona di
            questa partita** (allenatore o giocatore della distinta) nominata nel titolo:
            se un fatto la nomina e un altro fatto tenuto la nomina già, è lo stesso
            evento raccontato due volte e resta solo il primo (i fatti sono in ordine di
            punteggio). Niente persone nel titolo = nessun vincolo.
            """
            tenute: list[dict[str, Any]] = []
            gia: set[str] = set()
            for v in voci:
                low = str(v["title"]).lower()
                persone = {nm for nm in entities if len(nm) >= 5 and nm in low}
                if persone & gia:
                    out["doppioni"] += 1
                    continue
                gia |= persone
                tenute.append(v)
            return tenute

        scelte.sort(key=lambda v: (-v["punteggio"], -v["published_at"].value))
        tenute = un_evento(un_soggetto(scelte))
        out["scartate"] += len(scelte) - len(tenute) - out["doppioni"]
        out["pertinenti"] = len(tenute)
        # diversità: non più di due fatti della stessa categoria — il punteggio decide quali
        # due (prima i più freschi e più sostanziosi), e chi resta fuori si conta a parte
        pubblicabili: list[dict[str, Any]] = []
        per_categoria: dict[str, int] = {}
        for v in tenute:
            if per_categoria.get(v["topic"], 0) >= self.NEWS_CATEGORY_LIMIT:
                out["oltre"] += 1
                continue
            per_categoria[v["topic"]] = per_categoria.get(v["topic"], 0) + 1
            pubblicabili.append(v)
        for v in pubblicabili[:limit]:
            v.pop("_key", None)
            out["notizie"].append(v)
        for v in pubblicabili[limit:limit + self.NEWS_RESERVE_LIMIT]:
            v.pop("_key", None)
            out["riserva"].append(v)
        out["pubblicate"] = len(out["notizie"])
        return out

    def news_sapere(self, match_id: int, home_id: int, home_name: str,
                    away_id: int, away_name: str, kickoff: datetime) -> list[dict[str, str]]:
        """Blocco «Da sapere»: fatti di contorno, derivati dai nostri dati (docs/24 §3.5).

        Due regole, entrambe verificabili e senza testo inventato:

        - **dove si gioca**: se lo stadio di questa partita non è quello delle ultime gare
          interne della squadra di casa, la card lo dice, con le due capienze. È il caso
          della stagione a La Cartuja: il dato della partita e quello delle gare precedenti
          raccontano due stadi diversi, e chi legge deve saperlo;
        - **panchina nuova**: se l'allenatore è in carica da poche gare (≤3), la panchina è
          appena cambiata — un fatto che pesa sulla lettura della partita.

        Niente da dire = nessun blocco: la card non riempie lo spazio.
        """
        out: list[dict[str, str]] = []
        if self.info.empty or self.fixtures.empty or "stadium_name" not in self.info.columns:
            return out
        oggi = self.info[self.info.match_id == match_id]
        if not oggi.empty:
            riga = _first(oggi)
            stadio = str(_val(riga, "stadium_name") or "").strip()
            capienza = _val(riga, "stadium_capacity")
            casa = self.fixtures[(self.fixtures.home_id == home_id)
                                 & (self.fixtures.status == "finished")]
            ids = {int(x) for x in casa.match_id}
            if stadio and ids:
                st = self.info[self.info.match_id.isin(ids) & self.info.stadium_name.notna()]
                if len(st) >= 2:
                    conteggio = st.stadium_name.astype(str).value_counts()
                    abituale = str(conteggio.index[0])
                    cap_ab = None
                    righe_ab = st[st.stadium_name.astype(str) == abituale]
                    if not righe_ab.empty:
                        cap_ab = _val(_first(righe_ab), "stadium_capacity")
                    if abituale and abituale != stadio:
                        def posti(cap: Any) -> str:
                            try:
                                return f" ({int(cap):,} posti)".replace(",", ".")
                            except (TypeError, ValueError):
                                return ""
                        out.append({
                            "titolo": "Dove si gioca",
                            "testo": (f"il dato di questa partita indica {stadio}{posti(capienza)}; "
                                      f"le ultime {len(st)} gare interne di {home_name} si sono "
                                      f"giocate a {abituale}{posti(cap_ab)}.")})
        for tid, nome, opp_name, verbo in (
            (home_id, home_name, away_name, "allenato"),
            (away_id, away_name, home_name, "guidato"),
        ):
            co = self.coach(tid, kickoff)
            if not co:
                continue
            cname = str(co.get("name") or "").strip()
            former = COACH_FORMER_CLUBS.get(cname, set())
            if former and any(f in soft_key(opp_name) for f in former):
                out.append({
                    "titolo": "Ex di turno",
                    "testo": f"partita speciale per {cname}: affronta {opp_name}, squadra che ha già {verbo} in carriera.",
                })
            gare = co.get("matches")
            try:
                gare = int(gare)
            except (TypeError, ValueError):
                continue
            if gare <= 3:
                testo = (f"{nome} ha cambiato allenatore da poco: {co.get('name')} è in "
                        f"carica da {it_plural(gare, 'gara')}")
                if co.get("prev_name"):
                    testo += f", ha preso il posto di {co['prev_name']}"
                out.append({"titolo": "Panchina nuova", "testo": testo + "."})
        # Strisce aperte e digiuni di campionato (fatti oggettivi dai nostri dati)
        if not self.fixtures.empty:
            fin = self.fixtures[self.fixtures.status == "finished"]
            for tid, nome in ((home_id, home_name), (away_id, away_name)):
                matches = fin[(fin.utc_kickoff < kickoff) & ((fin.home_id == tid) | (fin.away_id == tid))]
                if len(matches) < 3:
                    continue
                recent = matches.sort_values("utc_kickoff").tail(8)
                res = []
                for _, r in recent.iterrows():
                    is_h = (r.home_id == tid)
                    hg, ag = r.home_goals, r.away_goals
                    if hg is None or ag is None:
                        continue
                    w = (hg > ag) if is_h else (ag > hg)
                    l = (hg < ag) if is_h else (ag < hg)
                    res.append("W" if w else "L" if l else "D")
                loss_streak = 0
                for ch in reversed(res):
                    if ch == "L":
                        loss_streak += 1
                    else:
                        break
                if loss_streak >= 3:
                    out.append({
                        "titolo": "Momento delicato",
                        "testo": f"{nome} è reduce da {it_plural(loss_streak, 'sconfitta')} consecutiv{'a' if loss_streak == 1 else 'e'} in campionato.",
                    })
                    continue
                winless = 0
                d_in = l_in = 0
                for ch in reversed(res):
                    if ch in ("L", "D"):
                        winless += 1
                        if ch == "L":
                            l_in += 1
                        else:
                            d_in += 1
                    else:
                        break
                if winless >= 5:
                    p_text = f"{it_plural(d_in, 'pareggio')}"
                    s_text = f"{it_plural(l_in, 'sconfitta')}"
                    out.append({
                        "titolo": "Digiuno di vittorie",
                        "testo": f"{nome} non vince da {it_plural(winless, 'gara')} di campionato ({p_text}, {s_text}).",
                    })
                    continue
                unbeaten = 0
                w_un = d_un = 0
                for ch in reversed(res):
                    if ch in ("W", "D"):
                        unbeaten += 1
                        if ch == "W":
                            w_un += 1
                        else:
                            d_un += 1
                    else:
                        break
                if unbeaten >= 5:
                    v_text = f"{it_plural(w_un, 'vittoria', 'vittorie')}"
                    p_text = f"{it_plural(d_un, 'pareggio')}"
                    out.append({
                        "titolo": "Striscia positiva",
                        "testo": f"{nome} è imbattuto da {it_plural(unbeaten, 'partita')} consecutiv{'a' if unbeaten == 1 else 'e'} ({v_text}, {p_text}).",
                    })
        # Fatti di rendimento dentro le proprie mura (docs/25 §4): servono quando la
        # rassegna stampa in italiano non copre la squadra. Senza queste due righe, con
        # il filtro lingua del 17/09/2026 la card restava vuota nel 78% delle partite di
        # Ligue 1 e nel 67% di quelle di Bundesliga (misurato su 68 schede): la parità
        # fra le 7 leghe non può dipendere da quanto la stampa italiana scrive di Le
        # Havre o di Paderborn. Qui i numeri vengono dai nostri dati e valgono per tutti.
        for tid, nome, in_casa in ((home_id, home_name, True), (away_id, away_name, False)):
            record = self._sapere_campo(tid, nome, in_casa, kickoff)
            if record:
                out.append(record)
            bomber = self._sapere_bomber(match_id, tid, nome, kickoff)
            if bomber:
                out.append(bomber)
        # Fatti di rendimento «di dettaglio» (docs/25 §5): entrano solo se la card non è
        # già piena, così non spostano mai i fatti che la tengono in piedi.
        for tid, nome in ((home_id, home_name), (away_id, away_name)):
            for fatto in (self._sapere_porta(tid, nome, kickoff),
                          self._sapere_finale(tid, nome, kickoff)):
                if fatto and len(out) < self.SAPERE_MAX:
                    out.append(fatto)
        return out

    def _assist_giocatore(self, team_id: int, player_id: int, kickoff: datetime) -> int:
        """Assist del giocatore nelle gare già giocate di questo campionato (0 se nessuno).

        Serve a completare l'«uomo gol»: chi segna e fa segnare pesa due volte. Come per
        i gol, contano solo le partite finite prima del calcio d'inizio.
        """
        if self.player_stats.empty or "key" not in self.player_stats.columns:
            return 0
        fin = self._gare_finite(kickoff)
        if fin.empty:
            return 0
        giocate = {int(x) for x in fin.match_id}
        a = self.player_stats[(self.player_stats.team_id == team_id)
                              & (self.player_stats.player_id == player_id)
                              & (self.player_stats.key == "assists")
                              & self.player_stats.match_id.isin(giocate)]
        if a.empty:
            return 0
        try:
            return int(a["value"].sum())
        except (TypeError, ValueError):
            return 0

    def _sapere_porta(self, team_id: int, nome: str, kickoff: datetime) -> dict[str, str] | None:
        """«Porta inviolata»: quante volte la squadra ha finito la gara senza subire gol.

        Con una o due gare il dato non dice nulla; da **tre** in su distingue una difesa
        solida da una squadra che concede sempre qualcosa. Serve anche a spiegare il
        «Dentro le mura»: punti fatti spesso con le reti inviolate pesano diversamente.
        """
        fin = self._gare_finite(kickoff)
        if fin.empty:
            return None
        gare = fin[(fin.home_id == team_id) | (fin.away_id == team_id)]
        if len(gare) < 3:
            return None
        subiti = gare.apply(lambda r: r.away_goals if r.home_id == team_id else r.home_goals,
                            axis=1)
        chiuse = int((subiti == 0).sum())
        if chiuse < 2:
            return None
        if chiuse == len(gare):
            return {"titolo": "Porta inviolata",
                    "testo": (f"{nome} non ha ancora subito gol in campionato "
                              f"({it_plural(len(gare), 'gara')}).")}
        return {"titolo": "Porta inviolata",
                "testo": (f"{nome} ha chiuso la porta in {it_plural(chiuse, 'gara')} "
                          f"su {len(gare)}.")}

    def _sapere_finale(self, team_id: int, nome: str, kickoff: datetime) -> dict[str, str] | None:
        """«Finale da brividi»: quanti gol la squadra subisce **dopo il 75'**.

        Viene dagli eventi minuto per minuto, non da una media: è il dato che spiega
        perché una partita chiusa al 70' può ancora muoversi. Soglia: almeno **3** gol
        subiti nel finale e almeno un terzo del totale, altrimenti è un caso.
        """
        fin = self._gare_finite(kickoff)
        if self.events.empty or fin.empty or "is_home" not in self.events.columns:
            return None
        giocate = {int(x) for x in fin.match_id}
        ev = self.events[self.events.match_id.isin(giocate)
                         & (self.events.type == "Goal")
                         & self.events.minute.notna()]
        if ev.empty:
            return None
        m = ev.merge(fin[["match_id", "home_id", "away_id"]], on="match_id", how="inner")
        if m.empty:
            return None
        # il gol è «subito da» chi non l'ha segnato: is_home dice chi ha segnato
        m = m[m.apply(lambda r: (r.away_id if bool(r.is_home) else r.home_id) == team_id,
                      axis=1)]
        totale = len(m)
        if totale < 4:
            return None
        tardi = int((m.minute.astype(float) >= 75).sum())
        if tardi < 3 or tardi / totale < 0.34:
            return None
        return {"titolo": "Finale da brividi",
                "testo": (f"{nome} ha subito {tardi} dei {totale} gol dopo il 75' "
                          f"(il {round(100 * tardi / totale)}% di quelli presi fin qui).")}

    def _gare_finite(self, kickoff: datetime) -> Any:
        """Gare di campionato già giocate prima del calcio d'inizio (stagione corrente)."""
        if self.fixtures.empty or "status" not in self.fixtures.columns:
            return self.fixtures
        fin = self.fixtures[(self.fixtures.status == "finished")
                            & (self.fixtures.utc_kickoff < kickoff)]
        return fin

    def _sapere_campo(self, team_id: int, nome: str, in_casa: bool,
                      kickoff: datetime) -> dict[str, str] | None:
        """«Dentro le mura» / «Lontano da casa»: il rendimento nel proprio campo.

        Il «Confronto di stagione» dice quanto vale la squadra **in media**; qui si
        separa ciò che ha fatto dove si gioca questa partita: il vantaggio del campo
        non è una voce di colore, è metà del punteggio di una squadra di metà
        classifica. Pubblicato solo con almeno **3** gare giocate in quel ruolo:
        con una o due il bilancio è un caso, non un fatto.
        """
        fin = self._gare_finite(kickoff)
        if fin.empty:
            return None
        colonna = "home_id" if in_casa else "away_id"
        gare = fin[fin[colonna] == team_id]
        v = p = s = 0
        for _, r in gare.iterrows():
            hg, ag = r.home_goals, r.away_goals
            if hg is None or ag is None or pd.isna(hg) or pd.isna(ag):
                continue
            fatti, subiti = (hg, ag) if in_casa else (ag, hg)
            if fatti > subiti:
                v += 1
            elif fatti < subiti:
                s += 1
            else:
                p += 1
        n = v + p + s
        if n < 3:
            return None
        punti = 3 * v + p
        esito = (f"{it_plural(v, 'vittoria', 'vittorie')}, {it_plural(p, 'pareggio')} "
                 f"e {it_plural(s, 'sconfitta', 'sconfitte')}")
        titolo = "Dentro le mura" if in_casa else "Lontano da casa"
        dove = "in casa" if in_casa else "in trasferta"
        return {"titolo": titolo,
                "testo": (f"{nome} {dove}: {esito} in {it_plural(n, 'gara')} "
                          f"({it_plural(punti, 'punto', 'punti')} su {3 * n}, "
                          f"{_it2(punti / n)} a gara).")}

    def _sapere_bomber(self, match_id: int, team_id: int, nome: str,
                       kickoff: datetime) -> dict[str, str] | None:
        """«L'uomo gol»: chi ha segnato di più per quella squadra in questo campionato.

        Fatto sempre disponibile (basta un gol segnato) e mai ridondante: la scheda
        elenca la rosa in ordine di ruolo, non dice chi sta segnando. Se il giocatore
        risulta **indisponibile** per questa partita lo dice: «il miglior marcatore è
        fuori» è esattamente l'informazione che manca a chi legge, e nascondere il
        nome solo perché è infortunato sarebbe una verità a metà.
        """
        if self.player_stats.empty:
            return None
        ps = self.player_stats[(self.player_stats.team_id == team_id)
                               & (self.player_stats.key == "goals")]
        if ps.empty:
            return None
        fin = self._gare_finite(kickoff)
        if not fin.empty:
            giocate = {int(x) for x in fin.match_id}
            ps = ps[ps.match_id.isin(giocate)]
        if ps.empty:
            return None
        somme = ps.groupby("player_id")["value"].sum().sort_values(ascending=False,
                                                                   kind="mergesort")
        if somme.empty:
            return None
        pid = int(somme.index[0])
        # La fonte scrive lo stesso giocatore in due modi («Adzic» e «Adžić»): il nome
        # pubblicato è la grafia più frequente, non la prima riga capitata — altrimenti
        # la stessa scheda potrebbe chiamarlo in due modi diversi fra le sue sezioni.
        nomi = ps.loc[ps.player_id == pid, "player_name"].mode()
        pname = str(nomi.iloc[0]) if len(nomi) else ""
        if not pname:
            return None
        try:
            gol = int(somme.iloc[0])
        except (TypeError, ValueError):
            return None
        if gol < 1:
            return None
        assist = self._assist_giocatore(team_id, pid, kickoff)
        testo = (f"il miglior marcatore di {nome} in questo campionato è {pname} "
                 f"({it_plural(gol, 'gol')}"
                 + (f" e {it_plural(assist, 'assist')})" if assist else ")"))
        if not self.lineup.empty:
            fuori = self.lineup[(self.lineup.match_id == match_id)
                                & (self.lineup.team_id == team_id)
                                & (self.lineup.role == "unavailable")
                                & (self.lineup.player_id == pid)]
            if not fuori.empty:
                tipo = str(fuori.iloc[0].get("unavailability_type") or "").strip().lower()
                # unavailability_it() è lo stesso traduttore usato dalle righe 2529 e 3569:
                # qui era l'unico punto a stampare il valore grezzo della fonte, e a schermo
                # usciva «(injury)» / «(suspension)» in inglese (8 occorrenze, audit 18/09).
                testo += (", che però è indisponibile per questa gara"
                          + (f" ({unavailability_it(tipo)})"
                             if tipo in ("injury", "suspension") else ""))
        return {"titolo": "L'uomo gol", "testo": testo + "."}

    def _news_branch(self, row: dict[str, Any]) -> str:
        """Brano della notizia **senza la testata**: il nome della testata non è contenuto.

        Difetto misurato (docs/24 §3): la descrizione di Google News è «titolo + testata»,
        quindi classificando titolo+brano la categoria la decideva la testata — un pezzo di
        cronaca ripreso da TUTTOmercatoWEB risultava «Mercato» e un titolo di Calciomercato
        pure. Il brano si usa, ma ripulito dai riferimenti alla fonte.
        """
        desc = str(row.get("description") or "")
        src = str(row.get("source") or "").strip()
        for s in (src, "Google News", "ESPN"):
            if s:
                desc = re.sub(re.escape(s), " ", desc, flags=re.IGNORECASE)
        title = str(row.get("title") or "")
        if title and title.lower() in desc.lower():
            desc = desc.lower().replace(title.lower(), " ")
        return desc.strip()

    def match_squad(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        """Rosa della partita secondo FotMob: nome e stato (titolare, panchina, indisponibile).

        Serve al bollettino stampa per due cose: riconoscere un giocatore citato in un
        titolo e dire in che stato è registrato per **questa** partita (docs/24 §3).
        """
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & self.lineup.role.isin(["starter", "sub", "unavailable"])]
        out = []
        for r in rows.itertuples(index=False):
            name = str(r.player_name or "").strip()
            if name:
                out.append({"name": name, "status": str(r.role)})
        return out

    # ---- mercato: arrivi e partenze (docs/21 P2-7, rifatto in docs/24 §4) ---------------------
    TRANSFER_GAP_DAYS: ClassVar[int] = 21
    TRANSFER_STALE_DAYS: ClassVar[int] = 90

    @staticmethod
    def fee_eur(value: Any) -> float | None:
        """Importo in euro da come lo pubblica la fonte; ``None`` se non è un importo.

        La fonte scrive l'importo in cifre (``3500000``), la formula in lettere
        (``prestito``, ``gratuito``) o dichiara di non dirlo (``undisclosed``). Tollerante
        per sicurezza su ``€ 3.5M``/``3,5 mln``: se non è un numero, non si inventa nulla.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value) if value > 0 else None
        t = str(value).strip().lower().replace("€", "").replace("eur", "").strip()
        if not t:
            return None
        t = t.replace(" ", "")
        m = re.fullmatch(r"([0-9][0-9.,]*)(m|mln|milioni|k|mila)?", t)
        if not m:
            return None
        num = m.group(1)
        mult = 1.0
        if m.group(2) in ("m", "mln", "milioni"):
            mult = 1_000_000.0
        elif m.group(2) in ("k", "mila"):
            mult = 1_000.0
        if mult == 1.0 and "," in num and "." in num:
            num = num.replace(".", "").replace(",", ".")
        elif "," in num:
            num = num.replace(",", ".")
        try:
            v = float(num) * mult
        except ValueError:
            return None
        return v if v > 0 else None

    @staticmethod
    def fee_it(value: Any) -> str:
        """Importo leggibile: ``12500000`` → ``12,5 M€``; formule tradotte, mai inglese."""
        t = str(value or "").strip()
        low = t.lower()
        if low in ("", "undisclosed", "n/d", "non noto"):
            return "importo non noto"
        if low in ("prestito", "loan", "on loan"):
            return "prestito"
        if low in ("gratuito", "free", "free transfer", "svincolato"):
            return "gratuito"
        v = MatchAnalysis.fee_eur(value)
        if v is None:
            return t                      # testo della fonte non riconosciuto: si pubblica com'è
        if v >= 1_000_000:
            n = f"{v / 1_000_000:.1f}".replace(".", ",")
            return f"{n.rstrip('0').rstrip(',')} M€"
        if v >= 1_000:
            n = f"{v / 1_000:.0f}"
            return f"{n} k€"
        return f"{v:.0f} €"

    def transfer_window(self, team_id: int, match_id: int | None = None,
                        n: int = 4) -> dict[str, Any] | None:
        """Mercato della squadra **della finestra in corso**, come pubblicato da FotMob.

        Rifatto in ``docs/24`` §4. La versione precedente pubblicava le 4 voci più recenti
        di tutta la tabella chiamandole «ultima finestra»: misurato sul sito del 2026-09-16,
        il 28% delle righe mostrate (1.187 su 4.231) veniva dalla stagione 2025-26, cioè
        dalla finestra di gennaio, e il tipo di movimento era tradotto con una mappa
        sbagliata (``contract`` → «rinnovo di contratto» su 630 righe su 1.115, che erano
        trasferimenti veri).

        Ora: la finestra è **ricavata dai dati** (dal movimento più recente all'indietro
        finché non passa più di :data:`TRANSFER_GAP_DAYS` fra due movimenti), si pubblicano
        gli estremi veri, e i movimenti si ordinano per importo pubblicato (a parità, per
        data) — cioè si vedono i colpi, non quattro voci qualunque. Gli importi si
        pubblicano in forma leggibile (``12,5 M€``) e in italiano.

        Se la fonte non ha movimenti recenti la card **non sparisce**: dice da quando non
        ne pubblica. Con ``match_id`` si aggiunge il collegamento con il campo: quali
        arrivi sono già nella distinta di questa partita.
        """
        out: dict[str, Any] = {"arrivals": [], "departures": [], "n_in": 0, "n_out": 0,
                               "window_start": "", "window_end": "", "stale": False,
                               "spesa": None, "incasso": None, "saldo": None,
                               "importi_noti": 0, "importi_mancanti": 0, "in_campo": [],
                               "ultimo": ""}
        if self.transfers.empty or "player_name" not in self.transfers.columns:
            return None
        df = self.transfers[self.transfers.team_id == team_id].copy()
        if df.empty:
            return None
        df["_date"] = pd.to_datetime(df.get("date"), utc=True, errors="coerce")
        df = df[df._date.notna()]
        if df.empty:
            return None
        df = df.sort_values("_date", ascending=False)
        dates = df._date.tolist()
        first = dates[0]
        for prev, cur in pairwise(dates):
            if (prev - cur) > pd.Timedelta(days=self.TRANSFER_GAP_DAYS):
                break
            first = cur
        finestra = df[df._date >= first]
        ultimo = pd.Timestamp(dates[0])
        out["ultimo"] = ultimo.strftime("%d/%m/%Y")
        out["window_start"] = pd.Timestamp(first).strftime("%d/%m/%Y")
        out["window_end"] = ultimo.strftime("%d/%m/%Y")
        oggi = pd.Timestamp.now(tz="UTC")
        if (oggi - ultimo).days > self.TRANSFER_STALE_DAYS:
            out["stale"] = True
            return out

        def entries(direction: str) -> list[dict[str, Any]]:
            d = finestra[finestra.direction == direction]
            if d.empty:
                return []
            rows = []
            for r in d.to_dict("records"):
                date = pd.Timestamp(r["_date"])
                rows.append({"name": str(r["player_name"]),
                             "counterpart": str(r.get("counterpart") or ""),
                             "fee": self.fee_it(r.get("fee_text")),
                             "fee_eur": self.fee_eur(r.get("fee_text")),
                             "date_it": date.strftime("%d/%m/%Y"),
                             "date": int(date.timestamp())})
            # importo pubblicato prima, poi il più recente: i colpi si vedono
            rows.sort(key=lambda x: (-(x["fee_eur"] or 0.0), -x["date"]))
            return rows

        for direction, chiave, count in (("in", "arrivals", "n_in"), ("out", "departures", "n_out")):
            rows = entries(direction)
            out[chiave] = rows[:n]
            out[count] = len(rows)
        importi = [r["fee_eur"] for r in entries("in") + entries("out")]
        out["importi_noti"] = sum(1 for v in importi if v)
        out["importi_mancanti"] = sum(1 for v in importi if not v)
        spesa = sum(v for v in (r["fee_eur"] for r in entries("in")) if v)
        incasso = sum(v for v in (r["fee_eur"] for r in entries("out")) if v)
        out["spesa"] = spesa if out["importi_noti"] else None
        out["incasso"] = incasso if out["importi_noti"] else None
        out["saldo"] = (spesa - incasso) if out["importi_noti"] else None
        out["saldo_it"] = self.fee_it(abs(out["saldo"])) if out["saldo"] is not None else ""
        out["saldo_segno"] = ("+" if (out["saldo"] or 0) > 0 else "−") if out["saldo"] else ""
        out["in_campo"] = self.arrivals_on_pitch(team_id, match_id, out["arrivals"]) \
            if match_id else []
        return out

    def arrivals_on_pitch(self, team_id: int, match_id: int,
                          arrivals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Quali arrivi della finestra sono già nella distinta di questa partita.

        È il collegamento che mancava fra «chi è arrivato» e «chi gioca»: misurato sulle 70
        schede con card del 2026-09-16, il 58,3% degli arrivi in finestra compare nella
        distinta (titolare o a disposizione), quindi l'informazione c'è ed è utile.
        """
        if not arrivals or self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role.isin(["starter", "sub"]))]
        if rows.empty:
            return []
        per_nome: dict[str, dict[str, Any]] = {}
        for r in rows.itertuples(index=False):
            per_nome[soft_key(str(r.player_name))] = {
                "name": str(r.player_name), "role": str(r.role),
                "value": float(r.market_value_eur) if pd.notna(r.market_value_eur) else 0.0,
                "status": "titolare" if r.role == "starter" else "a disposizione"}
        out = []
        for a in arrivals:
            hit = per_nome.get(soft_key(str(a["name"])))
            if hit:
                out.append({"name": hit["name"], "status": hit["status"], "value": hit["value"]})
        out.sort(key=lambda x: (-x["value"], x["name"]))
        return out

    def team_player_names(self, team_id: int) -> list[str]:
        """Nomi dei giocatori della squadra visti in stagione (per riconoscerli nei titoli)."""
        if self.player_stats.empty or "player_name" not in self.player_stats.columns:
            return []
        rows = self.player_stats[self.player_stats.team_id == team_id]
        return [str(n) for n in rows.player_name.dropna().unique().tolist()]

    def unavailable_for_news(self, team_name: str) -> list[str]:
        """Nomi degli indisponibili più recenti della squadra (per selezionare le notizie)."""
        if self.lineup.empty:
            return []
        canon = canonical(team_name)
        ids = self.fixtures[self.fixtures.home_name.map(canonical) == canon].home_id
        ids = set(ids) | set(self.fixtures[self.fixtures.away_name.map(canonical) == canon].away_id)
        if not ids:
            return []
        un = self.lineup[(self.lineup.team_id.isin(ids)) & (self.lineup.role == "unavailable")]
        return sorted(un.player_name.dropna().unique().tolist())[:12]


    @staticmethod
    def form_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Forma compatta per le liste: sequenza V/N/P e punti, sempre dal più vecchio al più recente."""
        points = sum(3 if row["res"] == "V" else 1 if row["res"] == "N" else 0 for row in rows)
        return {"rows": rows, "sequence": "".join(row["res"] for row in rows),
                "points": points, "n": len(rows)}

    def list_context(self, match_id: int, home_id: int, away_id: int,
                     home_name: str, away_name: str, kickoff: pd.Timestamp) -> dict[str, Any]:
        """Contesto a colpo d'occhio per una riga della pagina «Oggi».

        È deliberatamente più leggero di :meth:`build`: usa solo segnali già raccolti e non
        costruisce grafici, cronaca o tabelle avanzate. In questo modo l'elenco può mostrare
        la profondità disponibile su tutte le partite senza duplicare la scheda completa.
        """
        home_st, away_st = self.standing(home_name), self.standing(away_name)
        info = _first(self.info[self.info.match_id == match_id]) if not self.info.empty else {}
        weather = self._weather(match_id, _val(info, "weather_desc"),
                                _val(info, "weather_temp_c"), _val(info, "weather_precip_chance"))
        weather["wind"] = _val(info, "weather_wind")
        h2h_n = len(self._h2h_core(match_id, home_id, away_id, kickoff, n=60))
        # bilancio completo H2H per la card compatta (V/N/P dal punto di vista casa attuale, gol/gara, BTTS)
        try:
            h2h_pat = self.h2h_pattern(match_id, home_id, away_id, kickoff, n=60)
        except Exception:
            h2h_pat = None
        try:
            h2h_stat = self.h2h_stats(match_id, home_id, away_id, kickoff, n=5)
        except Exception:
            h2h_stat = None
        return {
            "home": {"standing": home_st,
                     "form": self.form_summary(self.form(home_id, kickoff, n=5))},
            "away": {"standing": away_st,
                     "form": self.form_summary(self.form(away_id, kickoff, n=5))},
            "prediction": self.prediction(match_id, home_name, away_name),
            "weather": weather,
            # una sola fonte per l'arbitro (P1.3, docs/19 §2.6): referee_profile() porta
            # anche il confronto con la media di lega; il dizionario scritto a mano qui
            # non l'aveva ed è lo schema che generava etichette sbagliate.
            "referee": self.referee_profile(match_id),
            "h2h_n": h2h_n,
            "h2h": h2h_pat,
            "h2h_recent": h2h_stat,
        }

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
                return {"source": "FotMob", "played": len(xg), "xg": xg.sum(),
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

    @staticmethod
    def ucl_spots(league_code: Any) -> int | None:
        """Posizioni UCL ordinarie della lega configurata, senza indovinare fallback."""
        if league_code is None or pd.isna(league_code):
            return None
        for lg in leagues():
            if lg.key == str(league_code):
                return lg.ucl_spots
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
            num = int(r.shirt_number) if not pd.isna(r.shirt_number) else None
            # arricchisci con ruolo italiano e id per badge / prior shrunk
            try:
                pos_it = self._role_it(r.player_id, _val(r._asdict(), "usual_position_id"), _val(r._asdict(), "position_id"))
            except Exception:
                pos_it = None
            try:
                usual = int(r.usual_position_id) if not pd.isna(r.usual_position_id) else None
            except Exception:
                usual = None
            out.append({"id": int(r.player_id) if not pd.isna(r.player_id) else None,
                        "name": r.player_name, "num": num, "rating": rating,
                        "season_rating": season_rating, "captain": bool(r.is_captain),
                        "pos": pos_it, "usual": usual})
        # ordina dal portiere: ruolo 0→3, poi numero maglia (1-99), poi nome
        # così la lista inizia sempre dal portiere come richiesto UX
        role_order = {0: 0, 1: 1, 2: 2, 3: 3}
        out.sort(key=lambda x: (role_order.get(x.get("usual"), 9), x["num"] is None, x["num"] if x["num"] is not None else 999, x["name"]))
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
        trend_recent = trend_before = None
        if len(rows) >= 6:                 # ultime 3 contro le precedenti: solo se ci sono 6 gare
            trend_recent, trend_before = sum(xg[-3:]) / 3, sum(xg[:-3]) / (len(xg) - 3)
            if trend_before > 0:
                delta = trend_recent - trend_before
                trend = "in crescita" if delta > 0.15 else "in calo" if delta < -0.15 else "stabile"
        return {"source": source, "played": len(rows), "rows": rows,
                "xg_pm": sum(xg) / len(xg), "xga_pm": sum(xga) / len(xga),
                "pts": sum(r["pts"] for r in rows), "xpts": round(sum(r["xpts"] for r in rows), 1),
                "ppda": sum(ppda) / len(ppda) if ppda else None,
                "home_pm": sum(r["xg"] for r in home_rows) / len(home_rows) if home_rows else None,
                "away_pm": sum(r["xg"] for r in away_rows) / len(away_rows) if away_rows else None,
                "trend": trend, "trend_recent": trend_recent, "trend_before": trend_before,
                # soglia dichiarata accanto alla frase: il lettore può rifare il giudizio (docs/20 §10)
                "trend_threshold": 0.15}

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
        vw = vd = vl = 0                     # sotto-serie: la casa attuale era di casa
        vgoals = 0
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
            if was_home:                   # lo stesso scenario di campo di QUESTA gara
                vw += int(signed > 0)
                vd += int(signed == 0)
                vl += int(signed < 0)
                vgoals += r["hg"] + r["ag"]
            margins.append(signed)
            key = f"{r['hg']}-{r['ag']}" if was_home else f"{r['ag']}-{r['hg']}"
            scorelines[key] = scorelines.get(key, 0) + 1
            btts += int(r["hg"] > 0 and r["ag"] > 0)
            over25 += int(r["hg"] + r["ag"] > 2.5)
        total = len(rows)
        top = sorted(scorelines.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        # sotto-serie «con la casa attuale in casa»: pubblicata solo da 8 casi —
        # sotto una doppia cifra di precedenti la frequenza non regge una frase (docs/20 §11)
        venue = None
        nv = vw + vd + vl
        if nv >= 8:
            venue = {"n": nv, "wins": vw, "draws": vd, "losses": vl, "gpg": vgoals / nv}
        return {"n": total, "wins": w, "draws": d, "losses": l,
                "gpg": sum(r["hg"] + r["ag"] for r in rows) / total,
                "margin": sum(margins) / total,
                "btts": btts / total, "over25": over25 / total, "draw_drought": last_draw,
                "top_scores": [{"score": s, "n": c, "share": c / total} for s, c in top],
                "venue": venue,
                "last": rows[0]["utc"], "first": rows[-1]["utc"]}

    # ---- gruppi di pari per le rate su campioni piccoli (docs/19 §1.10) ----------------------
    def _league_of(self, team_id: int) -> int | None:
        """Id della lega di una squadra dal calendario (``None`` se la squadra non c'è)."""
        if self.fixtures.empty or "league_id" not in self.fixtures.columns:
            return None
        sub = self.fixtures[(self.fixtures.home_id == team_id) | (self.fixtures.away_id == team_id)]
        if sub.empty or pd.isna(sub.iloc[-1]["league_id"]):
            return None
        return int(sub.iloc[-1]["league_id"])

    def _contrib_pools(self) -> dict[tuple[int | None, int | None], dict[str, Pool]]:
        """Medie dei pari di «xG+xA per 90» per (lega, ruolo), misurate sui dati del run.

        La scheda partita pubblica due rate su campioni piccoli — il contributo offensivo per 90
        di ``key_players_deep`` e il peso dell'infermeria di ``absences_weight`` — e prima del
        2026-09-16 la contrazione usava la costante di ruolo dell'xG+xA con peso fisso 180′
        (docs/19 §1.10): un numero scelto a mano, sbagliato di unità e applicato anche dove la
        statistica non c'entrava. Qui media e peso si misurano dal run, come nelle schede
        giocatore: stessa funzione, stesso contratto.
        """
        if self._pools_cache is not None:
            return self._pools_cache
        pools: dict[tuple[int | None, int | None], dict[str, Pool]] = {}
        ps, fx, lu = self.player_stats, self.fixtures, self.lineup
        if not ps.empty and not fx.empty and not lu.empty:
            chiavi = ["expected_goals", "expected_assists", "minutes_played"]
            q = ps[ps.key.isin(chiavi) & ps.value.notna()].copy()
            q["num"] = pd.to_numeric(q.value, errors="coerce")
            wide = q.groupby(["player_id", "key"]).num.sum().unstack("key")
            if "minutes_played" in wide.columns:
                wide = wide.rename(columns={"minutes_played": "minutes"})
                teams = pd.concat([
                    fx[["home_id", "league_id"]].rename(columns={"home_id": "team_id"}),
                    fx[["away_id", "league_id"]].rename(columns={"away_id": "team_id"}),
                ]).dropna().drop_duplicates("team_id", keep="last").set_index("team_id")["league_id"]
                lu2 = lu[lu.role != "coach"].dropna(subset=["player_id"]).sort_values("match_id")
                ident = lu2.groupby("player_id").last()[["team_id", "usual_position_id"]]
                groups = pd.DataFrame({
                    "league_id": ident["team_id"].map(teams),
                    "position": ident["usual_position_id"],
                }).reindex(wide.index)
                pools = player_pools(wide, groups,
                                     {"contrib": ["expected_goals", "expected_assists"]},
                                     minutes_col="minutes")
        self._pools_cache = pools
        return pools

    def _contrib_pool(self, player_id: int, team_id: int | None) -> tuple[Pool, str] | None:
        """Gruppo dei pari per un giocatore della scheda partita, con l'etichetta leggibile."""
        role = self._role_hist().get(int(player_id))
        league = self._league_of(int(team_id)) if team_id is not None else None
        trovato = pool_lookup(self._contrib_pools(), league, role, "contrib")
        if trovato is None:
            return None
        pool, (lg, rl) = trovato
        return pool, group_label(lg, rl)

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
        eligible = len(played)
        played = played.sort_values("contrib_p90", ascending=False).head(n)
        out = []
        for r in played.itertuples(index=False):
            d = r._asdict()
            gx, ax = d.get("expected_goals"), d.get("expected_assists")
            mins = float(self._num(d, "minutes_played"))
            contrib = float(r.contrib)
            # stima stabilizzata (docs/19 §1.10): media dei pari e peso misurati dal run
            gruppo = self._contrib_pool(int(r.player_id), team_id)
            contrib_shrunk = gruppo[0].per90(contrib, mins) if gruppo and mins else None
            out.append({
                "id": int(r.player_id), "name": r.player_name,
                "pos": self._role_it(r.player_id),
                "minutes": int(self._num(d, "minutes_played")), "games": int(self._num(d, "games")),
                "goals": int(self._num(d, "goals")), "assists": int(self._num(d, "assists")),
                "xg": None if gx is None or pd.isna(gx) else round(float(gx), 2),
                "xa": None if ax is None or pd.isna(ax) else round(float(ax), 2),
                "contrib_p90": float(r.contrib_p90),
                "pubblicabile": bool(mins >= MIN_DEN_FOR_RATE),
                "contrib_p90_shrunk": round(float(contrib_shrunk), 2) if contrib_shrunk is not None else None,
                "est_note": gruppo[0].note(gruppo[1]) if gruppo else None,
                "chances": int(self._num(d, "chances_created")),
                "big_chances": int(self._num(d, "big_chance_created_team_title")),
                "rating": None if pd.isna(r.rating_avg) else round(float(r.rating_avg), 2)})
        return {"rows": out, "floor": int(floor), "eligible": eligible}

    def absences_weight(self, match_id: int, team_id: int) -> dict[str, Any] | None:
        """Quanto pesa l'infermeria: gol, assist e xG+xA per 90 che gli assenti portano via.

        Ogni assente è pesato sui suoi numeri reali di stagione. «Titolare abituale» =
        almeno metà dei minuti medi per giocatore della squadra (minuti totali / 11).

        La rata pubblicata è **stabilizzata** (docs/19 §1.10): con il valore grezzo un assente
        con un minuto giocato pubblicava «15,30 xG+xA a partita», e quel numero entrava nella
        somma dell'infermeria. Sotto i 90′ si pubblica solo la stima, dichiarata come tale.
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
            mins = float(s.get("minutes", 0.0))
            gruppi = self._contrib_pool(pid, team_id) if pid is not None else None
            grezzo = (s.get("contrib", 0.0) / (mins / 90.0)) if mins else None
            stima = gruppi[0].per90(s.get("contrib", 0.0), mins) if gruppi and mins else None
            pubblicabile = bool(mins >= MIN_DEN_FOR_RATE)
            if stima is None:
                # nessun gruppo di pari utilizzabile (stagione appena iniziata, dati scarni):
                # si pubblica il grezzo senza inventare una stima che non sapremmo calcolare
                pubblicabile = True
            is_starter = bool(per_player and mins >= 0.5 * per_player)
            starters_out += int(is_starter)
            contrib_lost += stima if stima is not None else (grezzo or 0.0)
            players.append({**u, "minutes": int(mins) or None, "games": None,
                            "goals": int(s.get("goals", 0.0)), "assists": int(s.get("assists", 0.0)),
                            "contrib_p90": grezzo if pubblicabile else stima,
                            "contrib_raw": grezzo, "contrib_est": stima,
                            "pubblicabile": pubblicabile,
                            "est_note": gruppi[0].note(gruppi[1]) if gruppi else None,
                            "starter": is_starter})
        players.sort(key=lambda p: (-(p["contrib_p90"] or 0.0), -(p["minutes"] or 0)))
        return {"players": players, "n": len(players), "starters_out": starters_out,
                # somma delle stime stabilizzate: dichiarata come stima nel template
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
                "league_matches": len(lg) if not lg.empty else None}

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
        wanted = [("BallPossesion", "Possesso palla"), ("expected_goals", "xG"), ("expected_goals_on_target", "xGOT"),
                  ("total_shots", "Tiri"), ("ShotsOnTarget", "Tiri in porta"), ("big_chance", "Grandi occasioni"),
                  ("big_chance_missed_title", "Grandi occasioni fallite"), ("accurate_passes", "Passaggi riusciti"),
                  ("corners", "Calci d'angolo"), ("fouls", "Falli"), ("yellow_cards", "Ammonizioni"),
                  ("red_cards", "Espulsioni"), ("touches_opp_box", "Tocchi in area avversaria")]
        return self._stat_rows(match_id, home_id, away_id, wanted, "All")

    def detail_stats(self, match_id: int, home_id: int, away_id: int) -> list[dict[str, Any]]:
        """Statistiche di dettaglio: le chiavi FotMob non comprese nel riquadro principale.

        Stessa fonte e stessa formattazione di ``key_stats`` (testo della fonte, decimali con
        la virgola): una riga compare solo se **entrambe** le squadre hanno il dato, quindi
        nessun segnaposto. Copertura misurata su 239 partite finite, 7/7 leghe.
        """
        wanted = [("shots_inside_box", "Tiri da dentro l'area"), ("shots_outside_box", "Tiri da fuori area"),
                  ("expected_goals_open_play", "xG azione manovrata"),
                  ("expected_goals_set_play", "xG palle inattive"),
                  ("expected_goals_non_penalty", "xG senza rigori"),
                  ("duel_won", "Duelli vinti"), ("ground_duels_won", "Duelli a terra vinti"),
                  ("aerials_won", "Duelli aerei vinti"), ("interceptions", "Intercetti"),
                  ("clearances", "Rinvii"), ("blocked_shots", "Tiri bloccati"),
                  ("shot_blocks", "Contrasti su tiro"), ("dribbles_succeeded", "Dribbling riusciti"),
                  ("accurate_crosses", "Cross riusciti"), ("long_balls_accurate", "Lanci lunghi riusciti"),
                  ("passes", "Passaggi totali"), ("opposition_half_passes", "Passaggi metà campo avversaria"),
                  ("own_half_passes", "Passaggi nella propria metà"), ("keeper_saves", "Parate del portiere"),
                  ("shots_woodwork", "Legni"), ("Offsides", "Fuorigioco"),
                  ("player_throws", "Rimesse laterali"), ("ShotsOffTarget", "Tiri fuori")]
        return self._stat_rows(match_id, home_id, away_id, wanted, "All")

    def _stat_rows(self, match_id: int, home_id: int, away_id: int,
                   wanted: list[tuple[str, str]], period: str) -> list[dict[str, Any]]:
        """Righe di confronto casa/trasferta per una lista di chiavi, su un periodo."""
        if self.team_stats.empty:
            return []
        ts = self.team_stats[(self.team_stats.match_id == match_id) & (self.team_stats.period == period)]
        if ts.empty:
            return []
        out = []
        for key, label in wanted:
            h = ts[(ts.team_id == home_id) & (ts.key == key)]
            a = ts[(ts.team_id == away_id) & (ts.key == key)]
            if not h.empty and not a.empty:
                out.append({"label": label, "home": _stat_text_it(h.iloc[0].text),
                            "away": _stat_text_it(a.iloc[0].text)})
        return out

    def half_split(self, match_id: int, home_id: int, away_id: int) -> dict[str, Any] | None:
        """Primo e secondo tempo a confronto: xG, tiri, tiri in porta, possesso, angoli.

        FotMob pubblica le stesse chiavi per periodo (``FirstHalf``/``SecondHalf``) su
        239 partite finite, 7/7 leghe: serve a vedere **quando** una partita si è decisa.
        """
        wanted = [("expected_goals", "xG"), ("total_shots", "Tiri"), ("ShotsOnTarget", "Tiri in porta"),
                  ("BallPossesion", "Possesso palla"), ("corners", "Calci d'angolo"),
                  ("big_chance", "Grandi occasioni")]
        cols = []
        for period, label in (("FirstHalf", "Primo tempo"), ("SecondHalf", "Secondo tempo")):
            rows = self._stat_rows(match_id, home_id, away_id, wanted, period)
            if rows:
                cols.append({"label": label, "rows": rows})
        if len(cols) < 2:
            return None
        # righe comuni a entrambi i tempi, nello stesso ordine: la tabella resta allineata
        labels = [r["label"] for r in cols[0]["rows"]]
        cols[1]["rows"] = [r for r in cols[1]["rows"] if r["label"] in labels]
        if len(cols[1]["rows"]) != len(labels):
            return None
        return {"cols": cols, "labels": labels}

    def keeper_stats(self, match_id: int, home_id: int, away_id: int) -> dict[str, Any] | None:
        """Portieri a confronto: parate, gol prevenuti, errori, rigori parati.

        Il portiere è identificato dai dati, non dal ruolo in distinta: è il giocatore con
        righe ``saves``/``goals_prevented`` in ``player_stats``. Copertura 239 partite per le
        parate e i gol prevenuti, 93 per gli errori che hanno portato a un gol.
        """
        keys = ("saves", "goals_prevented", "errors_led_to_goal", "saved_penalties",
                "conceded_penalties", "penalties_won")
        sides = {}
        for side, team_id in (("home", home_id), ("away", away_id)):
            ps = self._match_player_stats(match_id, team_id)
            if ps.empty:
                continue
            # il portiere è chi ha statistiche **da portiere**: saves/goals_prevented.
            # Usare anche errors_led_to_goal o penalties_won pescava i difensori
            # (Arsenal-Coventry 11/09: van Ewijk, terzino, al posto del portiere).
            gk_keys = [k for k in ("saves", "goals_prevented") if k in set(ps.columns)]
            if not gk_keys:
                continue
            keepers = ps[ps[gk_keys].notna().any(axis=1)]
            if keepers.empty:
                continue
            if "minutes_played" in keepers.columns:      # il titolare è chi ha più minuti
                keepers = keepers.sort_values("minutes_played", ascending=False, na_position="last")
            r = keepers.iloc[0].to_dict()
            sides[side] = {"name": r["player_name"], "id": int(r["player_id"]),
                           **{k: (None if pd.isna(r.get(k, np.nan)) else float(r[k])) for k in keys}}
        if len(sides) < 2:
            return None
        return {"home": sides["home"], "away": sides["away"], "keys": keys}

    def physical_stats(self, match_id: int, home_id: int, away_id: int) -> dict[str, Any] | None:
        """Dati fisici: distanza, sprint, metri in sprint, giocatore più veloce.

        FotMob li pubblica solo per una parte delle partite (la copertura cresce con
        l'archivio e non è fissa): la card compare solo quando i dati ci sono, senza
        stime al posto dei numeri mancanti.
        """
        keys = ("physical_metrics_distance_covered", "physical_metrics_number_of_sprints",
                "physical_metrics_sprinting", "physical_metrics_topspeed")
        sides = {}
        for side, team_id in (("home", home_id), ("away", away_id)):
            ps = self._match_player_stats(match_id, team_id)
            if ps.empty or not set(keys) <= set(ps.columns):
                continue
            # pandas 3: con colonne di dtype 'str' l'indicizzazione con una *tupla* dà
            # KeyError anche quando le etichette ci sono → si passa sempre una lista
            have = ps[ps[list(keys)].notna().any(axis=1)]
            if have.empty:
                continue
            fastest = have.dropna(subset=["physical_metrics_topspeed"]).sort_values(
                "physical_metrics_topspeed", ascending=False)
            top = fastest.iloc[0] if not fastest.empty else None
            sides[side] = {
                "km": float(have.physical_metrics_distance_covered.sum() / 1000.0),
                "sprints": int(have.physical_metrics_number_of_sprints.fillna(0).sum()),
                "sprint_m": int(have.physical_metrics_sprinting.fillna(0).sum()),
                "players": len(have),
                "fastest": None if top is None else str(top.player_name),
                "topspeed": None if top is None else float(top.physical_metrics_topspeed)}
        if len(sides) < 2:
            return None
        return {"home": sides["home"], "away": sides["away"]}

    def _match_player_stats(self, match_id: int, team_id: int) -> pd.DataFrame:
        """Una riga per giocatore della squadra in questa partita (chiavi → colonne)."""
        if self.player_stats.empty:
            return pd.DataFrame()
        ps = self.player_stats[(self.player_stats.match_id == match_id) & (self.player_stats.team_id == team_id)]
        ps = ps[ps.value.notna()]
        if ps.empty:
            return pd.DataFrame()
        ps = ps.assign(num=pd.to_numeric(ps.value, errors="coerce"))
        wide = ps.groupby(["player_id", "player_name", "key"]).num.sum().unstack("key")
        return wide.reset_index()

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
        names = self._match_player_names(match_id)
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
            kind = ""
            if r.type == "Goal" and not own_goal:
                kind = GOAL_KIND_IT.get(str(_val(d, "goal_description") or ""), "")
            aid = _val(d, "assist_player_id") if r.type == "Goal" else None
            out.append({"type": r.type, "minute": _val(d, "minute"), "added": int(added) if added is not None else None,
                        "home": scored_home, "scorer_home": scored_home != own_goal,
                        "player": _val(d, "player_name"), "kind": kind,
                        "assist": names.get(int(aid)) if aid is not None and pd.notna(aid) else None,
                        "card": _val(d, "card"), "own_goal": own_goal, "score": score,
                        "swap_in": swap[0][1] if swap and len(swap) > 0 else None,
                        "swap_out": swap[1][1] if swap and len(swap) > 1 else None})
        return out

    def _match_player_names(self, match_id: int) -> dict[int, str]:
        """``player_id" → nome dalla distinta della partita.

        Serve agli assist: FotMob pubblica ``assistPlayerId`` su 535/753 gol e il nome è
        risolvibile nel 100% dei casi attraverso la distinta (titolari, panchina e
        indisponibili stanno tutti nella tabella ``lineup``).
        """
        if self.lineup.empty:
            return {}
        lu = self.lineup[(self.lineup.match_id == match_id) & self.lineup.player_id.notna()]
        return {int(r.player_id): str(r.player_name) for r in lu.itertuples(index=False)}

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
        return {"n": len(s), "xg": float(s.xg.sum()), "on_target": int(_on_target(s).sum()),
                "inside_box": int(s.is_inside_box.fillna(False).sum()), "big_chances": len(big),
                # quante grandi occasioni sono diventate gol: la conversione di serata
                # distingue «ha creato poco» da «ha sprecato» (utile per la gara successiva)
                "big_goals": int((big.event_type == "Goal").sum()),
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
                INSIGHT_SEEN["scartati"] += 1
                continue
            body = tr["text"]
            if _INSIGHT_EN_LEAK.search(body):
                continue  # rete di sicurezza: mai inglese a schermo
            if body in seen_text:
                continue
            seen_text.add(body)
            INSIGHT_SEEN["tradotti"] += 1
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
    def prediction(self, match_id: int, home_name: str | None = None,
                   away_name: str | None = None) -> dict[str, Any] | None:
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
        d["meta"] = prediction_meta(d, home_name, away_name)
        return d

    @staticmethod
    def _lambdas(pred: dict[str, Any] | None) -> tuple[float, float, float] | None:
        """λ casa, λ trasferta e ρ della previsione, oppure None se la previsione non ha λ.

        Nello store i valori mancanti arrivano come NaN (non None): una λ non finita deve
        far sparire il blocco, non generare una distribuzione di NaN pubblicata in scheda.
        """
        if not pred:
            return None
        try:
            lh, la = float(pred.get("lambda_home")), float(pred.get("lambda_away"))
        except (TypeError, ValueError):
            return None
        if not (np.isfinite(lh) and np.isfinite(la)) or lh < 0 or la < 0:
            return None
        rho = pred.get("dc_rho")
        try:
            rho = 0.0 if rho is None or pd.isna(rho) else float(rho)
        except (TypeError, ValueError):
            rho = 0.0
        if not np.isfinite(rho):
            rho = 0.0
        return lh, la, rho

    def score_matrix(self, pred: dict[str, Any] | None) -> dict[str, Any] | None:
        """Matrice 0–5 dei punteggi dalla λ e ρ della previsione (None se manca λ)."""
        lam = self._lambdas(pred)
        return None if lam is None else score_matrix(*lam)

    def goals_view(self, pred: dict[str, Any] | None) -> dict[str, Any] | None:
        """Distribuzione dei gol totali + dotplot quantile (None se la previsione non ha λ)."""
        lam = self._lambdas(pred)
        return None if lam is None else goals_view(*lam)

    def clash(self, home_name: str, home_id: int, away_name: str, away_id: int,
              pred: dict[str, Any] | None) -> dict[str, Any] | None:
        return style_rows(self.season_style(home_name, home_id),
                          self.season_style(away_name, away_id), pred)

    def clash_ranks(self, home_name: str, away_name: str) -> dict[str, Any] | None:
        """Graduatorie attacco/difesa e «duello chiave» da UNA sola fonte: la classifica.

        Perché la classifica e non gli xG: graduatorie e rapporti «× media campionato»
        devono confrontare quantità omogenee, e la classifica FotMob è un'unica fonte per
        tutte le squadre della lega, mentre gli xG mescolano fornitori (regola di purezza
        già dichiarata nella card «Scontro tattico»). Il duello chiave è il lato più
        sbilanciato del match: attacco casa × difesa ospite contro attacco ospite ×
        difesa casa, misurato come prodotto dei rapporti sulla media gol della lega.
        """
        if self.fm_standings.empty:
            return None
        h, a = self.standing(home_name), self.standing(away_name)
        if not h or not a or h.get("league_code") != a.get("league_code"):
            return None
        tab = self.fm_standings[self.fm_standings.league_code == h["league_code"]]
        tab = tab.drop_duplicates("team_id")
        n = len(tab)
        if n < 4 or not h.get("played") or not a.get("played"):
            return None
        att_rank = {int(r.team_id): i for i, r in enumerate(
            tab.sort_values(["goals_for", "goal_diff"], ascending=[False, False])
               .itertuples(index=False), 1)}
        def_rank = {int(r.team_id): i for i, r in enumerate(
            tab.sort_values("goals_against", kind="stable").itertuples(index=False), 1)}
        avg_gf = tab.goals_for.sum() / tab.played.sum()
        avg_ga = tab.goals_against.sum() / tab.played.sum()
        if not avg_gf or not avg_ga:
            return None

        def ratios(row: dict[str, Any]) -> tuple[float, float]:
            pg = int(row["played"]) or 1
            return (row["goals_for"] / pg) / avg_gf, (row["goals_against"] / pg) / avg_ga

        h_att, h_def = ratios(h)
        a_att, a_def = ratios(a)
        fmt = _it2
        if h_att * a_def >= a_att * h_def:
            duel = (f"duello chiave: attacco {home_name} ({fmt(h_att)}× la media gol della lega) "
                    f"contro difesa {away_name} ({fmt(a_def)}× la media gol subiti): il lato più "
                    f"sbilanciato del match")
        else:
            duel = (f"duello chiave: attacco {away_name} ({fmt(a_att)}× la media gol della lega) "
                    f"contro difesa {home_name} ({fmt(h_def)}× la media gol subiti): il lato più "
                    f"sbilanciato del match")
        return {
            "n": n,
            "home_line": (f"{att_rank[int(h['team_id'])]}º attacco · "
                          f"{def_rank[int(h['team_id'])]}ª difesa per gol in campionato (su {n})"),
            "away_line": (f"{att_rank[int(a['team_id'])]}º attacco · "
                          f"{def_rank[int(a['team_id'])]}ª difesa per gol in campionato (su {n})"),
            "duel_line": duel,
        }

    def key_status(self, match_id: int, team_id: int) -> dict[int, dict[str, Any]]:
        """Giocherà? Stato di ogni giocatore della distinta: titolare, panchina o assente.

        Incrocio diretto dei ruoli FotMob della partita (starter/sub/unavailable); per gli
        assenti la nota è motivo+rientro tradotti, come nell'infermeria. Se la fonte elenca
        lo stesso giocatore sia titolare sia indisponibile vince l'indisponibilità (regola
        già usata in ``starters``): dire «titolare probabile» di un infortunato è un falso.
        """
        if self.lineup.empty:
            return {}
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role.isin(["starter", "sub", "unavailable"]))
                           & self.lineup.player_id.notna()]
        out: dict[int, dict[str, Any]] = {}
        for r in rows.itertuples(index=False):
            if r.role == "unavailable":
                note = unavailability_it(_val(r._asdict(), "unavailability_type"))
                ret = _return_it(_val(r._asdict(), "expected_return"))
                out[int(r.player_id)] = {"status": "unavailable",
                                         "note": note + (f" · {ret}" if ret else "")}
        for r in rows.itertuples(index=False):
            pid = int(r.player_id)
            if r.role != "unavailable" and pid not in out:
                out[pid] = {"status": "starter" if r.role == "starter" else "sub"}
        return out

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
            meta = p.get("meta") or prediction_meta(p, h, a)
            top_key = meta["top_key"] if meta else None
            top_name = meta["top_name"] if meta else None
            pf = meta["top_probability"] if meta else max(p["p_home"], p["p_draw"], p["p_away"])
            if top_key == "X":
                s.append(f"Il pareggio è l'esito più probabile ({_pct(pf)}), ma resta una gara aperta.")
            elif pf >= 0.60:
                # P2.4 (docs/19 §2.8): «nettamente favorito» al 60% è più forte del dato —
                # a quella probabilità il favorito perde comunque 4 volte su 10, e contraddice
                # la cura dichiarata in prediction_meta(). Si pubblica la **frequenza naturale**
                # («su 100 partite così, N finiscono in quel modo»), formato che la letteratura
                # sulla comunicazione del rischio indica come meglio compreso delle percentuali
                # ed è già la filosofia del dotplot dei gol.
                s.append(f"Il modello indica {top_name} come esito più probabile ({_pct(pf)}): "
                         f"su 100 partite così, {round(pf * 100)} finiscono in quel modo.")
            elif pf >= 0.45:
                s.append(f"Il modello indica {top_name} ({_pct(pf)}), "
                         f"con margine contenuto sul secondo esito.")
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
            # quote interne alla stessa fonte (FotMob): sono la scomposizione coerente,
            # leggibile come «42% del totale» senza sommare fonti diverse (docs/20 §4)
            st = by.get("xG da palle inattive (quota)")
            if st and st["h"] is not None and st["h"] >= 40:
                s.append(f"{h} crea una quota alta di xG su palla inattiva ({dec(st['h'], 0)}% del totale).")
            if st and st["a"] is not None and st["a"] >= 40:
                s.append(f"{a} crea una quota alta di xG su palla inattiva ({dec(st['a'], 0)}% del totale).")
        for side, name in (("home", h), ("away", a)):
            f = ctx.get(f"{side}_form") or []
            if len(f) >= 3:
                pts = sum(3 if x["res"] == "V" else 1 if x["res"] == "N" else 0 for x in f)
                seq = "".join(x["res"] for x in f)
                # la forma è un contenuto obbligatorio, non un'eccezione da segnalare: se non
                # è estrema si dice comunque, con i numeri (parità fra le 7 leghe, docs/20 §13)
                if pts >= 2.4 * len(f):
                    giudizio = "grande forma"
                elif pts <= 0.6 * len(f):
                    giudizio = "in difficoltà"
                else:
                    giudizio = "andamento nella norma"
                s.append(f"{name}: {it_plural(pts, 'punto', 'punti')} nelle ultime "
                         f"{len(f)} ({seq}) — {giudizio}.")
            xg = ctx.get(f"{side}_xg")
            if xg and xg.get("xpts") is not None and xg.get("pts") is not None and xg["played"] >= 4:
                diff = xg["pts"] - xg["xpts"]
                # P2.4 (docs/19 §2.8): `dec(diff, plus=True)` con valore negativo produceva
                # «ha -3,0 punti rispetto agli xPTS» — in italiano si dice «ha 3,0 punti in
                # meno». Il segno si porta nelle parole, non davanti al numero: il valore
                # assoluto va in cifre e il verso nella frase.
                if diff >= 3:
                    s.append(f"{name} ha raccolto {_f(diff, 1)} punti in più di quanto dica l'xPTS: "
                             f"rendimento sopra la qualità del gioco prodotto, regressione possibile.")
                elif diff <= -3:
                    s.append(f"{name} ha {_f(-diff, 1)} punti in meno di quanto dica l'xPTS: "
                             f"rende meno di ciò che crea, segnale di sottovalutazione.")
            un = ctx.get(f"{side}_unavailable") or []
            if un:
                # «Giocatore di peso» = titolare abituale (minuti >= metà della media squadra):
                # criterio interno alla squadra, lo stesso per tutte e 7 le leghe — la soglia
                # fissa a 15M€ di valore marcava per definizione quasi solo la Premier League
                # (POR1: 5 rose su 77; verificato 2026-09-15, docs/20 §13). Se mancano i minuti
                # di stagione si ripiega sul valore di mercato; se manca anche quello, lo si dice.
                ab = ctx.get(f"{side}_absences")
                if ab and ab.get("has_stats"):
                    heavy = [p for p in ab["players"] if p.get("starter")]
                else:
                    heavy = [u for u in un if u.get("value") and u["value"] >= 15_000_000]
                # P2.4 (docs/19 §2.8): «Assenze Inter: 3 (tra cui 2 giocatori di peso) —
                # Lautaro, Barella, Calhanoglu» è un formato elenco-dati, non una frase.
                # Si scrive in italiano corrente, con la congiunzione prima dell'ultimo nome.
                # Il criterio di «peso» NON cambia: resta «titolare abituale» (docs/20 §13).
                quanti = it_plural(len(un), "assente")
                if heavy:
                    # con un solo assente «1 assente, uno dei quali titolare» stona:
                    # l'unico indisponibile È il titolare, e la frase lo dice per esteso.
                    if len(un) == 1:
                        peso = ", titolare abituale"
                    elif len(heavy) == 1:
                        peso = ", uno dei quali titolare abituale"
                    else:
                        peso = f", {len(heavy)} dei quali titolari abituali"
                elif not (ab and ab.get("has_stats")) and all(not u.get("value") for u in un):
                    peso = " (peso non valutabile: fonte senza minuti né valori di mercato)"
                else:
                    peso = ""
                # P2.2 (`docs/28` §3): i nomi e l'impatto stanno nella tabella dell'infermeria
                # della squadra (minuti, gol+assist, xG+xA per 90 stabilizzato, motivo e
                # rientro); ripeterne qui i primi quattro era la stessa informazione due volte,
                # e la seconda meno informata della prima. La frase tiene quello che la tabella
                # non dice in una riga: *quanto* pesa l'assenza — quanti, quanti titolari
                # abituali, quanta produzione offensiva manca — e manda al dettaglio.
                #
                # Solo pre-partita, però: a gara finita la tabella dell'infermeria **non c'è**
                # (la fonte riporta le assenze una volta su due, quindi la pagina non può
                # distinguere «nessuno fuori» da «non raccolto»: vedi il commento nel template).
                # Lì la narrativa resta l'unico posto dove i nomi compaiono, e li tiene.
                if ctx.get("status") == "finished":
                    elenco = _elenco_it([u["name"] for u in un[:4]])
                    coda = "…" if len(un) > 4 else ""
                    s.append(f"{name} deve rinunciare a {quanti}{peso}: {elenco}{coda}.")
                else:
                    s.append(f"{name} deve rinunciare a {quanti}{peso} — nomi e impatto in "
                             f"«Indisponibili».")
            rest = ctx.get(f"{side}_rest")
            if rest is not None and rest <= 3:
                cup = ctx.get(f"{side}_rest_cup")
                tail = f", con un turno di {cup} in mezzo" if cup else ""
                s.append(f"{name} gioca dopo soli {rest} giorni di riposo{tail}.")
        ref = ctx.get("referee")
        if ref and ref.get("name"):
            y, ly = ref.get("yellows"), ref.get("league_yellows")
            n = int(ref.get("matches") or 0)
            if y is not None and n >= MIN_REFEREE_MATCHES:
                # Soglie RELATIVE alla lega (P1.2, docs/19 §2.6): in Liga Portugal la media
                # è 5,04 gialli/partita, in Ligue 1 3,85 — un valore assoluto (≥5 = «molto
                # severo») chiamava «molto severo» un arbitro portoghese nella media.
                # Senza media di lega si pubblicano i numeri, non il giudizio.
                if ly is None:
                    pens = (f", {it_plural(ref['pens'], 'rigore')} in {it_plural(n, 'gara')}"
                            if ref.get("pens") is not None else "")
                    s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita su "
                             f"{it_plural(n, 'gara')} designate{pens}.")
                else:
                    tone = ("sopra la media del campionato" if y >= 1.15 * ly
                            else "sotto la media del campionato" if y <= 0.85 * ly
                            else "nella media del campionato")
                    s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita, {tone} "
                             f"({_f(ly, 1)} la media di lega)"
                             + (f", {it_plural(ref['pens'], 'rigore')} in {it_plural(n, 'gara')}."
                                if ref.get("pens") is not None else "."))
            elif y is not None:
                # campione ridotto (mediana 33, minimo 6): la media ha un errore standard
                # grande → si pubblica il numero, mai l'aggettivo (P1.2, docs/19 §2.6);
                # i rigori compaiono comunque nella card «Contesto», qui non servono
                s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita su "
                         f"{it_plural(n, 'gara')} designate (campione ridotto, nessuna valutazione).")
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
        weather = self._weather(match_id, _val(info, "weather_desc"),
                                _val(info, "weather_temp_c"), _val(info, "weather_precip_chance"))
        weather["wind"] = _val(info, "weather_wind")
        prediction = self.prediction(match_id, f["home_name"], f["away_name"])
        # insieme condiviso dalle due colonne del bollettino stampa (docs/24 §3): lo stesso
        # articolo non deve comparire due volte nella stessa pagina
        news_seen: set[str] = set()
        # allenatori in panchina (servono alla rilevanza delle notizie e al blocco «Da sapere»)
        home_coach = (self.coach(home_id, kickoff) or {}).get("name")
        away_coach = (self.coach(away_id, kickoff) or {}).get("name")
        ctx: dict[str, Any] = {
            "match_id": match_id, "league_id": int(f["league_id"]), "round": _val(f, "round"),
            "utc_kickoff": kickoff, "status": status,
            "home_id": home_id, "away_id": away_id,
            "home_name": f["home_name"], "away_name": f["away_name"],
            "home_goals": _goals(info, "home_goals", f), "away_goals": _goals(info, "away_goals", f),
            "home_form": self.form(home_id, kickoff), "away_form": self.form(away_id, kickoff),
            "home_rest": self.rest_days(home_id, kickoff), "away_rest": self.rest_days(away_id, kickoff),
            "home_rest_cup": self.rest_cup(home_id, kickoff), "away_rest_cup": self.rest_cup(away_id, kickoff),
            # post-partita: quando si rigioca (campionato + coppe) e con quanto riposo
            "home_next": self.next_commitment(home_id, kickoff) if status == "finished" else None,
            "away_next": self.next_commitment(away_id, kickoff) if status == "finished" else None,
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
            "clash_ranks": self.clash_ranks(f["home_name"], f["away_name"])
                           if status != "finished" else None,
            "home_key_status": self.key_status(match_id, home_id) if status != "finished" else {},
            "away_key_status": self.key_status(match_id, away_id) if status != "finished" else {},
            "home_absences": self.absences_weight(match_id, home_id) if status != "finished" else None,
            "away_absences": self.absences_weight(match_id, away_id) if status != "finished" else None,
            "home_bench": self.bench_deep(home_id, f["home_name"], away_id, f["away_name"],
                                          kickoff, _val(info, "home_avg_starter_age"))
                          if status != "finished" else None,
            "away_bench": self.bench_deep(away_id, f["away_name"], home_id, f["home_name"],
                                          kickoff, _val(info, "away_avg_starter_age"))
                          if status != "finished" else None,
            "home_mood": self.club_mood(match_id, home_id, f["home_name"], kickoff)
                          if status != "finished" else [],
            "away_mood": self.club_mood(match_id, away_id, f["away_name"], kickoff)
                          if status != "finished" else [],
            # mercato (docs/21 P2-7, rifatto in docs/24 §4): finestra ricavata dai dati,
            # arrivi collegati alla distinta di questa partita
            "home_market": self.transfer_window(home_id, match_id) if status != "finished" else None,
            "away_market": self.transfer_window(away_id, match_id) if status != "finished" else None,
            # bollettino stampa (docs/24 §3): filtrato, categorizzato e deduplicato; l'insieme
            # `visti` è condiviso dalle due squadre, così lo stesso articolo non compare due volte
            "home_news": self.team_news(home_id, f["home_name"], kickoff,
                                        squad=self.match_squad(match_id, home_id),
                                        seen=news_seen, opponent=f["away_name"],
                                        coach=home_coach) if status != "finished" else _no_news(),
            "away_news": self.team_news(away_id, f["away_name"], kickoff,
                                        squad=self.match_squad(match_id, away_id),
                                        seen=news_seen, opponent=f["home_name"],
                                        coach=away_coach) if status != "finished" else _no_news(),
            # blocco «Da sapere» della card (docs/24 §3.5): derivato dai nostri dati
            "news_sapere": (self.news_sapere(match_id, home_id, f["home_name"], away_id,
                                             f["away_name"], kickoff)
                            if status != "finished" else []),
            "lineup_type": _val(info, "lineup_type"),
            "home_formation": _val(info, "home_formation"), "away_formation": _val(info, "away_formation"),
            "home_value": _val(info, "home_starters_value_eur"), "away_value": _val(info, "away_starters_value_eur"),
            # un unico profilo arbitro (P1.3, docs/19 §2.6): la chiave separata
            # «referee_profile» era una seconda fonte per lo stesso dato, meno informata
            # (senza il confronto con la media di lega).
            "referee": self.referee_profile(match_id),
            "stadium": {"name": _val(info, "stadium_name"), "city": _val(info, "stadium_city"),
                        "attendance": _val(info, "attendance")},
            "weather": weather,
            "h2h": (_val(info, "h2h_home_wins"), _val(info, "h2h_draws"), _val(info, "h2h_away_wins")),
            "h2h_list": self.h2h_list(match_id, home_id, away_id, f["home_name"], f["away_name"], kickoff),
            "h2h_stats": self.h2h_stats(match_id, home_id, away_id, kickoff),
            "momentum": self.momentum(match_id) if status == "finished" else None,
            "prediction": prediction,
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
            "generated_at": datetime.now(UTC),
        }
        if status == "finished":
            ctx["detail_stats"] = self.detail_stats(match_id, home_id, away_id)
            ctx["half_split"] = self.half_split(match_id, home_id, away_id)
            ctx["keepers"] = self.keeper_stats(match_id, home_id, away_id)
            ctx["physical"] = self.physical_stats(match_id, home_id, away_id)
        ctx["score_matrix"] = self.score_matrix(ctx["prediction"])
        # riga unica della card «Vita del club» quando non c'è nulla da pubblicare (docs/28 §2
        # P1.1): costruita qui perché è un fatto della partita (due squadre), non di una colonna
        ctx["news_quiet"] = (news_quiet_line(ctx["home_news"], ctx["away_news"],
                                             f["home_name"], f["away_name"])
                             if status != "finished" else None)
        ctx["goals"] = self.goals_view(ctx["prediction"])
        ctx["prob_steps"] = probability_steps(ctx["prediction"])
        ctx["fav_record"] = self.favorite_track_record(ctx["prediction"])
        ctx["league_pos"] = self.league_goals_percentile(ctx["prediction"])
        ctx["first_goal"] = self.first_goal_clock(ctx["prediction"])
        ctx["clash"] = self.clash(f["home_name"], home_id, f["away_name"], away_id, ctx["prediction"])
        ctx["xg_race"] = self.match_xg_race(match_id, home_id, away_id) if status == "finished" else None
        ctx["home_shotq"] = self.match_shot_quality(match_id, home_id) if status == "finished" else None
        ctx["away_shotq"] = self.match_shot_quality(match_id, away_id) if status == "finished" else None
        ctx["wp_path"] = self.match_wp(ctx["prediction"], ctx["timeline"]) if status == "finished" else None
        ctx["narrative"] = self.narrative(ctx)
        return ctx
