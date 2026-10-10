"""Card «laboratorio» della scheda partita (docs/73, invariante [46]).

Cosa si verifica qui, e perché:

* il what-if **sposta** le λ come dicono le regole dichiarate, e le tre formule riscritte
  dentro ``scripts/verify_site.py`` (invariante [46]) concordano con quelle del modello su
  una griglia di input: l'indipendenza dell'oracolo è un fatto misurabile, non promesso;
* un dato mancante resta **mancante** («dato non disponibile», λ non toccate) e non diventa
  uno zero che inclina la previsione di nascosto;
* il card sta **sotto** la previsione salvata, esce sulle partite ancora da giocare e non
  su quelle finite, e **non scrive** nulla in ``predictions.parquet``.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import UTC
from pathlib import Path

import pytest

from fda.models.predict import (
    ABSENCES_K,
    MARKET_VALUE_K,
    absences_tilt,
    market_value_tilt,
    rest_tilt,
)
from fda.site.build import SiteBuilder
from fda.site.laboratorio import (
    ASSENZE_K_PROTOCOLLO,
    IDEE,
    MERCATO_K_SOSTENUTO,
    laboratorio,
)
from tests.test_site import _seed


def _verify_site():
    """Modulo ``scripts/verify_site.py`` caricato per percorso (come in test_site.py)."""
    p = Path(__file__).parent.parent / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _base(lh: float = 1.40, la: float = 1.10, rho: float = -0.04) -> dict:
    return {"lambda_home": lh, "lambda_away": la, "dc_rho": rho,
            "p_home": 0.40, "p_draw": 0.28, "p_away": 0.32}


def test_le_formule_dell_oracolo_coincidono_con_quelle_del_modello():
    """[46] Le tre formule riscritte in `verify_site` riproducono i tilt di `predict.py`.

    È la condizione che rende sensato l'invariante: se le due implementazioni divergessero,
    [46] segnalerebbe differenze che non esistono (o, peggio, ne nasconderebbe di vere).
    La griglia copre i casi limite dichiarati: rapporti fuori dalla clip, contributi oltre
    il minimo del fattore, giorni sulle soglie (2/3/4/5/6/7) e squadre senza dato.
    """
    vs = _verify_site()
    coppie_lambda = [(1.4, 1.1), (0.6, 2.3), (2.9, 0.4)]
    valori = [(None, None), (100e6, 50e6), (50e6, 400e6), (1e9, 1e6), (12e6, 90e6)]
    persi = [(None, None), (0.0, 0.0), (0.4, 0.0), (0.0, 1.9), (2.4, 0.7), (9.9, 9.9)]
    riposi = [(None, None), (1, 1), (2, 7), (3, 3), (4, 5), (6, 9), (7, 7), (20, 19), (0, 12)]
    # i due k con cui il card pubblica il what-if: quello sostenuto e la costante del codice
    k_mercato = (MERCATO_K_SOSTENUTO, MARKET_VALUE_K)
    k_assenze = (ASSENZE_K_PROTOCOLLO, ABSENCES_K)
    confronto = 0
    for lh, la in coppie_lambda:
        for hv, av in valori:
            for k in k_mercato:
                assert vs._lab_mercato(lh, la, hv, av, k=k) == pytest.approx(
                    market_value_tilt(lh, la, hv, av, k=k)[:2], abs=1e-12)
                confronto += 1
        for ch, ca in persi:
            for k in k_assenze:
                assert vs._lab_assenze(lh, la, ch, ca, k=k) == pytest.approx(
                    absences_tilt(lh, la, ch, ca, k=k)[:2], abs=1e-12)
                confronto += 1
        for rh, ra in riposi:
            assert vs._lab_riposo(lh, la, rh, ra) == pytest.approx(
                rest_tilt(lh, la, rh, ra)[:2], abs=1e-12)
            confronto += 1
    assert confronto == 3 * (2 * len(valori) + 2 * len(persi) + len(riposi))


def test_il_what_if_sposta_le_lambda_e_ricalcola_l_1x2():
    """Il card mostra λ e 1X2 diverse, e la somma dell'1X2 resta 100 a meno di un arrotondamento."""
    base = _base()
    lab = laboratorio(base, rest_home=7, rest_away=2, valore_home=320e6, valore_away=80e6,
                      perso_home=0.9, perso_away=0.0)
    assert lab is not None
    assert (lab["lh"], lab["la"]) == (1.40, 1.10)
    assert sum((lab["p_home"], lab["p_draw"], lab["p_away"])) == pytest.approx(1.0, abs=1e-9)
    righe = {r["key"]: r for r in lab["righe"]}
    # il mercato è l'unico con un effetto visibile su questo caso: rapporto 4× → clip 4,0
    assert righe["mercato"]["sposta"] and righe["mercato"]["lh"] > 1.40
    # le assenze pesano sulla casa: il totale resta, quindi la λ di casa scende e l'altra sale
    assert righe["assenze"]["sposta"]
    assert righe["assenze"]["lh"] < 1.40 and righe["assenze"]["la"] > 1.10
    # il totale dei gol attesi è preservato per costruzione: 1,40 + 1,10 = 2,50
    assert righe["assenze"]["lh"] + righe["assenze"]["la"] == pytest.approx(2.50, abs=0.011)
    # riposo 7 contro 2: fattori opposti, e qui lo spostamento si vede
    assert righe["riposo"]["sposta"]
    for r in lab["righe"]:
        assert sum((r["p_home"], r["p_draw"], r["p_away"])) == pytest.approx(1.0, abs=1e-9)
        assert r["d_pp"] >= 0 and r["d_lambda"] > 0


