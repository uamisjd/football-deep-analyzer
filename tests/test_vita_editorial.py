"""Integrazione editoriale, letture sul tema e separazione dal contesto numerico (docs/97)."""


import pytest
from bs4 import BeautifulSoup

from fda.site.club_news_checks import audit_club_life
from fda.sources.news import classify_news
from tests.test_vita_club import assert_closed, news, render_card, seed


def test_idrissa_e_larissa_non_sono_risse():
    for title in ["Nota ufficiale: Idrissa Gueye", "Il Larissa annuncia la nuova stagione", "Il sorriso di Idrissa"]:
        topic, proof = classify_news(title, "", "Fonte")
        assert topic != "fuoricampo" and proof != "rissa"
    assert classify_news("Inter: rissa fuori dal campo fra giocatori", "", "Fonte")[0] == "fuoricampo"


def test_una_nota_generica_non_inventa_un_evento(tmp_path):
    _, ma = seed(tmp_path, [{"title": "Nota ufficiale: Idrissa Gueye"}])
    result = news(ma, squad=[{"name": "Idrissa Gueye", "status": "unavailable"}])
    assert not result["notizie"] and not result["riserva"] and result["esaminate"] == 1
    assert_closed(result)


def test_analisi_e_smentite_non_sono_eventi_accertati(tmp_path):
    st, ma = seed(tmp_path, [{"title": "Inter, esonero del tecnico? La società non conferma"}])
    path = render_card(tmp_path, st, ma)
    soup = BeautifulSoup(path.read_text(), "html.parser")
    article = soup.select_one('.news-list > li')
    assert article["data-news-kind"] == "analysis"
    assert article.select_one('.news-kind').get_text(strip=True) == 'Analisi / dichiarazione'
    assert audit_club_life(path.parents[1], st.base_dir)["defects"] == 0


def test_due_sanzioni_simili_restano_due_titoli_consultabili(tmp_path):
    st, ma = seed(tmp_path, [
        {"title": "Inter: misure cautelari per gli scontri di maggio", "url": "https://example.org/old-event"},
        {"title": "Inter: misure cautelari dopo un nuovo episodio diverso", "url": "https://example.org/new-event"},
    ])
    result = news(ma)
    assert result["pubblicate"] == 1 and result["correlate"] == 1
    assert_closed(result)
    path = render_card(tmp_path, st, ma)
    html = path.read_text()
    assert "non necessariamente fatti distinti" in html
    assert 'https://example.org/old-event' in html and 'https://example.org/new-event' in html
    assert "eventi confermati" not in html and "due fonti indipendenti" not in html
    report = audit_club_life(path.parents[1], st.base_dir)
    assert report["defects"] == 0 and report["counts"]["related"] == 1


def test_fonti_correlate_e_limiti_chiudono_l_imbuto(tmp_path):
    rows = [
        {"title": f"Inter, misure cautelari per i tifosi: aggiornamento {i}", "url": f"https://example.org/{i}"}
        for i in range(7)
    ]
    _, ma = seed(tmp_path, rows)
    result = news(ma)
    assert result["pubblicate"] == 1 and result["correlate"] == 6
    assert len(result["notizie"][0]["related"]) == 6
    assert_closed(result)


def test_nessun_ripiego_su_statistiche_o_vip_per_riempire(tmp_path):
    st, ma = seed(tmp_path, [
        {"title": "Inter, sfida sulla destra: il giovane vuole la maglia"},
        {"title": "Inter, i minutaggi dei nazionali sono da record"},
        {"title": "Inter, un VIP speciale in tribuna"},
    ])
    result = news(ma)
    assert result["pubblicate"] == 0 and result["correlate"] == 0
    assert_closed(result)
    path = render_card(tmp_path, st, ma)
    assert "non abbassiamo la soglia per riempire la pagina" in path.read_text()


