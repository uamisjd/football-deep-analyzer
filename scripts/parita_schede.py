"""Parità fra le schede pre-partita: stessa struttura, stessa quantità, su ogni partita.

Direttiva utente del 2026-09-19: «ogni partita deve avere la stessa alta qualità e quantità».
Le schede pre-partita nascono dallo stesso template con le stesse guardie, ma una guardia può
far sparire una card **su una pagina sola** e nessuno se ne accorge: è successo con «Clima del
club» (59 schede su 60, Alverca–Rio Ave), scoperto misurando — non da un test. Questa sonda
trasforma quella misura in un gate.

Misura, su ``site/partite/*.html``:

1. **struttura** — l'insieme degli id delle card deve essere *identico* in tutte le schede
   pre-partita (una sezione in più o in meno su una pagina è una differenza di qualità fra due
   partite, non un dettaglio);
2. **indice** — le voci della barra ``match-jump`` devono essere le stesse, nello stesso ordine
   (una voce che compare solo su alcune schede promette una sezione che le altre non hanno);
3. **quantità** — il testo visibile di ogni scheda (senza aprire le tendine) e il peso di ogni
   sezione non devono crollare rispetto alle altre schede: una sezione *presente ma vuota* è il
   segno di una guardia che scatta a metà;
4. **dove sta la differenza** (informativo) — min, mediana e max per sezione, così si vede se la
   forbice è fisiologica (una partita con tre precedenti in archivio e una con quaranta) o
   sospetta (una sezione a zero su una scheda).

Le soglie sono dichiarate e prudenti: 75% della mediana sul totale e 25% della mediana sulla
singola sezione. Non giudicano se una partita *ha* meno dati — quello si vede in pagina e nei
numeri — ma se la pagina si è *dimenticata* di raccontarli.

Uso: ``.venv/bin/python -m scripts.parita_schede [site_dir] [--data data_dir]`` —
richiede una build già fatta (``fda build``); esce 0 se tutte le schede sono pari,
1 elencando le differenze.

**Stato vuoto legittimo (sosta dei campionati, 2026-09-21).** Durante una pausa
(nazionali, nessuna gara in programma nei 7 giorni della finestra dettagliata) la
build produce correttamente **zero** schede pre-partita: solo pagine post-partita
d'archivio. Il vecchio comportamento trattava lo zero come «build mancante» e
fermava il run — misurato il 2026-09-21 (ultime gare il 20/09, ripresa il 09/10).
Ora lo zero si distingue leggendo ``fixtures.parquet``: se in finestra non c'è
davvero nessuna gara non finita, il gate non è applicabile (exit 0); se invece le
gare ci sono e le schede mancano, la build le ha perse (exit 1).
"""

from __future__ import annotations

import argparse
import collections
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fda.config import DETAIL_WINDOW_DAYS, load_leagues_config
from scripts.prematch_sections import leaf_cards, parse

ROOT = Path(__file__).resolve().parent.parent

#: Soglie dichiarate (vedi il docstring): sotto questi valori la differenza non è più
#: «una partita con meno dati», è una pagina costruita peggio delle altre.
SOGLIA_TOTALE = 0.75
SOGLIA_SEZIONE = 0.25

#: Eccezioni ammesse, con la ragione accanto. Vuoto: oggi le 60 schede pre-partita hanno la
#: stessa struttura, misurata il 2026-09-19. Se un giorno una sezione manca davvero perché la
#: fonte non pubblica quel dato, si dichiara qui (id della sezione → perché) **e** si scrive in
#: pagina una riga che lo dice al lettore: un'eccezione silenziosa è il difetto che questa
#: sonda esiste per impedire. Non si allenta il controllo.
ECCEZIONI: dict[str, str] = {}

PRE = "Analisi pre-partita"
NAV = "match-jump"
CARD_TAG = {"div", "details", "section"}


def schede(site: Path) -> list[tuple[str, str]]:
    """Le pagine pre-partita della build: ``(match_id, html)``."""
    partite = site / "partite"
    if not partite.is_dir():
        return []
    out = []
    for pg in sorted(partite.glob("*.html")):
        html = pg.read_text(encoding="utf-8")
        if PRE in html:
            out.append((pg.stem, html))
    return out


