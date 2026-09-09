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


def or_dash(v) -> str:
    """Valore formattato, oppure '—' se manca (dato assente, mai inventato)."""
    s = v if isinstance(v, str) else dec(v)
    return s if s else "—"