def test_dato_mancante_non_diventa_zero():
    """Senza input nessuna λ si muove e la riga lo dichiara: nessuno «0» inventato."""
    lab = laboratorio(_base(), rest_home=None, rest_away=None,
                      valore_home=None, valore_away=None, perso_home=None, perso_away=None)
    assert lab is not None
    assert len(lab["righe"]) == len(IDEE) == 3
    for r in lab["righe"]:
        assert r["disponibile"] is False
        assert r["motivo"]
        assert (r["lh"], r["la"]) == (1.40, 1.10)
        assert r["sposta"] is False
        assert r["in_home"] is None and r["in_away"] is None
    assert lab["n_spostano"] == 0


def test_una_sosta_uguale_per_tutti_non_sposta_nulla():
    """Il riposo preserva il totale: con la stessa sosta (20 e 19 giorni) non cambia nulla.

    È il caso reale delle 65 prossime del 2026-10-10 (docs/73 §3): «non sposta nulla» è
    una misura, non una riga vuota, e va pubblicata come tale.
    """
    lab = laboratorio(_base(), rest_home=20, rest_away=19, valore_home=None, valore_away=None,
                      perso_home=0.0, perso_away=0.0)
    righe = {r["key"]: r for r in lab["righe"]}
    assert righe["riposo"]["disponibile"] and righe["riposo"]["sposta"] is False
    assert righe["riposo"]["d_lambda"] == pytest.approx(0.0, abs=1e-12)
    # «nessun assente con la distinta pubblicata» è uno zero misurato: disponibile, ma non sposta
    assert righe["assenze"]["disponibile"] and righe["assenze"]["in_home"] == 0.0
    assert righe["assenze"]["sposta"] is False


