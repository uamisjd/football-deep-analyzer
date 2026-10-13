"""Salva i dati in un worktree isolato: la build e i Parquet locali restano intatti.

Il daily modifica più tabelle ma nei run intermedi salva solo il registro preregistrato.
Un rebase nel checkout della build fallirebbe per le altre modifiche non committate.
Qui commit/rebase/push avvengono su una HEAD detached temporanea, mai sul working tree
che contiene il sito verificato. Un conflitto non viene ignorato: il run fallisce e allerta.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts.fotografia_dati import SNAPSHOT_MARKER

REGISTRO = "data/processed/prospettico.parquet"


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True, timeout=120)


def selected_paths(root: Path, full: bool) -> set[str]:
    """Include nuove tabelle e cancellazioni; esclude DuckDB/cache/artefatti ignorati."""
    if not full:
        if not (root / REGISTRO).is_file():
            raise FileNotFoundError(f"registro preregistrato assente: {REGISTRO}")
        return {REGISTRO}
    tracked = git(root, "ls-files", "-z", "data/processed").stdout.split("\0")
    paths = {p for p in tracked if p.endswith(".parquet")}
    paths.update(p.relative_to(root).as_posix() for p in (root / "data/processed").glob("*.parquet"))
    # Conserva il comportamento storico per eventuali checkpoint aggiornati dal daily.
    if (root / "docs/STATO.md").is_file():
        paths.add("docs/STATO.md")
    return paths


def publish(root: Path, branch: str, *, full: bool, attempts: int = 3) -> bool:
    """True se committa/pusha, False se non ci sono modifiche. Nessuna rete fuori git."""
    root = root.resolve()
    git(root, "check-ref-format", "--branch", branch)
    if attempts < 1:
        raise ValueError("attempts deve essere positivo")
    paths = selected_paths(root, full)
    with tempfile.TemporaryDirectory(prefix="fda-publish-") as tmp:
        work = Path(tmp) / "worktree"
        git(root, "worktree", "add", "--detach", str(work), "HEAD")
        try:
            for rel in sorted(paths):
                src, dst = root / rel, work / rel
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                else:
                    dst.unlink(missing_ok=True)
            if not paths:
                return False
            git(work, "add", "-A", "--", *sorted(paths))
            if not git(work, "diff", "--cached", "--name-only").stdout.strip():
                print("nessun dato nuovo da salvare")
                return False
            stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
            kind = "run" if full else "registro prospettico"
            args = ["commit", "-m", f"data: {kind} {stamp} UTC [skip ci]"]
            if full:
                args.extend(["-m", SNAPSHOT_MARKER])
            git(work, *args)
            for attempt in range(attempts):
                git(work, "fetch", "origin", branch)
                # FETCH_HEAD è la ref esatta appena letta, anche con un refspec ridotto.
                git(work, "rebase", "FETCH_HEAD")
                try:
                    git(work, "push", "origin", f"HEAD:refs/heads/{branch}")
                    print(f"salvato: {kind}")
                    return True
                except subprocess.CalledProcessError:
                    if attempt + 1 == attempts:
                        raise
                    time.sleep(attempt + 1)
            return False  # il ciclo termina sempre con return/raise
        finally:
            # --force rimuove soltanto il worktree TEMPORANEO, anche dopo conflitto.
            git(root, "worktree", "remove", "--force", str(work))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--branch", required=True)
    parser.add_argument("--full", choices=("true", "false"), required=True)
    args = parser.parse_args()
    try:
        publish(args.root, args.branch, full=args.full == "true")
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
