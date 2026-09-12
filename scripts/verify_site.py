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
AGREEMENT = re.compile(r"\b1 (rossi|gialli|rigori|gare|partite|vittorie|pareggi|tiri|giorni|precedenti)\b")
LOCAL_HREF = re.compile(r'href="([^"#]+\.html)(#[^"]*)?"')


class Text(HTMLParser):
    """Testo leggibile di una pagina (senza style/script/head/svg) + href locali."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Any]]) -> None:
        if tag in ("style", "script", "head", "svg"):
            self.skip += 1
        if tag in ("p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "table", "section", "br"):
            self.parts.append(" ")      # separa i blocchi: «…link</a>1 gare» non deve sembrare «x1 gare»
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
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
            base = site if href.startswith("/") else page.parent
            if not (base / href.lstrip("/")).exists():
                fails.append(f"{rel}: collegamento interno mancante {href}")
    return fails, len(pages)


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
        cells = re.findall(r'<td[^>]*title="(\d)-(\d) · (\d+,\d+)%">(\d+,\d)</td>', html)
        if len(cells) != 36:
            fails.append(f"{pg.name}: celle matrice {len(cells)} (attese 36)")
            continue
        n_matrix += 1
        checks += 1
        worst, tot = 0.0, 0.0
        for i, j, _title_p, cell_p in cells:
            rendered = float(cell_p.replace(",", "."))
            worst = max(worst, abs(rendered - round(float(m["cells"][int(i)][int(j)]["p"]) * 100, 1)))
            tot += rendered
        tail_m = re.search(r"Coda 6\+ gol: (\d+,\d)%", html)
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
    checks = 0
    if not args.content_only:
        numeric, checks = check_numbers(site, Path(args.data) if args.data else None)
        fails += numeric

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
