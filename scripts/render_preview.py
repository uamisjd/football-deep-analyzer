"""Genera i PNG di anteprima dell'header e della home di CalcioMetro.

Disegna con Pillow (nessuna libreria di sistema né browser richiesti). **Niente è copiato a
mano** (revisione del 18/09/2026, `docs/27` §5.1):

- i **colori** si leggono a runtime da ``assets/site.css`` (token ``:root`` e gradiente
  dell'header) e da ``templates/base.html`` (badge del logo nell'SVG data-URI). Prima erano
  una copia manuale con la nota «se il CSS cambia, cambiare anche questi»: misurato allora,
  **7 token su 18 divergevano** dal CSS e i PNG versionati mostravano una palette che il sito
  non usava più. Se un token sparisce lo script si ferma nominandolo.
- il **contenuto** (titolo, riepilogo, due schede) si legge da ``site/index.html``, quindi
  l'anteprima segue il build invece di invecchiare. Senza build si usa uno snapshot di
  riserva — i valori veri del 18/09/2026 — e lo dice a schermo.

Salva in due posti:
- ``site/``            (per l'URL del server di preview; il build la rigenera — non persistente)
- ``docs/preview/``    (versionato: è la copia ufficiale)

I vecchi SVG ``home-preview.svg``/``header-preview.svg`` sono stati ritirati: erano un
mock vettoriale disegnato a mano che aveva derivato dal sito reale. Uso:
``python scripts/render_preview.py [--out DIR]`` (default: site/ + docs/preview/).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = REPO_ROOT / "docs" / "preview"

FONT_DIR = "/tmp/sora"
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# --- colori: letti dal CSS e dai template, NON copiati a mano ---------------------------------
# Fino al 18/09/2026 qui c'era una copia manuale dei token con l'istruzione «se il CSS cambia,
# cambiare anche questi». Misurato allora: **7 token su 18 divergevano** da site.css
# (--line #1f2836 vs #263142, --mut #93a0b3 vs #a8b5c8, --mut2, --surface2, --draw, --lose,
# --accent-dim), più i 6 colori V/N/P dichiarati «approssimazioni»: le immagini versionate in
# docs/preview/ mostravano una palette che il sito non usa più. Leggendo i valori a runtime la
# divergenza diventa strutturalmente impossibile, e se un token sparisce lo script si ferma con
# un messaggio che nomina il token invece di disegnare un colore inventato.
CSS = REPO_ROOT / "src" / "fda" / "site" / "assets" / "site.css"
BASE_HTML = REPO_ROOT / "src" / "fda" / "site" / "templates" / "base.html"


def _hex_rgb(v: str) -> tuple[int, int, int]:
    h = v.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _css_tokens() -> dict[str, tuple[int, int, int]]:
    """Token del tema scuro: il blocco `:root{...}` di site.css, così com'è."""
    blocco = CSS.read_text(encoding="utf-8").split(":root{", 1)[1].split("\n}", 1)[0]
    return {k: _hex_rgb(v) for k, v in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})", blocco)}


def _tok(d: dict[str, tuple[int, int, int]], nome: str) -> tuple[int, int, int]:
    if nome not in d:
        raise SystemExit(f"render_preview: il token {nome} non è più in {CSS.name} — "
                         f"aggiornare lo script invece di disegnare un colore a caso")
    return d[nome]


_T = _css_tokens()

BG = _tok(_T, "--bg")
SURFACE = _tok(_T, "--surface")
LINE = _tok(_T, "--line")
TXT = _tok(_T, "--txt")
TXT2 = _tok(_T, "--txt2")
MUT = _tok(_T, "--mut")
MUT2 = _tok(_T, "--mut2")
CALCIO = _tok(_T, "--brand-a")
METRO = _tok(_T, "--brand-b")
ACCENT = _tok(_T, "--accent")
ACCENT_DIM = _tok(_T, "--accent-dim")
ON_ACCENT = _tok(_T, "--on-accent")
WIN = _tok(_T, "--win")
DRAW = _tok(_T, "--draw")
LOSE = _tok(_T, "--lose")
AMBER = _tok(_T, "--amber")
SURFACE2 = _tok(_T, "--surface2")
SURFACE3 = _tok(_T, "--surface3")
# forme recenti (.form-dot V/N/P): token veri del tema scuro, non più approssimazioni
V_BG, V_FG = _tok(_T, "--v-bg"), _tok(_T, "--v-fg")
N_BG, N_FG = _tok(_T, "--n-bg"), _tok(_T, "--n-fg")
P_BG, P_FG = _tok(_T, "--p-bg"), _tok(_T, "--p-fg")

