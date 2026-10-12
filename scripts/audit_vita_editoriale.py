"""Diagnostica editoriale e copertura delle sette leghe (docs/97), offline e read-only.

Non è una stima di recall o di accuratezza giornalistica. Confronta titoli esposti con
le etichette manuali congelate; i titoli non annotati sono esplicitamente da revisionare.
--reference-date permette di ricontrollare il campione storico a parità di calendario.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from fda.config import DETAIL_WINDOW_DAYS, leagues
from fda.site.analysis import MatchAnalysis
from fda.store import Store

ROOT = Path(__file__).resolve().parents[1]


def measure(data: Path, reference: date, gold: Path) -> dict:
    store = Store(data)
    ma = MatchAnalysis(store)
    fx = ma.fixtures
    local = pd.to_datetime(fx.utc_kickoff, utc=True).dt.tz_convert("Europe/Rome").dt.date
    cohort = fx[~fx.status.isin(["finished", "cancelled"])
                & local.ge(reference) & local.le(reference + timedelta(days=DETAIL_WINDOW_DAYS))]
    names = {lg.fotmob_id: lg.key for lg in leagues()}
    annotated = {r["title"]: r for r in json.loads(gold.read_text())["cases"]}
    groups = {lg.key: Counter() for lg in leagues()}
    rows = []
    for game in cohort.sort_values("utc_kickoff").itertuples():
        key = names[game.league_id]
        groups[key]["matches"] += 1
        seen = set()
        for tid, team, opponent in ((game.home_id, game.home_name, game.away_name),
                                    (game.away_id, game.away_name, game.home_name)):
            nw = ma.team_news(tid, team, game.utc_kickoff, squad=ma.match_squad(game.match_id, tid),
                              opponent=opponent, coach=(ma.coach(tid, game.utc_kickoff) or {}).get("name"), seen=seen)
            group = groups[key]
            group["sides"] += 1
            group["collected_rows"] += nw["esaminate"]
            group["sides_with_rows"] += nw["esaminate"] > 0
            exposed = nw["notizie"] + nw["riserva"]
            correlated = [r for v in exposed for r in v.get("related", [])]
            group["primary"] += len(nw["notizie"])
            group["reserve"] += len(nw["riserva"])
            group["related"] += len(correlated)
            group["sides_with_signals"] += bool(exposed)
            group["rejected_low_reputation"] += nw["bassa_reputazione"]
            group["rejected_language"] += nw["lingua"]
            for article in exposed + correlated:
                label = annotated.get(article["title"])
                row = {"match_id": int(game.match_id), "team": team, "league": key,
                       "title": article["title"], "source": article["source"], "url": article["url"],
                       "published_at": str(article["published_at"]), "kind": article["kind"],
                       "signal": article["signal_label"], "evidence": article["evidence"],
                       "annotation": label["expected"] if label else "not_reviewed"}
                rows.append(row)
    store.close()
    counts = Counter(r["annotation"] for r in rows)
    return {"reference_date": reference.isoformat(), "by_league": {k: dict(v) for k, v in groups.items()},
            "rows": rows, "annotation_counts": dict(counts),
            "distinct_titles": len({r["title"] for r in rows}),
            "scope": "campione di sviluppo; non precisione futura, recall o verifica delle fonti"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=ROOT / "data/processed")
    p.add_argument("--reference-date", type=date.fromisoformat, default=date(2026, 10, 12))
    p.add_argument("--gold", type=Path, default=ROOT / "tests/fixtures/vita_editorial_review_2026-10-12.json")
    p.add_argument("--json", type=Path)
    args = p.parse_args(argv)
    report = measure(args.data, args.reference_date, args.gold)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Lega | schede | lati | voci | principali | riserva | sul tema | lati con segnalazioni")
    for key, values in report["by_league"].items():
        print(key, *(values.get(k, 0) for k in ["matches", "sides", "collected_rows", "primary", "reserve", "related", "sides_with_signals"]), sep=" | ")
    print("Titoli distinti:", report["distinct_titles"], "· annotazioni:", report["annotation_counts"])
    print(report["scope"])
    return 1 if report["annotation_counts"].get("reject", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
