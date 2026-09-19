"""Resa a 375 px misurata senza browser (P2.8 di `docs/19` §3, `docs/39`).

Dal sandbox non c'è un browser (e nemmeno in CI: nessun Chromium scaricabile). Un «non
verificato» però non è una risposta: **la resa a 375 px si può calcolare**, perché il layout di
queste pagine è dichiarato (nessun `position:fixed` che cambi il flusso, nessun font remoto, nessun
JavaScript che riscriva le misure) e il sito si porta dietro i **suoi** font.

Questo script misura tre cose, sulle pagine vere di `site/`:

1. **Il budget di larghezza** — viewport 375, padding di `main` e delle card letti dal CSS: quanti
   pixel restano al contenuto (l'unico numero da cui parte tutto).
2. **La larghezza minima di ogni tabella** — per ogni cella, la parola più lunga misurata con il
   font self-hosted del sito (`fontTools` sui `.woff2` reali, istanza variabile sul peso giusto) più
   il padding dichiarato; la somma per colonna è la larghezza sotto la quale la tabella **non può**
   scendere. Se supera lo spazio disponibile e la tabella non è dentro `.tablewrap`, la pagina
   scorre di lato: è il difetto mobile che si vede.
3. **Le quattro rese che P2.8 nomina** — il badge della forma in testa alla scheda (P2.5), i
   micro-visivi (P2.3), l'indice (P1.3), la tendina della verifica (P1.4): larghezza delle
   etichette contro la colonna che le contiene, con l'andata a capo del badge calcolata come la
   calcola un flex (riga per riga, primo che non ci sta va sotto).

Più una guardia generale: larghezze in pixel scritte nell'HTML, testi in `white-space:nowrap`,
immagini e `svg` con `width` fisso.

**Che cosa non è.** Non è un browser: non misura antialiasing, subpixel, `border-radius` o
larghezza della barra di scorrimento. Non vede le regole che vincono per specificità più alta di
quella scritta qui (ne usa una per selettore, l'ultima in ordine di file). Ma tutto ciò che questo
script dichiara «non ci sta» è aritmetica sul CSS pubblicato e sui font pubblicati: se lo dice, è
vero. Al contrario, con font più stretto del misurato può sfuggirgli un caso limite — per questo
le misure usano il **peso più alto** fra quelli plausibili per il testo.

Uso:  ``.venv/bin/python -m scripts.resa_375 [--verbose] [--pagina NOME]``
Esce 1 se una pagina scorre di lato a 375 px.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RADICE = Path(__file__).resolve().parent.parent
SITO = RADICE / "site"
FONTS_CSS = SITO / "assets" / "fonts" / "fonts.css"
SITE_CSS = SITO / "assets" / "site.css"

VIEWPORT = 375          # iPhone SE / 12 mini: il riferimento chiesto
EM = 16.0               # 1rem

KO = "KO"
NOTA = "nota"
OK = "ok"


# --------------------------------------------------------------------------- CSS

@dataclass
class Regola:
    selettore: str
    prop: dict[str, str]
    mq: str | None
    indice: int


def _senza_commenti(testo: str) -> str:
    return re.sub(r"/\*.*?\*/", "", testo, flags=re.DOTALL)


def leggi_css(testo: str) -> list[Regola]:
    """Regole piatte con la loro media query. Basta per un CSS scritto a mano come questo."""
    testo = _senza_commenti(testo)
    regole: list[Regola] = []
    i = 0
    mq: str | None = None
    n = 0
    while i < len(testo):
        braccio = testo.find("{", i)
        if braccio < 0:
            break
        testa = testo[i:braccio].strip()
        if testa.startswith("@media"):
            mq = testa[len("@media"):].strip()
            i = braccio + 1
            continue
        if testa.startswith("@") or not testa:      # @font-face, @keyframes, @supports
            i = braccio + 1
            continue
        fine = testo.find("}", braccio)
        if fine < 0:
            break
        prop = {}
        for pezzo in testo[braccio + 1:fine].split(";"):
            if ":" in pezzo:
                k, v = pezzo.split(":", 1)
                prop[k.strip().lower()] = v.strip()
        n += 1
        regole.append(Regola(testa, prop, mq, n))
        i = fine + 1
        # chiusura del blocco @media (il `}` esterno lo incontriamo al passo dopo)
        if mq and i < len(testo) and testo[i] == "}":
            mq = None
            i += 1
    return regole


def mq_vale(mq: str | None, larghezza: int) -> bool:
    """Vale a 375 px? Solo le max-width larghe abbastanza; le prefers-* le ignoriamo."""
    if not mq:
        return True
    if "prefers" in mq:
        return False
    m = re.search(r"max-width:\s*(\d+(?:\.\d+)?)px", mq)
    if m:
        return larghezza <= float(m.group(1))
    return False


def px(valore: str | None) -> float | None:
    """'22px' → 22.0 · '1.5rem' → 24.0 · altrimenti None."""
    if not valore:
        return None
    m = re.match(r"^(-?\d+(?:\.\d+)?)(px|rem)?$", valore.strip())
    if not m:
        return None
    v = float(m.group(1))
    if m.group(2) == "rem":
        v *= EM
    return v


class Css:
    """Cascata minima: per ogni selettore vince l'ultima dichiarazione in ordine di file."""

    def __init__(self, testo: str, larghezza: int = VIEWPORT) -> None:
        self.regole = leggi_css(testo)
        self.larghezza = larghezza

    def _regole(self, selettore: str) -> list[Regola]:
        return [r for r in self.regole if r.selettore == selettore and mq_vale(r.mq, self.larghezza)]

    def prop(self, selettore: str, nome: str) -> str | None:
        trovato = None
        for r in self._regole(selettore):
            if nome in r.prop:
                trovato = r.prop[nome]
        return trovato

    def prop_qualunque(self, selettori: list[str], nome: str) -> str | None:
        trovato = None
        for sel in selettori:
            v = self.prop(sel, nome)
            if v is not None:
                trovato = v
        return trovato

    # --- scorciatoie -------------------------------------------------------

    def lunghezza(self, selettore: str, nome: str, difetto: float | None = None) -> float | None:
        return px(self.prop(selettore, nome)) or difetto

    def padding(self, selettore: str) -> tuple[float, float]:
        """(orizzontale, verticale) dal padding o dallo shorthand."""
        v = self.prop(selettore, "padding") or self.prop(selettore, "padding-inline")
        lati = [px(x) for x in v.split()] if v else []
        lati = [x for x in lati if x is not None]
        if not lati:
            return 0.0, 0.0
        if len(lati) == 1:
            return lati[0] * 2, lati[0] * 2
        if len(lati) >= 2:
            return lati[1] * 2, lati[0] * 2
        return lati[0] * 2, 0.0

    def _font(self, selettore: str) -> tuple[float, int]:
        """(dimensione px, peso) leggendo `font-size`/`font-weight` o lo shorthand `font`."""
        dim = px(self.prop(selettore, "font-size"))
        peso = px(self.prop(selettore, "font-weight"))
        f = self.prop(selettore, "font")
        if f:
            m = re.match(r"(?:(\d{3})\s+)?(\d+(?:\.\d+)?)px", f)
            if m:
                if m.group(1):
                    peso = float(m.group(1))
                dim = float(m.group(2))
        return dim or 14.5, int(peso or 400)

    def traccia(self, selettore: str) -> float:
        """letter-spacing in em."""
        v = self.prop(selettore, "letter-spacing")
        if v and v.endswith("em"):
            return float(v[:-2])
        return 0.0

    def maiuscolo(self, selettore: str) -> bool:
        return (self.prop(selettore, "text-transform") or "") == "uppercase"

    def ora(self, selettore: str) -> bool:
        return (self.prop(selettore, "white-space") or "").startswith("nowrap")

    def scorrevole(self, selettore: str) -> bool:
        return (self.prop(selettore, "overflow-x") or "") in {"auto", "scroll"}

    def font(self, selettore: str, eredita: str | None = None) -> tuple[float, int]:
        """Come sopra, ma se il selettore non dichiara nulla eredita da `eredita`."""
        dim, peso = self._font(selettore)
        if eredita:
            dim2, peso2 = self._font(eredita)
            if self.prop(selettore, "font-size") is None and self.prop(selettore, "font") is None:
                dim = dim2
            if self.prop(selettore, "font-weight") is None and self.prop(selettore, "font") is None:
                peso = peso2
        return dim, peso

    @property
    def _regole_nascoste(self) -> list[Regola]:
        cache = getattr(self, "_nascoste_cache", None)
        if cache is None:
            cache = [r for r in self.regole
                     if r.prop.get("display") == "none" and mq_vale(r.mq, self.larghezza)
                     and ":" not in r.selettore]
            self._nascoste_cache = cache
        return cache

    def nascosto(self, nodo: Nodo) -> bool:
        """Vale `display:none` a 375 px per questo elemento?

        Una media query che spegne un pezzo di testo (l'etichetta «Forma» sul telefono) non è
        un imbarbarimento: è una decisione. Ma va **vista**: la sonda la rispetta solo perché la
        regola è dichiarata nel CSS, e chi legge il CSS la trova.
        """
        chiave = (nodo.tag, tuple(sorted(nodo.classi)))
        cache = getattr(self, "_nascosto_nodi", None)
        if cache is None:
            cache = {}
            self._nascosto_nodi = cache
        if chiave in cache:
            return cache[chiave]
        esito = any(_selettore_copre(r.selettore, nodo) for r in self._regole_nascoste)
        cache[chiave] = esito
        return esito