# gradiente dell'header: non è un token, sta nella regola `header{background:linear-gradient(...)}`
_GRAD = re.search(r"header\{background:linear-gradient\(180deg,(#[0-9a-fA-F]{3,8}),(#[0-9a-fA-F]{3,8})\)",
                  CSS.read_text(encoding="utf-8"))
if not _GRAD:
    raise SystemExit(f"render_preview: gradiente dell'header non trovato in {CSS.name}")
HEADER_TOP, HEADER_BOT = _hex_rgb(_GRAD.group(1)), _hex_rgb(_GRAD.group(2))

# badge del logo: è nell'SVG data-URI di base.html (fill/stroke url-encoded come %23xxxxxx)
_BADGE = re.search(r"fill='%23([0-9a-fA-F]{6})' stroke='%23([0-9a-fA-F]{6})'",
                   BASE_HTML.read_text(encoding="utf-8"))
if not _BADGE:
    raise SystemExit(f"render_preview: colori del badge non trovati in {BASE_HTML.name}")
BADGE, BADGE_STROKE = _hex_rgb("#" + _BADGE.group(1)), _hex_rgb("#" + _BADGE.group(2))

# --- contenuto della home ---------------------------------------------------------------------
# Anche qui la copia manuale invecchiava: il blocco PAGE/CARDS era fermo al build 15/09/2026
# (Elche–Real Madrid, Ajax 75 %) mentre la home pubblicata ne mostrava altre. Ora i valori si
# leggono da `site/index.html` quando c'è, cioè l'anteprima segue il build; lo snapshot qui
# sotto resta solo come riserva per un checkout senza build (e il test lo dichiara).
def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


# Riserva usata solo quando `site/index.html` non esiste (checkout pulito, CI): sono i valori
# veri del build 18/09/2026, non un esempio inventato. Con un build presente non vengono letti.
PAGE_FALLBACK = {
    "title": "Partite di oggi — venerdì 18 settembre 2026",
    "subtitle": "Il quadro della giornata, poi il dettaglio verificabile di ogni partita.",
    "summary": [("6", "partite"), ("6", "campionati"), ("6/6", "con modello"),
                ("20:00", "prossimo calcio d'inizio")],
    "summary_note": "Dati e probabilità sono quelli dell'ultimo aggiornamento indicato in alto.",
    "day": "venerdì 18 settembre 2026",
    "updated": "18/09/2026 20:03 (ora italiana)",
}
CARDS_FALLBACK: list[dict] = [
    {"status": "In programma", "dot": ACCENT, "kickoff": "20:00", "league": "Eredivisie",
     "home": "FC Groningen", "home_rank": "9ª · 8 pt", "away": "PEC Zwolle", "away_rank": "16ª · 4 pt",
     "score": "vs", "score_note": "calcio d'inizio",
     "fav": "FC Groningen", "pct": 54, "note": "favorito · +29 punti sul secondo (Pareggio 25%)",
     "bar": (54, 25, 21),
     "signal": "✓ DC ed Elo sullo stesso preferito (FC Groningen): DC 54,6% · Elo 53,4% · distanza 1,2 punti",
     "signal_tone": "agree",
     "foot": "Modello Gol attesi 1,99 + 1,21 (3,20 totali) · Over 2,5 62% (62 su 100 con 3+ gol)",
     "form_home": (["V", "P", "P", "N", "N"], "5 pt"), "form_away": (["P", "V", "P", "N", "P"], "4 pt"),
     "facts": ["Meteo nuvoloso · 16°C", "Arbitro Martin van den Kerkhof · 2,2 gialli/gara",
               "Precedenti 27 precedenti: 11-7-9 (2,1 gol/gara)"]},
    {"status": "In programma", "dot": ACCENT, "kickoff": "20:30", "league": "Bundesliga",
     "home": "Bayern München", "home_rank": "4ª · 7 pt", "away": "Union Berlin", "away_rank": "16ª · 1 pt",
     "score": "vs", "score_note": "calcio d'inizio",
     "fav": "Bayern München", "pct": 84, "note": "favorito · +73 punti sul secondo (Pareggio 11%)",
     "bar": (84, 11, 5),
     "signal": "✓ DC ed Elo sullo stesso preferito (Bayern München): DC 81,6% · Elo 86,6% · distanza 5,0 punti",
     "signal_tone": "agree",
     "foot": "Modello Gol attesi 3,14 + 0,71 (3,85 totali) · Over 2,5 74% (74 su 100 con 3+ gol)",
     "form_home": (["V", "N", "V"], "7 pt"), "form_away": (["N", "P", "P"], "1 pt"),
     "facts": ["Meteo parzialmente nuvoloso · 19°C", "Arbitro Benjamin Brand · 3,7 gialli/gara",
               "Precedenti 15 precedenti: 10-5-0 (3,3 gol/gara)"]},
]


