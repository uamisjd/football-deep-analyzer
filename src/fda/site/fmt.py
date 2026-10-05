"""Formattazione numerica italiana condivisa tra i moduli del sito.

Stessa semantica dei filtri Jinja (`dec`, `it_num`): virgola decimale, separatore
migliaia con punto. I moduli Python che preparano stringhe pronte per i template
usano queste funzioni, così la formattazione è definita in un solo posto.
"""

from __future__ import annotations

import math
import re

import pandas as pd

# nomi estesi per le date pronte all'uso (erano in build.py: spostati qui perché anche
# analysis.py compone righe di testo con giorno e ora — fonte unica, niente duplicati)
ITALIAN_DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
ITALIAN_MONTHS = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                  "settembre", "ottobre", "novembre", "dicembre"]


def it_day_time(ts, tz) -> str:
    """Timestamp UTC → 'martedì 15/09, ore 20:00' nel fuso display ``tz``."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert(tz)
    return f"{ITALIAN_DAYS[t.weekday()]} {t.day:02d}/{t.month:02d}, ore {t.hour:02d}:{t.minute:02d}"


def dec(v, nd: int = 2, plus: bool = False) -> str:
    """Numero → stringa con virgola decimale italiana: 3.86 → '3,86' (plus=True → '+0,04')."""
    if v is None:
        return ""
    fv = float(v)
    if pd.isna(fv):
        return ""
    s = f"{fv:.{nd}f}".replace(".", ",")
    return f"+{s}" if plus and fv >= 0 else s


def int_it(v) -> str:
    """Numero → intero con separatore migliaia italiano: 57000 → '57.000'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return f"{int(float(v)):,}".replace(",", ".")


def displayed(v, nd: int = 2) -> float:
    """Il numero **esattamente come lo stampa** :func:`dec` (arrotondato a ``nd`` cifre).

    Serve a chi deve sommare due valori che sono già a schermo: la somma va fatta su
    ciò che il lettore legge, non sui valori grezzi (vedi :func:`displayed_sum`).
    """
    return float(f"{float(v):.{nd}f}")


def displayed_sum(a, b, nd: int = 2) -> float:
    """Somma di due valori **come il lettore li somma**: prima arrotondati a ``nd``, poi addizionati.

    Perché serve (misurato 2026-09-16 su 165 schede pre-partita): la riga in testa alla
    scheda stampa i due gol attesi arrotondati («1,40 + 0,99») e il totale calcolato sui
    valori **grezzi** (2,3829 → «2,38»): 44 schede su 165 (26,7%) mostravano un totale che
    non è la somma delle due cifre stampate, e lo stesso nelle card di *Oggi*/«Prossime»
    (88 occorrenze su 330). Il numero pubblicato deve chiudere con se stesso: la somma si
    calcola su ciò che è stampato.
    """
    return round(displayed(a, nd) + displayed(b, nd), nd)


def dec_sum(a, b, nd: int = 2) -> str:
    """«1,40 + 0,99» → ``'2,39'``: il totale coerente con le due cifre stampate.

    Filtro Jinja (``|dec_sum``): è l'unico modo ammesso per pubblicare una somma di valori
    già formattati — una somma calcolata sui grezzi produce un totale che non chiude.
    """
    if a is None or b is None:
        return ""
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return ""
    if pd.isna(fa) or pd.isna(fb):
        return ""
    return dec(displayed_sum(fa, fb, nd), nd)


#: Decimale scritto col punto dentro una stringa libera. È la **stessa** espressione di
#: ``scripts/verify_site.py`` (``DECIMAL_POINT``): i due devono restare identici, altrimenti
#: il gate segnala ciò che il sito pubblica (o viceversa). Esclude i separatori di migliaia
#: (1-3 cifre, punto, esattamente 3 cifre) e i numeri attaccati a una lettera o a una barra
#: («v1.5», «Chrome/124.0»), che non sono decimali nostri.
_DECIMALE_PUNTO = re.compile(r"(?<![\w/,\-:])\d{1,3}\.\d{1,2}(?![\w.])|\d{1,3}\.\d{4,}")