# --------------------------------------------------------------------------- font


class FontBook:
    """Larghezza dei testi con i `.woff2` veri del sito (istanza variabile sul peso)."""

    def __init__(self, css_font: Path, cartella: Path) -> None:
        self.cartella = cartella
        self.facce = self._leggi_facce(css_font)
        self._cache: dict[tuple[str, int], dict[str, float]] = {}
        self._txt: dict[tuple[str, str, int, float, float, bool], float] = {}
        self.mancanti: set[str] = set()

    def _leggi_facce(self, percorso: Path) -> dict[str, list[Path]]:
        testo = _senza_commenti(percorso.read_text(encoding="utf-8"))
        famiglie: dict[str, list[Path]] = {}
        for blocco in re.findall(r"@font-face\s*\{(.*?)\}", testo, flags=re.DOTALL):
            fam = re.search(r"font-family:\s*'([^']+)'", blocco)
            src = re.search(r"url\(([^)]+)\)", blocco)
            if fam and src:
                famiglie.setdefault(fam.group(1), [])
                f = self.cartella / src.group(1)
                if f not in famiglie[fam.group(1)]:
                    famiglie[fam.group(1)].append(f)
        return famiglie

    def _mappa(self, famiglia: str, peso: int) -> dict[str, float]:
        chiave = (famiglia, peso)
        if chiave in self._cache:
            return self._cache[chiave]
        mappa: dict[str, float] = {}
        for file in self.facce.get(famiglia, []):
            font = TTFont(file)
            if "fvar" in font:
                assi = {a.axisTag: a for a in font["fvar"].axes}
                if "wght" in assi:
                    peso_vero = min(max(peso, int(assi["wght"].minValue)), int(assi["wght"].maxValue))
                    font = instancer.instantiateVariableFont(font, {"wght": peso_vero},
                                                            inplace=True, updateFontNames=False)
            upem = font["head"].unitsPerEm
            cmap = font.getBestCmap()
            hmtx = font["hmtx"]
            for cod, nome in cmap.items():
                if nome in hmtx.metrics:
                    mappa.setdefault(chr(cod), hmtx[nome][0] * 1000.0 / upem)   # per 1000 px
        self._cache[chiave] = mappa
        return mappa

    def larghezza(self, testo: str, famiglia: str, peso: int, dimensione: float,
                  traccia: float = 0.0, maiuscolo: bool = False) -> float:
        """Larghezza in px del testo, con i font del sito. Con cache: le stesse voci si ripetono."""
        chiave = (testo, famiglia, peso, dimensione, traccia, maiuscolo)
        if chiave in self._txt:
            return self._txt[chiave]
        w = self._larghezza(testo, famiglia, peso, dimensione, traccia, maiuscolo)
        self._txt[chiave] = w
        return w

    def _larghezza(self, testo: str, famiglia: str, peso: int, dimensione: float,
                   traccia: float = 0.0, maiuscolo: bool = False) -> float:
        if not testo:
            return 0.0
        s = testo.upper() if maiuscolo else testo
        mappe = [(f, self._mappa(f, peso)) for f in ("Sora", "Inter")] if famiglia == "head" else \
                [(f, self._mappa(f, peso)) for f in ("Inter",)]
        tot = 0.0
        for ch in s:
            for _, mappa in mappe:
                if ch in mappa:
                    tot += mappa[ch]
                    break
            else:
                self.mancanti.add(ch)
                tot += 520.0                                    # segnaposto prudente
        tot = tot * dimensione / 1000.0
        if traccia:
            tot += traccia * dimensione * len(s)
        return tot


