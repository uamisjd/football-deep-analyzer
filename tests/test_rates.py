"""Stima stabilizzata delle rate su campioni piccoli (docs/19 §1.10, docs/22 §5).

Numeri scelti a mano e verificabili: la media dei pari pesa sul tempo di gioco (non è la media
delle rate), il peso k è un quarto del denominatore mediano, e il difetto trovato il
2026-09-16 — «un minuto giocato, un tiro, 90,00 tiri/90 pubblicati» — non deve ripresentarsi.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fda.site.rates import (
    MIN_DEN_FOR_RATE,
    MIN_POOL_PEERS,
    POOL_WEIGHT,
    SMALL_SAMPLE_MINUTES,
    group_label,
    lookup,
    player_pools,
    pool_of,
    shrink_rate,
)


# ---- la contrazione -------------------------------------------------------------------------
def test_senza_informazione_la_stima_e_la_media_dei_pari():
    """k nullo o denominatore nullo → nessuna invenzione: la stima è la media dei pari."""
    assert shrink_rate(9, 95, 0.12, 0) == 0.12
    assert shrink_rate(9, 0, 0.12, 400) == 0.12
    assert shrink_rate(0, 95, 0.12, -5) == 0.12


def test_un_minuto_e_un_tiro_non_pubblicano_piu_90_tiri_per_90():
    """Il caso reale del difetto: 1′ con un tiro pubblicava «90,00 tiri/90» (docs/19 §1.10)."""
    pool = pool_of([30.0] * 10, [900.0] * 10)          # pari: 3,00 tiri/90 su campioni pieni
    assert pool is not None
    assert pool.rate * 90 == pytest.approx(3.0)
    stima = pool.per90(1, 1)                            # un tiro in un minuto
    assert pool.k == pytest.approx(225)                 # 0,25 × 900′ mediani dei pari
    assert stima == pytest.approx(3.39, abs=0.01)       # 90,00 grezzo → 3,39 dichiarato come stima
    assert stima < 5


def test_il_minutaggio_pieno_non_viene_stravolto():
    """Chi ha giocato 3.000′ resta vicino al proprio dato: la stima non riscrive i fatti."""
    pool = pool_of([30.0] * 10, [900.0] * 10)           # media dei pari 3,00/90, k = 0,25 × 900 = 225
    assert pool.k == pytest.approx(POOL_WEIGHT * 900)
    stima = pool.per90(300, 3000)                       # 9,00 grezzo su un campione pieno
    assert stima == pytest.approx(8.58, abs=0.01)
    assert 8.0 < stima < 9.0


def test_la_contrazione_e_monotona():
    """Più evidenza dello stesso segno non può abbassare la stima (proprietà, non numero)."""
    pool = pool_of([30.0] * 10, [900.0] * 10)
    assert pool.per90(2, 100) < pool.per90(5, 100) < pool.per90(9, 100)
    # stesso tasso, più minuti: la stima si avvicina al grezzo (9,00/90)
    assert pool.per90(1, 10) < pool.per90(10, 100) < pool.per90(100, 1000) < 9.0


# ---- il gruppo dei pari ---------------------------------------------------------------------
def test_media_dei_pari_pesata_sul_tempo_di_gioco():
    """Non è la media delle rate: chi ha giocato di più pesa di più (aggregato, non media semplice)."""
    pool = pool_of([10.0, 0.0], [1000.0, 100.0], min_peers=2)
    assert pool is not None
    assert pool.n == 2
    assert pool.rate == pytest.approx(10.0 / 1100.0)     # 0,0091/min, non (0,01+0)/2
    assert pool.rate * 90 == pytest.approx(0.818, abs=0.001)


def test_peso_e_mediana_del_gruppo():
    """k = POOL_WEIGHT × denominatore mediano; la media usa i campioni pieni quando ci sono."""
    den = [300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0, 650.0]   # mediana 475
    pool = pool_of([1.0] * 8, den, min_peers=8)
    assert pool is not None and pool.k == pytest.approx(POOL_WEIGHT * 475)
    # con 8 pari sopra i 270′ la media non guarda i due spezzoni da 40′
    pool2 = pool_of([100.0] * 8 + [9.0, 9.0], den + [40.0, 40.0], min_peers=8)
    assert pool2 is not None and pool2.n == 8
    assert pool2.soglia == SMALL_SAMPLE_MINUTES
    assert pool2.k == pytest.approx(POOL_WEIGHT * 475)   # la mediana ignora i 40′


def test_sotto_i_minimi_non_si_stima():
    """Meno pari del minimo → nessuna media: il chiamante ripiega, non si inventa un gruppo."""
    assert pool_of([1.0] * (MIN_POOL_PEERS - 1), [500.0] * (MIN_POOL_PEERS - 1)) is None
    # denominatori sotto la soglia pubblicabile: non entrano nella media
    assert pool_of([1.0] * 20, [10.0] * 20) is None


def test_early_season_ripiega_sui_campioni_pubblicabili():
    """A settembre nessuno ha 270′: la media usa i pari sopra i 90′ e lo **dichiara** (soglia)."""
    pool = pool_of([1.0] * 10, [100.0] * 10, min_peers=8)
    assert pool is not None
    assert pool.soglia == MIN_DEN_FOR_RATE
    assert pool.n == 10


# ---- gruppi per (lega, ruolo) e ripieghi -----------------------------------------------------
def _totals(rows):
    return pd.DataFrame(rows).set_index("player_id")


def test_gruppi_per_lega_e_ruolo_con_ripieghi_e_etichette():
    """Gruppo specifico se ha abbastanza pari; altrimenti la lega; altrimenti tutte le leghe."""
    righe = [{"player_id": i, "minutes": 600.0, "shots": 10.0,
              "league_id": 55 if i < 10 else 47, "position": 3 if i < 10 else 3}
             for i in range(20)]
    groups = _totals(righe)[["league_id", "position", "minutes"]]
    totals = _totals(righe)[["shots"]]
    pools = player_pools(totals, groups, {"shots": ["shots"]}, min_peers=8)
    assert (55, 3) in pools and (47, 3) in pools and (None, None) in pools
    # lega senza pari sufficienti → ripiego sul gruppo della lega (tutti i ruoli)
    # lega 87: 5 attaccanti + 5 centrocampisti → nessun gruppo per ruolo abbastanza numeroso,
    # ma il gruppo della lega (tutti i ruoli) sì: il ripiego è dichiarato, non nascosto
    righe2 = ([r for r in righe if r["league_id"] == 55]
              + [{"player_id": 200 + i, "minutes": 600.0, "shots": 30.0, "league_id": 87,
                  "position": 3 if i < 5 else 2} for i in range(10)])
    g2 = _totals(righe2)[["league_id", "position", "minutes"]]
    t2 = _totals(righe2)[["shots"]]
    p2 = player_pools(t2, g2, {"shots": ["shots"]}, min_peers=8)
    trovato = lookup(p2, 87, 3, "shots")
    assert trovato is not None
    assert trovato[1] == (87, None)                     # ripiego sulla lega: dichiarato, non nascosto
    assert (87, 3) not in p2 and (87, None) in p2
    assert lookup(p2, 55, 3, "shots")[1] == (55, 3)     # gruppo specifico dove i pari bastano
    assert lookup(p2, 99, 9, "shots")[1] == (None, None)  # lega sconosciuta → tutte le leghe
    assert lookup(p2, 55, 3, "saves") is None            # statistica senza media → nessuna stima


def test_etichette_dei_gruppi_leggibili():
    assert group_label(None, None) == "tutte le leghe"
    assert group_label(55, 3) == "attaccanti di Serie A"
    assert group_label(55, None) == "tutti i ruoli di Serie A"
    assert group_label(999, 2) == "centrocampisti"       # lega fuori config: niente nome inventato


def test_la_nota_del_gruppo_dichiara_media_peso_e_numerosita():
    """Il tooltip delle stime deve essere verificabile: media, peso e quanti pari l'hanno formata."""
    pool = pool_of([30.0] * 12, [900.0] * 12)
    assert pool is not None
    nota = pool.note("attaccanti di Serie A")
    assert "media dei pari (attaccanti di Serie A) 3,00/90" in nota
    assert "peso k=225′" in nota and "n=12" in nota


