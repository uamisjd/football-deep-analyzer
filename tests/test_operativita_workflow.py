"""Contratti di pubblicazione: i test del Python non bastano se il YAML li aggira."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def daily():
    return yaml.load((ROOT / ".github/workflows/daily.yml").read_text(), Loader=yaml.BaseLoader)


def test_notification_after_run_and_deploy_including_failure():
    wf = daily()
    notify = wf["jobs"]["notify"]
    assert notify["needs"] == ["run", "deploy"]
    assert "always()" in notify["if"]
    assert "default_branch" in notify["if"]
    commands = [s for s in notify["steps"] if "run" in s]
    assert len(commands) == 1
    assert commands[0]["run"] == "python scripts/ci_alert.py on-result"
    assert commands[0]["env"]["FDA_RUN_RESULT"] == "${{ needs.run.result }}"
    assert commands[0]["env"]["FDA_DEPLOY_RESULT"] == "${{ needs.deploy.result }}"
    assert not any("ci_alert.py" in s.get("run", "") for s in wf["jobs"]["run"]["steps"])


def test_daily_uses_isolated_publish_and_preserves_diagnostic_logs():
    steps = daily()["jobs"]["run"]["steps"]
    publish = next(s for s in steps if "scripts.pubblica_dati" in s.get("run", ""))
    assert "--full" in publish["run"]
    assert "git reset" not in publish["run"] and "git rebase" not in publish["run"]
    artifact = next(s for s in steps if s.get("with", {}).get("name", "").startswith("run-log-"))
    assert artifact["if"] == "always()"
    assert all(name in artifact["with"]["path"] for name in ("run.log", "verify.log", "parita.log", "resa375.log"))
    assert steps.index(artifact) > steps.index(publish)


def test_permissions_are_scoped_to_jobs():
    wf = daily()
    assert wf["permissions"] == {"contents": "read"}
    assert wf["jobs"]["run"]["permissions"] == {"contents": "write"}
    assert wf["jobs"]["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}
    assert wf["jobs"]["notify"]["permissions"] == {"contents": "read", "actions": "read", "issues": "write"}


def test_ci_builds_site_and_executes_all_gates():
    wf = yaml.load((ROOT / ".github/workflows/tests.yml").read_text(), Loader=yaml.BaseLoader)
    assert wf["jobs"]["site"]["needs"] == "test"
    commands = "\n".join(s.get("run", "") for s in wf["jobs"]["site"]["steps"])
    for command in ("fda build", "scripts/verify_site.py", "scripts/parita_schede.py", "scripts.resa_375"):
        assert command in commands
    assert "set -euo pipefail" in commands


def test_actions_pinned_and_python_constrained():
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        wf = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        for job in wf["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert re.fullmatch(r"[\w/-]+@[a-f0-9]{40}", step["uses"]), path
                if "pip install" in step.get("run", "") and "-e" in step["run"]:
                    assert "-c requirements-ci.txt" in step["run"], path


def test_browser_check_is_a_required_ci_job():
    wf = yaml.load((ROOT / ".github/workflows/tests.yml").read_text(), Loader=yaml.BaseLoader)
    browser = wf["jobs"]["browser"]
    assert browser["needs"] == "site"
    commands = "\n".join(s.get("run", "") for s in browser["steps"])
    assert "npm ci" in commands
    assert "npm run test:browser" in commands
    assert not browser.get("continue-on-error")


def test_ci_inputs_are_environment_not_shell_source():
    step = next(s for s in daily()["jobs"]["run"]["steps"] if "fda daily" in s.get("run", ""))
    assert "${{" not in step["run"]
    assert '"${ARGS[@]}"' in step["run"]
