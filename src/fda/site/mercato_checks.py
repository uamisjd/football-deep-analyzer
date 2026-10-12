"""Audit della card Mercato dai Parquet e dall'HTML, senza chiamare il generatore (docs/95).

La finestra dichiarata delimita il confronto. Identità normalizzate come nel resto del
progetto; importi, copertura e collegamento alle distinte sono ricalcolati da zero.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from ..teams import soft_key

CARD = re.compile(r'<div class="card" id="mercato">.*?(?=<div class="card" id="[^"]+"|<footer)', re.DOTALL)
HEADER = re.compile(r"(\d+) arriv[oi] · (\d+) parten[zt][ae] nella finestra dal (\d{2}/\d{2}/\d{4}) al (\d{2}/\d{2}/\d{4})")
CATEGORIES = ("numeric", "free", "loan", "unknown")
LABELS = {"official": "distinta ufficiale", "predicted": "formazione prevista",
          "previous": "ultima distinta disponibile", "unknown": "distinta raccolta (tipo non dichiarato)"}


def quote(value: Any) -> tuple[str, float | None]:
    """Formule non confuse con importi: nessuna conversione monetaria implicita."""
    if value is None or pd.isna(value):
        return "unknown", None
    t = str(value).strip().lower()
    if t in {"gratuito", "free", "free transfer", "svincolato"}:
        return "free", None
    if t in {"prestito", "loan", "on loan"}:
        return "loan", None
    clean = re.sub(r"\s+", "", t.replace("€", "").replace("eur", ""))
    m = re.fullmatch(r"([\d.,]+)(mln|milioni|m|mila|k)?", clean)
    if not m:
        return "unknown", None
    number, unit = m.groups()
    if not unit and "," in number and "." in number:
        number = number.replace(".", "")
    try:
        v = Decimal(number.replace(",", "."))
        v *= {"m": 1000000, "mln": 1000000, "milioni": 1000000, "k": 1000, "mila": 1000}.get(unit, 1)
    except InvalidOperation:
        return "unknown", None
    if not v.is_finite() or v <= 0:
        return "unknown", None
    return "numeric", float(v)


def selected_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Rappresentanti delle voci nella finestra: priorità alla versione recente.

    Politica dichiarata, non deduzione di carriera: stesso nome/direzione e stesso club
    oppure entro 30 giorni = ripubblicazione; club diverso oltre 30 giorni resta distinto.
    """
    chosen = []
    for _, group in frame.groupby(["_name", "direction"], sort=False):
        records = list(group.sort_values("_date", ascending=False, kind="stable").itertuples())
        # Uso degli indici invece degli attributi '_' rinominati da itertuples.
        newest = group.loc[records[0].Index]
        for entry in records:
            r = group.loc[entry.Index]
            same_club = bool(r["_club"]) and r["_club"] == newest["_club"]
            if entry.Index == records[0].Index or (
                not same_club and newest["_date"] - r["_date"] > pd.Timedelta(days=30)
            ):
                chosen.append(entry.Index)
    return frame.loc[chosen].copy() if chosen else frame.iloc[:0].copy()


def subtotal(frame: pd.DataFrame) -> float | None:
    """Un lato ignoto non diventa zero. Gratuiti/no movimenti sostengono invece lo zero."""
    values = [amount for kind, amount in frame["_quote"] if kind == "numeric"]
    if values:
        return math.fsum(values)
    return 0.0 if all(kind == "free" for kind, _ in frame["_quote"]) else None


def displayed_amount(text: str, label: str) -> tuple[float | None, float]:
    m = re.search(rf"{label}\s+([+−-]?)([\d.,]+)\s*(M€|k€|€)", text)
    if not m:
        return None, 0.0
    unit = {"M€": 1e6, "k€": 1e3, "€": 1}[m.group(3)]
    amount = float(m.group(2).replace(",", ".")) * unit
    digits = len(m.group(2).split(",")[1]) if "," in m.group(2) else 0
    return (-amount if m.group(1) in {"−", "-"} else amount), unit * 10 ** (-digits) / 2


