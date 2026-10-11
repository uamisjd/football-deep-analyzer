"""La terna 1/X/2 pubblicata chiude sempre a 100 (docs/78 §14)."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from fda.site.fmt import pct_triple


def test_pct_triple_chiude_sempre_a_cento():
    """La somma è esatta in unità intere, che è ciò che il lettore vede a schermo.

    Con un decimale i tre valori sono float: 33,4 + 33,3 + 33,3 fa 99,99999999999999 in
    aritmetica binaria (la stessa ragione per cui esiste `displayed_sum`). A schermo si
    legge «33,4 / 33,3 / 33,3» = 100,0: qui si confronta la somma **delle cifre stampate**.
    """
    casi = [(0.3335, 0.3335, 0.333), (0.6111, 0.2778, 0.1111), (0.515, 0.235, 0.25),
            (0.625, 0.25, 0.125), (0.42, 0.31, 0.27), (1 / 3, 1 / 3, 1 / 3)]
    for t in casi:
        assert sum(pct_triple(t, 0)) == 100, t
        assert sum(round(v * 10) for v in pct_triple(t, 1)) == 1000, t


def test_terne_pubblicate_sommano_cento(tmp_path):
    """Le tre grafie pubblicate (tabella, testi in evidenza, description) chiudono a 100."""
    from fda.site.build import SiteBuilder
    from tests.test_site import _seed

    st = _seed(tmp_path)
    out = tmp_path / "sito"
    b = SiteBuilder(store=st, out_dir=out)
    fx = st.read("fixtures")
    b.build_indexes(fx)
    b.build_accuracy(fx)
    b.build_match_pages(set(fx.match_id.tolist()))
    pat = {
        "tabella": re.compile(r'<td class="r">(\d{1,3}) / (\d{1,3}) / (\d{1,3})</td>'),
        "testo": re.compile(r"1 (\d{1,3})% · X (\d{1,3})% · 2 (\d{1,3})%"),
        "descrizione": re.compile(r"1 (\d{1,3})% X (\d{1,3})% 2 (\d{1,3})%"),
    }
    trovate = 0
    for pagina in sorted(out.rglob("*.html")):
        h = pagina.read_text(encoding="utf-8")
        for dove, p in pat.items():
            for m in p.finditer(h):
                trovate += 1
                somma = sum(int(x) for x in m.groups())
                assert somma == 100, f"{pagina.name} ({dove}): {m.group(0)} = {somma}"
    assert trovate > 0, "nessuna terna pubblicata nel sito di prova: il test non prova nulla"
    st.close()


def _somma(m: re.Match) -> int:
    return sum(int(x) for x in m.groups())


def test_terna_avversariale_nel_testo_in_evidenza():
    """(0,615 · 0,235 · 0,15): con tre `round()` indipendenti la terna somma 101.

    61,5 → 62 · 23,5 → 24 · 15,0 → 15: 101. `pct_triple` distribuisce il resto e chiude a
    100. Il caso non è teorico: 11 righe su 40 della tabella Accuratezza erano così.
    """
    from fda.site.build import _t1x2_testo

    testo = _t1x2_testo({"p_home": 0.615, "p_draw": 0.235, "p_away": 0.15})
    m = re.search(r"(\d+)% · X (\d+)% · 2 (\d+)%", testo)
    assert m, testo
    assert sum(int(x) for x in m.groups()) == 100, testo
    assert testo == "1 62% · X 23% · 2 15% — incerta"


def test_tabella_accuratezza_chiude_a_cento_con_numeri_avversariali(tmp_path):
    """La tabella «Ultime partite valutate» pubblica la terna da `pct_triple`."""
    from fda.site.build import SiteBuilder
    from fda.store import Store
    from tests.test_accuratezza_copertura import _fx, _pred

    # timestamp con fuso: `build_accuracy` legge il calendario nel fuso di visualizzazione
    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame([_fx(900001, "2026-09-01 18:00+00:00", 2, 1)]))
    st.write("predictions", pd.DataFrame([
        _pred(900001, "2026-09-01 18:00+00:00", "2026-08-30 10:00+00:00",
              ph=0.615, pd_=0.235, pa=0.15)]))
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_accuracy(st.read("fixtures"))
    html = (out / "accuratezza.html").read_text(encoding="utf-8")
    terne = re.findall(r'<td class="r">(\d{1,3}) / (\d{1,3}) / (\d{1,3})</td>', html)
    assert terne, "la tabella «Ultime partite valutate» non è stata pubblicata"
    for a, b, c in terne:
        assert int(a) + int(b) + int(c) == 100, terne
    assert (a, b, c) == ("62", "23", "15"), terne      # non «62 / 24 / 15»
    st.close()


def test_descrizione_della_scheda_chiude_a_cento(tmp_path):
    """La description (meta e og:) va su Google: la terna deve chiudere a 100."""
    from fda.site.build import SiteBuilder
    from tests.test_site import _seed

    st = _seed(tmp_path)
    pr = st.read("predictions")
    futuro = int(st.read("fixtures").query("status == 'scheduled'").match_id.iloc[0])
    pr.loc[pr.match_id == futuro, ["p_home", "p_draw", "p_away"]] = [0.615, 0.235, 0.15]
    st.write("predictions", pr)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({futuro})
    html = (out / "partite" / f"{futuro}.html").read_text(encoding="utf-8")
    terne = re.findall(r"1 (\d{1,3})% X (\d{1,3})% 2 (\d{1,3})%", html)
    assert terne, "la scheda non ha pubblicato la terna 1X2 nella description"
    for a, b, c in terne:
        assert int(a) + int(b) + int(c) == 100, terne
    assert (a, b, c) == ("62", "23", "15"), terne
    st.close()


# riga della tabella dell'andamento 1X2 nelle schede: minuto, punteggio, poi la terna
RIGA_WP = re.compile(r'<td class="mut small">(\d+)\'</td>\s*<td>[^<]*</td>\s*'
                     r'<td class="r">(\d{1,3})%</td>\s*<td class="r">(\d{1,3})%</td>\s*'
                     r'<td class="r">(\d{1,3})%</td>')


def test_andamento_1x2_della_scheda_chiude_a_cento(tmp_path):
    """La tabella dell'andamento minuto per minuto: i tre `round()` facevano 99 o 101.

    Con λ 0,5/0,5 sulla fixture Inter–Monza la scheda pubblicava 27/47/27 e 2/15/84
    (entrambe 101 su 754 righe del sito: 153 rotte in 103 pagine). È la stessa classe
    della tabella Accuratezza: la terna passa da `pct_triple`.
    """
    from fda.site.build import SiteBuilder
    from tests.test_site import _seed

    st = _seed(tmp_path)
    mid = int(st.read("fixtures").query("status == 'finished'").match_id.iloc[0])
    pr = st.read("predictions")
    pr.loc[pr.match_id == mid, ["lambda_home", "lambda_away"]] = [0.5, 0.5]
    st.write("predictions", pr)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({mid})
    html = (out / "partite" / f"{mid}.html").read_text(encoding="utf-8")
    righe = RIGA_WP.findall(html)
    assert len(righe) >= 2, "la scheda non ha pubblicato la tabella dell'andamento 1X2"
    for minuto, a, b, c in righe:
        assert int(a) + int(b) + int(c) == 100, (minuto, a, b, c)
    assert [r[1:] for r in righe] != [("27", "47", "27"), ("2", "15", "84")], righe
    st.close()


def test_check_47_intercetta_le_quattro_grafie(tmp_path):
    """Il gate [47] deve riconoscere la terna rotta in tutte le forme che il sito pubblica."""
    import importlib.util
    import sys

    src = Path(__file__).resolve().parents[1] / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("_vs_terne", src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_vs_terne"] = mod
    spec.loader.exec_module(mod)

    (tmp_path / "sana.html").write_text(
        '<td class="r">63 / 19 / 18</td> 1 62% · X 23% · 2 15% 1 62% X 23% 2 15%\n'
        '<td class="mut small">50\'</td>\n<td>1-0 · Rossi</td>\n'
        '<td class="r">44%</td>\n<td class="r">30%</td>\n<td class="r">26%</td>',
        encoding="utf-8")
    (tmp_path / "tabella.html").write_text('<td class="r">63 / 19 / 17</td>', encoding="utf-8")
    (tmp_path / "testo.html").write_text("1 62% · X 23% · 2 16%", encoding="utf-8")
    (tmp_path / "descrizione.html").write_text("1 62% X 23% 2 16%", encoding="utf-8")
    (tmp_path / "andamento.html").write_text(
        '<td class="mut small">50\'</td>\n<td>1-0 · Rossi</td>\n'
        '<td class="r">6%</td>\n<td class="r">21%</td>\n<td class="r">72%</td>', encoding="utf-8")

    fails, checks = mod.check_terne_1x2(tmp_path)
    # 4 terne sane (una per grafia) + 4 rotte (una per file)
    assert checks == 8, f"una terna per grafia su ogni file: {checks}"
    assert len(fails) == 4, fails
    assert all("somma" in f for f in fails), fails
    assert not any("sana" in f for f in fails), "falso positivo sul file sano"
