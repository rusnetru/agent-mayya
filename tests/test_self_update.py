import subprocess
from pathlib import Path

import pytest

from src.update.self_update import (
    check_for_updates,
    current_commit,
    dependencies_changed,
    has_uncommitted_changes,
    self_update,
)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.email=test@test.com", "-c", "user.name=test", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def origin_and_clone(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(["init", "-b", "main"], origin)
    (origin / "requirements.txt").write_text("anthropic\n")
    (origin / "file.txt").write_text("v1\n")
    _git(["add", "."], origin)
    _git(["commit", "-m", "initial"], origin)

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(origin), str(clone)], capture_output=True, text=True, check=True)
    _git(["branch", "--set-upstream-to=origin/main", "main"], clone)

    return origin, clone


def test_current_commit_returns_hash(origin_and_clone):
    _, clone = origin_and_clone
    commit = current_commit(clone)
    assert len(commit) == 40


def test_has_uncommitted_changes_detects_dirty_tree(origin_and_clone):
    _, clone = origin_and_clone
    assert has_uncommitted_changes(clone) is False
    (clone / "file.txt").write_text("modified\n")
    assert has_uncommitted_changes(clone) is True


def test_check_for_updates_detects_new_remote_commit(origin_and_clone):
    origin, clone = origin_and_clone
    assert check_for_updates(clone) is False

    (origin / "file.txt").write_text("v2\n")
    _git(["add", "."], origin)
    _git(["commit", "-m", "update"], origin)

    assert check_for_updates(clone) is True


def test_self_update_pulls_new_commit(origin_and_clone):
    origin, clone = origin_and_clone
    before = current_commit(clone)

    (origin / "file.txt").write_text("v2\n")
    _git(["add", "."], origin)
    _git(["commit", "-m", "update"], origin)

    result = self_update(clone)
    assert result.updated is True
    assert result.before_commit == before
    assert result.after_commit != before
    assert (clone / "file.txt").read_text() == "v2\n"


def test_self_update_refuses_when_dirty(origin_and_clone):
    origin, clone = origin_and_clone
    (clone / "file.txt").write_text("local edit\n")

    (origin / "file.txt").write_text("v2\n")
    _git(["add", "."], origin)
    _git(["commit", "-m", "update"], origin)

    result = self_update(clone)
    assert result.updated is False
    assert "uncommitted" in result.message


def test_self_update_reports_no_update_when_already_current(origin_and_clone):
    _, clone = origin_and_clone
    result = self_update(clone)
    assert result.updated is False
    assert result.before_commit == result.after_commit


def test_dependencies_changed_detects_requirements_diff(origin_and_clone):
    origin, clone = origin_and_clone
    before = current_commit(clone)

    (origin / "requirements.txt").write_text("anthropic\nnetworkx\n")
    _git(["add", "."], origin)
    _git(["commit", "-m", "add dep"], origin)

    result = self_update(clone)
    assert result.updated is True
    assert result.dependencies_changed is True
    assert dependencies_changed(clone, before, result.after_commit) is True
