"""Somme pubblicate: «1,40 + 0,99» deve dare «2,39» (docs/22 §2).

Il difetto corretto qui era di formattazione, non di modello: il totale era calcolato sui
valori grezzi (2,3829 → «2,38») mentre le due cifre stampate accanto danno «2,39». Vale la
regola generale: **un numero derivato pubblicato si calcola su ciò che è pubblicato**.
"""

import numpy as np
import pytest

from fda.site.fmt import dec, dec_sum, displayed, displayed_sum


def test_somma_stampata_caso_reale():
    """Caso reale della scheda 5749662: il totale pubblicato era 2,38 invece di 2,39."""
    lh, la = 1.3977650142126163, 0.9851191700388995
    assert dec(lh) == "1,40" and dec(la) == "0,99"
    assert dec(lh + la) == "2,38"           # il totale calcolato sui grezzi: NON chiude
    assert dec_sum(lh, la) == "2,39"        # la somma delle due cifre stampate: chiude
    assert displayed_sum(lh, la) == 2.39


def test_somma_stampata_a_ogni_precisione():
    """La regola vale a ogni precisione (l'unità è 10^-nd), non solo a due decimali.

    Non si fissa il valore atteso a mano (dipende dall'arrotondamento binario): si verifica
    la **proprietà** che conta — il totale è la somma dei due numeri effettivamente stampati.
    """
    for nd in (0, 1, 2):
        for a, b in ((1.345, 1.345), (2.5, 0.4), (1.44, 0.955), (0.0, 0.0)):
            sa, sb = dec(a, nd), dec(b, nd)
            somma = float(sa.replace(",", ".")) + float(sb.replace(",", "."))
            tot = dec_sum(a, b, nd)
            assert tot, (a, b, nd)
            assert abs(float(tot.replace(",", ".")) - somma) < 1e-9, f"{sa} + {sb} ≠ {tot}"


def test_somma_stampata_proprieta_su_numeri_casuali():
    """2000 coppie casuali: il totale stampato chiude sempre con i due numeri stampati."""
    rng = np.random.default_rng(20260916)
    for a, b in zip(rng.uniform(0, 4, size=2000), rng.uniform(0, 4, size=2000)):
        sa, sb = dec(a), dec(b)
        tot = dec_sum(a, b)
        assert tot == f"{float(sa.replace(',', '.')) + float(sb.replace(',', '.')):.2f}".replace(".", ","), \
            f"{sa} + {sb} ≠ {tot}"


def test_somma_stampata_valori_assenti():
    """Nessun totale inventato: senza uno dei due valori il campo resta vuoto."""
    assert dec_sum(None, 1.0) == ""
    assert dec_sum(1.0, None) == ""
    assert dec_sum(float("nan"), 1.0) == ""
    assert dec_sum("x", 1.0) == ""


def test_displayed_e_la_cifra_stampata_da_dec():
    """`displayed` è per definizione ciò che `dec` scrive: qualunque uso deve concordare."""
    rng = np.random.default_rng(7)
    for v in list(rng.uniform(0, 10, size=500)) + [0.0, 100.0, 1.005, 2.675]:
        assert f"{displayed(v):.2f}" == f"{v:.2f}"


# --- P2.6: pct_triple senza import pesanti nel corpo della funzione (docs/19 §4) ---


def test_pct_triple_non_importa_numpy_dentro_la_funzione():
    """L'import stava nel corpo: veniva eseguito a ogni card renderizzata (P2.6).

    Su 3 elementi `sorted` è stabile per definizione e dà lo stesso ordine di
    `np.argsort(kind="stable")`, quindi numpy qui era una dipendenza inutile in un
    percorso caldo. Il test inchioda la proprietà, non l'implementazione.
    """
    import inspect

    from fda.site import fmt

    corpo = inspect.getsource(fmt.pct_triple)
    assert "import numpy" not in corpo, "numpy è tornato dentro pct_triple (percorso caldo)"
    assert "import matplotlib" not in corpo, "matplotlib non deve entrare in fmt.pct_triple"


