"""Genera PNG di anteprima dell'header e della home di CalcioMetro.

Disegna con Pillow (nessuna libreria di sistema richiesta) usando i valori reali
del design system, così puoi vedere il risultato anche senza la preview.

Salva in due posti:
- ``site/``            (per l'URL del server, ma il build la rigenera — non persistente)
- ``docs/preview/``    (versionato, non toccato dal build — è la copia ufficiale)

Gli SVG ufficiali vivono in ``docs/preview/`` (vettoriali, fedeli al design);
i PNG sono una copia raster di supporto (font di ripiego se Sora non è disponibile).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = REPO_ROOT / "docs" / "preview"

FONT_DIR = "/tmp/sora"
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
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
WIN = (40, 200, 147)       # --win
DRAW = (127, 138, 160)     # --draw
LOSE = (224, 96, 90)       # --lose
AMBER = (230, 179, 74)     # --amber
SURFACE3 = (33, 44, 58)    # --surface3 #212c3a
HEADER_TOP = (14, 20, 29)
HEADER_BOT = (11, 16, 23)
BADGE = (18, 32, 46)
BADGE_STROKE = (47, 65, 88)
TICK = (66, 86, 111)


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
    # ombra
    rrect(d, (x + 3, y + 4, x + s + 3, y + s + 4), s * 0.28, (0, 0, 0))
    # badge
    rrect(d, (x, y, x + s, y + s), s * 0.28, BADGE, BADGE_STROKE, 2)
    # lettere
    fb = font("Sora-Bold.ttf", int(s * 0.62))
    cy = y + int(s * 0.70)
    cx = x + s // 2
    d.text((cx - s * 0.24, cy), "C", font=fb, fill=CALCIO, anchor="mm")
    d.text((cx + s * 0.24, cy), "M", font=fb, fill=METRO, anchor="mm")


def header(d: ImageDraw.ImageDraw, W: int = 1200) -> int:
    H = 168
    # gradiente
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
    d.text((wx, wy + 32), "Analisi calcistica profonda · 7 campionati", font=fsub, fill=MUT, anchor="lm")

    # nav — tutte e 7 le voci, allineate a destra come nel sito reale
    fn = font("Sora-SemiBold.ttf", 16)
    nav = [("Oggi", True), ("Prossime", False), ("Risultati", False), ("Accuratezza", False),
           ("Proiezioni", False), ("Stato fonti", False), ("Info", False)]
    widths = {}
    for label, active in nav:
        w = d.textlength(label, font=fn)
        if active:
            w += 32
        widths[label] = w
    gap = 20
    total = sum(widths.values()) + gap * (len(nav) - 1)
    nx = W - 48 - total
    for label, active in nav:
        w = widths[label]
        if active:
            rrect(d, (nx, H // 2 - 23, nx + w, H // 2 + 23), 11, ACCENT)
            d.text((nx + w / 2, H // 2), label, font=fn, fill=(6, 35, 26), anchor="mm")
        else:
            d.text((nx + w / 2, H // 2), label, font=fn, fill=TXT2, anchor="mm")
        nx += w + gap

    # badge v2
    fv = font("Sora-Bold.ttf", 13)
    rrect(d, (W - 48, H - 34, W - 6, H - 10), 12, (15, 49, 38), LINE)
    d.text((W - 27, H - 22), "v2", font=fv, fill=CALCIO, anchor="mm")
    d.text((W - 56, H - 22), "aggiornato 09/09/2026", font=fv, fill=MUT, anchor="rm")
    return H


def draw_prob_bar(d, x, y, w, h, ph, pd, pa):
    label_colors = [(6, 35, 26), (13, 20, 32), (6, 35, 26)]
    segs = [(ph, (46, 212, 156)), (pd, DRAW), (pa, (224, 96, 90))]
    total = ph + pd + pa
    cx = x
    sizef = 14
    fseg = font("Sora-Bold.ttf", sizef)
    for i, (p, fillc) in enumerate(segs):
        segw = int(w * p / total)
        if segw > 0:
            d.rectangle((cx, y, cx + segw, y + h), fill=fillc)
            if segw > 22:
                d.text((cx + segw / 2, y + h / 2), str(round(p * 100)), font=fseg,
                       fill=label_colors[i], anchor="mm")
        cx += segw


def home() -> None:
    W, H = 1200, 980
    img = cnv(W, H)
    d = ImageDraw.Draw(img)
    top = header(d, W)

    y = top
    y += 40
    fh1 = font("Sora-Bold.ttf", 34)
    d.text((48, y), "Partite di oggi — mercoledì 9 settembre 2026", font=fh1, fill=TXT)
    y += 52
    fsub = font("Sora-Regular.ttf", 17)
    d.text((48, y), "Probabilità 1 / X / 2 del modello, gol attesi e Over 2,5. Clicca una partita per l'analisi completa.",
           font=fsub, fill=MUT)
    y += 52

    fday = font("Sora-Bold.ttf", 15)
    d.text((48, y), "MERCOLEDÌ 9 SETTEMBRE 2026", font=fday, fill=ACCENT)
    d.line((48, y + 12, 160, y + 12), fill=ACCENT, width=3)
    y += 40

    matches = [
        ("18:45", "Eredivisie", "FC Twente", "09/09", "Telstar", 0.62, 0.20, 0.18, "1", "2,38–1,23 · O2.5 60%"),
        ("21:45", "Liga Portugal", "Moreirense", "09/09", "Benfica", 0.13, 0.16, 0.70, "2", "1,03–2,54 · O2.5 69%"),
    ]
    for tm in matches:
        hr, lg, home_t, dt, away_t, ph, pd, pa, top_o, niche = tm
        rrect(d, (48, y, W - 48, y + 128), 14, SURFACE, LINE)
        ft = font("Sora-Regular.ttf", 15)
        d.text((70, y + 30), hr, font=ft, fill=MUT)
        rrect(d, (70, y + 52, 160, y + 80), 7, (15, 49, 38))
        d.text((115, y + 66), lg, font=font("Sora-Bold.ttf", 13), fill=ACCENT, anchor="mm")
        d.text((330, y + 70), home_t, font=font("Sora-Bold.ttf", 20), fill=TXT2, anchor="rm")
        rrect(d, (360, y + 40, 452, y + 84), 10, SURFACE3, LINE)
        d.text((406, y + 62), dt, font=font("Sora-Bold.ttf", 19), fill=TXT, anchor="mm")
        d.text((470, y + 70), away_t, font=font("Sora-Bold.ttf", 20), fill=TXT2, anchor="lm")
        draw_prob_bar(d, 736, y + 36, 340, 36, ph, pd, pa)
        d.text((736, y + 86), f"Il modello punta su {top_o} ({round(max(ph,pd,pa)*100)}%)",
               font=font("Sora-SemiBold.ttf", 15), fill=TXT)
        d.text((736, y + 108), f"λ {niche}", font=font("Sora-Regular.ttf", 14), fill=MUT)
        y += 160

    # footer
    fy = H - 150
    d.rectangle((0, fy, W, H), fill=(11, 16, 23))
    d.line((0, fy, W, fy), fill=LINE, width=1)
    draw_logo(d, 48, fy + 40, 56)
    fb = font("Sora-Bold.ttf", 24)
    d.text((128, fy + 60), "Calcio", font=fb, fill=CALCIO, anchor="lm")
    cw = d.textlength("Calcio", font=fb)
    d.text((128 + cw, fy + 60), "Metro", font=fb, fill=METRO, anchor="lm")
    d.text((48, fy + 110), "Progetto personale a scopo informativo. Le probabilità sono stime di un modello (18+).",
           font=font("Sora-Regular.ttf", 14), fill=MUT2)

    img.save("site/home-preview.png")
    print("site/home-preview.png salvato", img.size)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PREVIEW_DIR / "home-preview.png")
    print(f"{PREVIEW_DIR / 'home-preview.png'} salvato", img.size)


def header_only() -> None:
    W, H = 1200, 168
    img = cnv(W, H)
    d = ImageDraw.Draw(img)
    header(d, W)
    img.save("site/header-preview.png")
    print("site/header-preview.png salvato", img.size)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PREVIEW_DIR / "header-preview.png")
    print(f"{PREVIEW_DIR / 'header-preview.png'} salvato", img.size)


if __name__ == "__main__":
    header_only()
    home()
