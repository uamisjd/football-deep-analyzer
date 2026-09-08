"""Verifica classifiche FotMob + backfill xG sui dati di `origin/main` (dopo un run `daily`).

Legge i Parquet versionati via `git show <ref>:<path>` (nessuna rete oltre a github.com)
e controlla, per ognuna delle 7 leghe: tabella presente e completa (n° squadre da
config, rank 1..N, giocate = V+N+P, punti = 3V+N salvo penalizzazioni), copertura
dettagli delle finite (xG disponibili per `season_xg`), errori in `source_status`. Uso:

    python scripts/verify_standings.py [--ref origin/main]

Stampa solo un riepilogo breve (paletti anti-blocco: niente dati grezzi in chat).
Ritorna 1 se una lega è senza tabella o con errori gravi.
"""
from __future__ import annotations

import argparse
import io
import subprocess

import pandas as pd
import yaml


def git(*args: str) -> bytes:
    out = subprocess.run(["git", *args], check=True, capture_output=True)
    return out.stdout


def read_parquet_at(ref: str, path: str) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(git("show", f"{ref}:{path}")))


def league_config(ref: str) -> dict[str, dict]:
    """{key: {fotmob_id, teams, has_understat}} da config/leagues.yaml al ref dato."""
    raw = yaml.safe_load(git("show", f"{ref}:config/leagues.yaml").decode())
    return {lg["key"]: {"fotmob_id": lg["fotmob_id"], "teams": lg["teams"],
                        "has_understat": bool(lg.get("understat_slug"))} for lg in raw["leagues"]}


def check_table(df: pd.DataFrame, n_teams: int) -> tuple[list[str], list[str]]:
    """Controlli di coerenza sulla tabella di una lega. Ritorna (problemi, avvisi)."""
    problems, warnings = [], []
    if len(df) != n_teams:
        problems.append(f"{len(df)} squadre invece di {n_teams}")
        return problems, warnings
    need = {"rank", "played", "wins", "draws", "losses", "goals_for", "goals_against", "points"}
    if not need.issubset(df.columns):
        problems.append(f"colonne mancanti: {sorted(need - set(df.columns))}")
        return problems, warnings
    ranks = sorted(int(r) for r in df["rank"] if pd.notna(r))
    if ranks != list(range(1, n_teams + 1)):
        problems.append("rank non sequenziali 1..N")
    bad_played = bad_points = missing_goals = 0
    for r in df.itertuples(index=False):
        vals = [r.played, r.wins, r.draws, r.losses, r.points]
        if any(pd.isna(v) for v in vals):
            bad_played += 1
            continue
        if int(r.played) != int(r.wins) + int(r.draws) + int(r.losses):
            bad_played += 1
        if int(r.points) != 3 * int(r.wins) + int(r.draws):
            bad_points += 1                      # può essere una penalizzazione reale
        if pd.isna(r.goals_for) or pd.isna(r.goals_against):
            missing_goals += 1
    if bad_played:
        problems.append(f"{bad_played} righe con giocate != V+N+P")
    if bad_points:
        warnings.append(f"{bad_points} righe con punti != 3V+N (penalizzazioni?)")
    if missing_goals:
        warnings.append(f"{missing_goals} righe senza gol fatti/subiti")
    return problems, warnings


def finished_coverage(fx: pd.DataFrame, mi: pd.DataFrame) -> dict[int, tuple[int, int]]:
    """Per league_id: (finite in calendario, finite con xG nei dettagli)."""
    out: dict[int, tuple[int, int]] = {}
    fin = fx[fx.status == "finished"] if not fx.empty else fx
    for lid in sorted(fin.league_id.dropna().astype(int).unique()):
        n_cal = int((fin.league_id == lid).sum())
        det = mi[(mi.league_id == lid) & (mi.status == "finished") & mi.home_xg.notna()] \
            if not mi.empty and "home_xg" in mi.columns else mi.iloc[0:0]
        out[lid] = (n_cal, len(det))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="origin/main", help="ref git da leggere (default origin/main)")
    args = ap.parse_args()

    sha = git("rev-parse", args.ref).decode().strip()
    date = git("show", "-s", "--format=%cI", sha).decode().strip()
    print(f"ref {args.ref} -> {sha[:9]} (commit del {date})")

    try:
        tab = read_parquet_at(args.ref, "data/processed/fotmob_standings.parquet")
    except subprocess.CalledProcessError:
        print("✗ fotmob_standings.parquet assente: il run con Fix A non è ancora su main")
        return 1
    fx = read_parquet_at(args.ref, "data/processed/fixtures.parquet")
    mi = read_parquet_at(args.ref, "data/processed/match_info.parquet")
    st = read_parquet_at(args.ref, "data/processed/source_status.parquet")
    cfg = league_config(args.ref)

    print("\n== Tabelle di lega (FotMob) ==")
    failed = False
    for key, lg in cfg.items():
        df = tab[tab.league_code == key] if not tab.empty else tab
        if df.empty:
            print(f"✗ {key}: tabella assente")
            failed = True
            continue
        problems, warnings = check_table(df, lg["teams"])
        flag = "✗" if problems else "✓"
        failed |= bool(problems)
        extra = ("; ".join(problems + [f"avviso: {w}" for w in warnings]) or
                 f"{len(df)} squadre, rank ok, punti ok")
        print(f"{flag} {key}: {extra}")

    print("\n== Copertura xG finite (dettagli/match) ==")
    cov = finished_coverage(fx, mi)
    by_id = {lg["fotmob_id"]: (key, lg["has_understat"]) for key, lg in cfg.items()}
    for lid, (n_cal, n_det) in cov.items():
        key, has_us = by_id.get(lid, (f"id={lid}", True))
        pct = f"{100 * n_det / n_cal:.0f}%" if n_cal else "—"
        need = "" if has_us else (" ✓" if n_cal and n_det / n_cal >= 0.8 else " ✗ backfill incompleto")
        failed |= need.startswith(" ✗")
        print(f"  {key}: {n_det}/{n_cal} finite con xG ({pct}){need if not has_us else ''}")

    print("\n== source_status FotMob (ultima riga) ==")
    st["run_at"] = pd.to_datetime(st.run_at, utc=True)
    fm = st[st.source.str.startswith("fotmob:")].sort_values("run_at").groupby("source").tail(1)
    for r in fm.sort_values("source").itertuples(index=False):
        err = (r.error or "")[:70] if isinstance(r.error, str) else ""
        print(f"{'OK ' if r.ok else 'ERR'} {r.source:16s} {r.run_at:%m-%d %H:%M} UTC  req={int(r.requests)} {err}")
    print("\nESITO:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