def test_pct_triple_resta_stabile_sul_tie_break_1x2():
    """A parità di resto la precedenza deve restare (1, X, 2): è l'ordine pubblicato."""
    from fda.site.fmt import pct_triple

    # tre resti identici: il punto mancante va al primo in ordine (1), non a caso
    assert pct_triple((1 / 3, 1 / 3, 1 / 3)) == [34, 33, 33]
    # con nd=1 la somma è esatta *in unità intere di 0,1*; la divisione finale per 10
    # reintroduce il floating point (33,4+33,3+33,3 = 99,99999999999999), quindi si
    # confronta con tolleranza. È il motivo per cui il lavoro è fatto in interi.
    assert sum(pct_triple((1 / 3, 1 / 3, 1 / 3), 1)) == pytest.approx(100.0, abs=1e-9)


@pytest.mark.parametrize("nd", [0, 1])
def test_pct_triple_somma_esatta_su_molti_vettori_casuali(nd):
    """Proprietà pubblicata: le barre 1X2 devono chiudere esattamente il 100%."""
    import random

    from fda.site.fmt import pct_triple

    rng = random.Random(12345)
    for _ in range(3000):
        a, b, c = rng.random(), rng.random(), rng.random()
        s = a + b + c
        out = pct_triple((a / s, b / s, c / s), nd)
        assert sum(out) == pytest.approx(100.0, abs=1e-9)
        assert all(v >= 0 for v in out), "nessuna percentuale negativa"


# ---- decimali col punto dentro il testo libero (blocco del daily del 28/09/2026) ------------
def test_decimali_it_converte_solo_i_decimali():
    """La sonda Open-Meteo pubblicava «45.48,9.12» in *Stato fonti*: un decimale col punto
    su una sola pagina è bastato a fermare il ``daily`` per otto giorni (il gate
    ``verify_site`` esce 1 prima del commit dei dati e del deploy)."""
    from fda.site.fmt import decimali_it

    assert decimali_it("previsione per 45.48 · 9.12 alle 10:53") == "previsione per 45,48 · 9,12 alle 10:53"
    assert decimali_it("xG 1.69 su 3.5") == "xG 1,69 su 3,5"
    assert decimali_it("") == "" and decimali_it(None) == ""
    assert decimali_it("nessun numero") == "nessun numero"


def test_decimali_it_non_tocca_migliaia_versioni_url():
    """Falsi positivi da non creare: separatori di migliaia, versioni, URL, orari."""
    from fda.site.fmt import decimali_it

    for testo in ("84.594 righe", "1.234.567 byte", "v1.5", "Chrome/124.0 Safari/537.36",
                  "https://www.sportmediaset.mediaset.it/rss/calcio.xml", "HTTP 404",
                  "ore 10:53 UTC", "3,1 gialli/gara"):
        assert decimali_it(testo) == testo, testo


def test_decimali_it_allineata_al_gate_di_verify_site():
    """Ciò che :func:`decimali_it` lascia intatto non deve far fallire il gate, e ciò che
    converte deve essere esattamente ciò che il gate intercetta: le due espressioni vivono
    in file diversi (``fmt.py`` e ``scripts/verify_site.py``) e devono restare identiche."""
    import importlib.util
    import re
    from pathlib import Path

    from fda.site.fmt import _DECIMALE_PUNTO, decimali_it

    p = Path(__file__).parent.parent / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site_fmt", p)
    vs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vs)
    assert _DECIMALE_PUNTO.pattern == vs.DECIMAL_POINT.pattern

    for testo in ("previsione per 45.48,9.12", "xG 1.69", "84.594 righe", "v1.5"):
        assert bool(vs.DECIMAL_POINT.search(testo)) == bool(_DECIMALE_PUNTO.search(testo))
        assert not re.search(vs.DECIMAL_POINT, decimali_it(testo)), testo