def _ancore(html: str) -> tuple[str, ...]:
    return tuple(f"#{h}" for h in re.findall(r'<a href="#([^"]+)">[^<]+</a>',
                                             html.split(f'class="{NAV}"', 1)[1].split("</nav>", 1)[0]))


def attese_prepartita(data: Path) -> int | None:
    """Gare non finite in finestra su ``fixtures.parquet`` (``None`` se illeggibile).

    Stessa finestra della build (``SiteBuilder.build_indexes``): da oggi a oggi +
    ``DETAIL_WINDOW_DAYS`` in date locali, esclusi finiti e annullati (gli annullati
    non ricevono nessuna pagina). Una pagina contiene «Analisi pre-partita» se e solo
    se il suo stato non è ``finished`` (``match.html``): questo conteggio è quindi il
    numero di schede pre-partita che la build **deve** aver prodotto.
    """
    import pandas as pd

    fx_path = data / "fixtures.parquet"
    if not fx_path.is_file():
        return None
    try:
        fx = pd.read_parquet(fx_path)
        if fx.empty or not {"utc_kickoff", "status"}.issubset(fx.columns):
            return None
        tz = ZoneInfo(load_leagues_config().get("timezone_display", "Europe/Rome"))
        oggi = datetime.now(tz).date()
        local = pd.to_datetime(fx["utc_kickoff"], utc=True, errors="coerce").dt.tz_convert(tz).dt.date
        in_finestra = (local >= oggi) & (local <= oggi + timedelta(days=DETAIL_WINDOW_DAYS))
        return int((in_finestra & ~fx["status"].isin(["finished", "cancelled"])).sum())
    except Exception:
        return None


