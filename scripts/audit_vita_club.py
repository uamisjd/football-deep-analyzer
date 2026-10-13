"""Audit read-only di Vita del club: periodo, imbuto, provenienza e limiti (docs/96).

Uso: .venv/bin/python scripts/audit_vita_club.py --site site --json rapporto.json
I criteri editoriali sono euristiche testate a parte, non verità certificate dall'audit.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from fda.site.club_news_checks import audit_club_life

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = audit_club_life(args.site, args.data)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Vita del club:", report["counts"])
    print(f"Controlli: {report['checks']} · difetti: {report['defects']} · "
          f"{dict(Counter(e['kind'] for e in report['errors']))}")
    for error in report["errors"][:8]:
        print(f"{error['match_id']} / {error['team']}: {error['message']}")
    if not report["counts"].get("news_pages"):
        print("Nessuna card misurata: non è una verifica riuscita.")
        return 1
    return int(report["defects"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
