"""Genera i PNG di anteprima dell'header e della home di CalcioMetro.

Disegna con Pillow (nessuna libreria di sistema né browser richiesti) usando i valori
reali del design system e i **dati veri del build 15/09/2026** (le due schede finite
della giornata: Rayo Vallecano–Espanyol e Ajax–Willem II, come pubblicate su
``site/index.html``). Così chi apre ``docs/preview/`` vede il layout corrente, non il
design del 09/09 (audit Q6, docs/21 P2-8b).

Salva in due posti:
- ``site/``            (per l'URL del server di preview; il build la rigenera — non persistente)
- ``docs/preview/``    (versionato: è la copia ufficiale)

I vecchi SVG ``home-preview.svg``/``header-preview.svg`` sono stati ritirati: erano un
mock vettoriale disegnato a mano che aveva derivato dal sito reale (questo script è
invece l'unica fonte dei PNG, coi token del CSS copiati uno a uno). Uso:
``python scripts/render_preview.py [--out DIR]`` (default: site/ + docs/preview/).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = REPO_ROOT / "docs" / "preview"

FONT_DIR = "/tmp/sora"
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# token del tema scuro (base.html :root) — se il CSS cambia, cambiare anche questi
BG = (12, 17, 24)          # --bg #0c1118
SURFACE = (19, 26, 36)     # --surface #131a24
LINE = (31, 40, 54)        # --line #1f2836
TXT = (233, 238, 246)      # --txt #e9eef6
TXT2 = (196, 206, 220)     # --txt2 #c4cedc
MUT = (147, 160, 179)      # --mut #93a0b3
MUT2 = (108, 122, 141)     # --mut2 #6c7a8d
CALCIO = (46, 229, 157)    # --brand-a #2ee59d
METRO = (231, 178, 60)     # --brand-b #e7b23c
ACCENT = (40, 200, 147)    # --accent #28c893
ACCENT_DIM = (17, 44, 36)  # --accent-dim (approssimazione dal CSS)
ON_ACCENT = (6, 35, 26)    # --on-accent #06231a
WIN = (40, 200, 147)       # --win
DRAW = (127, 138, 160)     # --draw
LOSE = (224, 96, 90)       # --lose
AMBER = (230, 179, 74)     # --amber
SURFACE2 = (23, 31, 43)    # --surface2
SURFACE3 = (33, 44, 58)    # --surface3 #212c3a
HEADER_TOP = (14, 20, 29)
HEADER_BOT = (11, 16, 23)
BADGE = (18, 32, 46)
BADGE_STROKE = (47, 65, 88)
# forme recenti (.form-dot V/N/P): approssimazioni dei token --v-*/--n-*/--p-* del tema scuro
V_BG, V_FG = (17, 52, 39), (93, 224, 160)
N_BG, N_FG = (40, 46, 58), (196, 206, 220)
P_BG, P_FG = (58, 28, 29), (240, 128, 122)

# i valori veri della home del build 15/09/2026 (site/index.html): una gara in corso
# (Elche–Real Madrid, con infermeria) e una finita col favorito netto (Ajax 75%, 5–1)
PAGE = {
    "title": "Partite di oggi — martedì 15 settembre 2026",
    "subtitle": "Il quadro della giornata, poi il dettaglio verificabile di ogni partita.",
    "summary": [("4", "partite"), ("2", "campionati"), ("4/4", "con modello"),
                ("1", "in corso"), ("3", "terminate")],
    "summary_note": "Dati e probabilità sono quelli dell'ultimo aggiornamento indicato in alto.",
    "day": "martedì 15 settembre 2026",
    "updated": "15/09/2026 23:32 (ora italiana)",
}

CARDS = [
    {"status": "In corso", "dot": LOSE, "kickoff": "21:30", "league": "LaLiga",
     "home": "Elche", "home_rank": "20ª · 2 pt", "away": "Real Madrid", "away_rank": "2ª · 15 pt",
     "score": "0–2", "score_note": "calcio d'inizio",
     "fav": "Real Madrid", "pct": 59, "note": "favorito · +37 punti sul secondo (Pareggio 22%)",
     "bar": (19, 22, 59),
     "signal": "✓ DC ed Elo sullo stesso preferito (Real Madrid): DC 56,9% · Elo 63,8% · distanza 6,9 punti",
     "signal_tone": "agree",
     "foot": "Gol attesi 1,09 + 2,04 (3,13 totali) · Over 2,5 61% (61 su 100 con 3+ gol)",
     "form_home": (["N", "P", "P", "P", "N"], "2 pt"), "form_away": (["V", "V", "V", "P", "V"], "12 pt"),
     "facts": ["Infermeria Elche 2 assenti · Real Madrid 3 assenti", "Meteo sereno · 24°C",
               "Arbitro Jesús Gil Manzano · 5,0 gialli/gara", "Precedenti 13: 0-3-10 (3,5 gol/gara)"]},
    {"status": "Terminata", "dot": MUT2, "kickoff": "20:00", "league": "Eredivisie",
     "home": "Ajax", "home_rank": "4ª · 13 pt", "away": "Willem II", "away_rank": "17ª · 2 pt",
     "score": "5–1", "score_note": "finale",
     "fav": "Ajax", "pct": 75, "note": "favorito · +58 punti sul secondo (Pareggio 17%)",
     "bar": (75, 17, 8),
     "signal": "✓ DC ed Elo sullo stesso preferito (Ajax): DC 72,2% · Elo 78,2% · distanza 6,0 punti",
     "signal_tone": "agree",
     "foot": "Gol attesi 2,58 + 0,80 (3,38 totali) · Over 2,5 66% (66 su 100 con 3+ gol)",
     "form_home": (["V", "N", "V", "P", "V"], "10 pt"), "form_away": (["P", "P", "N", "P", "N"], "2 pt"),
     "facts": ["Meteo per lo più nuvoloso · 19°C", "Arbitro Allard Lindhout · 2,8 gialli/gara",
               "Precedenti 23: 19-2-2 (3,5 gol/gara)"]},
]


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
