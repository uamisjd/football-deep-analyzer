"""Misura della crescita del repository (politica A di ``docs/105``, misure di ``docs/109`` §4).

Serve a rendere **ripetibile** una verifica che altrimenti si rifà a mano: quanti byte scrivono i
commit di ``main`` ogni giorno, quante fotografìe complete dei dati entrano in archivio e quanto
manca alla soglia raccomandata da GitHub (1 GB), al ritmo misurato.

Uso::

    python -m scripts.crescita_repo                          # ultimi 14 giorni di origin/main
    python -m scripts.crescita_repo --days 30 --ref HEAD
    python -m scripts.crescita_repo --da 2026-10-14 --ritmo 3 --repo uamisjd/football-deep-analyzer

``--da`` restringe la finestra a una data (utile per misurare il **dopo** una politica) e
``--ritmo`` sceglie su quante giornate recenti calcolare il ritmo della proiezione: la media
dell'intera finestra mescolerebbe giorni con regole diverse, come è successo il 15/10.

Legge la storia con la plumbing di ``git`` (nessuna rete, nessun file modificato) e, con
``--repo``, aggiunge la dimensione che GitHub riporta via ``gh api``. In un clone superficiale i
commit senza il genitore disponibile vengono **contati come saltati e dichiarati**: la misura è
onesta anche quando non è completa.

Le funzioni pure (``parse_raw_changes``, ``classify_commit``, ``days_to_target``,
``mean_recent``) hanno i test in ``tests/test_crescita_repo.py``; nessuna di esse tocca il
repository o la rete.
"""

from __future__ import annotations

import argparse
import collections
import subprocess
import sys
from dataclasses import dataclass

REGISTRO = "data/processed/prospettico.parquet"
DATA_PREFIX = "data/processed/"
TARGET_MIB = 1024.0  # soglia «ideale» raccomandata da GitHub (docs/109 §4)


def parse_raw_changes(text: str) -> list[tuple[str, str]]:
    """Estrae ``(sha_del_blob, percorso)`` dall'output di ``git diff-tree --raw``.

    Le righe di creazione/modifica hanno il blob nella quinta colonna (indice 3); le righe di
    cancellazione hanno zeri e vengono scartate: non scrivono byte.
    """
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 5 or not path:
            continue
        blob = parts[3]
        if set(blob) == {"0"}:  # cancellazione
            continue
        out.append((blob, path))
    return out


def classify_commit(paths: list[str]) -> str:
    """Classe di un commit: ``snapshot`` · ``registro`` · ``codice``.

    ``snapshot`` = tocca più di un file in ``data/processed`` (la fotografia completa del run);
    ``registro`` = tocca **solo** ``prospettico.parquet`` (il registro preregistrato, escluso
    dalla regola «una al giorno»); ``codice`` = tutto il resto (documenti, codice, workflow).
    """
    if not paths:
        return "vuoto"
    data = [p for p in paths if p.startswith(DATA_PREFIX)]
    if not data:
        return "codice"
    if all(p == REGISTRO for p in data):
        return "registro"
    return "snapshot"


def days_to_target(current_mib: float, mib_per_day: float, target_mib: float = TARGET_MIB) -> float | None:
    """Giorni (frazionari) per arrivare a ``target_mib`` al ritmo ``mib_per_day``.

    ``None`` se il ritmo non è positivo (non si arriva mai); ``0.0`` se il bersaglio è già
    superato: meglio dichiararlo che stampare un numero negativo.
    """
    if mib_per_day <= 0:
        return None
    remaining = max(0.0, float(target_mib) - float(current_mib))
    return remaining / float(mib_per_day)


def mean_recent(rows: list[DayRow], n: int) -> float:
    """Media dei byte/giorno sulle ``n`` giornate più recenti che hanno commit.

    ``rows`` è qualunque sequenza di ``DayRow`` (l'ordine non conta: si ordina per data).
    Ritorna ``0.0`` se non ci sono giornate con commit.
    """
    piene = sorted((r for r in rows if r.commits), key=lambda r: r.day, reverse=True)[:n]
    if not piene:
        return 0.0
    return sum(r.mib for r in piene) / len(piene)


@dataclass
class DayRow:
    day: str
    commits: int
    snapshots: int
    registro: int
    files: int
    mib: float


def _sh(*args: str, check: bool = True) -> str:
    proc = subprocess.run(args, check=False, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} → {proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _blob_sizes(shas: list[str]) -> dict[str, int]:
    if not shas:
        return {}
    proc = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectsize) %(objectname)"],
        check=False, input="\n".join(shas), capture_output=True, text=True,
    )
    sizes: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "blob":
            sizes[parts[2]] = int(parts[1])
    return sizes