def _from_site_index(path: Path) -> tuple[dict, list[dict]] | None:
    """PAGE e CARDS letti dalla home generata. None se il sito non è stato costruito."""
    if not path.exists():
        return None
    h = path.read_text(encoding="utf-8")

    def g(pat: str, s: str, default: str = "") -> str:
        m = re.search(pat, s, re.DOTALL)
        return m.group(1) if m else default

    summary = [(_strip(a), _strip(b)) for a, b in
               re.findall(r'<div class="overview-metric[^"]*"><strong>(.*?)</strong>'
                          r'<span>(.*?)</span>', h, re.DOTALL)][:5]
    page = {
        "title": _strip(g(r"<h1>(.*?)</h1>", h)),
        "subtitle": _strip(g(r'<p class="mut page-subtitle">(.*?)</p>', h)),
        "summary": summary or PAGE_FALLBACK["summary"],
        "summary_note": _strip(g(r'<span class="mut">(.*?)</span>', h)),
        "day": _strip(g(r'<div class="day-heading"><h2[^>]*>(.*?)</h2>', h)),
        "updated": _strip(g(r"aggiornato\s*([^<]*)", h)),
    }
    if not page["title"]:
        return None

    punti = {"live": LOSE, "paused": AMBER, "scheduled": ACCENT,
             "finished": MUT2, "postponed": AMBER}
    cards = []
    for blk in re.findall(r'<article class="match-card".*?</article>', h, re.DOTALL)[:2]:
        # le icone sono SVG: tolti prima, così i <span> dei fatti non hanno figli inattesi
        blk = re.sub(r"<svg.*?</svg>", "", blk, flags=re.DOTALL)
        m = re.search(r'data-status="(\w+)"', blk)
        st = m.group(1) if m else "scheduled"
        forms = []
        for blocco_forma, punti_forma in re.findall(
                r'<span class="form-line"(.*?)<span class="fact-value">(.*?)</span>', blk, re.DOTALL)[:2]:
            forms.append(([d for d in re.findall(r'class="form-dot (\w)"', blocco_forma)],
                          _strip(punti_forma)))
        bar = re.findall(r'<span class="[hda]" style="width:(\d+)%">', blk)
        sig = re.search(r'<div class="signal signal-(\w+)"[^>]*>(.*?)</div>', blk, re.DOTALL)
        proj = re.search(r'<div class="projection-copy">.*?<strong>(.*?)\s*'
                         r'<span class="projection-p">(\d+)%</span></strong>', blk, re.DOTALL)
        facts = [_strip(x) for x in re.findall(
            r'<span class="fact"[^>]*>((?:\s*<span[^>]*>[^<]*</span>)+)\s*</span>', blk, re.DOTALL)]
        cards.append({
            "status": _strip(g(r'<span class="status[^"]*">\s*<span class="status-dot"[^>]*></span>'
                               r'\s*(.*?)</span>', blk)),
            "dot": punti.get(st, MUT2),
            "kickoff": _strip(g(r'class="kickoff">(.*?)</time>', blk)),
            "league": _strip(g(r'<span class="tag">(.*?)</span>', blk)),
            "home": _strip(g(r'home-team">\s*<a[^>]*>(.*?)</a>', blk)),
            "home_rank": _strip(g(r'home-team">.*?<span class="team-rank">(.*?)</span>', blk)),
            "away": _strip(g(r'away-team">\s*<a[^>]*>(.*?)</a>', blk)),
            "away_rank": _strip(g(r'away-team">.*?<span class="team-rank">(.*?)</span>', blk)),
            "score": _strip(g(r'<div class="match-score">\s*<strong>(.*?)</strong>', blk)),
            "score_note": _strip(g(r'<div class="match-score">.*?<span>(.*?)</span>', blk)),
            "fav": _strip(proj.group(1)) if proj else "",
            "pct": int(proj.group(2)) if proj else 0,
            "note": _strip(g(r'<span class="projection-note">(.*?)</span>', blk)),
            "bar": tuple(int(x) for x in bar[:3]) if len(bar) == 3 else (0, 0, 0),
            "signal": _strip(sig.group(2)) if sig else "",
            "signal_tone": sig.group(1) if sig else "agree",
            "foot": _strip(g(r'<div class="model-foot"[^>]*>(.*?)</div>', blk)),
            "form_home": forms[0] if forms else ([], ""),
            "form_away": forms[1] if len(forms) > 1 else ([], ""),
            "facts": [f for f in facts if f][:4],
        })
    return (page, cards) if cards else None


