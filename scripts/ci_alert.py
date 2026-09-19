"""Segnala guasti e ripristini del run giornaliero (docs/41 §4, P1.1).

Perché esiste:
    Un run di GitHub Actions (`daily.yml`) che fallisce lascia il sito congelato
    all'ultimo deploy valido senza alcun avviso (il 19/09 sono state 14h27m di fermo
    silenzioso). Questo script automatizza l'allerta a costo zero:
    - In caso di fallimento (`on-failure`): apre una issue con titolo univoco
      «🚨 Fallimento run giornaliero (daily)», allegando timestamp (UTC e IT),
      link al run/commit ed estratto diagnostico dai log (`run.log`, `verify.log`,
      `parita.log`, `resa375.log`). Se una issue è già aperta, aggiunge un commento
      invece di aprirne di duplicate.
    - Al primo run successivo che torna verde (`on-success`): trova le issue di guasto
      aperte e le chiude in automatico con un commento di ripristino.

Uso:
    python scripts/ci_alert.py on-failure [--workflow daily] [--logs run.log verify.log ...]
    python scripts/ci_alert.py on-success [--workflow daily]
    python scripts/ci_alert.py --dry-run on-failure

Non fallisce mai con codice diverso da 0: se `gh` non è installato o i permessi non
sono sufficienti, emette un avviso su stderr ma non maschera l'errore originario del run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ISSUE_TITLE = "🚨 Fallimento run giornaliero (daily)"
ISSUE_LABEL = "bug"
DEFAULT_LOGS = ("run.log", "verify.log", "parita.log", "resa375.log")
ERROR_KEYWORDS = (
    "traceback",
    "error",
    "exception",
    "failed",
    "fallito",
    "problemi",
    "problema",
    "assertionerror",
    "non conformi",
    "troppo larghe",
    "exit 1",
)


def get_ci_context() -> dict[str, str]:
    """Raccoglie i metadati del contesto CI dalle variabili d'ambiente di GitHub Actions."""
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "uamisjd/football-deep-analyzer")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "0")
    sha = os.environ.get("GITHUB_SHA", "")
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    event = os.environ.get("GITHUB_EVENT_NAME", "schedule")
    workflow = os.environ.get("GITHUB_WORKFLOW", "daily")

    run_url = f"{server}/{repo}/actions/runs/{run_id}" if run_id else f"{server}/{repo}/actions"
    commit_url = f"{server}/{repo}/commit/{sha}" if sha else f"{server}/{repo}"

    # Orari formattati in UTC e ora italiana (UTC+2 d'estate, UTC+1 d'inverno)
    now_utc = datetime.now(UTC)
    # Calcolo fuso orario approssimato Europa/Roma (+2 da fine marzo a fine ottobre, +1 altrove)
    mese = now_utc.month
    it_offset = 2 if (3 < mese < 11) or (mese == 3 and now_utc.day >= 25) or (mese == 10 and now_utc.day < 25) else 1
    tz_it = timezone(timedelta(hours=it_offset))
    now_it = now_utc.astimezone(tz_it)
    tz_label = "CEST / UTC+2" if it_offset == 2 else "CET / UTC+1"

    return {
        "server_url": server,
        "repo": repo,
        "run_id": run_id,
        "run_number": run_number,
        "sha": sha,
        "short_sha": sha[:7] if sha else "HEAD",
        "ref": ref,
        "event": event,
        "workflow": workflow,
        "run_url": run_url,
        "commit_url": commit_url,
        "time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "time_it": now_it.strftime("%Y-%m-%d %H:%M:%S"),
        "tz_label": tz_label,
    }


def extract_diagnostics(log_files: list[Path | str], max_lines_per_log: int = 25) -> str:
    """Estrae gli estratti di errore o la coda dai file di log presenti."""
    blocks: list[str] = []
    for lf in log_files:
        p = Path(lf)
        if not p.is_file() or p.stat().st_size == 0:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = [ln.rstrip() for ln in content.splitlines() if ln.strip()]
            if not lines:
                continue

            # Cerca se ci sono righe con errori evidenti
            err_indices = [
                i
                for i, ln in enumerate(lines)
                if any(kw in ln.lower() for kw in ERROR_KEYWORDS)
            ]

            if err_indices:
                # Prende dal primo errore rilevato (o una finestra sensata)
                start_idx = max(0, err_indices[0] - 2)
                end_idx = min(len(lines), start_idx + max_lines_per_log)
                excerpt_lines = lines[start_idx:end_idx]
            else:
                # Altrimenti prende la coda del file
                excerpt_lines = lines[-max_lines_per_log:]

            excerpt = "\n".join(excerpt_lines)
            blocks.append(f"#### Log `{p.name}`\n```\n{excerpt}\n```")
        except Exception as exc:  # noqa: BLE001
            blocks.append(f"#### Log `{p.name}`\n*(errore lettura log: {exc})*")

    if not blocks:
        return "*(Nessun file di log diagnostico trovato o log vuoti)*"
    return "\n\n".join(blocks)