# ---- quote (percentuali): denominatore in eventi, non in minuti -------------------------------
def test_una_quota_si_contrae_sugli_eventi_non_sui_minuti():
    """22 passaggi riusciti su 25 tentativi: il campione è 25 tentativi, non i minuti giocati."""
    pool = pool_of([80.0] * 10, [100.0] * 10, filtro=[900.0] * 10, min_peers=8)
    assert pool is not None
    assert pool.rate == pytest.approx(0.8)               # somma riusciti / somma tentativi
    assert pool.k == pytest.approx(POOL_WEIGHT * 100)     # peso in tentativi, non in minuti
    stima = pool.shrink(22, 25)                           # 88,0% grezzo su 25 tentativi
    assert stima == pytest.approx((22 + 25 * 0.8) / 50)   # 84,0%: il grezzo da 25 tentativi si muove
    assert 0.83 < stima < 0.85


def test_il_filtro_dei_pari_resta_sui_minuti():
    """Un pari da 45′ non entra nella media del gruppo anche se ha 100 tentativi (docs/23 §2)."""
    num, den, fil = [80.0] * 10, [100.0] * 10, [900.0] * 10
    senza = pool_of(num, den, min_peers=8)                         # filtro = tentativi
    con = pool_of(num + [5.0], den + [100.0], filtro=fil + [45.0], min_peers=8)
    assert senza is not None and senza.n == 10
    assert con is not None and con.n == 10                          # lo spezzone resta fuori
    assert con.rate == pytest.approx(senza.rate)


