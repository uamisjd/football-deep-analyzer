"""Formattazione numerica italiana condivisa tra i moduli del sito.

Stessa semantica dei filtri Jinja (`dec`, `it_num`): virgola decimale, separatore
migliaia con punto. I moduli Python che preparano stringhe pronte per i template
usano queste funzioni, così la formattazione è definita in un solo posto.
"""

from __future__ import annotations

import pandas as pd


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