def format_failure_issue_body(ctx: dict[str, str], diag: str) -> str:
    """Formatta il corpo markdown della issue di allerta guasto."""
    return f"""## 🚨 Il workflow `{ctx['workflow']}` è fallito

Il run giornaliero su branch `{ctx['ref']}` è fallito e il sito è fermo all'ultimo deploy funzionante.

- **Data / Ora:** {ctx['time_it']} ({ctx['tz_label']}) · {ctx['time_utc']} UTC
- **Run Actions:** [#{ctx['run_number']}]({ctx['run_url']})
- **Evento trigger:** `{ctx['event']}`
- **Commit:** [{ctx['short_sha']}]({ctx['commit_url']})

### Diagnostica dai log

{diag}

---
*Segnalazione automatica da `daily.yml`. Quando un run successivo completerà con successo tutti i passaggi, questa issue verrà chiusa in automatico.*
"""


def format_failure_comment_body(ctx: dict[str, str], diag: str) -> str:
    """Formatta il corpo markdown del commento di aggiornamento su issue già aperta."""
    return f"""### ⚠️ Nuovo fallimento nel run [#{ctx['run_number']}]({ctx['run_url']})

- **Data / Ora:** {ctx['time_it']} ({ctx['tz_label']}) · {ctx['time_utc']} UTC
- **Evento trigger:** `{ctx['event']}`
- **Commit:** [{ctx['short_sha']}]({ctx['commit_url']})

### Diagnostica dai log

{diag}
"""


def format_recovery_comment_body(ctx: dict[str, str]) -> str:
    """Formatta il corpo markdown del commento di ripristino per chiudere la issue."""
    return f"""### ✅ Ripristinato

Il run giornaliero [#{ctx['run_number']}]({ctx['run_url']}) (commit [{ctx['short_sha']}]({ctx['commit_url']})) è terminato con **successo** su tutti i controlli:
- Raccolta dati, modelli e simulazioni completati
- Verifica sito (`verify_site`), parità schede e resa 375 px superate
- Commit dei dati e deploy su GitHub Pages eseguiti

*Issue chiusa automaticamente.*
"""


