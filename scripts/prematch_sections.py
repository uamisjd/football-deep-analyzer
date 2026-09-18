"""Censimento della scheda partita **pre-partita**: sezioni, peso, ridondanze.

Misura, sulle pagine generate in ``site/partite/*.html``, le tre domande della
direttiva «scheda delle partite che devono giocare» (2026-09-18):

1. **Elenco delle sezioni** — titoli h2/h3 di ogni scheda con stato *pre-partita*
   (le gare non ancora finite) e su quante schede compaiono.
2. **Peso di ogni sezione** — quota di testo **visibile senza aprire le tendine**
   (mediana sulle schede) e quota che sta dietro una tendina chiusa: dalla P1.1 di
   `docs/28` una parte del testo non occupa più il primo schermo, e un censimento che
   contasse solo il DOM non vedrebbe il guadagno.
3. **Ridondanze** — quante volte lo stesso dato ricompare altrove: i valori di
   stagione della card squadra (xG creati/concessi per gara, PPDA) contati in quanti
   *altri* riquadri compaiono — hero compreso, che è il posto da cui `docs/28` §2
   (P1.2) li ha tolti —, il nome di un indisponibile, e le frasi-spiegazione ripetute
   (sorgenti citate, «partite su 100», «stabilizzata»).

Il parser è in sola libreria standard (nessuna dipendenza non dichiarata) e legge
l'HTML generato: la stessa pagina che vede il lettore. Stampa solo riepiloghi
(conteggi e mediane), mai dati grezzi, come le altre sonde di ``scripts/``.

Uso: ``.venv/bin/python -m scripts.prematch_sections [site_dir]`` — richiede una
build già fatta (``fda build``); senza ``site/`` esce con messaggio azionabile.
"""

from __future__ import annotations

import argparse
import collections
import html as html_lib
import re
import statistics
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOID = {"br", "img", "input", "meta", "link", "hr", "source", "area", "base", "col", "embed",
        "param", "track", "wbr"}
FLOW = {"div", "section", "details"}
PHRASES = ("stabilizzata", "stima stabilizzata", "partite su 100", "Understat", "FotMob",
           "football-data.co.uk", "non media delle ultime 3")


