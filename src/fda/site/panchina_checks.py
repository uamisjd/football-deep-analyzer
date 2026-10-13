"""Oracoli della card panchina, indipendenti dal generatore (docs/94).

Non importano MatchAnalysis né i suoi formatter. Controllano il significato di rango,
distanza e precisione MC, non soltanto che una seconda copia del calcolo dia lo stesso testo.
Condivisi dai due verificatori, mai chiamati dalla costruzione del sito.
"""

from __future__ import annotations

import math
import re
from html import unescape
from typing import Any

import numpy as np
import pandas as pd


def safety_findings(text: str, table: pd.DataFrame, team_id: int) -> list[str]:
    """Un pari punti non promuove una squadra: la zona dipende dal rango ufficiale.

    Nei sette formati coperti: ultimi tre posti a rischio; a 18 squadre il 16º è lo
    spareggio, 17º/18º retrocedono direttamente. Le tabelle sintetiche ridotte dei test
    mantengono la convenzione precedente (ultimi due posti), senza inventare spareggi.
    """
    row = table[table["team_id"].eq(team_id)]
    if row.empty:
        return []
    n = table["team_id"].nunique()
    last_safe = n - 3 if n in (18, 20) else n - 2
    direct_start = n - 2 if n == 20 else n - 1
    row = row.iloc[0]
    rank = int(row["rank"])
    if rank > last_safe and "in zona salvezza diretta" in text:
        return [f"falsa salvezza: rango {rank}, ultimo posto di salvezza diretta {last_safe}"]
    anchor = table[table["rank"].eq(last_safe)]
    if rank < direct_start or anchor.empty:
        return []
    distance = int(anchor.iloc[0]["points"]) - int(row["points"])
    if distance > 0:
        published = re.search(r"(\d+) punt[oi] dalla salvezza diretta", text)
        if published is None or int(published.group(1)) != distance:
            return [f"distanza dalla salvezza: attesi {distance} punti dal {last_safe}º posto"]
    elif distance == 0:
        expected = f"a pari punti con il {last_safe}º posto (salvezza diretta)"
        if expected not in text:
            return [f"pari punti con il {last_safe}º posto non dichiarato senza attribuire la salvezza"]
    elif "in zona retrocessione diretta" not in text:
        # Un'eventuale classifica non monotona per punti non autorizza a dichiarare salvezza.
        return ["rango in retrocessione: nessuna distanza positiva ricavabile dai punti"]
    return []


def monte_carlo_findings(raw_cell: str, n_sims: Any) -> list[str]:
    """Numero di simulazioni dal Parquet e limite SE ≥ 50/√N punti percentuali.

    Il controllo del limite è diseguale, non una copia dell'arrotondamento del generatore:
    il testo non può promettere una precisione migliore di quella sostenuta dal campione.
    """
    try:
        n = float(n_sims)
    except (TypeError, ValueError):
        n = float("nan")
    html = unescape(raw_cell)
    if not math.isfinite(n) or n <= 0 or not n.is_integer() or isinstance(n_sims, (bool, np.bool_)):
        return [] if "numerosità non dichiarata" in html else ["numerosità MC assente spacciata per nota"]
    found = re.search(r"([\d.]+) simulazioni Monte Carlo del resto del campionato: "
                      r"errore standard fino a ([\d,]+) punti percentuali", html)
    if not found:
        return ["numerosità o precisione Monte Carlo non dichiarata nel tooltip"]
    if int(found.group(1).replace(".", "")) != int(n):
        return [f"numero di simulazioni dichiarato diverso da {int(n)}"]
    published = float(found.group(2).replace(",", "."))
    bound = 50 / math.sqrt(n)
    if published + 1e-12 < bound or published > bound + 0.100000001:
        return [f"errore standard MC dichiarato incoerente con {int(n)} simulazioni"]
    return []