def test_la_nota_di_una_quota_dichiara_eventi_non_minuti():
    """Il tooltip di una quota dichiara media, peso (in eventi) e numerosità: verificabile."""
    pool = pool_of([80.0] * 10, [100.0] * 10, filtro=[900.0] * 10, min_peers=8)
    assert pool is not None
    nota = pool.note_pct("difensori di LaLiga", unit="tentativi")
    assert "media dei pari (difensori di LaLiga) 80,0%" in nota
    assert "peso k=25 tentativi" in nota and "n=10" in nota
    assert "/90" not in nota                                        # una quota non è una rata per 90


def test_pools_accettano_un_denominatore_in_eventi():
    """``dens`` cambia il denominatore della rata (tentativi), non la scelta dei pari (minuti)."""
    righe = [{"player_id": i, "minutes": 900.0, "tentati": 100.0, "riusciti": 80.0,
              "league_id": 55, "position": 1} for i in range(10)]
    groups = _totals(righe)[["league_id", "position", "minutes"]]
    totals = _totals(righe)[["tentati", "riusciti"]]
    pools = player_pools(totals, groups, {"pass_pct": ["riusciti"]},
                         dens={"pass_pct": ["tentati"]}, min_peers=8)
    p, chiave = lookup(pools, 55, 1, "pass_pct")
    assert chiave == (55, 1)
    assert p.rate == pytest.approx(0.8)                 # 800 riusciti / 1.000 tentativi
    assert p.k == pytest.approx(POOL_WEIGHT * 100)
    # senza `dens` il denominatore sarebbero i minuti: 800/9.000 = 8,9% — numero che non significa nulla
    p2 = player_pools(totals, groups, {"pass_pct": ["riusciti"]}, min_peers=8)[(55, 1)]["pass_pct"]
    assert p2.rate == pytest.approx(80.0 / 900.0)