def collect_days(ref: str, days: int) -> tuple[list[DayRow], int]:
    """Byte scritti e classi per giorno. Ritorna ``(righe, commit_saltati)``."""
    log = _sh("git", "log", f"--since={days} days ago", "--format=%H %ad",
              "--date=format:%Y-%m-%d", ref).splitlines()
    per_day: dict[str, dict[str, float]] = collections.defaultdict(
        lambda: {"commits": 0, "snapshot": 0, "registro": 0, "files": 0, "bytes": 0})
    skipped = 0
    for line in log:
        sha, day = line.split()
        parents = _sh("git", "rev-list", "--parents", "-n", "1", sha).split()[1:]
        if parents:
            parent_ok = subprocess.run(
                ["git", "cat-file", "-e", f"{parents[0]}^{{commit}}"],
                check=False, capture_output=True).returncode == 0
            if not parent_ok:
                # clone superficiale: senza il genitore il diff non è misurabile e `--root`
                # conterebbe l'intero albero come nuovo. Si dichiara invece di gonfiare.
                skipped += 1
                continue
            raw = _sh("git", "diff-tree", "-r", "--raw", "--no-commit-id", f"{parents[0]}..{sha}")
        else:
            raw = _sh("git", "diff-tree", "-r", "--raw", "--no-commit-id", "--root", sha)
        changes = parse_raw_changes(raw)
        bucket = per_day[day]
        bucket["commits"] += 1
        bucket["files"] += len(changes)
        kind = classify_commit([p for _, p in changes])
        if kind == "snapshot":
            bucket["snapshot"] += 1
        elif kind == "registro":
            bucket["registro"] += 1
        sizes = _blob_sizes(sorted({b for b, _ in changes}))
        bucket["bytes"] += sum(sizes.get(b, 0) for b, _ in changes)
    rows = [DayRow(day=day, commits=int(b["commits"]), snapshots=int(b["snapshot"]),
                   registro=int(b["registro"]), files=int(b["files"]), mib=b["bytes"] / 1048576)
            for day, b in per_day.items()]
    rows.sort(key=lambda r: r.day, reverse=True)
    return rows, skipped


def github_size_kb(repo: str) -> int | None:
    """Dimensione del repository secondo l'API di GitHub, in KB (``None`` se non disponibile)."""
    try:
        out = _sh("gh", "api", f"repos/{repo}", "--jq", ".size")
        return int(out.strip())
    except (OSError, RuntimeError, ValueError) as exc:
        # gh assente, rete chiusa, repo sbagliato o risposta non numerica: la storia locale basta
        print(f"[i] dimensione GitHub non letta ({exc.__class__.__name__}): uso solo la storia locale")
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crescita del repository: byte scritti al giorno e proiezione")
    ap.add_argument("--ref", default="origin/main", help="riferimento da misurare (default: origin/main)")
    ap.add_argument("--days", type=int, default=14, help="finestra in giorni (default: 14)")
    ap.add_argument("--da", default=None, help="considera solo i giorni da questa data (AAAA-MM-GG)")
    ap.add_argument("--ritmo", type=int, default=3, help="giornate recenti per il ritmo della proiezione")
    ap.add_argument("--repo", default=None, help="repo GitHub (owner/name) per la dimensione via gh api")
    args = ap.parse_args(argv)

    rows, skipped = collect_days(args.ref, args.days)
    if args.da:
        rows = [r for r in rows if r.day >= args.da]
    if not rows:
        print("nessun commit misurabile nella finestra", file=sys.stderr)
        return 1
    print(f"{'giorno':12}{'commit':>7}{'file':>7}{'foto':>6}{'registro':>9}{'MiB scritti':>12}")
    for r in rows:
        print(f"{r.day:12}{r.commits:7}{r.files:7}{r.snapshots:6}{r.registro:9}{r.mib:12.1f}")
    media = sum(r.mib for r in rows if r.commits) / max(1, sum(1 for r in rows if r.commits))
    ritmo = mean_recent(rows, args.ritmo)
    print(f"\nmedia finestra: {media:.1f} MiB/giorno · ritmo di proiezione (ultimi {args.ritmo} "
          f"giorni con commit): {ritmo:.1f} MiB/giorno · fotografie complete: "
          f"{sum(r.snapshots for r in rows)} · commit del solo registro: {sum(r.registro for r in rows)}")
    if skipped:
        print(f"[i] commit saltati (genitore assente nel clone): {skipped}")

    size_kb = github_size_kb(args.repo) if args.repo else None
    if size_kb is not None:
        current_mib = size_kb / 1024
        giorni = days_to_target(current_mib, ritmo)
        testa = f"github: {size_kb} KB ≈ {current_mib:.1f} MiB"
        if giorni is None:
            print(f"{testa} · ritmo non positivo: nessuna proiezione")
        else:
            print(f"{testa} · ai {ritmo:.1f} MiB/giorno i {TARGET_MIB:.0f} MiB raccomandati "
                  f"arrivano in ~{giorni:.0f} giorni")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
