"""Scarica i font del sito e li serve in locale: zero richieste a Google a runtime.

**Perché esiste (docs/26 §8, scelta dell'utente 2026-09-18).** `base.html` caricava Sora e
Inter da `fonts.googleapis.com` su **ogni** pagina — misurato: **8.252 link** su 4.126
pagine, due `preconnect` + un foglio di stile. Era l'unica dipendenza esterna a runtime di
un sito che per regola non usa servizi di terzi (`docs/00` §E), con tre effetti: Google vede
ogni visita, i caratteri arrivano dopo l'HTML (salto tipografico), e con Google irraggiungibile
la resa cambia.

**Cosa fa.** Chiede a Google il CSS con uno User-Agent moderno (restituisce **woff2** con
`unicode-range`, cioè i sottoinsiemi piccoli e non il font completo), scarica ogni woff2 in
`src/fda/site/assets/fonts/` e riscrive il CSS con percorsi relativi. Da quel momento
`SiteBuilder.font_locali_presenti()` risponde True, il build copia la directory in
`site/assets/fonts/` e `base.html` linka il CSS locale invece di Google.

**Uso.**
    python scripts/font_locali.py           # scarica e scrive (serve rete verso Google)
    python scripts/font_locali.py --check   # verifica senza scaricare (offline, CI)

Dal sandbox dell'agente Google Fonts non è raggiungibile (`curl` → 000, misurato
2026-09-17): lo script va eseguito dove la rete c'è — in locale, oppure in un runner di
GitHub Actions con `workflow_dispatch`.

**Licenza.** Sora e Inter sono **SIL Open Font License 1.1**: ridistribuibili con il
progetto purché la nota di licenza resti accanto ai file. Lo script scrive `LICENSE.txt`
nella directory dei font con il testo dell'OFL e l'attribuzione.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

import requests

# Stesso identico URL che `base.html` usava per Google: stesse famiglie, stessi pesi.
CSS_URL = ("https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800"
           "&family=Inter:wght@400;500;600;700&display=swap")
# User-Agent moderno: senza, Google risponde con TTF invece che woff2 (più pesanti).
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0.0.0 Safari/537.36")
FONTS_DIR = Path(__file__).resolve().parents[1] / "src" / "fda" / "site" / "assets" / "fonts"
_URL = re.compile(r"url\((https://fonts\.gstatic\.com/[^)]+?\.woff2)\)")

LICENSE = """\
Sora e Inter — SIL Open Font License 1.1 (https://scripts.sil.org/OFL)

Questi file sono ridistribuiti invariati con il progetto football-deep-analyzer, come la
licenza consente, insieme a questa nota. Nessun carattere è stato modificato.
"""


def riscrivi_css(testo: str, scarica: Callable[[str], bytes]) -> tuple[str, list[str]]:
    """Riscrive le URL remote di un CSS di Google in percorsi relativi.

    Funzione pura sul testo: chi scarica è passato come argomento, così la logica si testa
    senza rete. Ritorna ``(css_locale, nomi_file)``; un URL ripetuto (stesso sottoinsieme
    usato da più pesi) viene scaricato una volta sola.
    """
    nomi: list[str] = []
    visti: dict[str, str] = {}

    def sostituisci(m: re.Match[str]) -> str:
        url = m.group(1)
        if url not in visti:
            nome = url.rsplit("/", 1)[-1]
            blob = scarica(url)
            if not blob:
                raise RuntimeError(f"file vuoto per {url}")
            visti[url] = nome
            nomi.append(nome)
            (FONTS_DIR / nome).write_bytes(blob)
        return f"url({visti[url]})"

    return _URL.sub(sostituisci, testo), nomi


def scarica_file(url: str) -> bytes:
    r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.content


def check() -> int:
    """Stato dei font locali, senza rete: 0 se completi, 1 se mancano."""
    css = FONTS_DIR / "fonts.css"
    woff2 = sorted(FONTS_DIR.glob("*.woff2")) if FONTS_DIR.exists() else []
    if not css.exists() or not woff2:
        print("font locali ASSENTI: il sito linka ancora fonts.googleapis.com.")
        print(f"  attesi in {FONTS_DIR.relative_to(FONTS_DIR.parents[4])}: fonts.css + *.woff2")
        print("  esegui `python scripts/font_locali.py` dove la rete verso Google è disponibile")
        return 1
    testo = css.read_text(encoding="utf-8")
    mancano = [n for n in set(re.findall(r"url\(([^)]+\.woff2)\)", testo))
               if not (FONTS_DIR / n).exists()]
    totale = sum(f.stat().st_size for f in woff2)
    print(f"font locali presenti: {len(woff2)} woff2 · {totale / 1024:.0f} kB · "
          f"licenza {'sì' if (FONTS_DIR / 'LICENSE.txt').exists() else 'MANCANTE'}")
    if mancano:
        print(f"  il CSS locale fa riferimento a file assenti: {sorted(mancano)}")
        return 1
    if "fonts.gstatic.com" in testo:
        print("  il CSS locale punta ancora a fonts.gstatic.com")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verifica senza scaricare")
    args = ap.parse_args()
    if args.check:
        return check()

    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(CSS_URL, timeout=60, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"Google Fonts non raggiungibile ({type(exc).__name__}: {exc}).")
        print("Esegui lo script dove la rete c'è: in locale o in un runner di Actions.")
        return 1
    css, nomi = riscrivi_css(r.text, scarica_file)
    (FONTS_DIR / "fonts.css").write_text(
        "/* Generato da scripts/font_locali.py — non modificare a mano. */\n" + css,
        encoding="utf-8")
    (FONTS_DIR / "LICENSE.txt").write_text(LICENSE, encoding="utf-8")
    totale = sum((FONTS_DIR / n).stat().st_size for n in nomi)
    print(f"scaricati {len(nomi)} woff2 · {totale / 1024:.0f} kB in "
          f"{FONTS_DIR.relative_to(FONTS_DIR.parents[4])}")
    print("dal prossimo `fda build` il sito serve i font in locale (nessun link a Google).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