def decimali_it(testo) -> str:
    """Stringa libera → stessa stringa coi decimali in virgola italiana.

    Perché serve: le frasi di diagnostica (``source_status.detail``, ``source_probe.detail``,
    i messaggi d'errore) arrivano in *Stato fonti* **verbatim** e non passano dai filtri
    numerici. Il 28/09/2026 la sonda Open-Meteo ha pubblicato le coordinate di San Siro come
    «45.48,9.12»: un decimale col punto su una sola pagina ha fermato il ``daily`` per otto
    giorni (il gate ``verify_site`` esce 1 prima del commit dei dati e del deploy). Il
    produttore è stato corretto, ma la pagina pubblica testo generato altrove e già salvato
    nei Parquet: la conversione all'ultimo miglio rende la pagina indipendente da come il
    testo è stato scritto a monte.

    Non tocca i separatori di migliaia («84.594»), le versioni («v1.5») né gli URL.
    """
    if not isinstance(testo, str) or not testo:
        return testo if isinstance(testo, str) else ""
    return _DECIMALE_PUNTO.sub(lambda m: m.group(0).replace(".", ","), testo)


def pct_str(v, nd: int = 0) -> str:
    """Frazione 0–1 → percentuale italiana: 0.842 → '84%' (nd=1 → '84,2%')."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return f"{float(v) * 100:.{nd}f}".replace(".", ",") + "%"


def plural_it(singular: str) -> str:
    """Plurale regolare italiano: gara→gare, pareggio→pareggi, punto→punti, gol→gol.

    Regole: -a → -e; -io → -i (cade solo la -o: pareggio/pareggi, non «pareggii»);
    -o/-e → -i; il resto è invariabile. Le forme irregolari si passano a :func:`it_plural`.
    """
    if singular.endswith("a"):
        return singular[:-1] + "e"
    if singular.endswith("io"):
        return singular[:-1]
    if singular.endswith(("o", "e")):
        return singular[:-1] + "i"
    return singular            # invariabili: gol, assist, città


def it_plural(v, singular: str, plural: str | None = None) -> str:
    """Contatore + nome concordato: 1 → '1 gara', 3 → '3 gare'.

    Serve perché a schermo comparivano «1 gare», «1 vittorie», «1 pareggi», «1 tiri»
    (1098 occorrenze su 1098 pagine, audit 2026-09-12). ``plural`` va passato solo per le
    forme irregolari.
    """
    n = int(float(v or 0))
    return f"{n} {singular if n == 1 else (plural or plural_it(singular))}"


def or_dash(v) -> str:
    """Valore formattato, oppure '—' se manca (dato assente, mai inventato)."""
    s = v if isinstance(v, str) else dec(v)
    return s if s else "—"


def pct_triple(p: tuple[float, float, float], nd: int = 0) -> list[float]:
    """Vettore 1X2 continuo → 3 valori con ``nd`` decimali che sommano **esattamente** 100.

    Perché serve: arrotondare le tre probabilità in modo indipendente produce 99 o 101
    (99,9 o 100,1 con un decimale). Nelle righe compatte del calendario il lettore non ha
    contesto per accorgersene, ma nelle **barre 1X2** l'errore si vede: le larghezze dei
    segmenti devono chiudere il 100% del contenitore, altrimenti la barra resta corta o
    straborda, e l'etichetta deve coincidere con la larghezza.

    Metodo del resto massimo, con ramo + e − corretti: ``resto > 0`` assegna ai resti
    maggiori, ``resto < 0`` toglie ai resti minori; tie-break sull'ordine (1, X, 2)
    deterministico (stable argsort). ``nd=0`` restituisce interi (comportamento storico),
    ``nd=1`` un decimale: il lavoro è fatto in unità intere di ``10**-nd``, quindi la somma
    è esatta e non dipende dall'aritmetica binaria dei decimali.

    >>> pct_triple((0.61, 0.2424, 0.1476))
    [61, 24, 15]
    >>> pct_triple((0.61, 0.2424, 0.1476), 1)
    [61.0, 24.2, 14.8]
    """
    nd = int(nd)
    unit = 10 ** nd
    raw = [float(v) * 100.0 * unit for v in p]
    base = [math.floor(x) for x in raw]
    resto = 100 * unit - sum(base)
    if resto:
        residuals = [r - f for r, f in zip(raw, base)]
        # ordinamento stabile su 3 elementi: `sorted` in Python è stabile per definizione,
        # quindi a parità di resto la precedenza resta (1, X, 2) esattamente come con
        # `np.argsort(kind="stable")`. Su tre valori non serve numpy (P2.6, docs/19 §4):
        # l'import stava dentro la funzione, che è chiamata una volta per card.
        if resto > 0:
            order = sorted(range(3), key=lambda i: -residuals[i])   # maggiori prima
            passo = 1
        else:
            order = sorted(range(3), key=lambda i: residuals[i])    # minori prima
            passo = -1
        for i in range(abs(resto)):
            base[order[i % 3]] += passo
    if nd == 0:
        return base
    return [b / unit for b in base]
