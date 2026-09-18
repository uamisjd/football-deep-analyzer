"""P1.15 — costo del filtro di `prossime.html` (docs/19 §3.10).

`prossime.html` è la pagina più pesante del sito (1.513 KB, 1.987 card). Il filtro
client-side gira nel browser, che nel sandbox non esiste: questi test **non** misurano
millisecondi, inchiodano le due proprietà strutturali da cui dipende il costo, così una
riscrittura futura non le perde in silenzio.

1. **debounce sulla ricerca**: un passaggio dopo l'ultimo tasto, non uno per tasto;
2. **badge precalcolati**: i conteggi per bucket di stato non dipendono né dalla ricerca
   né dalla lega, quindi si contano una volta sola invece che a ogni frame.
"""

from __future__ import annotations

import re
from pathlib import Path

SITE_SRC = Path(__file__).resolve().parents[1] / "src" / "fda" / "site"
INDEX = SITE_SRC / "templates" / "index.html"
CSS = SITE_SRC / "assets" / "site.css"


def _script() -> str:
    """Il blocco <script> del filtro (la pagina è resa anche come prossime.html)."""
    html = INDEX.read_text(encoding="utf-8")
    assert "data-match-toolbar" in html, "toolbar del filtro sparita da index.html"
    return html


def test_la_ricerca_e_sottoposta_a_debounce():
    """Digitare «juventus» deve filtrare una volta, non otto (docs/19 §3.10)."""
    js = _script()
    handler = re.search(r"search\?\.addEventListener\('input'.*?\}\);", js, re.DOTALL)
    assert handler, "manca il gestore 'input' della ricerca"
    body = handler.group(0)
    assert "clearTimeout(timer)" in body, "debounce senza reset del timer precedente"
    assert re.search(r"setTimeout\(scheduleApply,\s*120\)", body), \
        "il debounce deve essere di 120 ms come misurato in docs/19 §3.10"


def test_invio_bypassa_il_debounce():
    """Chi preme Invio vuole il risultato subito: il ritardo di 120 ms non deve applicarsi."""
    js = _script()
    assert "'Enter'" in js and "clearTimeout(timer); scheduleApply();" in js, \
        "Invio deve annullare il timer e filtrare immediatamente"


def test_i_badge_di_stato_sono_contati_una_volta_sola():
    """I conteggi non dipendono da ricerca/lega: ricalcolarli a ogni frame è lavoro sprecato.

    Misura che motiva il test: con 1.987 card e 5 bottoni, il ricalcolo per frame costava
    9.935 confronti, l'83% del lavoro totale di un passaggio di filtro.
    """
    js = _script()
    assert js.count("const statusCounts") == 1, "i conteggi devono essere precalcolati una volta"
    assert js.count("function updateBadges") == 1, "una sola implementazione dei badge"
    # il vecchio ricalcolo per-frame non deve tornare
    assert "cards.filter(c => alias.includes" not in js, \
        "i badge sono tornati a scandire tutte le card a ogni passaggio di filtro"


def test_i_badge_non_sono_ricalcolati_dentro_il_loop_di_filtro():
    """`applyNow()` deve occuparsi solo di mostrare/nascondere, non dei conteggi."""
    js = _script()
    apply_now = re.search(r"function applyNow\(\).*?\n  \}", js, re.DOTALL)
    assert apply_now, "applyNow() non trovata"
    assert "filter-count" not in apply_now.group(0), \
        "i badge vanno aggiornati fuori da applyNow(), che gira a ogni frame di digitazione"


def test_le_card_restano_fuori_dal_layout_finche_non_servono():
    """`content-visibility` sulle card: il parsing di 1.987 nodi non deve costare layout."""
    css = CSS.read_text(encoding="utf-8")
    rule = re.search(r"\.match-card\{[^}]*\}", css)
    assert rule, ".match-card sparita dal CSS"
    assert "content-visibility:auto" in rule.group(0)
    # `auto <size>`: il browser usa la dimensione REALE una volta misurata, invece di
    # restare inchiodato a una stima fissa (che qui nessuno può verificare senza browser).
    assert re.search(r"contain-intrinsic-size:\s*auto\s+\d+px", rule.group(0)), \
        "serve `contain-intrinsic-size: auto <px>` per non congelare una stima non misurata"