def run_gh_cmd(args: list[str], dry_run: bool = False) -> tuple[int, str, str]:
    """Esegue un comando gh, restituendo (returncode, stdout, stderr)."""
    if dry_run:
        print(f"[DRY-RUN] gh {' '.join(args)}")
        return 0, "{}", ""

    gh_bin = shutil.which("gh")
    if not gh_bin:
        msg = "gh CLI non trovato nel sistema: impossibile interagire con le issue di GitHub"
        print(f"avviso: {msg}", file=sys.stderr)
        return 1, "", msg

    try:
        proc = subprocess.run(
            [gh_bin, *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:  # noqa: BLE001
        msg = f"eccezione durante esecuzione gh: {exc}"
        print(f"avviso: {msg}", file=sys.stderr)
        return 1, "", msg


def find_open_failure_issues(repo: str, dry_run: bool = False) -> list[dict[str, Any]]:
    """Cerca le issue aperte associate al fallimento del daily."""
    code, out, _err = run_gh_cmd(
        ["issue", "list", "--repo", repo, "--state", "open", "--json", "number,title,url"],
        dry_run=dry_run,
    )
    if code != 0 or not out:
        return []
    try:
        items = json.loads(out)
        return [
            item
            for item in items
            if isinstance(item, dict)
            and (
                ISSUE_TITLE in item.get("title", "")
                or "Fallimento run giornaliero" in item.get("title", "")
            )
        ]
    except Exception as exc:  # noqa: BLE001
        print(f"avviso: errore parsing JSON issue list: {exc}", file=sys.stderr)
        return []


def write_step_summary(content: str) -> None:
    """Scrive sul summary del job in Actions se la variabile d'ambiente è presente."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as fp:
                fp.write(f"\n{content}\n")
        except Exception as exc:  # noqa: BLE001
            print(f"avviso: scrittura step summary fallita: {exc}", file=sys.stderr)


def handle_failure(
    ctx: dict[str, str],
    log_files: list[Path | str],
    dry_run: bool = False,
) -> int:
    """Gestisce il fallimento: apre una issue o aggiunge un commento se già aperta."""
    diag = extract_diagnostics(log_files)
    open_issues = find_open_failure_issues(ctx["repo"], dry_run=dry_run)

    if open_issues:
        target_issue = open_issues[0]
        issue_num = str(target_issue.get("number"))
        comment_body = format_failure_comment_body(ctx, diag)
        print(f"Aggiunta commento su issue #{issue_num} aperta...")
        code, _out, err = run_gh_cmd(
            ["issue", "comment", issue_num, "--repo", ctx["repo"], "--body", comment_body],
            dry_run=dry_run,
        )
        if code != 0:
            print(f"avviso: impossibile aggiungere commento a issue #{issue_num}: {err}", file=sys.stderr)
        else:
            print(f"Commento aggiunto con successo su issue #{issue_num}.")
    else:
        issue_body = format_failure_issue_body(ctx, diag)
        print("Creazione nuova issue di guasto...")
        # Prova con label bug, fallback senza label se la label non esiste
        cmd = [
            "issue",
            "create",
            "--repo",
            ctx["repo"],
            "--title",
            ISSUE_TITLE,
            "--label",
            ISSUE_LABEL,
            "--body",
            issue_body,
        ]
        code, out, err = run_gh_cmd(cmd, dry_run=dry_run)
        if code != 0:
            print(f"avviso: tentativo con label fallito ({err}), ritento senza label...", file=sys.stderr)
            cmd_nolabel = [
                "issue",
                "create",
                "--repo",
                ctx["repo"],
                "--title",
                ISSUE_TITLE,
                "--body",
                issue_body,
            ]
            code2, out, err2 = run_gh_cmd(cmd_nolabel, dry_run=dry_run)
            if code2 != 0:
                print(f"avviso: creazione issue fallita: {err2}", file=sys.stderr)
            else:
                print(f"Issue creata: {out}")
        else:
            print(f"Issue creata: {out}")

    write_step_summary(f"### 🚨 Segnalazione Guasto CI\n\n- Workflow `{ctx['workflow']}` fallito.\n- Run: [#{ctx['run_number']}]({ctx['run_url']})")
    return 0


def handle_success(ctx: dict[str, str], dry_run: bool = False) -> int:
    """Gestisce il successo: chiude eventuali issue di guasto aperte."""
    open_issues = find_open_failure_issues(ctx["repo"], dry_run=dry_run)
    if not open_issues:
        print("Nessuna issue di guasto aperta da chiudere.")
        return 0

    close_body = format_recovery_comment_body(ctx)
    for issue in open_issues:
        issue_num = str(issue.get("number"))
        print(f"Chiusura issue di guasto #{issue_num}...")
        code, _out, err = run_gh_cmd(
            [
                "issue",
                "close",
                issue_num,
                "--repo",
                ctx["repo"],
                "--comment",
                close_body,
                "--reason",
                "completed",
            ],
            dry_run=dry_run,
        )
        if code != 0:
            print(f"avviso: chiusura issue #{issue_num} fallita: {err}", file=sys.stderr)
        else:
            print(f"Issue #{issue_num} chiusa con successo.")

    write_step_summary(f"### ✅ Segnalazione Ripristino CI\n\n- Run [#{ctx['run_number']}]({ctx['run_url']}) verde: chiuse {len(open_issues)} issue di allerta.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Allerta automatica guasto/ripristino workflow Actions")
    parser.add_argument("action", choices=["on-failure", "on-success"], help="Azione da compiere")
    parser.add_argument("--workflow", default=None, help="Nome del workflow (default da GITHUB_WORKFLOW)")
    parser.add_argument(
        "--logs",
        nargs="*",
        default=list(DEFAULT_LOGS),
        help="Percorsi dei file di log da cui estrarre diagnostica",
    )
    parser.add_argument("--dry-run", action="store_true", help="Stampa le azioni senza chiamare le API GitHub")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ctx = get_ci_context()
    if args.workflow:
        ctx["workflow"] = args.workflow

    if args.action == "on-failure":
        return handle_failure(ctx, args.logs, dry_run=args.dry_run)
    if args.action == "on-success":
        return handle_success(ctx, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
