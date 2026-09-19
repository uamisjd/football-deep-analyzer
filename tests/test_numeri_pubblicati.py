"""I numeri pubblicati: separatore delle migliaia, contatori piccoli e parser che li rileggono.

Tre difetti misurati il 19/09/2026 sul sito pubblicato (docs/41 §3.1, §3.2, §3.5) e chiusi
qui con un test ciascuno:

* **numeri sopra 999 senza separatore** — «dc-elo-tilt-0.4: 5836 partite», «su 1014 gol
  nelle 303 partite» (164 schede su 4.137), «(4565/5836)» nella tabella di calibrazione,
  colonna «mercato» di `accuratezza.html`, pannello «Composizione del campione»,
  `model_versions`. Il filtro `it_num` esisteva già: mancava in quei punti.
* **contatori sotto 1.000 ma destinati a superarlo** — `docs/40` §8 chiedeva un test di
  render coi contatori a 1 perché la soglia dei mille in produzione non era mai stata
  attraversata: qui quel test c'è, con lo stesso seed usato dagli altri test di sito.
* **il gate che non rileggeva ciò che aveva chiesto di formattare** — dopo il fix,
  «42,7% (2.494/5.836)» faceva andare `check_numbers` in `ValueError` e il gate moriva:
  ogni numero pubblicato con il separatore vuole il parser che accetta quella formattazione.
"""

import importlib.util
from pathlib import Path

from fda.site.build import SiteBuilder
from fda.site.fmt import int_it
from tests.test_site import _seed


def _site_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site_mod", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_int_it_mette_il_separatore_solo_sopra_mille():
    """`int_it` è la fonte unica: 5836 → «5.836», 356 → «356», 1 → «1»."""
    assert int_it(5836) == "5.836"
    assert int_it(1014) == "1.014"
    assert int_it(1000) == "1.000"
    assert int_it(999) == "999"
    assert int_it(356) == "356"
    assert int_it(1) == "1"
    assert int_it(0) == "0"
    assert int_it(57000.0) == "57.000"      # nel parquet gli interi arrivano float
    assert int_it(None) == ""               # dato assente → vuoto, mai uno zero inventato


def test_render_con_contatori_a_uno(tmp_path):
    """`docs/40` §8: coi contatori a 1 le pagine si costruiscono e restano leggibili.

    Lo seed dei test di sito ha **una** gara valutata: è il caso limite opposto ai 5.836 di
    produzione e serve perché la soglia dei mille non era mai stata attraversata. Se un
    domani la numerazione passa da 1 a 1.000 il testo deve solo guadagnare il separatore,
    non rompersi (una divisione per zero, un «1 gare», una cella vuota).
    """
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    builder = SiteBuilder(store=st, out_dir=out)
    builder.build_accuracy(st.read("fixtures"))
    html = (out / "accuratezza.html").read_text(encoding="utf-8")

    # il contatore a 1 è concordato al singolare (non «1 gare») e i contatori del pannello
    # «Composizione del campione» compaiono davvero: prima della correzione erano i punti
    # in cui mancava il filtro e una cardinalità piccola restava invisibile
    assert "1 gara valutata" in html
    assert "1 gare" not in html
    assert "Composizione del campione" in html
    # la riga di riepilogo «Tutti» espone la numerosità: con una sola gara è «1», non vuoto
    assert "<td>Tutti</td><td class=\"r\">1</td>" in html
    # calibrazione con n=1: il rapporto k/n resta un rapporto leggibile
    assert "(1/1)" in html or "(0/1)" in html
    # nessun numero a quattro cifre senza separatore è comparso con una cardinalità piccola
    assert "5836 partite" not in html
    st.close()


def test_check_numbers_rilegge_i_numeri_con_il_separatore(tmp_path):
    """Il morso del §3.5: il gate accetta sia «2494/5836» sia «2.494/5.836» e non va in eccezione.

    Senza `_int_it` e senza `[\\d.]+` nelle regex di [3], [3b], [7] e [8], il gate **moriva**
    (`ValueError: invalid literal for int() with base 10: '42.7% (2494/5836)'`) appena il sito
    pubblicava il separatore che il gate stesso aveva chiesto.
    """
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    for numero in ("2494/5836", "2.494/5.836"):
        pagina = f"""
<table><tbody>
<tr><td>Tutti</td><td class="r">105</td><td class="r">0,2010</td><td class="r">0,5982</td>
    <td class="r">50%</td><td class="r">0,2333</td><td class="r">{numero.split('/')[1]}</td>
    <td class="r">-0,032</td></tr>
<tr><td>1 · vittoria in casa</td><td class="r">42,7% ({numero})</td><td class="r">44,0%</td>
    <td class="r">35,1%</td><td class="r">53,2%</td><td class="r">ok</td></tr>
</tbody></table>
<p>{numero.split('/')[1]} partite valutate su {numero.split('/')[1]} gol</p>
"""
        (site / "accuratezza.html").write_text(pagina, encoding="utf-8")
        # non deve andare in eccezione: è questo il difetto del 19/09
        fails, checks = vs.check_numbers(site, None)
        assert checks > 0
        assert not [f for f in fails if "ValueError" in f], fails