def test_i_dati_numerici_sono_etichettati_come_contesto_non_notizie(tmp_path):
    from fda.site.build import SiteBuilder
    from tests.test_site import _seed

    st = _seed(tmp_path)
    builder = SiteBuilder(store=st, out_dir=tmp_path / "site")
    builder.build_match_pages({5749669})
    soup = BeautifulSoup((tmp_path / "site/partite/5749669.html").read_text(), 'html.parser')
    card = soup.find(id='notizie')
    context = card.select_one('details.news-context')
    assert context is not None and "non sono notizie di stampa" in context.summary.get_text()
    assert context.select('.sapere')
    assert not card.select('.news-list .sapere')


def test_copertura_singolare_e_titoli_principali_letti_dal_dom(tmp_path):
    from fda.site.club_news_checks import primary_titles

    st, ma = seed(tmp_path, [{"title": "Inter, la polizia esegue misure cautelari dopo gli scontri tra i tifosi"}])
    path = render_card(tmp_path, st, ma)
    html = path.read_text()
    assert "1 titolo consultabile" in html and "1 titoli" not in html
    assert "1 voce archiviata" in html and "1 voci" not in html
    assert primary_titles(html) == {"Inter, la polizia esegue misure cautelari dopo gli scontri tra i tifosi"}


def test_marcatore_clima_non_include_letture_sul_tema_o_riserve(tmp_path):
    from fda.site.club_news_checks import primary_titles

    st, ma = seed(tmp_path, [
        {"title": "Inter, misure cautelari: primo articolo sui tifosi", "url": "https://example.org/1"},
        {"title": "Inter, misure cautelari: un altro articolo sui tifosi", "url": "https://example.org/2"},
    ])
    path = render_card(tmp_path, st, ma)
    expected = {n["title"] for n in news(ma)["notizie"]}
    assert len(expected) == 1 and primary_titles(path.read_text()) == expected


@pytest.mark.parametrize("field", ["kind", "related_count"])
def test_audit_rifiuta_etichette_o_contatori_non_veri(tmp_path, field):
    st, ma = seed(tmp_path, [
        {"title": "Inter, misure cautelari dopo gli scontri", "url": "https://example.org/1"},
        {"title": "Inter, altre misure cautelari per i tifosi", "url": "https://example.org/2"},
    ])
    path = render_card(tmp_path, st, ma)
    assert audit_club_life(path.parents[1], st.base_dir)["defects"] == 0
    html = path.read_text()
    if field == 'kind':
        html = html.replace('Evento segnalato', 'Fatto accertato')
    else:
        html = html.replace('1 lettura sul tema', '2 letture sul tema')
    assert html != path.read_text()
    path.write_text(html)
    assert audit_club_life(path.parents[1], st.base_dir)["defects"] > 0


def test_letture_sul_tema_in_grassetto_e_concordate_per_verify_site(tmp_path):
    """Regressione issue #109 (5749705.html): contatore in <b>...</b> e singolare '1 lettura sul tema'."""
    import re

    from scripts import verify_site as vs

    st, ma = seed(tmp_path, [
        {"title": "Inter, misure cautelari dopo gli scontri", "url": "https://example.org/1"},
        {"title": "Inter, altre misure cautelari per i tifosi", "url": "https://example.org/2"},
    ])
    path = render_card(tmp_path, st, ma)
    html = path.read_text()
    assert "· <b>1 lettura sul tema</b>" in html
    assert "1 letture sul tema" not in html
    p = vs.Text()
    p.feed(html)
    assert vs.AGREEMENT.search("".join(p.parts)) is None
    assert vs.AGREEMENT.search("1 letture sul tema") is not None
    blocchi = re.split(r'<p (?:class="[^"]*" )?style="margin:12px 0 6px"><b>', html)[1:]
    head = blocchi[0].split("<ul", 1)[0]
    m = re.search(r"· (?:<b>)?(\d+) lettur[ae] sul tema", head)
    assert m is not None and int(m.group(1)) == 1