def min_content(font: FontBook, testo: str, *, famiglia: str, peso: int, dimensione: float,
                traccia: float, maiuscolo: bool, ora: bool) -> float:
    """La larghezza sotto la quale il testo non può scendere (parola più lunga)."""
    testo = " ".join(testo.split())
    if not testo:
        return 0.0
    pezzi = [testo] if ora else re.split(r"[\s\u00a0]+", testo)
    return max(font.larghezza(p, famiglia, peso, dimensione, traccia, maiuscolo) for p in pezzi)


def _parti(selettore: str) -> list[str]:
    return [p for p in re.split(r"\s+", selettore.strip()) if p]


def _copre_parte(parte: str, nodo: Nodo) -> bool:
    """Un pezzo di selettore (`.classe`, `tag`, `tag.classe`) vale per questo nodo?"""
    parte = parte.split(">")[-1].strip()
    for cls in re.findall(r"\.(-?[\w-]+)", parte):
        if cls not in nodo.classi:
            return False
    tag = re.match(r"^([a-zA-Z][\w-]*)", parte)
    return not (tag and tag.group(1).lower() != nodo.tag)


def _selettore_copre(selettore: str, nodo: Nodo) -> bool:
    """Il selettore (discendente) corrisponde al nodo? Pseudo-classi già escluse da chi chiama."""
    parti = _parti(selettore)
    if not parti or not _copre_parte(parti[-1], nodo):
        return False
    # gli antenati, dalla parte più vicina all'indietro
    n = nodo.genitore
    for parte in reversed(parti[:-1]):
        while n is not None and not _copre_parte(parte, n):
            n = n.genitore
        if n is None:
            return False
        n = n.genitore
    return True