def _gestisci_vuoto(site: Path, data: Path) -> int:
    """Zero schede pre-partita: build mancante, sosta legittima o build che perde pagine."""
    partite = site / "partite"
    n_pagine = len(list(partite.glob("*.html"))) if partite.is_dir() else 0
    if n_pagine == 0:
        print(f"nessuna pagina in {site}/partite: serve una build (`fda build`)")
        return 1
    attese = attese_prepartita(data)
    if attese is None:
        print(f"0 schede pre-partita in {site}/partite e {data}/fixtures.parquet illeggibile: "
              f"impossibile distinguere una sosta da una build persa")
        return 1
    if attese == 0:
        print(f"[P] schede pre-partita: 0 su {n_pagine} pagine — sosta dei campionati "
              f"(0 gare non finite in finestra su fixtures.parquet): parità non applicabile")
        return 0
    print(f"0 schede pre-partita in {site}/partite ma {attese} gare non finite in finestra: "
          f"la build le ha perse")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("site", nargs="?", default=str(ROOT / "site"),
                    help="cartella del sito generato")
    ap.add_argument("--data", default=str(ROOT / "data" / "processed"),
                    help="cartella dei Parquet (per distinguere una sosta da una build persa)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    site = Path(args.site)
    pagine = schede(site)
    if not pagine:
        return _gestisci_vuoto(site, Path(args.data))

    problemi: list[str] = []
    strutture: dict[tuple[str, ...], list[str]] = collections.defaultdict(list)
    indici: dict[tuple[str, ...], list[str]] = collections.defaultdict(list)
    totale: dict[str, int] = {}
    pesi: dict[str, dict[str, int]] = collections.defaultdict(dict)

    for mid, html in pagine:
        root = parse(site / "partite" / f"{mid}.html")
        ids = tuple(sorted({n.attrs["id"] for n in root.find_all(CARD_TAG) if n.attrs.get("id")}))
        strutture[ids].append(mid)
        indici[_ancore(html)].append(mid)
        # il peso si misura sulle card-foglia (una griglia come #club contiene altre card:
        # contarla per intero conterebbe due volte le stesse sezioni), con la stessa
        # definizione di `scripts/prematch_sections.py` e lo stesso numero pubblicato lì
        somma = 0
        for titolo, _dom, car, _nodo in leaf_cards(root):
            somma += car
            pesi[titolo][mid] = car
        totale[mid] = somma

    # 1) struttura: l'insieme degli id deve essere identico in tutte le schede
    if len(strutture) > 1:
        atteso = max(strutture, key=lambda k: len(strutture[k]))
        for ids, mids in strutture.items():
            if ids == atteso:
                continue
            manca = [i for i in atteso if i not in ids and i not in ECCEZIONI]
            extra = [i for i in ids if i not in atteso]
            for mid in mids[:4]:
                pezzi = []
                if manca:
                    pezzi.append(f"sezioni assenti: {', '.join(manca)}")
                if extra:
                    pezzi.append(f"sezioni in più: {', '.join(extra)}")
                problemi.append(f"{mid}: {' · '.join(pezzi) or 'struttura diversa dalle altre schede'}")

    # 2) indice: stesse voci, stesso ordine
    if len(indici) > 1:
        atteso_nav = max(indici, key=lambda k: len(indici[k]))
        for nav, mids in indici.items():
            if nav == atteso_nav:
                continue
            manca = [v for v in atteso_nav if v not in nav]
            for mid in mids[:4]:
                problemi.append(f"{mid}: indice diverso"
                                + (f" (mancano {', '.join(manca)})" if manca else ""))

    # 3) quantità: totale e singole sezioni
    med_tot = statistics.median(totale.values())
    for mid, car in sorted(totale.items()):
        if car < SOGLIA_TOTALE * med_tot:
            problemi.append(f"{mid}: {car} caratteri visibili, sotto il "
                            f"{SOGLIA_TOTALE:.0%} della mediana ({med_tot:.0f})")
    comuni = [i for i, d in pesi.items() if len(d) == len(pagine)]
    for sezione in sorted(comuni):
        med = statistics.median(pesi[sezione].values())
        if med < 80:
            continue                      # sezioni brevi per natura (titoli, ancore)
        for mid, car in sorted(pesi[sezione].items()):
            if car < SOGLIA_SEZIONE * med:
                problemi.append(f"{mid}: la sezione «{sezione}» ha {car} caratteri visibili "
                                f"contro una mediana di {med:.0f} — presente ma vuota")

    # --- riepilogo -------------------------------------------------------------------
    n = len(pagine)
    print(f"[P] schede pre-partita: {n} · struttura "
          + ("identica" if len(strutture) == 1 else f"DIVERSA ({len(strutture)} varianti)")
          + f" ({len(max(strutture, key=lambda k: len(strutture[k])))} id)")
    print("[P] indice: " + ("uguale in tutte" if len(indici) == 1 else f"{len(indici)} varianti")
          + f" · {len(max(indici, key=lambda k: len(indici[k])))} voci")
    print(f"[P] testo visibile per scheda: min {min(totale.values())} · mediana {med_tot:.0f}"
          f" · max {max(totale.values())} (il minimo è il "
          f"{min(totale.values()) / med_tot:.0%} della mediana)")
    forbici = sorted(((max(d.values()) - min(d.values()), s) for s, d in pesi.items() if len(d) == n),
                     reverse=True)[:6]
    print("[P] dove varia di più la quantità (min–max per sezione): "
          + " · ".join(f"{s} {min(pesi[s].values())}–{max(pesi[s].values())}" for _f, s in forbici))

    if problemi:
        coinvolte = sorted({p.split(":")[0] for p in problemi})
        print(f"\n{len(coinvolte)} schede fuori dalla parità · {len(problemi)} differenze:")
        for p in problemi[:20]:
            print("  -", p)
        if len(problemi) > 20:
            print(f"  … e altre {len(problemi) - 20}")
        print("\nChe fare: se la sezione manca perché la fonte non pubblica quel dato, si "
              "aggiunge in pagina la riga che lo dice (come «Nessun indisponibile segnalato») "
              "e, se l'assenza è strutturale, si dichiara in `ECCEZIONI` con la ragione.")
        return 1
    print("\nnessuna differenza: ogni scheda pre-partita ha le stesse sezioni, lo stesso indice "
          "e la stessa quantità di testo delle altre")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