def test_le_misure_d_archivio_sono_quelle_registrate_nei_documenti():
    """Campioni, intervalli e verdetti sono **misure registrate**, pinnati uno per uno.

    [46] verifica i numeri che si possono ricalcolare a ogni build (λ e 1X2 del what-if).
    Questi no: vengono dal backtest, e nessun ricalcolo quotidiano li rifà. Sono quindi
    costanti con provenienza, e il rischio è che restino indietro quando una misura viene
    rifatta: qui si pinnano sui valori di `docs/69` §1 e `docs/71` §2-§3, così chi li
    cambia deve aver rifatto la misura e aggiornato il documento che la registra.

    I numeri sono confrontati in forma normalizzata (il meno tipografico «−» vale «-»):
    quello che conta è la cifra, non il glifo con cui è scritta.
    """
    def _n(testo: str) -> str:
        return testo.replace("\u2212", "-").replace("\u2013", "-")

    idee = {i.key: i for i in IDEE}
    assert set(idee) == {"mercato", "assenze", "riposo"}

    mercato = idee["mercato"]
    assert mercato.campione.startswith("341 gare")                  # docs/69 §1
    assert _n(mercato.misura).count("-0,004785") == 1               # k = 0,03, l'unico con IC fuori zero
    assert "[−0,008769; −0,000581]".replace("\u2212", "-") in _n(mercato.misura)
    assert _n(mercato.misura).count("-0,009475") == 1               # k = 0,12, indistinguibile da zero
    assert "[−0,025091; +0,007122]".replace("\u2212", "-") in _n(mercato.misura)
    assert mercato.k_usato == MERCATO_K_SOSTENUTO == 0.03
    assert mercato.k_dichiarato == MARKET_VALUE_K == 0.12

    assenze = idee["assenze"]
    assert "98 gare" in assenze.campione and "137 → 98" in assenze.campione    # docs/71 §2
    assert "300 gare" in assenze.misura and "5 leghe su 7" in assenze.misura   # docs/71 §3.2
    assert assenze.verdetto.startswith("non testabile")
    assert assenze.k_usato == ASSENZE_K_PROTOCOLLO == 0.20          # tetto della griglia {0; 0,1; 0,2}
    assert assenze.k_dichiarato == ABSENCES_K == 0.30               # fuori dalla griglia

    riposo = idee["riposo"]
    assert "1.591 λ" in riposo.campione and "5.895" in riposo.campione         # docs/69 §1
    assert "+0,0000787" in riposo.misura and "[+0,0000154; +0,000141]" in riposo.misura
    assert riposo.verdetto.startswith("non usata")
    assert riposo.k_usato is None and riposo.k_dichiarato is None

    # il k del what-if è quello sostenuto, non la costante del codice (revisione del
    # 2026-10-10, `docs/74` §10): con il k sbagliato lo spostamento vale ~4 volte tanto.
    assert MERCATO_K_SOSTENUTO < MARKET_VALUE_K
    assert ASSENZE_K_PROTOCOLLO < ABSENCES_K
    for idea in IDEE:
        assert idea.fonte.startswith("docs/")
        assert idea.formula and idea.verdetto and idea.verdetto_help


def test_il_confronto_con_il_k_dichiarato_esce_in_pagina(tmp_path):
    """Il what-if col k sostenuto e il confronto col k del codice: due numeri, due attributi."""
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    futura = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    st.close()
    righe = re.findall(r'<tr data-idea="([a-z]+)"[^>]*>', futura)
    assert righe == ["mercato", "assenze", "riposo"]
    mercato = re.search(r'<tr data-idea="mercato"[^>]*>', futura).group(0)
    assenze = re.search(r'<tr data-idea="assenze"[^>]*>', futura).group(0)
    riposo = re.search(r'<tr data-idea="riposo"[^>]*>', futura).group(0)
    # le due idee con un k pubblicano entrambe le coppie di λ (what-if + confronto)
    for riga in (mercato, assenze):
        assert "data-lh2=" in riga and "data-q1=" in riga, riga
    assert "data-lh2=" not in riposo, "il riposo non ha un k: nessun confronto"
    assert "k = 0,03" in futura and "k = 0,12" in futura
    assert "k = 0,20" in futura and "k = 0,30" in futura


def test_senza_previsione_niente_card():
    assert laboratorio(None, rest_home=3, rest_away=4, valore_home=1e6, valore_away=2e6,
                       perso_home=0.1, perso_away=0.2) is None


def test_il_card_non_tocca_la_previsione_salvata(tmp_path):
    """Il laboratorio legge, non scrive: `predictions.parquet` è identico dopo la scheda.

    È la condizione 4 di `docs/73` §5, ed è la ragione per cui il card può stare in pagina
    senza diventare un secondo pronostico: la previsione pubblicata in cima resta quella
    calcolata da `fda predict`.
    """
    from fda.site.analysis import MatchAnalysis

    st = _seed(tmp_path)
    prima = (tmp_path / "processed" / "predictions.parquet").read_bytes()
    ma = MatchAnalysis(st)
    fx = st.read("fixtures")
    riga = fx[fx.match_id == 5749669].iloc[0]
    kickoff = riga["utc_kickoff"].to_pydatetime() if hasattr(riga["utc_kickoff"], "to_pydatetime") \
        else riga["utc_kickoff"]
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)
    pred = ma.preds[ma.preds.match_id == 5749669].iloc[0].to_dict()
    istantanea = dict(pred)
    lab = ma.laboratorio(5749669, int(riga.home_id), int(riga.away_id), kickoff, pred)
    assert lab is not None
    assert pred == istantanea, "il card ha modificato il dict della previsione"
    ma.store.close()
    assert (tmp_path / "processed" / "predictions.parquet").read_bytes() == prima


