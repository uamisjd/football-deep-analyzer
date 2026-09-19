"""Test per l'allerta automatica su guasto/ripristino CI (scripts/ci_alert.py)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from scripts import ci_alert


def test_get_ci_context_defaults(monkeypatch) -> None:
    for k in [
        "GITHUB_SERVER_URL",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_SHA",
        "GITHUB_REF_NAME",
        "GITHUB_EVENT_NAME",
        "GITHUB_WORKFLOW",
    ]:
        monkeypatch.delenv(k, raising=False)

    ctx = ci_alert.get_ci_context()
    assert ctx["repo"] == "uamisjd/football-deep-analyzer"
    assert ctx["workflow"] == "daily"
    assert ctx["ref"] == "main"
    assert "time_utc" in ctx
    assert "time_it" in ctx


def test_get_ci_context_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "testuser/testrepo")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "42")
    monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_WORKFLOW", "daily")

    ctx = ci_alert.get_ci_context()
    assert ctx["repo"] == "testuser/testrepo"
    assert ctx["run_id"] == "123456789"
    assert ctx["run_number"] == "42"
    assert ctx["short_sha"] == "abcdef1"
    assert ctx["run_url"] == "https://github.com/testuser/testrepo/actions/runs/123456789"
    assert ctx["commit_url"] == "https://github.com/testuser/testrepo/commit/abcdef1234567890"


def test_extract_diagnostics_missing_files(tmp_path: Path) -> None:
    p1 = tmp_path / "non_esiste.log"
    res = ci_alert.extract_diagnostics([p1])
    assert "Nessun file di log" in res


def test_extract_diagnostics_with_error(tmp_path: Path) -> None:
    p = tmp_path / "verify.log"
    p.write_text(
        "Avvio verifica sito...\n"
        "Controllo pagine in corso...\n"
        "Problemi trovati: [37] concordanza '1 assenti' errata\n"
        "Traceback (most recent call last):\n"
        "  File scripts/verify_site.py, line 120, in <module>\n"
        "AssertionError: 1 problemi rilevati\n",
        encoding="utf-8",
    )
    res = ci_alert.extract_diagnostics([p])
    assert "Log `verify.log`" in res
    assert "Problemi trovati:" in res
    assert "AssertionError" in res


def test_extract_diagnostics_tail_fallback(tmp_path: Path) -> None:
    p = tmp_path / "run.log"
    p.write_text("\n".join(f"riga {i}" for i in range(50)), encoding="utf-8")
    res = ci_alert.extract_diagnostics([p], max_lines_per_log=10)
    assert "Log `run.log`" in res
    assert "riga 49" in res
    assert "riga 0" not in res  # solo la coda


def test_format_bodies() -> None:
    ctx = {
        "repo": "uamisjd/football-deep-analyzer",
        "run_id": "100",
        "run_number": "10",
        "sha": "1234567890",
        "short_sha": "1234567",
        "ref": "main",
        "event": "schedule",
        "workflow": "daily",
        "run_url": "https://github.com/uamisjd/football-deep-analyzer/actions/runs/100",
        "commit_url": "https://github.com/uamisjd/football-deep-analyzer/commit/1234567890",
        "time_utc": "2026-09-19 12:00:00",
        "time_it": "2026-09-19 14:00:00",
        "tz_label": "CEST / UTC+2",
    }
    diag = "Log di errore di test"

    issue_body = ci_alert.format_failure_issue_body(ctx, diag)
    assert "🚨 Il workflow `daily` è fallito" in issue_body
    assert "[#10](https://github.com/uamisjd/football-deep-analyzer/actions/runs/100)" in issue_body
    assert "[1234567]" in issue_body
    assert "Log di errore di test" in issue_body

    comment_body = ci_alert.format_failure_comment_body(ctx, diag)
    assert "⚠️ Nuovo fallimento nel run [#10]" in comment_body

    rec_body = ci_alert.format_recovery_comment_body(ctx)
    assert "✅ Ripristinato" in rec_body
    assert "[#10]" in rec_body


def test_find_open_failure_issues() -> None:
    mock_out = json.dumps([
        {"number": 1, "title": "🚨 Fallimento run giornaliero (daily)", "url": "https://.../1"},
        {"number": 2, "title": "Altra issue non correlata", "url": "https://.../2"},
        {"number": 3, "title": "Fallimento run giornaliero su main", "url": "https://.../3"},
    ])
    with patch("scripts.ci_alert.run_gh_cmd", return_value=(0, mock_out, "")):
        issues = ci_alert.find_open_failure_issues("test/repo")
        assert len(issues) == 2
        assert issues[0]["number"] == 1
        assert issues[1]["number"] == 3


def test_handle_failure_creates_new_issue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    ctx = ci_alert.get_ci_context()
    calls: list[list[str]] = []

    def mock_run_gh(args: list[str], dry_run: bool = False):
        calls.append(args)
        if args[0] == "issue" and args[1] == "list":
            return 0, "[]", ""
        if args[0] == "issue" and args[1] == "create":
            return 0, "https://github.com/uamisjd/football-deep-analyzer/issues/5", ""
        return 0, "", ""

    with patch("scripts.ci_alert.run_gh_cmd", side_effect=mock_run_gh):
        code = ci_alert.handle_failure(ctx, [])
        assert code == 0
        assert any("create" in c for c in calls)


def test_handle_failure_comments_on_existing_issue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    ctx = ci_alert.get_ci_context()
    calls: list[list[str]] = []

    mock_issues = json.dumps([{"number": 7, "title": ci_alert.ISSUE_TITLE, "url": "https://.../7"}])

    def mock_run_gh(args: list[str], dry_run: bool = False):
        calls.append(args)
        if args[0] == "issue" and args[1] == "list":
            return 0, mock_issues, ""
        if args[0] == "issue" and args[1] == "comment":
            return 0, "", ""
        return 0, "", ""

    with patch("scripts.ci_alert.run_gh_cmd", side_effect=mock_run_gh):
        code = ci_alert.handle_failure(ctx, [])
        assert code == 0
        assert any("comment" in c and "7" in c for c in calls)
        assert not any("create" in c for c in calls)


def test_handle_success_closes_issue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    ctx = ci_alert.get_ci_context()
    calls: list[list[str]] = []

    mock_issues = json.dumps([{"number": 8, "title": ci_alert.ISSUE_TITLE, "url": "https://.../8"}])

    def mock_run_gh(args: list[str], dry_run: bool = False):
        calls.append(args)
        if args[0] == "issue" and args[1] == "list":
            return 0, mock_issues, ""
        if args[0] == "issue" and args[1] == "close":
            return 0, "", ""
        return 0, "", ""

    with patch("scripts.ci_alert.run_gh_cmd", side_effect=mock_run_gh):
        code = ci_alert.handle_success(ctx)
        assert code == 0
        assert any("close" in c and "8" in c for c in calls)


def test_handle_success_noop_when_no_issues() -> None:
    ctx = ci_alert.get_ci_context()
    calls: list[list[str]] = []

    def mock_run_gh(args: list[str], dry_run: bool = False):
        calls.append(args)
        if args[0] == "issue" and args[1] == "list":
            return 0, "[]", ""
        return 0, "", ""

    with patch("scripts.ci_alert.run_gh_cmd", side_effect=mock_run_gh):
        code = ci_alert.handle_success(ctx)
        assert code == 0
        assert not any("close" in c for c in calls)


def test_run_gh_cmd_graceful_missing_gh(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _bin: None)
    code, _out, err = ci_alert.run_gh_cmd(["issue", "list"])
    assert code == 1
    assert "non trovato" in err


def test_dry_run_flag() -> None:
    ctx = ci_alert.get_ci_context()
    # Dry run non deve lanciare comandi reali
    code = ci_alert.handle_failure(ctx, [], dry_run=True)
    assert code == 0
    code2 = ci_alert.handle_success(ctx, dry_run=True)
    assert code2 == 0