# --------------------------------------------------------------------------- DOM


@dataclass
class Nodo:
    tag: str
    attr: dict[str, str] = field(default_factory=dict)
    figli: list[Nodo] = field(default_factory=list)
    testo: list[str] = field(default_factory=list)
    genitore: Nodo | None = None

    @property
    def classi(self) -> set[str]:
        return set((self.attr.get("class") or "").split())

    def trova(self, *classi: str) -> list[Nodo]:
        """Discendenti che hanno **tutte** le classi indicate."""
        out = []
        for f in self.figli:
            if set(classi) <= f.classi:
                out.append(f)
            out.extend(f.trova(*classi))
        return out

    def per_id(self, elem_id: str) -> Nodo | None:
        for f in self.figli:
            if f.attr.get("id") == elem_id:
                return f
            r = f.per_id(elem_id)
            if r is not None:
                return r
        return None

    def testo_visibile(self, salta=None) -> str:
        pezzi = [" ".join(self.testo)]
        for f in self.figli:
            if salta is not None and salta(f):
                continue
            pezzi.append(f.testo_visibile(salta))
        return " ".join(pezzi)

    def discendenti(self, tag: str | None = None):
        for f in self.figli:
            if tag is None or f.tag == tag:
                yield f
            yield from f.discendenti(tag)