def test_il_card_esce_sotto_la_previsione_e_solo_sulle_prossime(tmp_path):
    """Posizione (dopo «Come nasce questa probabilità») e presenza solo pre-partita."""
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669, 5749645})
    futura = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    finita = (out / "partite" / "5749645.html").read_text(encoding="utf-8")

    assert 'id="laboratorio"' in futura
    assert 'id="laboratorio"' not in finita, "su una gara finita il what-if non ha senso"
    assert futura.index('id="previsione"') < futura.index('id="laboratorio"')
    # docs/73 §5.1: dentro l'area previsione ma **sotto** la previsione salvata e sotto
    # «Come nasce questa probabilità»; il campione di prova non ha i passi salvati, quindi
    # la scomposizione non esce e si controlla la posizione che esiste davvero.
    if 'id="scomposizione"' in futura:
        assert futura.index('id="scomposizione"') < futura.index('id="laboratorio"')
    if 'id="fascia-storica"' in futura:
        assert futura.index('id="laboratorio"') < futura.index('id="fascia-storica"')
    # la pagina dice che non è un secondo pronostico, e ogni riga ha idea, misura e verdetto
    assert "non usate</b> in questa previsione" in futura
    righe = re.findall(r'<tr data-idea="([a-z]+)"', futura)
    assert righe == ["mercato", "assenze", "riposo"]
    for chiave in ("341 gare", "98 gare", "1.591 λ", "ΔRPS"):
        assert chiave in futura, f"manca la misura d'archivio: {chiave}"
    st.close()


def test_l_invariante_46_ricalcola_il_card(tmp_path):
    """[46] su un sito generato: λ, 1X2 e dati usati tornano senza le formule del modello."""
    vs = _verify_site()
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    st.close()
    fails, checks = vs.check_laboratorio(out, tmp_path / "processed")
    assert not fails, fails[:5]
    assert checks >= 10, f"troppi pochi controlli: {checks}"


def test_l_invariante_46_vede_anche_un_confronto_falso(tmp_path):
    """[46] controlla anche la seconda coppia: il k del codice non è un numero di facciata."""
    vs = _verify_site()
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    st.close()
    pagina = out / "partite" / "5749669.html"
    html = pagina.read_text(encoding="utf-8")
    riga = re.search(r'<tr data-idea="mercato"[^>]*data-lh2="([-\d.]+)"', html)
    assert riga, "la riga del mercato non pubblica il confronto col k dichiarato"
    falsa = html.replace(f'data-lh2="{riga.group(1)}"', 'data-lh2="2.50"', 1)
    pagina.write_text(falsa, encoding="utf-8")
    fails, _ = vs.check_laboratorio(out, tmp_path / "processed")
    assert fails and any("confronto" in f for f in fails), fails[:5]


def test_l_invariante_46_vede_un_numero_falso(tmp_path):
    """[46] non è di facciata: una λ alterata nella pagina viene scoperta."""
    vs = _verify_site()
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    st.close()
    pagina = out / "partite" / "5749669.html"
    html = pagina.read_text(encoding="utf-8")
    riga = re.search(r'<tr data-idea="riposo"[^>]*>', html)
    assert riga, "riga del riposo assente"
    falsa = riga.group(0).replace('data-lh="', 'data-lh="9').replace('data-la="', 'data-la="9')
    pagina.write_text(html.replace(riga.group(0), falsa), encoding="utf-8")
    fails, _ = vs.check_laboratorio(out, tmp_path / "processed")
    assert fails and any("riposo" in f for f in fails), fails[:5]
