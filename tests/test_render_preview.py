"""Smoke test di scripts/render_preview.py: i PNG di anteprima si generano davvero.

Non giudica l'estetica (quella si controlla a occhio su docs/preview/): verifica che lo
script giri in un ambiente pulito (Pillow dichiarata tra le dev-extras dal P2-8b) e
produca i due file alle dimensioni attese.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]


def _modulo():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rp", REPO / "scripts" / "render_preview.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_preview_genera_i_png(tmp_path):
    out = subprocess.run([sys.executable, str(REPO / "scripts" / "render_preview.py"),
                          "--out", str(tmp_path)],
                         capture_output=True, text=True, timeout=120, check=False)
    assert out.returncode == 0, out.stderr[-800:]
    for name, size in (("header-preview.png", (1200, 168)), ("home-preview.png", None)):
        f = tmp_path / name
        assert f.exists(), f"manca {name}"
        with Image.open(f) as img:
            assert img.size[0] == size[0] if size else img.size[0] == 1200
            assert img.size[1] > 900 if name == "home-preview.png" else img.size[1] == 168


def test_colori_letti_dal_css_non_copiati_a_mano():
    """Ogni colore dello script deve essere il token di site.css, non una copia.

    Fino al 18/09/2026 i token erano scritti a mano con la nota «se il CSS cambia, cambiare
    anche questi»: 7 su 18 divergevano e docs/preview/ mostrava una palette vecchia
    (`docs/27` §5.1). Ora si leggono a runtime, e questo test fissa il collegamento.
    """
    import re

    rp = _modulo()
    css = (REPO / "src/fda/site/assets/site.css").read_text(encoding="utf-8")
    blocco = css.split(":root{", 1)[1].split("\n}", 1)[0]
    tok = {k: v for k, v in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", blocco)}
    hexa = lambda t: "#{:02x}{:02x}{:02x}".format(*t)

    coppie = [("BG", "--bg"), ("SURFACE", "--surface"), ("LINE", "--line"), ("TXT", "--txt"),
              ("TXT2", "--txt2"), ("MUT", "--mut"), ("MUT2", "--mut2"), ("CALCIO", "--brand-a"),
              ("METRO", "--brand-b"), ("ACCENT", "--accent"), ("ACCENT_DIM", "--accent-dim"),
              ("ON_ACCENT", "--on-accent"), ("WIN", "--win"), ("DRAW", "--draw"),
              ("LOSE", "--lose"), ("AMBER", "--amber"), ("SURFACE2", "--surface2"),
              ("SURFACE3", "--surface3"), ("V_BG", "--v-bg"), ("V_FG", "--v-fg"),
              ("N_BG", "--n-bg"), ("N_FG", "--n-fg"), ("P_BG", "--p-bg"), ("P_FG", "--p-fg")]
    for costante, token in coppie:
        assert hexa(getattr(rp, costante)) == tok[token], f"{costante} ≠ {token} ({tok[token]})"

    grad = re.search(r"header\{background:linear-gradient\(180deg,(#\w+),(#\w+)\)", css)
    assert grad, "gradiente dell'header non più nel CSS: aggiornare lo script"
    assert hexa(rp.HEADER_TOP) == grad.group(1) and hexa(rp.HEADER_BOT) == grad.group(2)


def test_parser_della_home_legge_i_campi_veri():
    """Il parser di site/index.html deve prendere ogni campo, non lasciare buchi.

    È la garanzia che l'anteprima segua davvero il build: se il markup della card cambia,
    qui un campo torna vuoto e il test lo dice, invece di disegnare una scheda muta.
    """
    rp = _modulo()
    html = """<html><body><header><span>v2 · aggiornato 18/09/2026 20:03 (ora italiana)</span></header>
    <h1>Partite di oggi — venerdì 18 settembre 2026</h1>
    <p class="mut page-subtitle">Il quadro della giornata.</p>
    <div class="overview-metric"><strong>6</strong><span>partite</span></div>
    <div class="overview-metric"><strong>6/6</strong><span>con modello</span></div>
    <span class="mut">Nota di servizio.</span>
    <div class="day-heading"><h2 id="d1">venerdì 18 settembre 2026</h2></div>
    <article class="match-card" data-status="scheduled">
      <span class="status status-scheduled"><span class="status-dot"></span>In programma</span>
      <time datetime="x" class="kickoff">20:00</time><span class="tag">Eredivisie</span>
      <div class="match-team home-team">
        <a href="p.html">FC Groningen</a><span class="team-rank">9ª · 8 pt</span></div>
      <div class="match-score"><strong>vs</strong><span>calcio d'inizio</span></div>
      <div class="match-team away-team">
        <a href="p.html">PEC Zwolle</a><span class="team-rank">16ª · 4 pt</span></div>
      <div class="projection-copy"><strong>FC Groningen <span class="projection-p">54%</span></strong>
        <span class="projection-note">favorito · +29 punti sul secondo (Pareggio 25%)</span></div>
      <span class="h" style="width:54%"></span><span class="d" style="width:25%"></span>
      <span class="a" style="width:21%"></span>
      <div class="signal signal-agree">✓ DC ed Elo sullo stesso preferito</div>
      <div class="model-foot">Gol attesi <b>1,99 + 1,21</b></div>
      <span class="form-line"><span class="form-dots"><span class="form-dot V">V</span>
        <span class="form-dot P">P</span></span><span class="fact-value">5 pt</span></span>
      <span class="form-line"><span class="form-dots"><span class="form-dot N">N</span></span>
        <span class="fact-value">4 pt</span></span>
      <span class="fact" title="t"><svg><path d="M0 0"/></svg>
        <span class="fact-label">Meteo</span><span>nuvoloso · 16°C</span></span>
    </article></body></html>"""
    f = Path(__file__).parent / "_tmp_index.html"
    f.write_text(html, encoding="utf-8")
    try:
        letti = rp._from_site_index(f)
    finally:
        f.unlink()
    assert letti is not None
    page, cards = letti
    assert page["title"] == "Partite di oggi — venerdì 18 settembre 2026"
    assert page["updated"] == "18/09/2026 20:03 (ora italiana)"
    assert page["summary"] == [("6", "partite"), ("6/6", "con modello")]
    assert len(cards) == 1
    c = cards[0]
    attesi = {"status": "In programma", "kickoff": "20:00", "league": "Eredivisie",
              "home": "FC Groningen", "home_rank": "9ª · 8 pt", "away": "PEC Zwolle",
              "away_rank": "16ª · 4 pt", "score": "vs", "fav": "FC Groningen", "pct": 54,
              "bar": (54, 25, 21), "signal_tone": "agree"}
    for k, v in attesi.items():
        assert c[k] == v, f"{k}: {c[k]!r} ≠ {v!r}"
    assert c["form_home"] == (["V", "P"], "5 pt")
    assert c["form_away"] == (["N"], "4 pt")
    assert c["facts"] == ["Meteo nuvoloso · 16°C"]
    assert c["dot"] == rp.ACCENT          # scheduled → --accent, come .status-dot-scheduled
