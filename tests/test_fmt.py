"""Somme pubblicate: «1,40 + 0,99» deve dare «2,39» (docs/22 §2).

Il difetto corretto qui era di formattazione, non di modello: il totale era calcolato sui
valori grezzi (2,3829 → «2,38») mentre le due cifre stampate accanto danno «2,39». Vale la
regola generale: **un numero derivato pubblicato si calcola su ciò che è pubblicato**.
"""

import numpy as np

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