class Node:
    """Nodo minimo: tag, attributi, figli (nodi) e testo (stringhe)."""

    __slots__ = ("attrs", "children", "tag")

    def __init__(self, tag: str, attrs: dict[str, str] | None = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[Node | str] = []

    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def text(self) -> str:
        parts: list[str] = []

        def walk(n: Node | str) -> None:
            if isinstance(n, str):
                parts.append(n)
            else:
                for c in n.children:
                    walk(c)

        walk(self)
        return re.sub(r"\s+", " ", html_lib.unescape(" ".join(parts))).strip()

    def find_all(self, tags: set[str] | None = None, cls: str | None = None) -> list[Node]:
        out: list[Node] = []
        for c in self.children:
            if isinstance(c, Node):
                if (tags is None or c.tag in tags) and (cls is None or cls in c.classes()):
                    out.append(c)
                out.extend(c.find_all(tags, cls))
        return out


class Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")


def parse(path: Path) -> Node:
    t = Tree()
    t.feed(path.read_text(encoding="utf-8"))
    return t.root


def leaf_cards(root: Node) -> list[tuple[str, int, int, Node]]:
    """Card-foglia: elemento di flusso con un h2 dentro, che non ne contiene altre.

    È la stessa definizione usata per il censimento: ogni blocco titolato una volta
    sola, così una griglia (``#squadre``, ``#club``) non viene contata due volte.

    Ogni card torna come ``(titolo, caratteri_nel_DOM, caratteri_visibili, nodo)``.
    """
    out: list[tuple[str, int, int, Node]] = []
    for el in root.find_all(FLOW):
        h2 = next((h for h in el.find_all({"h2"}) if h.text()), None)
        if h2 is None:
            continue
        if any(c is not el and next((h for h in c.find_all({"h2"}) if h.text()), None)
               for c in el.find_all(FLOW)):
            continue
        text = el.text()
        if len(text) < 80:
            continue
        out.append((h2.text(), len(text), len(visible_text(el)), el))
    return out


def visible_text(node: Node) -> str:
    """Testo che si legge **senza aprire le tendine**: dentro un ``<details>`` chiuso resta
    solo il ``<summary>`` (il titolo della tendina), il resto non è nel primo schermo."""
    parts: list[str] = []

    def walk(n: Node | str, dentro_chiuso: bool) -> None:
        if isinstance(n, str):
            if not dentro_chiuso:
                parts.append(n)
            return
        chiuso = dentro_chiuso
        if n.tag == "details" and "open" not in n.attrs:
            chiuso = True
            for c in n.children:                      # il summary resta visibile
                if isinstance(c, Node) and c.tag == "summary":
                    walk(c, False)
            return
        for c in n.children:
            walk(c, chiuso)

    walk(node, False)
    return re.sub(r"\s+", " ", html_lib.unescape(" ".join(parts))).strip()


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 1) if values else 0.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Censimento della scheda pre-partita.")
    ap.add_argument("site_dir", nargs="?", default=str(ROOT / "site"),
                    help="cartella del sito generato (default: site/)")
    args = ap.parse_args(argv)
    site = Path(args.site_dir)
    pages = sorted((site / "partite").glob("*.html"))
    if not pages:
        print(f"nessuna pagina in {site / 'partite'} — esegui prima `fda build`")
        return 1

    pre: list[Path] = []
    for p in pages:
        txt = p.read_text(encoding="utf-8")
        if 'id="sintesi"' in txt and "Analisi pre-partita" in txt:
            pre.append(p)
    print(f"schede partita: {len(pages)} · pre-partita: {len(pre)} "
          f"(post-partita: {len(pages) - len(pre)})")
    if not pre:
        return 1

    titles: collections.Counter[str] = collections.Counter()
    sizes: dict[str, list[int]] = collections.defaultdict(list)
    chiusi: dict[str, list[int]] = collections.defaultdict(list)
    totals: list[int] = []
    visibili: list[int] = []
    phrase_hits: dict[str, list[int]] = {p: [] for p in PHRASES}
    season_value_cards: list[int] = []
    absent_name_cards: list[int] = []
    signals: collections.Counter[str] = collections.Counter()

    for path in pre:
        root = parse(path)
        main = next((n for n in root.find_all({"main"})), root)
        cards = leaf_cards(main)
        total = sum(n for _, n, _v, _el in cards) or 1
        vis = sum(v for _, _n, v, _el in cards)
        totals.append(total)
        visibili.append(vis)
        for title, n, v, _el in cards:
            titles[title] += 1
            sizes[title].append(v / max(vis, 1) * 100)
            chiusi[title].append((n - v) / max(total, 1) * 100)
        text = main.text()
        for phrase in PHRASES:
            phrase_hits[phrase].append(text.count(phrase))
        # P1.2 (`docs/28` §2): il posto canonico del xG/gara e del PPDA di stagione è la card
        # della squadra. Si contano gli **altri** riquadri che ripetono quei valori — hero
        # compreso, che è il posto da cui l'intervento li ha tolti; così il prima e il dopo
        # si misurano con la stessa definizione.
        hero = next((n for n in main.find_all(FLOW, cls="hero-model")), None)
        blocks = [el for _, _, _v, el in cards] + ([hero] if hero is not None else [])
        for _, _, _v, el in cards:
            season = el.text()
            if "xG creati / gara" not in season:
                continue
            values = re.findall(r"xG creati / gara ([\d,]+)", season)
            values += re.findall(r"xG concessi / gara ([\d,]+)", season)
            values += re.findall(r"PPDA ([\d,]+)", season)
            for v in values:
                pat = re.compile(r"(?<![\d,])" + re.escape(v) + r"(?![\d])")
                others = [b for b in blocks if b is not el and pat.search(b.text())]
                season_value_cards.append(len(others))
        notizie = next((n for n in main.find_all(FLOW, cls=None) if n.attrs.get("id") == "notizie"),
                       None)
        if notizie is not None and not notizie.find_all(cls="news-list"):
            signals["Vita del club senza notizie pubblicabili"] += 1
        if "due fornitori diversi in questa gara" in text:
            signals["avviso: due fornitori xG diversi"] += 1
        if "Dati pressing (PPDA) incompleti" in text:
            signals["avviso: PPDA incompleto"] += 1
        if "Nessun indisponibile segnalato" in text:
            signals["nessun indisponibile in distinta"] += 1
        if "formazione ufficiale" in text:
            signals["formazione ufficiale"] += 1
        for _, _, _v, el in cards:
            if not re.search(r"Indisponibili \(\d+\)", el.text()):
                continue
            names = {cell.text() for row in el.find_all({"tr"}) for cell in row.find_all({"b"})}
            for name in filter(None, names):
                absent_name_cards.append(sum(1 for _, _, _v, c in cards if name in c.text()))

    med_dom, med_vis = int(statistics.median(totals)), int(statistics.median(visibili))
    print(f"testo per scheda: mediana {med_dom} caratteri nel DOM, di cui "
          f"{med_vis} visibili senza aprire le tendine (min {min(visibili)}, max {max(visibili)})")
    print("\n=== elenco delle sezioni (pre-partita) ===")
    print(f"{'titolo h2':56} {'schede':>7} {'% visibile':>10} {'% tendina':>9}  (visibile min–max)")
    structural = [(t, n) for t, n in titles.most_common() if n >= len(pre) * 0.5]
    per_team = [(t, n) for t, n in titles.most_common() if n < len(pre) * 0.5]
    for title, n in structural:
        v, h = sizes[title], chiusi[title]
        print(f"{title[:54]:56} {n:>5}/{len(pre):<2} {_median(v):>10} {_median(h):>9}  "
              f"({min(v):.1f}–{max(v):.1f})")
    if per_team:
        vals = [statistics.median(sizes[t]) for t, _ in per_team]
        print(f"{'card delle due squadre (titolo = nome squadra)':56} "
              f"{len(per_team):>3} tit. {_median(vals):>10}  "
              f"({min(vals):.1f}–{max(vals):.1f})")
    print("\n=== frasi ripetute per scheda (mediana · max) ===")
    for phrase in PHRASES:
        v = phrase_hits[phrase]
        print(f"{phrase[:34]:36} {_median(v):>6} · {max(v):>3}  "
              f"(schede con ≥1: {sum(1 for x in v if x)}/{len(pre)})")
    print("\n=== stesso dato in più card ===")
    if season_value_cards:
        dist = dict(sorted(collections.Counter(season_value_cards).items()))
        print(f"valore di stagione della card squadra (xG/gara, PPDA) ripetuto in: mediana "
              f"{_median(season_value_cards)} altri riquadri · distribuzione {dist}")
    if absent_name_cards:
        dist = dict(sorted(collections.Counter(absent_name_cards).items()))
        print(f"nome di un indisponibile: {len(absent_name_cards)} nomi · mediana "
              f"{_median(absent_name_cards)} card · max {max(absent_name_cards)} · distribuzione {dist}")
    print("\n=== altri segnali (schede su cui compaiono) ===")
    for label, n in signals.most_common():
        print(f"{label[:50]:52} {n:>5}/{len(pre)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
