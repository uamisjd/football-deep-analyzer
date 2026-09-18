"""Font auto-ospitati: il sito non deve chiamare Google a runtime (docs/26 §8).

Il difetto di partenza era misurabile: **8.252** link a ``fonts.googleapis.com`` su 4.126
pagine pubblicate (due ``preconnect`` + un foglio di stile in ogni ``<head>``), in un sito
che per regola non usa servizi di terzi. La scelta dell'utente del 2026-09-18 è servirli
dal sito; siccome dal sandbox dell'agente Google non è raggiungibile (``curl`` → 000), i
binari non sono nel repository e il meccanismo deve funzionare in **entrambi** gli stati:
con i font locali nessun link a Google, senza i font locali il caricamento da Google
rimane — una pagina senza caratteri sarebbe un regresso peggiore della richiesta esterna.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from fda.site.build import SiteBuilder, font_locali_presenti
from fda.store import Store

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("font_locali", REPO / "scripts" / "font_locali.py")
font_locali = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(font_locali)  # type: ignore[union-attr]


def _builder(tmp_path: Path, font_css: bool) -> str:
    """Rende ``base.html`` con l'ambiente del builder (filtri inclusi), su uno store vuoto."""
    b = SiteBuilder(store=Store(tmp_path / "processed"), out_dir=tmp_path / "out")
    b.env.globals["font_css"] = font_css
    b.env.globals["css_v"] = "abc123"
    return b.env.get_template("base.html").render(
        root="", generated_at=datetime.now(UTC), section="")


def test_senza_font_locali_resta_google(tmp_path: Path):
    html = _builder(tmp_path, font_css=False)
    assert "fonts.googleapis.com/css2?family=Sora" in html
    assert 'rel="preconnect" href="https://fonts.gstatic.com"' in html
    assert "assets/fonts/fonts.css" not in html


def test_con_font_locali_nessuna_richiesta_a_google(tmp_path: Path):
    html = _builder(tmp_path, font_css=True)
    assert "fonts.googleapis.com" not in html, "il sito non deve chiamare Google a runtime"
    assert "fonts.gstatic.com" not in html
    assert 'href="assets/fonts/fonts.css?v=abc123"' in html


def test_la_rilevazione_dei_font_locali_e_onesta(tmp_path: Path):
    """True solo con CSS **e** almeno un woff2: un CSS orfano non basta."""
    fonts = tmp_path / "fonts"
    assert font_locali_presenti(tmp_path) is False, "directory inesistente"
    fonts.mkdir()
    (fonts / "fonts.css").write_text("@font-face{}", encoding="utf-8")
    assert font_locali_presenti(tmp_path) is False, "CSS senza woff2"
    (fonts / "sora.woff2").write_bytes(b"wOF2")
    assert font_locali_presenti(tmp_path) is True
    # e sul repository vero risponde secondo lo stato reale, qualunque esso sia
    assert font_locali_presenti() in (True, False)


def test_il_css_remoto_viene_localizzato():
    """La logica di riscrittura è pura: si testa senza rete, con uno scaricatore finto."""
    chiamati: list[str] = []

    def scarica(url: str) -> bytes:
        chiamati.append(url)
        return b"wOF2" + url[-6:].encode()

    remoto = ("/* [2] */\n@font-face{font-family:'Sora';src:url(https://fonts.gstatic.com/s/a.woff2)}\n"
              "@font-face{font-family:'Inter';src:url(https://fonts.gstatic.com/s/b.woff2)}\n"
              "@font-face{font-family:'Sora';src:url(https://fonts.gstatic.com/s/a.woff2)}")
    vecchio_dir = font_locali.FONTS_DIR
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        font_locali.FONTS_DIR = Path(td)
        try:
            css, nomi = font_locali.riscrivi_css(remoto, scarica)
        finally:
            font_locali.FONTS_DIR = vecchio_dir
    assert "fonts.gstatic.com" not in css, "nessuna URL remota deve sopravvivere"
    assert "url(a.woff2)" in css and "url(b.woff2)" in css
    assert nomi == ["a.woff2", "b.woff2"], "un sottoinsieme ripetuto si scarica una volta"
    assert chiamati == ["https://fonts.gstatic.com/s/a.woff2",
                        "https://fonts.gstatic.com/s/b.woff2"]


def test_il_pacchetto_dichiara_i_font():
    """Quando ``font_locali.py`` verrà eseguito, i binari devono entrare nella wheel.

    È la stessa classe di difetto di ``site.css`` (docs/26 §2): un file letto a runtime con
    ``Path(__file__).parent/...`` che ``package-data`` non dichiara sparisce dall'installazione
    non editable. Il glob deve esserci **prima** che i file arrivino.
    """
    import tomllib

    with (REPO / "pyproject.toml").open("rb") as fh:
        patterns = tomllib.load(fh)["tool"]["setuptools"]["package-data"]["fda.site"]
    assert any(g.startswith("assets/fonts/") for g in patterns), patterns


def test_check_segnala_i_file_mancanti_senza_cadere(tmp_path: Path, capsys):
    """Il ramo di errore di ``--check`` deve stampare e uscire 1, non sollevare.

    Difetto reale introdotto e trovato da ``ruff`` (F821) mentre si scriveva lo script: la
    riga di diagnostica citava una variabile inesistente, quindi il controllo avrebbe
    sollevato ``NameError`` esattamente nel caso in cui doveva segnalare un problema.
    """
    (tmp_path / "fonts.css").write_text(
        "@font-face{src:url(a.woff2)}\n@font-face{src:url(b.woff2)}", encoding="utf-8")
    (tmp_path / "a.woff2").write_bytes(b"wOF2")  # presente; `b.woff2` manca
    vecchio = font_locali.FONTS_DIR
    font_locali.FONTS_DIR = tmp_path
    try:
        assert font_locali.check() == 1
        assert "b.woff2" in capsys.readouterr().out
    finally:
        font_locali.FONTS_DIR = vecchio


def test_check_passa_con_font_completi(tmp_path: Path, capsys):
    (tmp_path / "fonts.css").write_text("@font-face{src:url(a.woff2)}", encoding="utf-8")
    (tmp_path / "a.woff2").write_bytes(b"wOF2")
    (tmp_path / "LICENSE.txt").write_text("OFL", encoding="utf-8")
    vecchio = font_locali.FONTS_DIR
    font_locali.FONTS_DIR = tmp_path
    try:
        assert font_locali.check() == 0
        assert "1 woff2" in capsys.readouterr().out
    finally:
        font_locali.FONTS_DIR = vecchio