_letti = _from_site_index(REPO_ROOT / "site" / "index.html")
PAGE, CARDS = _letti if _letti else (PAGE_FALLBACK, CARDS_FALLBACK)
if not _letti:
    print("render_preview: site/index.html non trovato — uso lo snapshot di riserva "
          "(esegui `fda build` per un'anteprima sul build corrente)")


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    full = f"{FONT_DIR}/{path}"
    try:
        return ImageFont.truetype(full, size)
    except OSError:
        b = DEJAVU_BOLD if "Bold" in path else DEJAVU
        return ImageFont.truetype(b, size)


def cnv(w: int, h: int) -> Image.Image:
    return Image.new("RGB", (w, h), BG)


def rrect(d: ImageDraw.ImageDraw, box, rad, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=rad, fill=fill, outline=outline, width=width)


def draw_logo(d: ImageDraw.ImageDraw, x: int, y: int, s: int) -> None:
    """Logo CM semplificato ma fedele (badge + lettere C/M in due colori)."""
    rrect(d, (x + 3, y + 4, x + s + 3, y + s + 4), s * 0.28, (0, 0, 0))
    rrect(d, (x, y, x + s, y + s), s * 0.28, BADGE, BADGE_STROKE, 2)
    fb = font("Sora-Bold.ttf", int(s * 0.62))
    cy = y + int(s * 0.70)
    cx = x + s // 2
    d.text((cx - s * 0.24, cy), "C", font=fb, fill=CALCIO, anchor="mm")
    d.text((cx + s * 0.24, cy), "M", font=fb, fill=METRO, anchor="mm")


