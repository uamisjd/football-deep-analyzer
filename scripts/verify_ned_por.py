"""Verifica NED1/POR1 sui dati di `origin/main` (usare dopo un run `daily` post-merge).

Legge i Parquet versionati via `git show <ref>:<path>` (nessuna rete oltre a github.com),
conta le predizioni per lega (attese: NED1 ~11, POR1 ~9) e riporta eventuali errori
in `source_status`. Uso:

    python scripts/verify_ned_por.py [--ref origin/main]

Stampa solo un riepilogo breve (paletti anti-blocco: niente dati grezzi in chat).
"""
from __future__ import annotations

import argparse
import io
import subprocess

import pandas as pd

NED1, POR1 = 57, 61  # league_id FotMob


def git(*args: str) -> bytes:
    out = subprocess.run(["git", *args], check=True, capture_output=True)  # noqa: S603, S607
    return out.stdout


def read_parquet_at(ref: str, path: str) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(git("show", f"{ref}:{path}")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="origin/main", help="ref git da leggere (default origin/main)")
    args = ap.parse_args()

    sha = git("rev-parse", args.ref).decode().strip()
    date = git("show", "-s", "--format=%cI", sha).decode().strip()
    print(f"ref {args.ref} -> {sha[:9]} (commit del {date})")

    preds = read_parquet_at(args.ref, "data/processed/predictions.parquet")
    fx = read_parquet_at(args.ref, "data/processed/fixtures.parquet")
    st = read_parquet_at(args.ref, "data/processed/source_status.parquet")

    print("\n== Predizioni per lega (ultima per partita) ==")
    if preds.empty:
        print("(nessuna predizione)")
    else:
        last = preds.sort_values("made_at").groupby("match_id").tail(1)
        print(last.groupby("league_key").size().sort_index().to_string())
        for key in ("NED1", "POR1"):
            n = int((last.league_key == key).sum())
            print(f">>> {key}: {n} predizioni " + ("✓" if n else "✗ ancora assenti"))

    now = pd.Timestamp.now(tz="UTC")
    fx["utc_kickoff"] = pd.to_datetime(fx.utc_kickoff, utc=True)
    for lid, key in ((NED1, "NED1"), (POR1, "POR1")):
        g = fx[fx.league_id == lid]
        if g.empty:
            print(f"\n{key} (league_id {lid}): nessuna fixture")
            continue
        soon = g[(g.status == "scheduled") & (g.utc_kickoff >= now) & (g.utc_kickoff <= now + pd.Timedelta(days=2))]
        print(f"{key} (league_id {lid}): {len(g)} fixture, {int((g.status == 'scheduled').sum())} in programma, "
              f"{len(soon)} entro 48 h da ora")

    print("\n== source_status (ultima riga per fonte) ==")
    st["run_at"] = pd.to_datetime(st.run_at, utc=True)
    for r in st.sort_values("run_at").groupby("source").tail(1).sort_values("source").itertuples(index=False):
        err = (r.error or "")[:70] if isinstance(r.error, str) else ""
        print(f"{'OK ' if r.ok else 'ERR'} {r.source:24s} {r.run_at:%m-%d %H:%M} UTC  req={int(r.requests)} {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
