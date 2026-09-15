"""Verifica del sito generato: collegamenti, residui, italiano, coerenza numerica.

Nasce dall'audit del 2026-09-12 (``docs/10_verifica_sito_2026-09-12.md``): ogni controllo è
una regola misurata sui dati, con i falsi positivi già esclusi (i separatori di migliaia
«67.598» non sono decimali col punto; «Wind» è un cognome, non il meteo).

Uso:
    python scripts/verify_site.py                      # sito in site/, dati in data/processed
    python scripts/verify_site.py --site /tmp/s --data /tmp/d
Esce con codice 1 se trova almeno un problema (usabile come passo di CI).
"""

from __future__ import annotations

import argparse
import ast
import re
from collections import Counter
from html import unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# ---- residui che non devono mai arrivare a schermo -----------------------------------------
BAD_TOKENS = re.compile(r"(?<![\w.])(nan|NaN|None|NaT|inf|-inf|numpy\.|Timestamp\()(?![\w.])")
# decimale col punto: esclusi i separatori di migliaia (1-3 cifre . esattamente 3 cifre)
DECIMAL_POINT = re.compile(r"(?<![\w/,\-:])\d{1,3}\.\d{1,2}(?![\w.])|\d{1,3}\.\d{4,}")
ENGLISH = re.compile(
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|"
    r"June|July|August|September|October|November|December|injury|suspension|RegularPlay|FastBreak|"
    r"FromCorner|SetPiece|ThrowInSetPiece|OwnGoal|Mostly Clear|Partly Cloudy|Overcast|Showers|"
    r"Light Rain|Heavy Rain|Thunder|Doubtful|Day to day|Out for season|Club Friendlies|"
    r"haven't|matches in a row|clean sheet)\b")
# concordanza: «1 rossi», «1 gare», «1 vittorie»…
# Non intercettare il finale «,1 gialli» di un decimale (es. 3,1 gialli/gara):
# si cerca un vero contatore intero all'inizio della parola.
AGREEMENT = re.compile(r"(?<![\d,])\b1 (rossi|gialli|rigori|gare|partite|vittorie|pareggi|tiri|giorni|precedenti)\b")
LOCAL_HREF = re.compile(r'href="([^"#]+\.html)(#[^"]*)?"')