def header(d: ImageDraw.ImageDraw, W: int = 1200) -> int:
    """Header attuale: brand a sinistra, nav a destra (8 voci), badge v2 + tema ◐."""
    H = 168
    for i in range(H):
        t = i / H
        c = tuple(int(HEADER_TOP[k] * (1 - t) + HEADER_BOT[k] * t) for k in range(3))
        d.line((0, i, W, i), fill=c)
    d.line((0, H, W, H), fill=LINE, width=1)

    logo_s = 60
    draw_logo(d, 48, (H - logo_s) // 2, logo_s)
    fb = font("Sora-Bold.ttf", 42)
    wx = 48 + logo_s + 20
    wy = H // 2 - 6
    d.text((wx, wy), "Calcio", font=fb, fill=CALCIO, anchor="lm")
    cw = d.textlength("Calcio", font=fb)
    d.text((wx + cw, wy), "Metro", font=fb, fill=METRO, anchor="lm")
    fsub = font("Sora-SemiBold.ttf", 15)
    d.text((wx, wy + 27), "Analisi calcistica profonda · 7 campionati", font=fsub, fill=MUT, anchor="lm")

    # toggle tema (bottone ◐ a destra del badge, come in base.html)
    rrect(d, (W - 48 - 36, H // 2 - 18, W - 48, H // 2 + 18), 9, SURFACE2, LINE)
    d.text((W - 48 - 18, H // 2), "◐", font=font("Sora-Regular.ttf", 15), fill=MUT, anchor="mm")

    fv = font("Sora-Bold.ttf", 13)
    upd = f"v2 · aggiornato {PAGE['updated']}"
    uw = d.textlength(upd, font=fv)
    rrect(d, (W - 100 - uw - 20, H // 2 - 15, W - 100, H // 2 + 15), 12, (15, 49, 38), LINE)
    d.text((W - 100 - uw / 2 - 20, H // 2), upd, font=fv, fill=MUT, anchor="mm")

    # nav — le 8 voci attuali, sotto il brand come nel sito reale (wrap su due righe a 1200px)
    fn = font("Sora-SemiBold.ttf", 16)
    nav = [("Oggi", True), ("Prossime", False), ("Risultati", False), ("Accuratezza", False),
           ("Proiezioni", False), ("Giocatori", False), ("Stato fonti", False), ("Info", False)]
    gap = 18
    widths = {label: d.textlength(label, font=fn) + (30 if active else 0) for label, active in nav}
    total = sum(widths.values()) + gap * (len(nav) - 1)
    nx = W - 48 - total          # a 1200 px la nav sta su una riga, sotto brand e badge
    ny = H - 30
    for label, active in nav:
        w = widths[label]
        if active:
            rrect(d, (nx, ny - 20, nx + w, ny + 20), 10, ACCENT)
            d.text((nx + w / 2, ny), label, font=fn, fill=ON_ACCENT, anchor="mm")
        else:
            d.text((nx + w / 2, ny), label, font=fn, fill=TXT2, anchor="mm")
        nx += w + gap
    return H


def form_dots(d: ImageDraw.ImageDraw, x: int, y: int, letters: list[str]) -> int:
    """Pallini di forma (V/N/P) come .form-dot: quadratini arrotondati 19px."""
    f = font("Sora-Bold.ttf", 10)
    for ch in letters:
        bg, fg = {"V": (V_BG, V_FG), "N": (N_BG, N_FG), "P": (P_BG, P_FG)}[ch]
        rrect(d, (x, y, x + 19, y + 19), 5, bg)
        d.text((x + 9.5, y + 10), ch, font=f, fill=fg, anchor="mm")
        x += 22
    return x


def match_card(d: ImageDraw.ImageDraw, x: int, y: int, w: int, c: dict) -> int:
    """Una card partita col design attuale (testa, squadre, lettura, segnale, modello, fatti)."""
    H = 356
    rrect(d, (x, y, x + w, y + H), 14, SURFACE, LINE)
    ix = x + 22

    # testa: stato + orario + tag lega, a destra «Analisi ↗»
    fy = y + 26
    d.ellipse((ix, fy - 4, ix + 8, fy + 4), fill=c["dot"])
    fs = font("Sora-SemiBold.ttf", 13)
    d.text((ix + 14, fy), c["status"], font=fs, fill=MUT, anchor="lm")
    sx = ix + 14 + d.textlength(c["status"], font=fs) + 14
    d.text((sx, fy), c["kickoff"], font=font("Sora-Bold.ttf", 13), fill=TXT2, anchor="lm")
    sx += d.textlength(c["kickoff"], font=fs) + 12
    tw = d.textlength(c["league"], font=fs) + 20
    rrect(d, (sx, fy - 11, sx + tw, fy + 11), 7, ACCENT_DIM)
    d.text((sx + tw / 2, fy), c["league"], font=fs, fill=ACCENT, anchor="mm")
    fa = font("Sora-SemiBold.ttf", 13.5)
    d.text((x + w - 22, fy), "Analisi ↗", font=fa, fill=ACCENT, anchor="rm")

    # squadre: nomi grandi, sotto la posizione in classifica; al centro il punteggio
    ty = y + 78
    ft = font("Sora-Bold.ttf", 21)
    fr = font("Sora-Regular.ttf", 13)
    d.text((ix, ty), c["home"], font=ft, fill=TXT, anchor="lm")
    d.text((ix, ty + 24), c["home_rank"], font=fr, fill=MUT, anchor="lm")
    d.text((x + w - ix, ty), c["away"], font=ft, fill=TXT, anchor="rm")
    d.text((x + w - ix, ty + 24), c["away_rank"], font=fr, fill=MUT, anchor="rm")
    d.text((x + w / 2, ty - 2), c["score"], font=font("Sora-Bold.ttf", 30), fill=TXT, anchor="mm")
    d.text((x + w / 2, ty + 24), c["score_note"], font=fr, fill=MUT, anchor="mm")

    # lettura del modello: copia a sinistra, barra 1X2 + etichette a destra
    py = y + 142
    d.text((ix, py), "LETTURA DEL MODELLO", font=font("Sora-Bold.ttf", 10.5), fill=MUT)
    fl = font("Sora-Bold.ttf", 19)
    d.text((ix, py + 22), c["fav"], font=fl, fill=TXT, anchor="lm")
    pw = d.textlength(c["fav"], font=fl)
    d.text((ix + pw + 8, py + 22), f"{c['pct']}%", font=fl, fill=ACCENT, anchor="lm")
    d.text((ix, py + 46), c["note"], font=font("Sora-Regular.ttf", 13), fill=MUT, anchor="lm")

    bw = 340
    bx = x + w - 22 - bw
    ph, pd_, pa = c["bar"]
    seg_colors = [WIN, DRAW, LOSE]
    cx = bx
    for p, col in zip((ph, pd_, pa), seg_colors):
        segw = int(bw * p / 100)
        if segw > 0:
            d.rectangle((cx, py + 10, cx + segw, py + 34), fill=col)
        cx += segw
    labels = [("1", ph), ("X", pd_), ("2", pa)]
    fav_i = max(range(3), key=lambda i: labels[i][1])
    lx = bx
    for i, (sym, p) in enumerate(labels):
        lab = f"{sym} {p}%"
        f = font("Sora-Bold.ttf" if i == fav_i else "Sora-SemiBold.ttf", 12.5)
        d.text((lx, py + 44), lab, font=f, fill=ACCENT if i == fav_i else MUT, anchor="lm")
        lx += d.textlength(lab, font=f) + 16

    # segnale DC/Elo (striscia colorata come .signal)
    sy = py + 70
    tone_bg = ACCENT_DIM if c["signal_tone"] == "agree" else (46, 38, 17)
    tone_fg = ACCENT if c["signal_tone"] == "agree" else AMBER
    rrect(d, (ix, sy, x + w - 22, sy + 26), 7, tone_bg)
    d.text((ix + 12, sy + 13), c["signal"], font=font("Sora-SemiBold.ttf", 12.5), fill=tone_fg, anchor="lm")

    # piede modello: gol attesi e Over 2,5
    my = sy + 42
    mw = d.textlength("MODELLO", font=font("Sora-Bold.ttf", 10)) + 16
    rrect(d, (ix, my - 9, ix + mw, my + 9), 5, SURFACE3)
    d.text((ix + mw / 2, my), "MODELLO", font=font("Sora-Bold.ttf", 10), fill=MUT, anchor="mm")
    d.text((ix + mw + 10, my), c["foot"], font=font("Sora-Regular.ttf", 13), fill=TXT2, anchor="lm")

    # fatti rapidi: forme + meteo/arbitro/precedenti (chip come .match-facts)
    fy2 = my + 30
    fx = ix
    for who, (letters, pts) in (("FORMA", c["form_home"]), ("FORMA", c["form_away"])):
        d.text((fx, fy2 + 9), who, font=font("Sora-Bold.ttf", 10), fill=MUT, anchor="lm")
        fx += d.textlength(who, font=font("Sora-Bold.ttf", 10)) + 8
        fx = form_dots(d, fx, fy2, letters) + 4
        d.text((fx, fy2 + 9), pts, font=font("Sora-SemiBold.ttf", 12), fill=TXT2, anchor="lm")
        fx += d.textlength(pts, font=font("Sora-SemiBold.ttf", 12)) + 18
    ff = font("Sora-Regular.ttf", 12)
    fy3 = fy2 + 30
    fx = ix
    for fact in c["facts"]:
        fw = d.textlength(fact, font=ff)
        if fx + fw > x + w - 22:
            fx, fy3 = ix, fy3 + 21
        d.text((fx, fy3), fact, font=ff, fill=MUT, anchor="lm")
        fx += fw + 20
    return y + H


def home(out_dirs: list[Path]) -> None:
    W = 1200
    img = cnv(W, 1500)
    d = ImageDraw.Draw(img)
    y = header(d, W)

    y += 40
    d.text((48, y), PAGE["title"], font=font("Sora-Bold.ttf", 33), fill=TXT)
    y += 50
    d.text((48, y), PAGE["subtitle"], font=font("Sora-Regular.ttf", 17), fill=MUT)
    y += 44

    # riepilogo giornata (metriche in evidenza + nota)
    sh = 86
    rrect(d, (48, y, W - 48, y + sh), 12, SURFACE, LINE)
    mx = 72
    for value, label in PAGE["summary"]:
        d.text((mx, y + 26), value, font=font("Sora-Bold.ttf", 21), fill=ACCENT, anchor="lm")
        vw = d.textlength(value, font=font("Sora-Bold.ttf", 21))
        d.text((mx + vw + 8, y + 27), label, font=font("Sora-Regular.ttf", 13.5), fill=MUT, anchor="lm")
        mx += vw + 8 + d.textlength(label, font=font("Sora-Regular.ttf", 13.5)) + 28
    d.text((72, y + 60), PAGE["summary_note"], font=font("Sora-Regular.ttf", 12.5), fill=MUT2)
    y += sh + 26

    # filtri rapidi (chip di stato + ricerca, come .filter-buttons)
    d.text((48, y + 18), "Filtra partite", font=font("Sora-Bold.ttf", 12), fill=TXT2, anchor="lm")
    fx = 48 + d.textlength("Filtra partite", font=font("Sora-Bold.ttf", 12)) + 14
    for i, chip in enumerate(("Tutte", "In corso", "In programma", "Terminate")):
        fchip = font("Sora-SemiBold.ttf", 12)
        cw = d.textlength(chip, font=fchip) + 22
        active = i == 0
        rrect(d, (fx, y, fx + cw, y + 36), 8, ACCENT_DIM if active else SURFACE,
              ACCENT if active else LINE)
        d.text((fx + cw / 2, y + 18), chip, font=fchip, fill=ACCENT if active else TXT2, anchor="mm")
        fx += cw + 8
    rrect(d, (W - 48 - 220, y, W - 48, y + 36), 8, SURFACE, LINE)
    d.text((W - 48 - 206, y + 18), "Cerca squadra…", font=font("Sora-Regular.ttf", 12.5),
           fill=MUT2, anchor="lm")
    y += 64

    # etichetta del giorno (accent + sottolineatura, come gli h2 di giornata)
    d.text((48, y), PAGE["day"], font=font("Sora-Bold.ttf", 15), fill=ACCENT)
    d.line((48, y + 24, 190, y + 24), fill=ACCENT, width=3)
    y += 40

    for c in CARDS:
        y = match_card(d, 48, y, W - 96, c) + 24

    # footer attuale: brand + nota legale per esteso
    fy = y + 16
    H = fy + 170
    img2 = img.crop((0, 0, W, H))
    d = ImageDraw.Draw(img2)
    d.rectangle((0, fy, W, H), fill=(11, 16, 23))
    d.line((0, fy, W, fy), fill=LINE, width=1)
    draw_logo(d, 48, fy + 32, 40)
    fb = font("Sora-Bold.ttf", 22)
    d.text((104, fy + 52), "Calcio", font=fb, fill=CALCIO, anchor="lm")
    cw = d.textlength("Calcio", font=fb)
    d.text((104 + cw, fy + 52), "Metro", font=fb, fill=METRO, anchor="lm")
    legal = ("Progetto personale a scopo informativo e statistico. Le probabilità sono stime di un modello "
             "matematico, non consigli: nessuna garanzia di risultato. Il gioco d'azzardo è vietato ai minori "
             "e può causare dipendenza (18+).")
    d.text((48, fy + 96), legal[:118], font=font("Sora-Regular.ttf", 13), fill=MUT2)
    d.text((48, fy + 118), legal[118:], font=font("Sora-Regular.ttf", 13), fill=MUT2)

    for out in out_dirs:
        out.mkdir(parents=True, exist_ok=True)
        img2.save(out / "home-preview.png")
        print(f"{out / 'home-preview.png'} salvato", img2.size)


def header_only(out_dirs: list[Path]) -> None:
    W, H = 1200, 168
    img = cnv(W, H)
    d = ImageDraw.Draw(img)
    header(d, W)
    for out in out_dirs:
        out.mkdir(parents=True, exist_ok=True)
        img.save(out / "header-preview.png")
        print(f"{out / 'header-preview.png'} salvato", img.size)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None,
                    help="cartella di destinazione (default: site/ + docs/preview/)")
    args = ap.parse_args()
    dirs = [Path(args.out)] if args.out else [REPO_ROOT / "site", PREVIEW_DIR]
    header_only(dirs)
    home(dirs)
