"""Prove end-to-end Git: commit, rebase e push su un'origine locale senza rete."""
import subprocess

import pytest

from scripts import pubblica_dati as pd

BRANCH = "arena/7c92c1a2-football-deep-analyzer"


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def repos(tmp_path):
    remote, root, other = (tmp_path / x for x in ("remote.git", "build", "other"))
    git(tmp_path, "init", "--bare", str(remote))
    git(tmp_path, "clone", str(remote), str(root))
    git(root, "checkout", "-b", BRANCH)
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    write(root, "data/processed/news.parquet", "old news")
    write(root, pd.REGISTRO, "old register")
    write(root, "docs/STATO.md", "old state")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    git(root, "push", "-u", "origin", BRANCH)
    git(tmp_path, "clone", "--branch", BRANCH, str(remote), str(other))
    git(other, "config", "user.email", "test@example.invalid")
    git(other, "config", "user.name", "Other")
    return root, other


@pytest.mark.parametrize("full", [True, False])
def test_dirty_build_survives_commit_rebase_and_push(repos, full):
    root, other = repos
    write(root, "data/processed/news.parquet", "new news")
    write(root, pd.REGISTRO, "new register")
    write(root, "site/index.html", "verified build")
    # Commit concorrente già su origine: obbliga davvero il rebase.
    write(other, "unrelated.txt", "concurrent")
    git(other, "add", ".")
    git(other, "commit", "-m", "concurrent")
    git(other, "push")
    before, head = git(root, "status", "--porcelain"), git(root, "rev-parse", "HEAD")
    assert pd.publish(root, BRANCH, full=full)
    assert git(root, "status", "--porcelain") == before
    assert git(root, "rev-parse", "HEAD") == head
    assert (root / "site/index.html").read_text() == "verified build"
    git(other, "pull", "--ff-only")
    assert (other / pd.REGISTRO).read_text() == "new register"
    assert (other / "data/processed/news.parquet").read_text() == ("new news" if full else "old news")
    assert (other / "unrelated.txt").read_text() == "concurrent"
    assert not (other / "site/index.html").exists()
    msg = git(other, "log", "-1", "--format=%B")
    assert (pd.SNAPSHOT_MARKER in msg) is full
    assert len(git(root, "worktree", "list", "--porcelain").split("worktree ")) == 2


@pytest.mark.parametrize("full", [True, False])
def test_no_changes_no_commit(repos, full):
    root, other = repos
    before = git(other, "rev-parse", "HEAD")
    assert not pd.publish(root, BRANCH, full=full)
    git(other, "pull", "--ff-only")
    assert git(other, "rev-parse", "HEAD") == before


def test_full_snapshot_new_and_deleted_tables_excludes_derived_database(repos):
    root, other = repos
    (root / "data/processed/news.parquet").unlink()
    write(root, "data/processed/new.parquet", "new")
    write(root, "data/processed/fda.duckdb", "derived")
    assert pd.publish(root, BRANCH, full=True)
    git(other, "pull", "--ff-only")
    assert not (other / "data/processed/news.parquet").exists()
    assert (other / "data/processed/new.parquet").read_text() == "new"
    assert not (other / "data/processed/fda.duckdb").exists()


def test_register_unchanged_does_not_push_other_dirty_tables(repos):
    root, _ = repos
    write(root, "data/processed/news.parquet", "new news")
    assert not pd.publish(root, BRANCH, full=False)
    assert (root / "data/processed/news.parquet").read_text() == "new news"


def test_conflicting_concurrent_register_fails_without_losing_build(repos):
    root, other = repos
    write(root, pd.REGISTRO, "our register")
    write(other, pd.REGISTRO, "concurrent register")
    git(other, "add", ".")
    git(other, "commit", "-m", "concurrent register")
    git(other, "push")
    before = git(root, "status", "--porcelain")
    with pytest.raises(subprocess.CalledProcessError):
        pd.publish(root, BRANCH, full=False)
    assert (root / pd.REGISTRO).read_text() == "our register"
    assert git(root, "status", "--porcelain") == before
    assert len(git(root, "worktree", "list", "--porcelain").split("worktree ")) == 2
    assert (other / pd.REGISTRO).read_text() == "concurrent register"


def test_push_race_retries_rebase(repos, monkeypatch):
    root, other = repos
    write(root, pd.REGISTRO, "new register")
    real_git, pushes = pd.git, []

    def race(work, *args):
        if args[0] == "push":
            pushes.append(1)
            if len(pushes) == 1:
                write(other, "race.txt", "new remote commit")
                git(other, "add", ".")
                git(other, "commit", "-m", "race")
                git(other, "push")
        return real_git(work, *args)

    monkeypatch.setattr(pd, "git", race)
    monkeypatch.setattr(pd.time, "sleep", lambda _: None)
    assert pd.publish(root, BRANCH, full=False)
    assert len(pushes) == 2
    git(other, "pull", "--ff-only")
    assert (other / pd.REGISTRO).read_text() == "new register"
    assert (other / "race.txt").exists()


def test_missing_register_fails_closed(repos):
    root, _ = repos
    (root / pd.REGISTRO).unlink()
    with pytest.raises(FileNotFoundError):
        pd.publish(root, BRANCH, full=False)