class Text(HTMLParser):
    """Testo leggibile di una pagina (senza style/script/head/svg) + href locali."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Any]]) -> None:
        if tag in ("style", "script", "head", "svg"):
            self.skip += 1
        if tag in ("p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "table", "section", "br"):
            self.parts.append(" ")      # separa i blocchi: «…link</a>1 gare» non deve sembrare «x1 gare»
        for k, v in attrs:
            if k == "id" and v:
                self.ids.add(v)
            if tag == "a" and k == "href" and v:
                self.hrefs.append(v)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "head", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def check_pages(site: Path) -> tuple[list[str], int]:
    """Controlli di contenuto e collegamenti su tutte le pagine HTML. Ritorna (problemi, pagine)."""
    fails: list[str] = []
    pages = sorted(site.rglob("*.html"))
    for page in pages:
        rel = str(page.relative_to(site))
        parser = Text()
        parser.feed(page.read_text(encoding="utf-8"))
        text = re.sub(r"\s+", " ", "".join(parser.parts))

        for m in BAD_TOKENS.finditer(text):
            fails.append(f"{rel}: residuo {m.group(0)!r}")
        for m in ENGLISH.finditer(text):
            fails.append(f"{rel}: inglese {m.group(0)!r}")
        for m in DECIMAL_POINT.finditer(text):
            fails.append(f"{rel}: decimale col punto {m.group(0)!r}")
        for m in AGREEMENT.finditer(text):
            fails.append(f"{rel}: concordanza {m.group(0)!r}")

        for href in parser.hrefs:
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target, sep, fragment = href.partition("#")
            target_page = site / target.lstrip("/") if target.startswith("/") else page.parent / target
            if target and not target_page.exists():
                fails.append(f"{rel}: collegamento interno mancante {href}")
                continue
            if sep and fragment:
                if not target:
                    target_ids = parser.ids
                else:
                    target_parser = Text()
                    target_parser.feed(target_page.read_text(encoding="utf-8"))
                    target_ids = target_parser.ids
                if fragment not in target_ids:
                    fails.append(f"{rel}: ancora interna mancante {href}")
    return fails, len(pages)


# ---- calendario completo (vista «Prossime») ---------------------------------------------------
# Una riga per partita, compatta: le regole da rispettare sono le stesse delle schede, ma il
# lettore qui non ha contesto, quindi un arrotondamento sbagliato non sarebbe riconoscibile.
CAL_ROW = re.compile(
    r'<div class="cal-row([^"]*)" data-match-card data-league="([^"]+)" data-status="([^"]+)">(.*?)</div>',
    re.S)
CAL_PCT = re.compile(r'<span class="cal-p"[^>]*aria-label="1 (\d+)%, X (\d+)%, 2 (\d+)%"[^>]*>(.*?)</span>')
CAL_MONTH = re.compile(
    r'<details class="cal-month" id="mese-(\d{4})-(\d{2})"[^>]*>\s*<summary>([^<]+)'
    r'<span class="cal-count">([\d.]+) ([^<]+)</span></summary>(.*?)</details>', re.S)
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"]


def check_calendar(site: Path) -> tuple[list[str], int]:
    """[11] Calendario completo: righe coerenti, 1X2 che somma 100, mesi dichiarati correttamente."""
    fails: list[str] = []
    checks = 0
    righe_totali = 0
    for page in sorted(site.rglob("*.html")):
        rel = str(page.relative_to(site))
        h = page.read_text(encoding="utf-8", errors="replace")
        righe = list(CAL_ROW.finditer(h))
        mesi = list(CAL_MONTH.finditer(h))
        if not righe and not mesi:
            continue
        if rel != "prossime.html":
            fails.append(f"{rel}: calendario completo fuori dalla vista «Prossime» ({len(righe)} righe)")
        righe_totali += len(righe)

        for m in righe:
            classi, lega, stato, corpo = m.groups()
            checks += 1
            if "cal-fav-" not in classi and "senza previsione" not in corpo:
                fails.append(f"{rel}: riga di calendario senza esito preferito né «senza previsione»")
            if stato != "scheduled":
                fails.append(f"{rel}: riga di calendario con stato {stato!r} (atteso «scheduled»)")
            when = re.search(r'<time class="cal-when" datetime="(\d{4})-(\d{2})-(\d{2})">([^<]*)<b>(\d{2}:\d{2})</b>', corpo)
            if not when:
                fails.append(f"{rel}: riga di calendario senza data/ora leggibili")
            else:
                checks += 1
                anno, mese, giorno, testo, ora = when.groups()
                if not 1 <= int(mese) <= 12 or not 1 <= int(giorno) <= 31:
                    fails.append(f"{rel}: data di calendario impossibile {anno}-{mese}-{giorno}")
                if f" {int(giorno)} " not in f" {testo.strip()} ":
                    fails.append(f"{rel}: data {anno}-{mese}-{giorno} ma testo «{testo.strip()}»")
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", ora):
                    fails.append(f"{rel}: ora non valida {ora!r}")
            prob = CAL_PCT.search(corpo)
            if prob:
                checks += 1
                uno, x, due, visibile = (int(prob.group(1)), int(prob.group(2)),
                                         int(prob.group(3)), prob.group(4))
                if uno + x + due != 100:
                    fails.append(f"{rel}: 1X2 di calendario {uno}+{x}+{due} != 100")
                numeri = [int(v) for v in re.findall(r"\d+", re.sub(r"</?b>", "", visibile))]
                if numeri != [uno, x, due]:
                    fails.append(f"{rel}: 1X2 letto {numeri} != aria-label {[uno, x, due]}")
                grassetto = re.findall(r"<b>(\d+)</b>", visibile)
                if len(grassetto) != 1 or int(grassetto[0]) != max(uno, x, due):
                    fails.append(f"{rel}: preferito in grassetto {grassetto} su 1X2 {[uno, x, due]}")
                fav = re.search(r"cal-fav-([hda])", classi)
                atteso = ("h", "d", "a")[[uno, x, due].index(max(uno, x, due))]
                if not fav or fav.group(1) != atteso:
                    fails.append(f"{rel}: classe cal-fav-{fav.group(1) if fav else '?'} ma il preferito è {atteso}")
                gol = re.search(r'<span class="cal-gol"[^>]*>([^<]*)</span>', corpo)
                over = re.search(r'<span class="cal-o"[^>]*>([^<]*)</span>', corpo)
                if not gol or not re.fullmatch(r"\d+,\d", gol.group(1)):
                    fails.append(f"{rel}: gol attesi non in formato italiano {gol.group(1) if gol else None!r}")
                else:
                    checks += 1
                if not over or not re.fullmatch(r"\d{1,3}%", over.group(1)):
                    fails.append(f"{rel}: Over 2,5 non in percentuale {over.group(1) if over else None!r}")
                else:
                    checks += 1
            elif "senza previsione" not in corpo:
                fails.append(f"{rel}: riga di calendario senza probabilità e senza «senza previsione»")
            else:
                checks += 1

        # mesi: etichetta, ordine e conteggio dichiarato devono tornare con le righe stampate
        precedente: tuple[int, int] | None = None
        for m in mesi:
            checks += 1
            anno, mese, etichetta, conto, plurale, blocco = m.groups()
            anno, mese = int(anno), int(mese)
            if etichetta.strip() != f"{MESI_IT[mese - 1].capitalize()} {anno}":
                fails.append(f"{rel}: mese {anno}-{mese:02d} con etichetta «{etichetta.strip()}»")
            if precedente is not None and (anno, mese) <= precedente:
                fails.append(f"{rel}: mesi non in ordine ({precedente} → {(anno, mese)})")
            precedente = (anno, mese)
            n = len(CAL_ROW.findall(blocco))
            if int(conto.replace(".", "")) != n:
                fails.append(f"{rel}: {etichetta.strip()} dichiara {conto} partite ma ne stampa {n}")
            if plurale.strip() != ("partita" if n == 1 else "partite"):
                fails.append(f"{rel}: {etichetta.strip()} «{plurale.strip()}» con {n} righe")
        nav = set(re.findall(r'<a href="#mese-(\d{4}-\d{2})"', h))
        dettagli = {f"{m.group(1)}-{m.group(2)}" for m in mesi}
        if nav != dettagli:
            fails.append(f"{rel}: navigazione mesi {sorted(nav)} != sezioni {sorted(dettagli)}")
    print(f"[11] righe di calendario verificate: {righe_totali}")
    return fails, checks


#: barre 1X2 (scheda partita, passi della scomposizione, mini-barra delle liste).
#: L'header riusa ``class="bar"`` per il wordmark: i suoi segmenti non hanno ``style="width:…"``,
#: quindi non entrano nel controllo (nessuna esclusione esplicita da mantenere).
BAR_BLOCK = re.compile(r'<div class="bar"([^>]*)>(.*?)</div>', re.DOTALL)
BAR_SEG = re.compile(r'<span class="([hda])" style="width:(\d+(?:\.\d+)?)%"[^>]*>([^<]*)</span>')
PROB_LABELS = re.compile(r'<div class="prob-labels">(.*?)</div>', re.DOTALL)
LAB = re.compile(r'<span( class="is-fav")?>([1X2]) (\d+)%</span>')


def _num_it(s: str) -> float:
    """'61,0' → 61.0 (virgola decimale italiana)."""
    return float(s.replace(",", "."))


def check_bars(site: Path) -> tuple[list[str], int]:
    """[11a] Barre 1X2: larghezze, etichette e aria-label devono essere gli stessi tre numeri.

    Invariante di pubblicazione, non di calcolo: anche se il modello cambiasse, una barra che
    non chiude 100 è un difetto visibile (segmento mancante o strabordante) e un'etichetta che
    contraddice la larghezza è un numero non vero. Prima della correzione (docs/19 §3.3) il
    22% delle schede hero pubblicava 99% o 101% perché ogni probabilità era arrotondata da sola.
    """
    fails: list[str] = []
    checks = 0
    barre = 0
    for page in sorted(site.rglob("*.html")):
        rel = str(page.relative_to(site))
        h = page.read_text(encoding="utf-8", errors="replace")
        for attrs, corpo in BAR_BLOCK.findall(h):
            seg = BAR_SEG.findall(corpo)
            if len(seg) != 3:
                continue                      # wordmark dell'header o barra non 1X2
            checks += 1
            barre += 1
            if [c for c, _, _ in seg] != ["h", "d", "a"]:
                fails.append(f"{rel}: barra 1X2 con segmenti {[c for c, _, _ in seg]} (atteso h, d, a)")
            largh = [_num_it(w) for _, w, _ in seg]
            if abs(sum(largh) - 100.0) > 0.05:
                fails.append(f"{rel}: barra 1X2 larga {sum(largh):g}% ({largh})")
            for (_, w, testo), val in zip(seg, largh):
                if not testo.strip():
                    continue                  # mini-barra: le etichette stanno in .prob-labels
                m = re.search(r"(\d+(?:,\d+)?)\s*%", testo)
                if not m:
                    fails.append(f"{rel}: segmento della barra senza percentuale leggibile ({testo!r})")
                elif _num_it(m.group(1)) != val:
                    fails.append(f"{rel}: etichetta {m.group(1)}% ma larghezza {val:g}%")
                else:
                    checks += 1
            aria = re.search(r'aria-label="([^"]*)"', attrs)
            if aria:
                detti = [_num_it(v) for v in re.findall(r"(\d+(?:,\d+)?)\s?(?:per cento|%)", aria.group(1))]
                if len(detti) == 3:
                    checks += 1
                    if detti != largh:
                        fails.append(f"{rel}: aria-label {detti} != larghezze {largh}")
                else:
                    fails.append(f"{rel}: aria-label della barra con {len(detti)} percentuali (attese 3)")
            else:
                fails.append(f"{rel}: barra 1X2 senza aria-label (ruolo img)")
        for blocco in PROB_LABELS.findall(h):
            etichette = LAB.findall(blocco)
            if len(etichette) != 3:
                fails.append(f"{rel}: .prob-labels con {len(etichette)} esiti (attesi 3)")
                continue
            checks += 1
            valori = [int(v) for _, _, v in etichette]
            if sum(valori) != 100:
                fails.append(f"{rel}: etichette 1X2 {valori} non sommano 100")
            favoriti = [sim for sim, _, v in etichette if sim and int(v) == max(valori)]
            if [sim for sim, _, _ in etichette].count(" class=\"is-fav\"") != 1:
                fails.append(f"{rel}: .prob-labels con {blocco.count('is-fav')} favoriti evidenziati (atteso 1)")
            elif not favoriti:
                fails.append(f"{rel}: favorito evidenziato ma non è il massimo {valori}")
    print(f"[11a] barre 1X2 verificate: {barre}")
    return fails, checks


def check_numbers(site: Path, data: Path | None) -> tuple[list[str], int]:
    """Ricalcola i numeri pubblicati con le funzioni del progetto e li confronta."""
    import numpy as np
    import pandas as pd

    from fda.models.predict import rps as pb_rps
    from fda.site.advanced import dixon_coles_grid, grid_1x2, score_matrix
    from fda.store import Store

    st = Store(data) if data else Store()
    fails: list[str] = []
    checks = 0
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    preds = st.read("predictions")
    if preds.empty:
        return fails, checks
    preds = preds.sort_values("made_at").groupby("match_id").tail(1).set_index("match_id")
    mi = st.read("match_info")

    # 1) matrice dei punteggi: celle = score_matrix(λ, ρ) e celle+coda = 100%
    n_matrix = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Matrice dei punteggi" not in html:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: matrice senza previsione")
            continue
        r = preds.loc[mid]
        m = score_matrix(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        cells = re.findall(r'<td[^>]*title="(\d)-(\d) · (meno di 0,1|\d+,\d+)%[^"]*">(<1|\d+,\d)</td>', html)
        if len(cells) != 36:
            fails.append(f"{pg.name}: celle matrice {len(cells)} (attese 36)")
            continue
        n_matrix += 1
        for i, j, _title_p, cell_p in cells:
            checks += 1
            true_p = float(m["cells"][int(i)][int(j)]["p"]) * 100
            if cell_p == "<1":
                if true_p >= 0.05:
                    fails.append(f"{pg.name}: cella {i}-{j} mostra <1 ma vale {true_p:.2f}/100")
            else:
                if true_p < 0.05:
                    fails.append(f"{pg.name}: cella {i}-{j} mostra {cell_p} ma vale {true_p:.2f}/100 (<0,05)")
        worst, tot = 0.0, 0.0
        for i, j, _title_p, cell_p in cells:
            rendered = 0.0 if cell_p == "<1" else float(cell_p.replace(",", "."))
            worst = max(worst, abs(rendered - round(float(m["cells"][int(i)][int(j)]["p"]) * 100, 1)))
            tot += rendered
        tail_m = re.search(r"Almeno una delle due squadre segna 6\+ gol.*?: (\d+,\d) partite su 100", html)
        if not tail_m:
            fails.append(f"{pg.name}: etichetta della coda della matrice assente o ambigua")
        tail = float(tail_m.group(1).replace(",", ".")) if tail_m else 0.0
        if worst > 0.11:
            fails.append(f"{pg.name}: cella matrice diversa di {worst:.2f} pp")
        if not 99.0 <= tot + tail <= 100.6:
            fails.append(f"{pg.name}: matrice+coda = {tot + tail:.1f}%")
        # coerenza con le probabilità pubblicate (stessa τ del modello, vedi dc_grid)
        g = dixon_coles_grid(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        ph, pdw, _pa = grid_1x2(g)
        if abs(ph - float(r.p_home)) > 0.015 or abs(pdw - float(r.p_draw)) > 0.015:
            fails.append(f"{pg.name}: 1X2 griglia ({ph:.3f}/{pdw:.3f}) != previsione "
                         f"({r.p_home:.3f}/{r.p_draw:.3f})")
    print(f"[1] matrici punteggi verificate: {n_matrix}")

    # 2) probabilità in-play: ogni riga somma ~100 e l'ultima coincide col risultato
    n_wp = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Probabilità in-play" not in html:
            continue
        block = html.split("Probabilità in-play", 1)[1]
        rows = re.findall(r'<td class="mut small">(\d+)\'</td>\s*<td>([^<]*)</td>\s*'
                          r'<td class="r">(\d+)%</td>\s*<td class="r">(\d+)%</td>\s*<td class="r">(\d+)%</td>',
                          block)
        if not rows:
            fails.append(f"{pg.name}: tabella in-play senza righe")
            continue
        n_wp += 1
        checks += 1
        for minute, _score, a, b, c in rows:
            if abs(int(a) + int(b) + int(c) - 100) > 3:
                fails.append(f"{pg.name}: in-play {minute}' = {a}+{b}+{c}")
        sc = re.match(r"\s*(\d+)-(\d+)", rows[-1][1])
        hg, ag = (int(sc.group(1)), int(sc.group(2))) if sc else (0, 0)
        row = mi[mi.match_id == int(pg.stem)]
        if not row.empty and pd.notna(row.iloc[0]["home_goals"]):
            if (hg, ag) != (int(row.iloc[0]["home_goals"]), int(row.iloc[0]["away_goals"])):
                fails.append(f"{pg.name}: in-play finisce {hg}-{ag}, risultato "
                             f"{int(row.iloc[0]['home_goals'])}-{int(row.iloc[0]['away_goals'])}")
    print(f"[2] pagine con probabilità in-play verificate: {n_wp}")

    # 3) accuratezza: RPS ricalcolato in modo indipendente dalla pagina
    fx = st.read("fixtures")
    fin = fx[fx.status == "finished"][["match_id", "home_goals", "away_goals", "utc_kickoff"]]
    p = st.read("predictions").merge(fin, on="match_id", suffixes=("", "_fx"))
    p = p[p.made_at < p.utc_kickoff_fx].sort_values("made_at").groupby("match_id").tail(1)
    acc_path = site / "accuratezza.html"
    if not p.empty and acc_path.exists():
        outc = np.where(p.home_goals > p.away_goals, 0, np.where(p.home_goals == p.away_goals, 1, 2))
        mine = pb_rps(p[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist(), outc.tolist())
        mrow = re.search(r'Tutti</td><td class="r">(\d+)</td><td class="r">(\d+,\d+)</td>',
                         acc_path.read_text(encoding="utf-8"))
        if not mrow:
            fails.append("accuratezza.html: riga 'Tutti' non trovata")
        else:
            checks += 1
            n_page, rps_page = int(mrow.group(1)), float(mrow.group(2).replace(",", "."))
            if n_page != len(p):
                fails.append(f"accuratezza: {n_page} gare in pagina vs {len(p)} ricalcolate")
            if abs(rps_page - mine) > 0.002:
                fails.append(f"accuratezza: RPS pagina {rps_page} vs ricalcolato {mine:.4f}")
            print(f"[3] accuratezza: {len(p)} gare, RPS pagina {rps_page} = ricalcolato {mine:.4f}")

    # 7) accuratezza: intervalli di Wilson pubblicati, ricalcolati con la funzione del progetto
    if acc_path.exists():
        from fda.site.build import wilson_interval

        def _n(txt: str) -> float:
            return float(re.sub(r"<[^>]+>", "", txt).replace(".", "").replace(",", ".").rstrip("%"))

        righe = 0
        for row in re.findall(r"<tr><td>.*?</tr>", acc_path.read_text(encoding="utf-8"), re.S):
            mi = re.search(r'<td class="r mut">(\d+,\d+)\s*[–-]\s*(\d+,\d+)%</td>', row)
            if not mi:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            lo_p, hi_p = _n(mi.group(1)), _n(mi.group(2))
            kn = re.search(r"\((\d+)/(\d+)\)", row)
            if kn and len(cells) >= 7:                # riga di mercato: k/n esplicito, 9-10 celle
                k, n, prev = int(kn.group(1)), int(kn.group(2)), _n(cells[2])
            elif kn:                                  # riga di calibrazione: k/n esplicito, 5 celle
                k, n, prev = int(kn.group(1)), int(kn.group(2)), _n(cells[1])
            else:                                     # nessuna k/n pubblicata: k ≈ osservato × n
                n = int(_n(cells[1]))
                prev, obs = _n(cells[2]), _n(cells[3])
                k = int(round(obs * n / 100.0))
            lo, hi = wilson_interval(k, n)
            checks += 1
            righe += 1
            if abs(lo_p - lo * 100) > 0.06 or abs(hi_p - hi * 100) > 0.06:
                fails.append(f"accuratezza: intervallo pubblicato {lo_p}–{hi_p}% vs ricalcolato "
                             f"{lo * 100:.1f}–{hi * 100:.1f}% (k={k}, n={n})")
            fuori = "fuori intervallo" in row
            # il previsto in pagina è arrotondato a 0,1 punti: se cade a meno di mezzo decimo dal
            # bordo dell'intervallo, la pagina ha deciso con il valore non arrotondato e il
            # confronto sul testo stampato non può essere esatto (misurato: 2 falsi positivi su
            # 24 righe, una prevista al 31,59% con estremo 31,60% e una al 23,40% con 23,40%)
            ambiguo = min(abs(prev / 100 - lo), abs(prev / 100 - hi)) < 5e-4
            if not ambiguo and fuori != bool(not (lo <= prev / 100 <= hi)):
                fails.append(f"accuratezza: segnale {'fuori intervallo' if fuori else 'compatibile'} "
                             f"incoerente con previsto {prev}% e intervallo {lo * 100:.1f}–{hi * 100:.1f}%")
        if righe:
            print(f"[7] accuratezza: {righe} righe con intervallo di Wilson ricalcolate")

    # 8) backtest fuori campione: numerosità, RPS, bias dei gol e calibrazione ricalcolati.
    #    La pagina descrive il modello **calibrato** (come viene pubblicato), quindi il
    #    confronto applica la stessa calibrazione dello store alle righe grezze.
    bt_raw = st.read("backtest")
    if not bt_raw.empty and acc_path.exists():
        from fda.models.backtest import backtest_summary, calibrate_rows
        from fda.models.calibration import from_store

        cal = from_store(st)
        bt = calibrate_rows(bt_raw, cal)
        somm, somm_raw = backtest_summary(bt), backtest_summary(bt_raw)
        text = acc_path.read_text(encoding="utf-8")
        i = text.find("Backtest storico fuori campione")
        if i < 0:
            fails.append("accuratezza.html: tabella `backtest` presente ma nessuna card pubblicata")
        else:
            card = text[i:]
            m_n = re.search(r"su <b>(\d+)</b> partite", card)
            m_r = re.search(r"RPS <b>(\d+,\d+)</b>", card)
            if not m_n or not m_r:
                fails.append("accuratezza.html: card backtest senza numerosità o RPS")
            else:
                checks += 1
                mine = pb_rps(bt[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist(),
                              bt["outcome"].to_numpy(int).tolist())
                rps_bt = float(m_r.group(1).replace(",", "."))
                if int(m_n.group(1)) != len(bt):
                    fails.append(f"backtest: {m_n.group(1)} gare in pagina vs {len(bt)} in tabella")
                if abs(rps_bt - mine) > 0.002:
                    fails.append(f"backtest: RPS pagina {rps_bt} vs ricalcolato {mine:.4f}")
                print(f"[8] backtest: {len(bt)} gare fuori campione, RPS pagina {rps_bt} = ricalcolato {mine:.4f}")

            def _num(pattern: str, what: str) -> float | None:
                m = re.search(pattern, card, re.S)
                if not m:
                    fails.append(f"accuratezza.html: {what} non pubblicato nella card backtest")
                    return None
                return float(m.group(1).replace(",", "."))

            # bias dei gol e pareggio: i due numeri che la calibrazione deve tenere a posto
            got = _num(r"Gol attesi <b>(-?\d+,\d+)</b>", "gol attesi medi")
            if got is not None:
                checks += 1
                if abs(got - somm["lambda_media"]) > 0.002:
                    fails.append(f"backtest: gol attesi {got} vs ricalcolati {somm['lambda_media']:.3f}")
            got = _num(r"pareggio previsto <b>(\d+,\d+)%</b>", "pareggio previsto")
            if got is not None:
                checks += 1
                if abs(got - somm["pareggio_previsto"] * 100) > 0.06:
                    fails.append(f"backtest: pareggio previsto {got}% vs {somm['pareggio_previsto'] * 100:.1f}%")
            if not cal.is_identity:
                got = _num(r"λ × (\d+,\d+)", "moltiplicatore della calibrazione")
                if got is not None:
                    checks += 1
                    if abs(got - cal.lambda_scale) > 0.0015:
                        fails.append(f"backtest: calibrazione pubblicata λ×{got} vs salvata λ×{cal.lambda_scale:.3f}")
                if "versione <code>" not in card:
                    fails.append("backtest: versione della calibrazione non pubblicata")
                # il confronto "senza calibrazione" deve coincidere con la tabella grezza
                got = _num(r"Senza calibrazione lo stesso campione darebbe RPS (\d+,\d+)", "RPS grezza")
                if got is not None:
                    checks += 1
                    if abs(got - somm_raw["rps"]) > 0.002:
                        fails.append(f"backtest: RPS grezza {got} vs ricalcolata {somm_raw['rps']:.4f}")
                print(f"[8b] backtest calibrato: λ×{cal.lambda_scale:.3f} ρ{cal.rho_shift:+.2f} "
                      f"({cal.version}) · bias gol {somm_raw['bias_lambda']:+.3f} → {somm['bias_lambda']:+.3f} "
                      f"· pareggio {somm_raw['pareggio_previsto'] * 100:.1f}% → {somm['pareggio_previsto'] * 100:.1f}%"
                      f" (osservato {somm['pareggio_osservato'] * 100:.1f}%)")

    # 4) proiezioni di stagione: le probabilità di ogni lega sommano come devono
    sim = st.read("season_sim")
    if not sim.empty:
        for lg, g in sim.groupby("league_key"):
            checks += 1
            if abs(g.p_title.sum() - 1) > 0.01:
                fails.append(f"season_sim {lg}: somma P(titolo) = {g.p_title.sum():.3f}")
            if abs(g.p_top4.sum() - min(4, len(g))) > 0.02:
                fails.append(f"season_sim {lg}: somma P(top4) = {g.p_top4.sum():.3f}")
            if abs(g.p_rel.sum() - 3) > 0.02:
                fails.append(f"season_sim {lg}: somma P(retrocessione) = {g.p_rel.sum():.3f}")
        print(f"[4] leghe simulate: {sim.league_key.nunique()} · righe {len(sim)}")

    # 5) schede «oggi»: ruolo dei giocatori, conteggio indisponibili, archivio dei precedenti
    lineup, fixtures, h2h = st.read("lineup"), st.read("fixtures"), st.read("h2h")
    # codifica FotMob indipendente dal codice del sito: usualPosition parte da 0 (616 formazioni)
    role_names = {0: "portiere", 1: "difensore", 2: "centrocampista", 3: "attaccante"}
    hist: dict[int, int] = {}
    n_role = n_abs = n_h2h = 0
    if not lineup.empty and lineup.usual_position_id.notna().any():
        h = lineup[lineup.usual_position_id.notna()]
        hist = {int(k): int(v) for k, v in
                h.groupby("player_id").usual_position_id.agg(lambda x: x.astype(int).mode().iloc[0]).items()}
    hist_name: dict[int, str] = {}
    if not lineup.empty:
        hist_name = {int(k): str(v) for k, v in
                     lineup.dropna(subset=["player_name"]).drop_duplicates("player_id")
                     .set_index("player_id").player_name.items()}
    role_re = re.compile(r'giocatori/(\d+)\.html">([^<]+)</a>\s*<span class="mut small">'
                         r'(portiere|difensore|centrocampista|attaccante)</span>')
    abs_re = re.compile(r"Indisponibili \((\d+)\)")
    prev_re = re.compile(r"<th>Precedenti \((\d+)\)</th>")
    inf_re = re.compile(r'partite/(\d+)\.html(?:(?!partite/).)*?Infermeria: ([^<]*?) (\d+) assenti'
                        r' · ([^<]*?) (\d+) assenti', re.S)
    fx_by_id = {} if fixtures.empty else fixtures.set_index("match_id")
    un_count: dict[tuple[int, int], int] = {}
    if not lineup.empty:
        un = lineup[lineup.role == "unavailable"]
        un_count = {(int(a), int(b)): int(c) for (a, b), c in un.groupby(["match_id", "team_id"]).size().items()}
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        mid = int(pg.stem)
        for pid, _name, shown in role_re.findall(html):
            want = hist.get(int(pid))
            if want is None:
                continue                       # mai schierato: la pagina non stampa il ruolo
            checks += 1
            n_role += 1
            if shown != role_names[want]:
                fails.append(f"{pg.name}: ruolo {shown} per {_name}, atteso {role_names[want]}")
        if mid not in fx_by_id.index:
            continue
        row = fx_by_id.loc[mid]
        want_abs = sorted(x for x in (un_count.get((mid, int(row.home_id)), 0),
                                      un_count.get((mid, int(row.away_id)), 0)) if x)
        shown_abs = sorted(int(x) for x in abs_re.findall(html))
        if shown_abs:
            checks += 1
            n_abs += 1
            if shown_abs != want_abs:
                fails.append(f"{pg.name}: indisponibili {shown_abs} vs {want_abs} dalla distinta")
        m = prev_re.search(html)
        if m and not h2h.empty:
            kick = pd.to_datetime(row.utc_kickoff, utc=True)
            ids = (int(row.home_id), int(row.away_id))
            hh = h2h[h2h.match_id == mid].dropna(subset=["utc", "home_goals", "away_goals"])
            hh = hh[pd.to_datetime(hh.utc, utc=True) < kick].sort_values("utc",
                                                                        ascending=False).head(60)
            hh = hh[hh.home_id.isin(ids) & hh.away_id.isin(ids)]
            checks += 1
            n_h2h += 1
            if int(m.group(1)) != len(hh):
                fails.append(f"{pg.name}: {m.group(1)} precedenti in pagina vs {len(hh)} in archivio")
    for lg_page in ("index.html", "prossime.html"):
        path = site / lg_page
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        for mid, n1, c1, n2, c2 in inf_re.findall(html):
            if int(mid) not in fx_by_id.index:
                continue
            row = fx_by_id.loc[int(mid)]
            checks += 1
            n1, n2 = html_unescape(n1), html_unescape(n2)   # M'gladbach → M&#39;gladbach in HTML
            if (n1.strip(), int(c1)) != (str(row.home_name).strip(),
                                         un_count.get((int(mid), int(row.home_id)), 0)) or \
               (n2.strip(), int(c2)) != (str(row.away_name).strip(),
                                         un_count.get((int(mid), int(row.away_id)), 0)):
                fails.append(f"{lg_page}: infermeria {n1} {c1} / {n2} {c2} != distinta")
    print(f"[5] schede oggi: {n_role} ruoli, {n_abs} infermerie, {n_h2h} archivi precedenti")

    # 6) post-partita: assist della cronaca e split primo/secondo tempo contro le tabelle
    events, team_stats = st.read("events"), st.read("team_stats")
    n_assist = n_half = 0
    if not events.empty:
        goals = events[events.type == "Goal"]
        # nome dalla distinta DELLA STESSA partita: lo stesso player_id ha grafie diverse
        # fra le giornate (Uriel/Uriël van Aalst, Josko/Joško Gvardiol) e il sito usa quella
        # della partita, quindi il confronto va fatto sulla stessa base
        same_match: dict[tuple[int, int], str] = {}
        if not lineup.empty:
            same_match = {(int(a), int(b)): str(c) for a, b, c in
                          lineup.dropna(subset=["player_id", "player_name"])
                          [["match_id", "player_id", "player_name"]].itertuples(index=False)}
        names_by_match: dict[int, set[tuple[str, str]]] = {}
        for r in goals.itertuples(index=False):
            aid = getattr(r, "assist_player_id", None)
            if aid is None or pd.isna(aid):
                continue
            nm = same_match.get((int(r.match_id), int(aid))) or hist_name.get(int(aid))
            if nm:
                names_by_match.setdefault(int(r.match_id), set()).add((str(r.player_name), str(nm)))
        assist_re = re.compile(r"\u26bd <b>([^<]+)</b>.*?assist di ([^<]+)</span>")
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Cronaca essenziale" not in html:
                continue
            pairs = names_by_match.get(int(pg.stem), set())
            for scorer, helper in assist_re.findall(html):
                checks += 1
                n_assist += 1
                if (html_unescape(scorer), html_unescape(helper)) not in pairs:
                    fails.append(f"{pg.name}: assist \u00ab{helper}\u00bb a {scorer} non negli eventi")
    if not team_stats.empty:
        # tra le celle può esserci un a capo (il template va a capo dentro la riga)
        half_re = re.compile(r'<td class="c mut small">xG</td>\s*<td class="r">([^<]*)</td>\s*'
                             r'<td>([^<]*)</td>\s*<td class="r">([^<]*)</td>\s*<td>([^<]*)</td>')
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Primo e secondo tempo" not in html or int(pg.stem) not in fx_by_id.index:
                continue
            m = half_re.search(html)
            if not m:
                fails.append(f"{pg.name}: tabella 1T/2T senza riga xG")
                continue
            row = fx_by_id.loc[int(pg.stem)]
            want = []
            for period in ("FirstHalf", "SecondHalf"):
                ts = team_stats[(team_stats.match_id == int(pg.stem)) & (team_stats.period == period)
                                & (team_stats.key == "expected_goals")]
                for tid in (int(row.home_id), int(row.away_id)):
                    cell = ts[ts.team_id == tid]
                    want.append("" if cell.empty else str(cell.iloc[0].text).replace(".", ","))
            got = [html_unescape(x) for x in m.groups()]
            checks += 1
            n_half += 1
            if got != want:
                fails.append(f"{pg.name}: xG 1T/2T {got} vs {want} da team_stats")
    print(f"[6] post-partita: {n_assist} assist, {n_half} split 1T/2T")

    # 9) distribuzione dei gol totali + dotplot quantile: ricalcolate dalla λ/ρ salvate
    from fda.site.advanced import goals_view, probability_steps
    from fda.site.fmt import pct_triple

    n_goals = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="gol-totali"' not in html:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: distribuzione gol senza previsione")
            continue
        r = preds.loc[mid]
        gv = goals_view(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        barre = re.findall(r'<div class="gb([^"]*)"><span class="v">(\d+)</span>'
                           r'<span class="fill" style="height:([\d.]+)%"></span>'
                           r'<span class="x">([^<]+)</span></div>', html)
        checks += 1
        n_goals += 1
        if len(barre) != len(gv["bars"]):
            fails.append(f"{pg.name}: barre gol {len(barre)} (attese {len(gv['bars'])})")
            continue
        somma = 0
        for (_cls, v_txt, h_txt, x_txt), b in zip(barre, gv["bars"]):
            somma += int(v_txt)
            checks += 1
            if int(v_txt) != b["per100"]:
                fails.append(f"{pg.name}: barra {x_txt} gol = {v_txt} su 100, ricalcolato {b['per100']}")
            if x_txt != b["label"]:
                fails.append(f"{pg.name}: etichetta barra {x_txt} != {b['label']}")
            # [11b] altezza: entro il contenitore e proporzionale alla probabilità ricalcolata.
            # La scala deve includere la barra della coda, altrimenti «7+» straborda (183%).
            altezza = float(h_txt)
            if altezza > 100.0:
                fails.append(f"{pg.name}: barra {x_txt} gol alta {altezza:g}% — esce dal contenitore")
            elif altezza != round(b["h"] * 100):
                fails.append(f"{pg.name}: barra {x_txt} gol alta {altezza:g}%, ricalcolato {round(b['h'] * 100)}%")
        if somma != 100:
            fails.append(f"{pg.name}: le barre dei gol sommano {somma} su 100")
        if max(b["h"] for b in gv["bars"]) != 1.0:
            fails.append(f"{pg.name}: nessuna barra dei gol occupa il 100% della scala "
                         f"(massimo {max(b['h'] for b in gv['bars']):g})")
        # didascalia: moda, mediana, intervallo 10°-90° con la sua copertura reale, e la coda
        cap = re.search(r"il totale più frequente è\s+<b>(\d+)\s+gol</b>\s*\((\d+) su 100\)", html)
        if not cap or int(cap.group(1)) != gv["moda"] or int(cap.group(2)) != gv["bars"][gv["moda"]]["per100"]:
            fails.append(f"{pg.name}: moda dei gol in didascalia != ricalcolata ({gv['moda']})")
        med = re.search(r"la mediana è\s+(\d+)\s+e fra 10° e 90° percentile il totale resta\s+fra\s+(\d+)\s+e\s+"
                        r"(\d+\+?)\s+gol\s+—\s+cioè nel\s+<b>(\d+,\d)%</b>", html)
        attesi = (gv["mediana"], gv["q10"], gv["q90_label"], gv["copertura"])
        if not med:
            fails.append(f"{pg.name}: didascalia dei gol senza intervallo 10°-90° percentile")
        else:
            checks += 1
            letti = (int(med.group(1)), int(med.group(2)), med.group(3), float(med.group(4).replace(",", ".")))
            if letti != attesi:
                fails.append(f"{pg.name}: mediana/intervallo/copertura in didascalia {letti} != ricalcolati {attesi}")
            if not 80.0 < letti[3] <= 100.0:
                fails.append(f"{pg.name}: copertura {letti[3]}% fuori intervalo per un intervallo 10°-90° (attesa > 80)")
        # \s+ e non uno spazio secco: in HTML il whitespace è collassato, quindi un verificatore
        # che dipende da come va a capo il template segnala un difetto dove non c'è (e ha appena
        # fatto esattamente questo, su 160 pagine, quando la didascalia è stata riformattata)
        coda = re.search(rf"Totale\s+{re.escape(gv['coda_label'])}\s+gol:\s*(\d+,\d)%", html)
        if not coda or abs(float(coda.group(1).replace(",", ".")) - gv["p_coda"] * 100) > 0.06:
            fails.append(f"{pg.name}: coda dei gol in didascalia != ricalcolata ({gv['p_coda']:.4f})")
        # dotplot: i punti sono esattamente n_dots e stanno nelle colonne giuste
        # la cattura si ferma alla chiusura del contenitore (a capo + </div>), non al primo
        # </div></div>: altrimenti l'ultima colonna resta fuori e il confronto salta proprio
        # quella. Difetto rimasto nascosto finché la coda era sempre vuota (0 punti): con la
        # calibrazione a momenti alcune partite hanno punti anche nella colonna «7+».
        dp = re.search(r'<div class="goalgrid dotplot"[^>]*>(.*?)\n\s*</div>', html, re.S)
        if not dp:
            fails.append(f"{pg.name}: dotplot dei gol non trovato")
        else:
            colonne = re.findall(r'<div class="dp"><div class="stack">((?:<i></i>)*)</div>'
                                 r'<span class="x">([^<]+)</span>', dp.group(1))
            if len(colonne) != len(gv["columns"]):
                fails.append(f"{pg.name}: colonne dotplot {len(colonne)} (attese {len(gv['columns'])})")
            else:
                for (dots, label), col in zip(colonne, gv["columns"]):
                    if dots.count("<i>") != col["n"] or label != col["label"]:
                        fails.append(f"{pg.name}: colonna dotplot {label} = {dots.count('<i>')} punti, "
                                     f"attesi {col['n']} su {col['label']}")
            n_punti = sum(dots.count("<i>") for dots, _ in colonne)
            if n_punti != gv["n_dots"]:
                fails.append(f"{pg.name}: punti dotplot {n_punti} (attesi {gv['n_dots']})")
    print(f"[9] distribuzioni dei gol totali verificate: {n_goals}")

    # 10) scomposizione della probabilità: i passi pubblicati sono quelli salvati nella riga
    n_steps = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="scomposizione"' not in html:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: scomposizione senza previsione")
            continue
        r = preds.loc[mid]
        steps = probability_steps(r.to_dict())
        blocco = html.split('id="scomposizione"', 1)[1].split("</ol>", 1)[0]
        resi = re.findall(r'<span class="h" style="width:[^"]*">1 · (\d+,\d)%</span>'
                          r'<span class="d" style="width:[^"]*">X · (\d+,\d)%</span>'
                          r'<span class="a" style="width:[^"]*">2 · (\d+,\d)%</span>', blocco)
        labels = [(n, html_unescape(lab)) for n, lab in
                  re.findall(r"<strong>(\d+) · ([^<]+)</strong>", blocco)]
        checks += 1
        n_steps += 1
        if len(resi) != len(steps) or len(labels) != len(steps):
            fails.append(f"{pg.name}: passi pubblicati {len(resi)}/{len(labels)}, attesi {len(steps)}")
            continue
        # `passo`, non `st`: il nome `st` è lo Store aperto in testa alla funzione e un ciclo
        # che lo ombreggia lo fa diventare un dict, facendo esplodere `st.close()` in fondo
        for (h, x, a), (_n, lab), passo in zip(resi, labels, steps):
            if lab != passo["label"]:
                fails.append(f"{pg.name}: passo «{lab}» != «{passo['label']}»")
            # il confronto è con il vettore **pubblicato** (resto massimo a un decimale), non con
            # l'arrotondamento indipendente dei tre valori grezzi: era la stessa regola sbagliata
            # corretta nelle barre (docs/19 §3.3) e tollerava 0,06 pp di scarto. Qui lo scarto
            # ammesso è zero, perché la pagina e il verificatore chiamano la stessa funzione.
            attesi = pct_triple((passo["p_home"], passo["p_draw"], passo["p_away"]), 1)
            for shown, key, atteso in ((h, "p_home", attesi[0]), (x, "p_draw", attesi[1]),
                                       (a, "p_away", attesi[2])):
                if abs(float(shown.replace(",", ".")) - atteso) > 1e-9:
                    fails.append(f"{pg.name}: {passo['label']} {key} = {shown}% vs {atteso:.1f}% "
                                 f"(vettore pubblicato {attesi})")
        # la catena deve chiudersi sull'1X2 pubblicato in cima alla scheda
        for key in ("p_home", "p_draw", "p_away"):
            if abs(steps[-1][key] - float(r[key])) > 1e-6:
                fails.append(f"{pg.name}: ultimo passo {key} {steps[-1][key]:.4f} != pubblicato {r[key]:.4f}")
        # Δ esatto fra passi adiacenti: deve essere la differenza dei numeri stampati nel
        # riassunto (stesso esito preferito), non dei valori grezzi — il lettore rifà i conti
        delte = re.findall(r'<span class="delta">Δ (-?[+0-9,-]+) pp</span>', blocco)
        if len(delte) != len(steps) - 1:
            fails.append(f"{pg.name}: Δ di catena {len(delte)} per {len(steps)} passi")
        else:
            for i, dtxt in enumerate(delte):
                letto = float(dtxt.replace(",", "."))
                tops = [max(float(v.replace(",", ".")) for v in resi[k]) for k in (i, i + 1)]
                if abs(letto - round(tops[1] - tops[0], 1)) > 1e-9:
                    fails.append(f"{pg.name}: Δ del passo {i + 2} = {dtxt} pp, sono {tops[0]}→{tops[1]}")
    print(f"[10] scomposizioni della probabilità verificate: {n_steps}")

    # 11) titolo della scheda (P2 del modello): il margine pubblicato è la differenza dei due
    #     interi stampati vicini («+25 punti» tra 51% e 26%), e primo/secondo sono davvero
    #     i due esiti più probabili della triade; i λ sono «+», non un trattino
    n_margini = 0
    hero_re = re.compile(r'<strong>([^<]*)<em>(\d+)%</em>.*?'
                         r'\+(\d+(?:,\d+)?) punti sul secondo — (.*?) (\d+)%'
                         r' · 1 (\d+)% · X (\d+)% · 2 (\d+)%', re.S)
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        m = hero_re.search(html)
        if not m:
            continue
        top_v, margine, second_v = int(m.group(2)), float(m.group(3).replace(",", ".")), int(m.group(5))
        pcts = sorted((int(m.group(6)), int(m.group(7)), int(m.group(8))), reverse=True)
        checks += 1
        n_margini += 1
        if (top_v - second_v) != int(margine):
            fails.append(f"{pg.name}: margine +{margine:g} punti con {top_v}% e {second_v}% stampati")
        if (top_v, second_v) != (pcts[0], pcts[1]):
            fails.append(f"{pg.name}: primo/secondo {top_v}/{second_v} non sono i due esiti più alti {pcts}")
        if re.search(r"\d,\d+–\d,\d+</b><span>gol attesi", html) or \
                re.search(r"gol attesi \d+[,.]\d+–\d+[,.]\d+", html):
            fails.append(f"{pg.name}: gol attesi separati da trattino (lettura di un intervallo)")
        if not re.search(r"<b>\d+,\d+ \+ \d+,\d+</b><span>gol attesi · <b>\d+,\d+ totali</b>", html):
            fails.append(f"{pg.name}: gol attesi senza il totale esplicito")
        if " totali) · Over" not in html:
            fails.append(f"{pg.name}: descrizione SEO senza il totale dei gol attesi")
    print(f"[11] riassunti del modello verificati: {n_margini}")

    # 12) risultati esatti: la copertura dei sei punteggi è pubblicata e combacia con la
    #     previsione salvata; la gerarchia dei titoli dentro «Verifica approfondita» è h3
    n_cov = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        cm = re.search(r"Questi (\d+) punteggi coprono (\d+,\d+) partite su 100", html)
        if not cm:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: copertura senza previsione")
            continue
        block = html.split("Risultati esatti più probabili", 1)[1][:2000]
        celle = re.findall(r"<tr><td>\d+-\d+</td><td class=\"r\">(\d+,\d+)%</td></tr>", block)
        somma = sum(float(x.replace(",", ".")) for x in celle)
        letta = float(cm.group(2).replace(",", "."))
        checks += 1
        n_cov += 1
        if abs(somma - letta) > 0.35:
            fails.append(f"{pg.name}: copertura {letta}/100 ma le sei percentuali sommano {somma:.1f}")
        r = preds.loc[mid]
        try:
            raw = ast.literal_eval(r.top_scores) if isinstance(r.top_scores, str) else {}
        except (ValueError, SyntaxError):
            raw = {}
        if raw and abs(sum(raw.values()) * 100 - letta) > 0.06:
            fails.append(f"{pg.name}: copertura {letta}/100 vs {sum(raw.values()) * 100:.1f} dai dati")
        for titolo in ("Matrice dei punteggi", "Quanti gol, in pratica"):
            if f"<h2>{titolo}</h2>" in html:
                fails.append(f"{pg.name}: «{titolo}» è di secondo livello dentro Verifica approfondita")
    print(f"[12] coperture dei risultati esatti verificate: {n_cov}")

    # 15) fascia storica del pronostico: frequenze ricalcolate dalla tabella backtest, stessa
    #     fascia «questa» della scheda, numerità e intervallo di Wilson esatti a 0,1
    bt = st.read("backtest")
    n_fasc = 0
    if not bt.empty and "outcome" in bt.columns:
        from fda.site.analysis import MatchAnalysis
        from fda.site.build import wilson_interval

        pv_ = bt[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
        fav_ = pv_.max(axis=1)
        hit_ = pv_.argmax(axis=1) == bt["outcome"].to_numpy()
        tab_bt = []
        for lo_b, hi_b, label_b in MatchAnalysis.FAVORITE_BANDS:
            mm = (fav_ >= lo_b) & (fav_ < hi_b)
            nb = int(mm.sum())
            if nb < 30:
                continue
            kb = int(hit_[mm].sum())
            wl_b, wh_b = wilson_interval(kb, nb)
            tab_bt.append({"label": label_b, "lo": lo_b, "hi": hi_b, "n": nb,
                           "obs": kb / nb, "wl": wl_b, "wh": wh_b, "pm": float(fav_[mm].mean())})
        row_re = re.compile(
            r'<tr[^>]*>\s*<td>(fino al 40%|fra 40% e 50%|fra 50% e 60%|fra 60% e 75%|oltre il 75%)'
            r'(?: (<span class="tag"[^>]*>questa</span>))?</td>'
            r'\s*<td class="r">(\d+(?:\.\d+)?)</td>'
            r'\s*<td class="r">(\d+,\d+)%</td>'
            r'\s*<td class="r"><b>(\d+,\d+)%</b></td>'
            r'\s*<td class="r mut small">(\d+,\d+)–(\d+,\d+)%</td></tr>')
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if 'id="fascia-storica"' not in html:
                continue
            mid = int(pg.stem)
            if mid not in preds.index:
                fails.append(f"{pg.name}: fascia storica senza previsione")
                continue
            r = preds.loc[mid]
            here = float(max(r.p_home, r.p_draw, r.p_away))
            block = html.split('id="fascia-storica"', 1)[1][:5000]
            got = row_re.findall(block)
            if len(got) != len(tab_bt):
                fails.append(f"{pg.name}: righe fascia storica {len(got)} (attese {len(tab_bt)})")
                continue
            n_fasc += 1
            fav_lbl = re.search(r"fascia di QUESTA partita \(favorito (\d+,\d+)%\)", block)
            checks += 1
            if not fav_lbl or abs(float(fav_lbl.group(1).replace(",", ".")) - here * 100) > 0.06:
                fails.append(f"{pg.name}: favorito dichiarato {fav_lbl.group(1) if fav_lbl else '?'}% != {here * 100:.1f}%")
            for (lab, span, n_t, pm_t, obs_t, lo_t, hi_t), b in zip(got, tab_bt):
                checks += 1
                if lab != b["label"]:
                    fails.append(f"{pg.name}: fascia «{lab}» != «{b['label']}»")
                    continue
                if int(n_t.replace(".", "")) != b["n"]:
                    fails.append(f"{pg.name}: {lab} n={n_t} vs backtest {b['n']}")
                for txt, val, cosa in ((pm_t, b["pm"] * 100, "media prevista"),
                                       (obs_t, b["obs"] * 100, "frequenza osservata"),
                                       (lo_t, b["wl"] * 100, "IC inferiore"),
                                       (hi_t, b["wh"] * 100, "IC superiore")):
                    if abs(float(txt.replace(",", ".")) - val) > 0.06:
                        fails.append(f"{pg.name}: {lab} {cosa} {txt}% vs ricalcolata {val:.1f}%")
                # la marcatura «questa» deve stare sulla fascia del favorito di QUESTA scheda
                cur_page = bool(span)
                cur_data = bool(b["lo"] <= here < b["hi"])
                if cur_page != cur_data:
                    fails.append(f"{pg.name}: marcatura «questa» su {lab} ma il favorito {here:.3f} sta in un'altra fascia")
        print(f"[15] fasce storiche del pronostico verificate: {n_fasc}")

    # 16) percentile dei gol attesi nel campionato: ricalcolato da predictions.parquet pagina
    #     per pagina — il lettore legge una posizione che il conteggio sulle stesse λ conferma
    if not preds.empty and "league_key" in preds.columns:
        from fda.config import leagues as _leagues

        _lg_names = {x.key: x.name for x in _leagues()}
        pr_ = preds.reset_index() if "match_id" not in preds.columns else preds
        p_latest = pr_.sort_values("made_at").groupby("match_id").tail(1).copy()
        p_latest["lam"] = p_latest.lambda_home.astype(float) + p_latest.lambda_away.astype(float)
        n_pos = 0
        pos_re = re.compile(
            r'I (\d+,\d+) gol attesi totali in testa alla scheda vanno letti sulla scala del campionato:\s*'
            r'sono <b>più alti del (\d+)% delle (\d+) partite di ([^<]+) fin qui previste dal nostro modello</b>\s*'
            r'\(media di lega (\d+,\d+), mediana (\d+,\d+)\)')
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if 'id="posizione-lega"' not in html:
                continue
            mid = int(pg.stem)
            row = p_latest[p_latest.match_id == mid]
            m = pos_re.search(html.split('id="posizione-lega"', 1)[1][:2800])
            if row.empty or m is None:
                fails.append(f"{pg.name}: posizione-lega senza previsione o con testo atteso assente")
                continue
            lam_here = float(row.lam.iloc[0])
            dist = p_latest[p_latest.league_key == row.league_key.iloc[0]]["lam"]
            dist = dist[np.isfinite(dist)]
            n_exp = int(len(dist))
            checks += 1
            n_pos += 1
            here_t, pct_t, n_t, lg_t, mean_t, med_t = m.groups()
            if abs(float(here_t.replace(",", ".")) - lam_here) > 0.006:
                fails.append(f"{pg.name}: gol attesi {here_t} vs λ modello {lam_here:.3f}")
            below = float((dist < lam_here).mean())
            if int(pct_t) != int(round(below * 100)):
                fails.append(f"{pg.name}: percentile {pct_t}% vs ricalcolato {below * 100:.1f}%")
            if int(n_t) != n_exp:
                fails.append(f"{pg.name}: partite di lega {n_t} vs {n_exp} in predictions")
            if lg_t != _lg_names.get(str(row.league_key.iloc[0]), ""):
                fails.append(f"{pg.name}: nome lega «{lg_t}» diverso da config «{_lg_names.get(str(row.league_key.iloc[0]))}»")
            if abs(float(mean_t.replace(",", ".")) - float(dist.mean())) > 0.06:
                fails.append(f"{pg.name}: media di lega {mean_t} vs {dist.mean():.1f}")
            if abs(float(med_t.replace(",", ".")) - float(dist.median())) > 0.06:
                fails.append(f"{pg.name}: mediana di lega {med_t} vs {dist.median():.1f}")
        print(f"[16] percentile dei gol attesi nel campionato verificato: {n_pos}")

    # 17) primo gol: ritmo a due tempi calibrato su events.parquet — s, quartili in forma chiusa,
    #     P(0-0 all'intervallo) e P(0-0 piena) ricalcolate; «dopo il 90'» mai oltre il fischio
    ev_df = st.read("events")
    if not ev_df.empty and "type" in ev_df.columns and not preds.empty:
        import numpy as np

        pr_fg = preds.reset_index() if "match_id" not in preds.columns else preds
        pr_fg = pr_fg.sort_values("made_at").groupby("match_id").tail(1)
        gl = ev_df[ev_df.type == "Goal"]
        if len(gl) >= 60:
            s_fg = float((gl.minute <= 45).mean())
            n_fg = int(ev_df[ev_df.type == "Goal"].match_id.nunique())
            fg_re = re.compile(
                r"su (\d+(?:\.\d+)*) gol nelle\s*(\d+(?:\.\d+)*) partite di questa stagione \(7 leghe\), il "
                r"(\d+,\d)% cade nel 1° tempo", re.S)
            qq_re = re.compile(
                r"la metà centrale dei primi gol cade fra\s*(dopo il 90'|\d+')\s*e\s*"
                r"(dopo il 90'|\d+')\s*e la mediana è\s*(dopo il 90'|\d+')\. "
                r"Pari senza gol al riposo: <b>(\d+,\d)%</b>;\s*zero gol su novanta minuti: "
                r"(\d+,\d)%\.", re.S)
            n_q = 0
            for pg in pages:
                html = pg.read_text(encoding="utf-8")
                if 'id="primo-gol"' not in html:
                    continue
                mid = int(pg.stem)
                row_f = pr_fg[pr_fg.match_id == mid]
                checks += 1
                if row_f.empty:
                    fails.append(f"{pg.name}: card primo-gol senza previsione")
                    continue
                lam_fg = float(row_f.lambda_home.iloc[0]) + float(row_f.lambda_away.iloc[0])
                r1_f, r2_f = s_fg * lam_fg / 45.0, (1.0 - s_fg) * lam_fg / 45.0
                s_ht_f = float(np.exp(-r1_f * 45.0))

                def _qexp(p: float) -> float | None:
                    tail = 1.0 - p
                    t = (-np.log(tail) / r1_f) if tail >= s_ht_f else \
                        (45.0 + (-np.log(tail) - r1_f * 45.0) / r2_f)
                    return None if t > 90.0 else float(t)

                qs = {p: _qexp(p) for p in (0.25, 0.50, 0.75)}
                bl = html.split('id="primo-gol"', 1)[1][:2800]
                m_fg = fg_re.search(bl)
                if not m_fg or int(m_fg.group(1).replace(".", "")) != len(gl) or \
                        int(m_fg.group(2).replace(".", "")) != n_fg or \
                        abs(float(m_fg.group(3).replace(",", ".")) - s_fg * 100) > 0.06:
                    fails.append(f"{pg.name}: conteggi/quota gol di 1° tempo non tornano con events.parquet")
                m_q = qq_re.search(bl)
                if not m_q:
                    fails.append(f"{pg.name}: frase dei quartili del primo gol assente o diversa")
                    continue
                # la frase stampa «fra q1 e q3 e la mediana è q2»: riordino i gruppi
                labels = {0.25: m_q.group(1), 0.75: m_q.group(2), 0.50: m_q.group(3)}
                for p, t in qs.items():
                    atteso = "dopo il 90'" if t is None else f"{int(round(t))}'"
                    n_q += 1
                    if labels[p] != atteso:
                        fails.append(f"{pg.name}: quartile p={p} primo gol «{labels[p]}» vs modello «{atteso}»")
                if abs(float(m_q.group(4).replace(",", ".")) - s_ht_f * 100) > 0.06:
                    fails.append(f"{pg.name}: P(0-0 riposo) {m_q.group(4)}% vs {s_ht_f * 100:.1f}%")
                if abs(float(m_q.group(5).replace(",", ".")) - np.exp(-lam_fg) * 100) > 0.06:
                    fails.append(f"{pg.name}: P(0-0 piena) {m_q.group(5)}% vs {np.exp(-lam_fg) * 100:.1f}%")
            print(f"[17] quartili del primo gol verificati: {n_q}")

    # 13) nessun numero di verifica inventato nei template: se cambia il metodo il numero è falso
    tpl = Path(__file__).resolve().parents[1] / "src" / "fda" / "site" / "templates"
    n_tpl = 0
    if tpl.is_dir():
        for f in tpl.rglob("*.html"):
            testo = f.read_text(encoding="utf-8")
            n_tpl += 1
            if re.search(r"controlla \d[\d.]+ numeri", testo):
                fails.append(f"template {f.name}: conteggio dei controlli scritto a mano")

    # 14) n_train e compagni grandi con il separatore delle migliaia (esclusi gli anni 19xx/20xx)
    n_ntrain = 0
    no_year = r"\b(?!19\d\d|20\d\d)(\d{4,})\s*(?:partite|gare)\b"
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        male = re.search(no_year, re.sub(r"<[^>]+>", " ", html))
        if male:
            fails.append(f"{pg.name}: «{male.group(1)} partite/gare» senza separatore delle migliaia")
        else:
            n_ntrain += 1
    print(f"[13-14] template e formattazione anti-falso: {n_tpl} template, {n_ntrain} pagine")

    # 18) etichetta della colonna «impatto» dell'infermeria onesta e senza doppio significato
    # (docs/21 Q1): «fuori rosa» è SOLO il motivo FotMob «not in squad», mai l'assenza di
    # statistiche di stagione, che si scrive «senza minuti in stagione · n.d.» con tooltip.
    n_imp = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "senza minuti in stagione · n.d." in html or "fuori rosa · n.d." in html:
            n_imp += 1
            if "fuori rosa · n.d." in html:
                fails.append(f"{pg.name}: etichetta impatto fuorviante «fuori rosa · n.d.»")
            if "non ha ancora minuti nelle statistiche di stagione" not in html:
                fails.append(f"{pg.name}: etichetta «senza minuti in stagione» senza tooltip esplicativo")
    print(f"[18] etichette impatto infermeria verificate: {n_imp} pagine")

    # 19) panchina e posta in gioco (docs/21 P0-1): coach, subentro e percentuali Monte Carlo
    # ricalcolati dai Parquet; la sezione deve esserci se e solo se i dati ci sono.
    from fda.teams import canonical as _canon
    fx19 = st.read("fixtures")
    lu19 = st.read("lineup")
    sim19 = st.read("season_sim")
    from fda.site.analysis import MatchAnalysis as _MA
    ma19 = _MA(st)
    n_bench = 0
    if not fx19.empty and not lu19.empty and "role" in lu19.columns:
        ko19 = fx19.drop_duplicates("match_id").set_index("match_id")["utc_kickoff"]
        co19 = lu19[(lu19.role == "coach") & (lu19.match_id.isin(ko19.index))].copy()
        if not co19.empty:
            co19["ko"] = pd.to_datetime(co19.match_id.map(ko19), utc=True)
            co19 = co19.sort_values("ko", kind="stable")
        sim19map = {}
        if not sim19.empty:
            for r in sim19.itertuples(index=False):
                sim19map.setdefault(_canon(r.team), r)
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Analisi pre-partita" not in html:
                continue
            mid = int(pg.stem)
            if mid not in ko19.index:
                continue
            fr = fx19[fx19.match_id == mid].iloc[0]
            kickoff = pd.Timestamp(fr.utc_kickoff)
            txt = html_unescape(html)   # le etichette con apostrofo arrivano escaped (&#39;)
            atteso = False
            for tid, tname in ((int(fr.home_id), fr.home_name), (int(fr.away_id), fr.away_name)):
                ct = co19[(co19.team_id == tid) & (co19.ko <= kickoff)] if not co19.empty else co19
                coach = None
                if not ct.empty:
                    last = ct.iloc[-1]
                    cur = last.player_id
                    streak, prev = 0, None
                    for pid, nm in zip(ct.player_id.iloc[::-1], ct.player_name.iloc[::-1]):
                        if pid == cur:
                            streak += 1
                        else:
                            prev = nm
                            break
                    coach = (str(last.player_name), prev, streak)
                sr = sim19map.get(_canon(str(tname)))
                if coach or sr is not None:
                    atteso = True
                if coach and 'id="panchina"' in html:
                    checks += 1
                    if coach[0] not in txt:
                        fails.append(f"{pg.name}: panchina senza il coach {coach[0]} dei Parquet")
                    if coach[1] is not None:
                        if "panchina nuova" not in txt or str(coach[1]) not in txt:
                            fails.append(f"{pg.name}: subentro a {coach[1]} non dichiarato")
                if sr is not None and 'id="panchina"' in html:
                    checks += 1
                    pt, pe, pr = (int(round(float(sr.p_title) * 100)), int(round(float(sr.p_top4) * 100)),
                                  int(round(float(sr.p_rel) * 100)))
                    if f"titolo {pt}% · Europa {pe}% · salvezza {pr}%" not in txt:
                        fails.append(f"{pg.name}: posta in gioco {tname} non torna coi Parquet")
                    lab = ("corsa al titolo" if float(sr.p_title) >= 0.15 else
                           "corsa all'Europa" if float(sr.p_top4) >= 0.35 else
                           "lotta salvezza" if float(sr.p_rel) >= 0.35 else
                           "zona salvezza non lontana" if float(sr.p_rel) >= 0.15 else
                           "stagione di metà classifica")
                    if lab not in txt:
                        fails.append(f"{pg.name}: etichetta posta in gioco {tname} sbagliata ({lab})")
            if atteso and 'id="panchina"' not in html:
                fails.append(f"{pg.name}: scheda pre senza sezione panchina pur avendo i dati")
            # righe «utili» della card (rendimento, precedenti mirati, distacchi, virtuale):
            # ricalcolate con le funzioni del progetto e confrontate col testo stampato
            if 'id="panchina"' in html:
                for tid, tname, oid, oname in (
                        (int(fr.home_id), str(fr.home_name), int(fr.away_id), str(fr.away_name)),
                        (int(fr.away_id), str(fr.away_name), int(fr.home_id), str(fr.home_name))):
                    bd = ma19.bench_deep(tid, tname, oid, oname, kickoff)
                    if not bd:
                        continue
                    for key in ("tenure_line", "coach_ppg_line", "coach_vs_opp_line",
                                "coach_vs_coach_line", "table_line", "virtual_line"):
                        val = bd.get(key)
                        if val:
                            checks += 1
                            if val not in txt:
                                fails.append(f"{pg.name}: riga panchina «{key}» ({tname}) assente o diversa")
            n_bench += 1
    print(f"[19] panchina e posta in gioco verificate: {n_bench} pagine")

    # 20) notizie (docs/21 P1-5): ogni titolo/link stampato esiste in news.parquet per una
    # delle due squadre della pagina, dentro la finestra 12 giorni, max 4 per squadra.
    news20 = st.read("news")
    n_news = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="notizie"' not in html:
            if not news20.empty and "Analisi pre-partita" in html:
                ids20 = {int(r) for r in news20.team_id.unique()} if not news20.empty else set()
                fr20 = fx19[fx19.match_id == int(pg.stem)] if not fx19.empty else fx19
                if not fr20.empty:
                    fr20 = fr20.iloc[0]
                    if {int(fr20.home_id), int(fr20.away_id)} & ids20:
                        fails.append(f"{pg.name}: notizie disponibili ma sezione assente")
            continue
        n_news += 1
        if news20.empty:
            fails.append(f"{pg.name}: sezione notizie senza tabella news")
            continue
        mid = int(pg.stem)
        fr = fx19[fx19.match_id == mid].iloc[0] if not fx19.empty else None
        kickoff = pd.Timestamp(fr.utc_kickoff) if fr is not None else pd.Timestamp.now(tz="UTC")
        conti: dict[int, int] = {}
        for url, title in re.findall(r'<a href="(https?://[^"]+)" rel="noopener[^"]*">([^<]+)</a>', html):
            riga = news20[news20.url == url]
            if riga.empty:
                fails.append(f"{pg.name}: notizia senza riscontro in news.parquet ({title[:40]})")
                continue
            r = riga.iloc[0]
            checks += 1
            if html_unescape(r.title) != html_unescape(title):
                fails.append(f"{pg.name}: titolo stampato diverso dal raccolto ({title[:40]})")
            tid = int(r.team_id)
            if fr is not None and tid not in {int(fr.home_id), int(fr.away_id)}:
                fails.append(f"{pg.name}: notizia di squadra estranea alla partita")
            pa = pd.to_datetime(r.published_at, utc=True)
            if not pd.isna(pa) and not (kickoff - pd.Timedelta(days=12) <= pa <= kickoff + pd.Timedelta(days=1)):
                fails.append(f"{pg.name}: notizia fuori finestra 12 giorni ({title[:40]})")
            conti[tid] = conti.get(tid, 0) + 1
        for tid, n in conti.items():
            if n > 4:
                fails.append(f"{pg.name}: {n} notizie per la squadra {tid} (max 4)")
    print(f"[20] pagine con notizie riconciliate: {n_news}")

    # 21) clima del club (docs/21 P2-6): ogni riga stampata è ricalcolata da club_mood
    # con le stesse soglie; se una squadra ha segnali la card deve esserci.
    n_mood = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        fr = fx19[fx19.match_id == int(pg.stem)].iloc[0]
        kickoff = pd.Timestamp(fr.utc_kickoff)
        rows_h = ma19.club_mood(int(pg.stem), int(fr.home_id), str(fr.home_name), kickoff)
        rows_a = ma19.club_mood(int(pg.stem), int(fr.away_id), str(fr.away_name), kickoff)
        if rows_h or rows_a:
            n_mood += 1
            if 'id="clima"' not in html:
                fails.append(f"{pg.name}: segnali clima presenti ma card assente")
                continue
            for r in rows_h + rows_a:
                checks += 1
                if r["text"] not in txt:
                    fails.append(f"{pg.name}: riga clima «{r['text'][:40]}» assente o diversa")
        elif 'id="clima"' in html:
            fails.append(f"{pg.name}: card clima senza segnali calcolati")
    print(f"[21] pagine con clima del club riconciliate: {n_mood}")

    # 22) scontro tattico: graduatorie attacco/difesa e duello chiave ricalcolati dalla
    # classifica FotMob (fonte unica) e confrontati col testo stampato.
    n_duel = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        fr = fx19[fx19.match_id == int(pg.stem)].iloc[0]
        cr = ma19.clash_ranks(str(fr.home_name), str(fr.away_name))
        if not cr:
            continue
        n_duel += 1
        for key in ("home_line", "away_line", "duel_line"):
            checks += 1
            if cr[key] not in txt:
                fails.append(f"{pg.name}: riga scontro «{key}» assente o diversa")
    print(f"[22] duello chiave e graduatorie verificati: {n_duel} pagine")

    # 23) «giocherà?»: i badge titolare/panchina/assente stampati devono coincidere di
    # numero e contenuto coi ruoli della distinta; l'avviso sul top contributor assente
    # deve esserci se e solo se serve.
    n_status = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        mid = int(pg.stem)
        fr = fx19[fx19.match_id == mid].iloc[0]
        exp = {"starter": 0, "sub": 0, "unavailable": 0}
        alerts = 0
        listed = False
        for tid in (int(fr.home_id), int(fr.away_id)):
            sts = ma19.key_status(mid, tid)
            kp = ma19.key_players_deep(tid)
            rows = (kp or {}).get("rows") or []
            if rows:
                listed = True
            for r in rows:
                stt = (sts.get(r["id"]) or {}).get("status")
                if stt in exp:
                    exp[stt] += 1
            if rows and (sts.get(rows[0]["id"]) or {}).get("status") == "unavailable":
                alerts += 1
        if not listed:
            continue
        n_status += 1
        for badge, key in (("· titolare probabile", "starter"),
                           ("· in panchina", "sub"),
                           ("· assente:", "unavailable")):
            checks += 1
            if html.count(badge) != exp[key]:
                fails.append(f"{pg.name}: badge «{badge}» {html.count(badge)} vs {exp[key]} ruoli")
        has_alert = "è indisponibile" in txt
        if (alerts > 0) != has_alert:
            fails.append(f"{pg.name}: avviso top contributor assente coerente? {has_alert} vs {alerts}")
    print(f"[23] badge «giocherà?» riconciliati: {n_status} pagine")

    # 24) post-partita «Il prossimo impegno»: prima gara ufficiale (campionato + coppe)
    # ricalcolata dal calendario e confrontata con la riga stampata; se nessuna delle due
    # squadre ha gare future la card non deve esserci.
    n_next = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Lettura della partita" not in html or fx19.empty:
            continue
        rows = fx19[fx19.match_id == int(pg.stem)]
        if rows.empty or str(rows.iloc[0].status) != "finished":
            continue
        fr = rows.iloc[0]
        txt = html_unescape(html)
        ko = pd.Timestamp(fr.utc_kickoff)
        has_card, nx_lines = False, []
        for tid in (int(fr.home_id), int(fr.away_id)):
            nx = ma19.next_commitment(tid, ko)
            if nx:
                has_card = True
                nx_lines.append(nx["line"])
        checks += 1
        if has_card != ("Il prossimo impegno" in txt):
            fails.append(f"{pg.name}: card «Il prossimo impegno» incoerente col calendario")
            continue
        if not has_card:
            continue
        n_next += 1
        for line in nx_lines:
            checks += 1
            if line not in txt:
                fails.append(f"{pg.name}: riga prossimo impegno assente o diversa: «{line[:60]}…»")
    print(f"[24] «Il prossimo impegno» verificato: {n_next} pagine")

    # 25) conversione delle grandi occasioni: le celle «X su Y» devono coincidere coi tiri
    # mappati a xG ≥ 0,30 (autogol esclusi); la riga c'è se e solo se qualcuno ne ha avute.
    n_conv = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Tiri e occasioni" not in html or fx19.empty:
            continue
        rows = fx19[fx19.match_id == int(pg.stem)]
        if rows.empty or str(rows.iloc[0].status) != "finished":
            continue
        fr = rows.iloc[0]
        txt = html_unescape(html)
        cells, tot_big = [], 0
        for tid in (int(fr.home_id), int(fr.away_id)):
            summ = ma19.shot_summary(int(pg.stem), tid)
            big, bg = summ.get("big_chances", 0), summ.get("big_goals", 0)
            tot_big += big
            cells.append(f"{bg} su {big}")
        checks += 1
        if tot_big > 0:
            n_conv += 1
            if "…di cui convertite in gol" not in txt:
                fails.append(f"{pg.name}: riga conversione grandi occasioni assente")
            else:
                for cell in cells:
                    checks += 1
                    if cell not in txt:
                        fails.append(f"{pg.name}: cella conversione «{cell}» assente o diversa")
        elif "…di cui convertite in gol" in txt:
            fails.append(f"{pg.name}: riga conversione presente ma nessuna grande occasione")
    print(f"[25] conversione grandi occasioni verificata: {n_conv} pagine")

    st.close()
    return fails, checks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="site", help="cartella del sito generato")
    ap.add_argument("--data", default=None, help="cartella dei Parquet (default: data/processed)")
    ap.add_argument("--content-only", action="store_true", help="salta i controlli numerici (serve lo store)")
    args = ap.parse_args()

    site = Path(args.site)
    if not site.is_dir():
        print(f"cartella sito non trovata: {site}")
        return 2

    fails, pages = check_pages(site)
    print(f"pagine analizzate: {pages}")
    calendario, checks = check_calendar(site)
    fails += calendario
    barre, bar_checks = check_bars(site)
    fails += barre
    checks += bar_checks
    if not args.content_only:
        numeric, numeric_checks = check_numbers(site, Path(args.data) if args.data else None)
        fails += numeric
        checks += numeric_checks

    by_kind: Counter[str] = Counter(f.split(": ", 1)[1].split(" ")[0] for f in fails)
    print()
    if fails:
        print(f"PROBLEMI ({len(fails)}): {dict(by_kind)}")
        for f in fails[:40]:
            print("  -", f)
        return 1
    print(f"nessun problema · {checks} controlli numerici superati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