def audit_market(site: Path, data: Path, *, now: Any = None) -> dict[str, Any]:
    """Censisce solo le schede pre-partita; controlla le celle, non frasi altrove nel sito."""
    current = pd.to_datetime(now, utc=True) if now is not None else pd.Timestamp.now(tz="UTC")
    def read(name: str, columns: list[str]) -> pd.DataFrame:
        path = data / f"{name}.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=columns)

    tr = read("transfers", ["team_id", "date", "player_name", "counterpart", "fee_text", "direction"])
    fx = read("fixtures", ["match_id", "utc_kickoff", "home_id", "away_id", "home_name", "away_name"])
    lineup = read("lineup", ["match_id", "team_id", "role", "player_name"])
    info = read("match_info", ["match_id", "lineup_type"])
    if tr.empty or fx.empty:
        return {"counts": {}, "checks": 0, "errors": [], "defects": 0}
    tr = tr.assign(_date=pd.to_datetime(tr.date, utc=True, errors="coerce", format="mixed"),
                   _name=tr.player_name.map(lambda s: soft_key(str(s or ""))),
                   _club=tr.counterpart.map(lambda s: soft_key(str(s or ""))))
    tr["_quote"] = tr.fee_text.map(quote)
    errors: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    checks = 0

    def problem(mid: int, team: str, kind: str, message: str) -> None:
        errors.append({"match_id": mid, "team": team, "kind": kind, "message": message})

    pages = site / "partite" if (site / "partite").is_dir() else site
    for path in sorted(pages.glob("*.html")):
        html = path.read_text()
        if "Analisi pre-partita" not in html:
            continue
        counts["prematch_pages"] += 1
        card = CARD.search(html)
        if not card:
            continue  # assenza di entrambe le fonti controllata anche da [26]
        counts["market_pages"] += 1
        mid = int(path.stem)
        fixture = fx[fx.match_id.eq(mid)]
        if fixture.empty:
            problem(mid, "?", "fixture", "scheda senza calendario")
            continue
        fixture = fixture.iloc[0]
        cutoff = min(current, pd.to_datetime(fixture.utc_kickoff, utc=True))
        soup = BeautifulSoup(card.group(), "html.parser")
        grid = soup.find("div", class_="grid")
        sides = grid.find_all("div", class_="card", recursive=False) if grid else []
        if len(sides) != 2:
            problem(mid, "?", "structure", "la card deve avere due colonne")
            continue
        im = info[info.match_id.eq(mid)]
        raw_type = str(im.iloc[0].get("lineup_type", "")) if not im.empty else ""
        origin = {"confirmed": "official", "official": "official", "predicted": "predicted",
                  "probable": "predicted", "lastStarting11": "previous"}.get(raw_type, "unknown")
        for side, column in zip(("home", "away"), sides, strict=True):
            tid, team = int(fixture[f"{side}_id"]), str(fixture[f"{side}_name"])
            text = column.get_text(" ", strip=True)
            counts["sides"] += 1
            header = HEADER.search(text)
            source = tr[tr.team_id.eq(tid) & tr._date.notna() & tr._date.le(cutoff)]
            if not header:
                counts["inactive_sides"] += 1
                continue
            start, end = (pd.to_datetime(d, format="%d/%m/%Y", utc=True) for d in header.groups()[2:])
            checks += 1
            if end > cutoff.normalize():
                problem(mid, team, "future", "finestra successiva al limite pre-partita")
            window = source[source._date.ge(start) & source._date.lt(end + pd.Timedelta(days=1))]
            chosen = selected_rows(window)
            category = Counter(kind for kind, _ in chosen._quote)
            for kind in CATEGORIES:
                counts[kind] += category[kind]
            checks += 2
            if (int(header.group(1)), int(header.group(2))) != (
                    int(chosen.direction.eq("in").sum()), int(chosen.direction.eq("out").sum())):
                problem(mid, team, "counts", "conteggi della finestra diversi dai movimenti riconciliati")
            # Non basta contare gli importi mancanti: una formula di prestito non è un gratuito.
            coverage = column.select_one(".market-fees")
            expected = (f"Importi numerici: {category['numeric']} · Gratuiti: {category['free']} · "
                        f"Prestiti senza importo: {category['loan']} · Non dichiarati: {category['unknown']}")
            checks += 1
            if coverage is None or coverage.get_text(" ", strip=True) != expected:
                problem(mid, team, "fee_coverage", "copertura importi/formule assente o diversa")
            incoming, outgoing = chosen[chosen.direction.eq("in")], chosen[chosen.direction.eq("out")]
            spend, income = subtotal(incoming), subtotal(outgoing)
            net = spend - income if spend is not None and income is not None else None
            ledger = column.select_one(".market-ledger")
            ledger_text = ledger.get_text(" ", strip=True) if ledger else text
            for label, value in (("spesa", spend), ("incasso", income), ("saldo", net)):
                checks += 1
                published, tolerance = displayed_amount(ledger_text, label)
                if value is None:
                    if f"{label} non quantificabile" not in ledger_text:
                        problem(mid, team, "ledger", f"{label}: manca la dichiarazione di dato non quantificabile")
                elif published is None or abs(published - value) > tolerance + 1e-6:
                    problem(mid, team, "ledger", f"{label}: somma dei corrispettivi non riconciliata")
            eligible = lineup[lineup.match_id.eq(mid) & lineup.team_id.eq(tid)
                              & lineup.role.isin(["starter", "sub"])].copy()
            eligible["_name"] = eligible.player_name.map(lambda s: soft_key(str(s or "")))
            names = set(eligible["_name"]) & set(incoming["_name"])
            counts["lineup_matches"] += len(names)
            counts[f"lineup_{origin}_sides"] += bool(names)
            roster = column.select_one(".market-roster")
            if roster is None:
                roster = next((p for p in column.find_all("p") if "Già in campo:" in p.get_text()), None)
            checks += 1
            if not names:
                if roster is not None:
                    problem(mid, team, "roster", "riga di presenze senza arrivi riconosciuti")
                continue
            roster_text = roster.get_text(" ", strip=True) if roster else ""
            n = re.search(r"(?:riconosciuti:|Già in campo:)\s*(\d+)", roster_text)
            if n is None or int(n.group(1)) != len(names):
                problem(mid, team, "roster_count", f"attesi {len(names)} arrivi nell'intera finestra, non solo i quattro esposti")
            if LABELS[origin] not in roster_text or "Già in campo:" in roster_text:
                problem(mid, team, "roster_origin", f"origine da dichiarare: {LABELS[origin]}")
            # Il dettaglio espandibile è nella stessa regione: tutti i nomi restano consultabili.
            normalized = soft_key(roster_text)
            if any(name not in normalized for name in names):
                problem(mid, team, "roster_names", "uno o più arrivi riconosciuti non sono consultabili")
    return {"counts": {k: int(v) for k, v in counts.items()}, "checks": checks,
            "errors": errors, "defects": len(errors)}
