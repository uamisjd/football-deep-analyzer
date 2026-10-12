"""Audit read-only delle vere schede Mercato, non di tutte le fixture future (docs/95).

Il vecchio script era un confronto storico fra due deduplicazioni (docs/56): usava una
soglia di 30 ore invece delle 3 in produzione, non leggeva l'HTML e non era un gate.
Questo censisce le schede generate: movimenti nella finestra, copertura delle cifre,
bilancio parziale, tutti gli arrivi riconosciuti e provenienza della distinta.

Uso: .venv/bin/python scripts/audit_mercato.py [--site site] [--data data/processed] [--json rapporto.json]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from fda.site.mercato_checks import audit_market

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = audit_market(args.site, args.data)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("=== Mercato: schede e dati riconciliati ===")
    for key, value in report["counts"].items():
        print(f"{key}: {value}")
    types = Counter(e["kind"] for e in report["errors"])
    print(f"Controlli: {report['checks']} · difetti: {report['defects']} · {dict(types)}")
    for error in report["errors"][:8]:
        print(f"{error['match_id']} / {error['team']}: {error['message']}")
    if not report["counts"].get("market_pages", 0):
        print("Nessuna card Mercato misurabile: non è una verifica riuscita.")
        return 1
    return int(report["defects"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