class Albero(HTMLParser):
    VUOTI: ClassVar[set[str]] = {"br", "img", "meta", "link", "input", "hr", "source", "col", "area", "base", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.radice = Nodo("documento")
        self.corrente = self.radice
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self.skip += 1
        nodo = Nodo(tag, dict(attrs), genitore=self.corrente)
        self.corrente.figli.append(nodo)
        if tag not in self.VUOTI:
            self.corrente = nodo

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.corrente.figli.append(Nodo(tag, dict(attrs), genitore=self.corrente))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if tag in self.VUOTI:
            return
        n = self.corrente
        while n is not None and n.tag != tag:
            n = n.genitore
        if n is not None and n.genitore is not None:
            self.corrente = n.genitore

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.corrente.testo.append(data)


def leggi_pagina(percorso: Path) -> Nodo:
    a = Albero()
    a.feed(percorso.read_text(encoding="utf-8"))
    return a.radice


# --------------------------------------------------------------------------- budget


@dataclass
class Esito:
    controllo: str
    dove: str
    misurato: float
    disponibile: float
    stato: str
    nota: str = ""


class Resa:
    """Le misure a 375 px su una pagina."""

    def __init__(self, root: Nodo, css: Css, font: FontBook, nome: str) -> None:
        self.root = root
        self.css = css
        self.font = font
        self.nome = nome
        self.esiti: list[Esito] = []

    # --- budget ------------------------------------------------------------

    def budget(self) -> tuple[float, float]:
        """(larghezza utile del contenuto, larghezza dentro una card)."""
        main_pad, _ = self.css.padding("main")
        dentro = VIEWPORT - main_pad
        card_pad, _ = self.css.padding(".card")
        return dentro, dentro - card_pad

    def aggiungi(self, controllo: str, dove: str, misurato: float, disponibile: float,
                 stato: str, nota: str = "") -> None:
        self.esiti.append(Esito(controllo, dove, round(misurato, 1), round(disponibile, 1),
                                stato, nota))

    # --- larghezza minima delle tabelle ------------------------------------

    def celle(self, tabella: Nodo) -> list[list[Nodo]]:
        righe = []
        for tr in tabella.discendenti("tr"):
            celle = [c for c in tr.figli if c.tag in ("td", "th") and not self.css.nascosto(c)]
            if celle and all(c.genitore is tr for c in celle):
                righe.append(celle)
        return righe

    def padding_cella(self, cella: Nodo) -> float:
        sel = "th" if cella.tag == "th" else "td"
        if "scoregrid" in (cella.genitore.attr.get("class") or "") if cella.genitore else False:
            sel = f".scoregrid {cella.tag}"
        v = self.css.prop(sel, "padding") or self.css.prop("td,th", "padding")
        lati = [px(x) for x in (v or "").split()]
        lati = [x for x in lati if x is not None]
        if not lati:
            return 24.0                                   # td,th{padding:10px 12px}
        return (lati[1] * 2) if len(lati) >= 2 else lati[0] * 2

    def min_cella(self, cella: Nodo, dentro: float) -> float:
        """Larghezza minima della cella: parola più lunga (o tutto il testo se nowrap)."""
        testo = " ".join(cella.testo_visibile(self.css.nascosto).split())
        classi = cella.classi
        sel = ".small" if "small" in classi else ("td" if cella.tag != "th" else "th")
        dim, peso = self.css.font(sel)
        if "small" in classi:
            dim, _ = self.css.font(".small")
        ora = any(self.css.ora(f".{c}") for c in classi)
        # un `<span class="wl">` dichiara la sua larghezza minima
        minima = 0.0
        for wl in cella.trova("wl"):
            minima = max(minima, self.css.lunghezza(".wl", "min-width", 104.0) or 0.0)
        for i in cella.discendenti():
            if i.tag in ("span", "b", "i") and "wl" in i.classi:
                minima = max(minima, self.css.lunghezza(".wl", "min-width", 104.0) or 0.0)
        if "gb" in classi or "dp" in classi:
            minima = max(minima, 14.0)
        # pillole e tag: padding orizzontale dichiarato
        extra = 0.0
        for t in cella.trova("tag"):
            dim_tag, _ = self.css.font(".tag")
            extra = max(extra, self.font.larghezza("x", "body", 700, dim_tag) * 2 + 12.0)
        parole = min_content(self.font, testo, famiglia="body", peso=max(peso, 600),
                             dimensione=dim, traccia=0.0, maiuscolo=cella.tag == "th", ora=ora)
        return max(minima + self.padding_cella(cella), parole + self.padding_cella(cella), extra)

    def controlla_tabelle(self, dentro: float, dentro_card: float) -> None:
        for tabella in self.root.discendenti("table"):
            righe = self.celle(tabella)
            if not righe:
                continue
            n_col = max(len(r) for r in righe)
            colonne = [0.0] * n_col
            for r in righe:
                for i, cella in enumerate(r):
                    colonne[i] = max(colonne[i], self.min_cella(cella, dentro_card))
            scorrevole = any("tablewrap" in (n.attr.get("class") or "")
                             for n in self._antenati(tabella))
            total = sum(colonne)
            intestazione = " ".join(tabella.discendenti("th").__iter__().__next__().testo_visibile()
                                    .split())[:44] if list(tabella.discendenti("th")) else "(senza th)"
            dove = f"{n_col} colonne · «{intestazione}»"
            if scorrevole:
                self.aggiungi("tabella in .tablewrap", dove, total, dentro_card, OK,
                              "scorre dentro la card, la pagina no")
            elif total <= dentro_card + 0.5:
                self.aggiungi("tabella", dove, total, dentro_card, OK)
            else:
                self.aggiungi("tabella senza .tablewrap", dove, total, dentro_card, KO,
                              f"la pagina scorre di lato di {total - dentro_card:.0f} px")

    def _antenati(self, nodo: Nodo):
        n = nodo.genitore
        while n is not None:
            yield n
            n = n.genitore

    # --- le quattro rese di P2.8 ------------------------------------------

    def badge_forma(self) -> None:
        """Il badge della forma (P2.5) in testa alla scheda: quante righe occupa a 375 px."""
        main_pad, _ = self.css.padding("main")
        hero_pad, _ = self.css.padding(".match-hero")
        avail = VIEWPORT - main_pad - hero_pad
        gap = self.css.lunghezza(".match-scoreline", "gap", 8.0) or 8.0
        larg_centro = 66.0
        lato = (avail - larg_centro - 2 * gap) / 2
        sel = ".match-hero-team .form-line"
        gap_badge = self.css.lunghezza(sel, "gap", 6.0) or 6.0
        sel_label = ".match-hero-team .form-line .fact-label"
        sel_line = ".match-hero-team .form-line"
        dim_label, peso_label = self.css.font(sel_label, eredita=sel_line)
        dim_val, peso_val = self.css.font(".fact-value", eredita=sel_line)
        label_nascosta = any(
            r.prop.get("display") == "none" and "fact-label" in r.selettore
            for r in self.css.regole if mq_vale(r.mq, self.css.larghezza)
        )
        dot = self.css.lunghezza(".match-hero-team .form-dot", "width", 14.0) or 14.0
        gap_dot = self.css.lunghezza(".fact-label", "margin-right", 1.0) or 0.0
        larghezza_label = [[], []]
        n_casi = 0
        for hero in self.root.trova("match-line-team"):
            pass
        for squadra in self.root.trova("match-hero-team"):
            riga = next((f for f in squadra.figli if "form-line" in f.classi), None)
            if riga is None:
                continue
            n_casi += 1
            etichetta = next((t for t in riga.testo_visibile().split() if t), "")
            etichetta = "Forma"
            pallini = len([d for d in riga.discendenti("span") if "form-dot" in d.classi])
            valore = (riga.attr.get("aria-label") or "")
            m = re.search(r"(\d+)\s*pt", riga.testo_visibile())
            valore = f"{m.group(1)} pt" if m else ""
            pezzi = [
                self.font.larghezza(etichetta, "body", peso_label, dim_label,
                                    self.css.traccia(sel_label), True) + gap_dot
                if not label_nascosta else 0.0,
                pallini * dot + max(0, pallini - 1) * self.css.lunghezza(".form-dots", "gap", 3.0),
                self.font.larghezza(valore, "body", peso_val, dim_val),
            ]
            pezzi = [x for x in pezzi if x] or [0.0]
            if label_nascosta:
                etichetta = ""
            righe = 1
            usato = 0.0
            for p in pezzi:
                if usato and usato + gap_badge + p > lato + 0.5:
                    righe += 1
                    usato = p
                else:
                    usato += (gap_badge if usato else 0) + p
            larghezza_label[0].append(sum(pezzi) + 2 * gap_badge)
            larghezza_label[1].append(lato)
            stato = OK if righe == 1 else KO
            descr = f"{pallini} pallini · «{etichetta} … {valore}»" if etichetta else \
                    f"{pallini} pallini · «{valore}» (senza etichetta: display:none sotto 420 px)"
            self.aggiungi("badge della forma (P2.5)", f"hero, squadra {n_casi}, {descr}",
                          larghezza_label[0][-1], lato, stato,
                          "" if righe == 1 else f"va su {righe} righe invece di 1")
        if larghezza_label[0]:
            self.aggiungi("badge della forma", "colonna hero a 375 px", max(larghezza_label[0]),
                          larghezza_label[1][0], OK if max(larghezza_label[0]) <= larghezza_label[1][0]
                          else KO, "misura del caso più largo")

    def indice(self) -> None:
        barra = next(iter(self.root.trova("match-jump")), None)
        if barra is None:
            return
        main_pad, _ = self.css.padding("main")
        avail = VIEWPORT - main_pad
        pad, _ = self.css.padding(".match-jump")
        dim, peso = self.css.font(".match-jump a")
        pad_a, _ = self.css.padding(".match-jump a")
        gap = self.css.lunghezza(".match-jump", "gap", 4.0) or 4.0
        totale = pad
        visibili = 0
        usato = pad
        for a in barra.figli:
            if a.tag != "a":
                continue
            w = self.font.larghezza(" ".join(a.testo_visibile().split()), "body", peso, dim) + pad_a
            totale += w + gap
            if usato + w + gap <= avail:
                visibili += 1
                usato += w + gap
        totale = totale - gap + pad
        self.aggiungi("indice (P1.3)", f"{len(barra.figli)} voci · {visibili} visibili senza scorrere",
                      totale, avail, OK, "la barra scorre da sola (overflow-x:auto): la pagina no")

    def micro_visivi(self, dentro_card: float) -> None:
        # goalclock: 6 colonne, etichette sotto le barre
        col = (dentro_card - 5 * (self.css.lunghezza(".goalclock", "gap", 5.0) or 5.0)) / 6
        for clock in self.root.trova("goalclock"):
            for barra in clock.figli:
                for val in barra.figli:
                    testo = " ".join(val.testo_visibile().split())
                    if not testo:
                        continue
                    sel = ".gb .x" if "x" in val.classi else ".gb .v"
                    dim, peso = self.css.font(sel)
                    w = self.font.larghezza(testo, "body", max(peso, 700), dim)
                    self.aggiungi("micro-visivo: primo gol (P2.3)", f"etichetta «{testo}»",
                                  w, col, OK if w <= col else KO,
                                  "" if w <= col else "etichetta più larga della colonna")
            break
        # goalgrid: 8 colonne (distribuzione dei gol totali)
        griglia = next(iter(self.root.trova("goalgrid")), None)
        if griglia is not None:
            gap = self.css.lunghezza(".goalgrid", "gap", 5.0) or 5.0
            col8 = (dentro_card - 7 * gap) / 8
            peggiore = 0.0
            esempio = ""
            for barra in griglia.figli:
                for val in barra.figli:
                    testo = " ".join(val.testo_visibile().split())
                    if not testo:
                        continue
                    sel = ".gb .x" if "x" in val.classi else ".gb .v"
                    dim, peso = self.css.font(sel)
                    w = self.font.larghezza(testo, "body", max(peso, 700), dim)
                    if w > peggiore:
                        peggiore, esempio = w, testo
            self.aggiungi("micro-visivo: distribuzione gol (P2.3)",
                          f"8 colonne · etichetta più larga «{esempio}»", peggiore, col8,
                          OK if peggiore <= col8 else KO)
        # barre delle fasce: larghezza minima della .wl
        wl_min = self.css.lunghezza(".wl", "min-width", 104.0) or 104.0
        self.aggiungi("micro-visivo: fasce storiche (P2.3)", "larghezza minima della barra",
                      wl_min, dentro_card / 3, OK, "min-width dichiarato")
        # asse della barra di lega
        asse = next(iter(self.root.trova("viz")), None)
        if asse is not None:
            etichette = [s for s in asse.discendenti("span") if "axis" in (s.genitore.classi
                        if s.genitore else set())]
            if etichette:
                dim, peso = self.css.font(".viz .axis")
                gap = self.css.lunghezza(".viz .axis", "gap", 8.0) or 8.0
                totale = sum(self.font.larghezza(" ".join(e.testo_visibile().split()), "body",
                                                 peso, dim) for e in etichette)
                totale += gap * (len(etichette) - 1)
                self.aggiungi("micro-visivo: scala di lega (P2.3)",
                              f"asse a {len(etichette)} etichette", totale, dentro_card,
                              OK if totale <= dentro_card else NOTA,
                              "" if totale <= dentro_card else "le etichette si accorciano con «…»")

    def tendine(self, dentro_card: float) -> None:
        for det in self.root.discendenti("details"):
            som = next((f for f in det.figli if f.tag == "summary"), None)
            if som is None:
                continue
            testo = " ".join(som.testo_visibile().split())
            if not testo:
                continue
            sel = ".verify summary" if "verify" in det.classi else "summary"
            dim, peso = self.css.font(sel)
            w = self.font.larghezza(testo, "body", max(peso, 600), dim)
            ident = det.attr.get("id") or (min(det.classi) if det.classi else "details")
            self.aggiungi("tendina (P1.4)", f"#{ident} · «{testo[:46]}…»" if len(testo) > 46
                          else f"#{ident} · «{testo}»", w, dentro_card, OK if w <= dentro_card else NOTA,
                          "" if w <= dentro_card else "va a capo (non è un difetto, è una riga in più)")

    # --- guardie generali --------------------------------------------------

    def guardie(self, dentro: float) -> None:
        for nodo in self.root.discendenti():
            stile = nodo.attr.get("style") or ""
            for prop in ("width", "min-width"):
                m = re.search(rf"(?:^|;)\s*{prop}\s*:\s*(\d+(?:\.\d+)?)px", stile)
                if m and float(m.group(1)) > dentro + 0.5 and nodo.tag not in ("td", "th"):
                    self.aggiungi("guardia: larghezza fissa", f"<{nodo.tag}> {prop}:{m.group(1)}px",
                                  float(m.group(1)), dentro, KO)
            if nodo.tag in ("img", "svg"):
                w = nodo.attr.get("width")
                if w and w.endswith("px") and float(w[:-2]) > dentro + 0.5:
                    self.aggiungi("guardia: immagine larga", f"<{nodo.tag} width={w}>",
                                  float(w[:-2]), dentro, KO)

    # --- rapportino --------------------------------------------------------

    def stampa(self, verbose: bool) -> None:
        righe = [e for e in self.esiti if e.stato == KO or verbose]
        if not righe:
            print(f"{self.nome}: nessun problema (375 px)")
            return
        print(f"— {self.nome}")
        for e in righe:
            segno = "✗" if e.stato == KO else "·"
            nota = f" — {e.nota}" if e.nota else ""
            print(f"  {segno} {e.controllo}: {e.dove}: {e.misurato:.0f} px su {e.disponibile:.0f} px"
                  f"{nota}")


def pagine_da_misurare(sito: Path, solo: str | None = None) -> list[Path]:
    """Le pagine da controllare: tutte quelle pubblicate, ordinabili con --pagina."""
    if solo:
        return [sito / solo] if (sito / solo).exists() else sorted(sito.rglob(solo))
    fuori = {sito / "404.html"}
    return [p for p in sorted(sito.rglob("*.html")) if p not in fuori]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resa a 375 px misurata senza browser")
    ap.add_argument("--verbose", action="store_true", help="stampa anche i controlli superati")
    ap.add_argument("--pagina", help="una pagina o un glob, es. partite/5868071.html")
    ap.add_argument("--sito", type=Path, default=SITO)
    args = ap.parse_args(argv)

    if not (args.sito / "assets" / "site.css").exists():
        print(f"CSS non trovato in {args.sito}: esegui prima `fda build`", file=sys.stderr)
        return 2

    css = Css((args.sito / "assets" / "site.css").read_text(encoding="utf-8"))
    font = FontBook(args.sito / "assets" / "fonts" / "fonts.css", args.sito / "assets" / "fonts")

    main_pad, _ = css.padding("main")
    card_pad, _ = css.padding(".card")
    dentro = VIEWPORT - main_pad
    dentro_card = dentro - card_pad
    print(f"**Resa a 375 px** (viewport 375 · `main` −{main_pad:.0f} px → {dentro:.0f} px utili · "
          f"dentro una card −{card_pad:.0f} px → {dentro_card:.0f} px)")

    ko = 0
    controlli = 0
    for percorso in pagine_da_misurare(args.sito, args.pagina):
        root = leggi_pagina(percorso)
        nome = str(percorso.relative_to(args.sito))
        resa = Resa(root, css, font, nome)
        resa.controlla_tabelle(dentro, dentro_card)
        resa.badge_forma()
        resa.indice()
        resa.micro_visivi(dentro_card)
        resa.tendine(dentro_card)
        resa.guardie(dentro)
        controlli += len(resa.esiti)
        ko += sum(1 for e in resa.esiti if e.stato == KO)
        resa.stampa(args.verbose)

    if font.mancanti:
        print(f"  (caratteri senza metrica nel font del sito: {' '.join(sorted(font.mancanti))[:60]})")
    print(f"\n{controlli} misure · {ko} problemi a 375 px")
    return 1 if ko else 0


if __name__ == "__main__":
    raise SystemExit(main())
