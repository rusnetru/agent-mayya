"""Git-based self-update (replaces exe deployment).

The agent is deployed as a working git clone on the user's machine; "updating"
means pulling new commits from origin. This module wraps that as an operation
the agent itself (or a human via update.ps1) can call safely:

- refuses to update over uncommitted local changes (no silent data loss)
- fast-forward only (never auto-merges/rebases — a failed ff-only pull is a
  clear signal that something needs human attention)
- reports whether dependencies (requirements.txt) changed, so the caller
  knows to reinstall before restarting the agent
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateResult:
    updated: bool
    before_commit: str
    after_commit: str
    message: str
    dependencies_changed: bool = False


def _run_git(args: list[str], repo_path: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo_path), capture_output=True, text=True
    )


def current_commit(repo_path: str | Path) -> str:
    result = _run_git(["rev-parse", "HEAD"], repo_path)
    return result.stdout.strip()


def has_uncommitted_changes(repo_path: str | Path) -> bool:
    result = _run_git(["status", "--porcelain"], repo_path)
    return bool(result.stdout.strip())


def check_for_updates(repo_path: str | Path) -> bool:
    """True if origin has commits not yet present locally on this branch."""
    _run_git(["fetch"], repo_path)
    local = current_commit(repo_path)
    remote = _run_git(["rev-parse", "@{u}"], repo_path).stdout.strip()
    return bool(remote) and local != remote


def dependencies_changed(repo_path: str | Path, before: str, after: str) -> bool:
    if before == after:
        return False
    result = _run_git(["diff", "--name-only", before, after, "--", "requirements.txt"], repo_path)
    return bool(result.stdout.strip())


def self_update(repo_path: str | Path, allow_dirty: bool = False) -> UpdateResult:
    """Pull the latest commits via fast-forward merge only.

    Returns an UpdateResult describing what happened; never raises on a
    declined update (dirty tree / non-ff history) — those are reported via
    `updated=False` and `message`, since they're expected operational states,
    not exceptional ones.
    """
    before = current_commit(repo_path)

    if not allow_dirty and has_uncommitted_changes(repo_path):
        return UpdateResult(
            updated=False,
            before_commit=before,
            after_commit=before,
            message="uncommitted local changes — refusing to update",
        )

    _run_git(["fetch"], repo_path)
    pull = _run_git(["pull", "--ff-only"], repo_path)
    after = current_commit(repo_path)

    if pull.returncode != 0:
        return UpdateResult(
            updated=False,
            before_commit=before,
            after_commit=after,
            message=pull.stderr.strip() or "git pull failed",
        )

    updated = before != after
    return UpdateResult(
        updated=updated,
        before_commit=before,
        after_commit=after,
        message=pull.stdout.strip() or "already up to date",
        dependencies_changed=dependencies_changed(repo_path, before, after) if updated else False,
    )
