"""Resolve local changes that block the AgentOne self-update.

The update pipeline deliberately refuses a dirty worktree (``launcher.updates``).
These helpers are the opt-in, staff-only ways out of that state:

* ``undo_local_changes`` stashes everything, keeping the changes recoverable;
* ``merge_local_changes`` stashes, runs the normal update, then reapplies the
  changes. Conflicts are either resolved by an explicit local/remote preference
  or reported back so the caller can open an LLM session.

Every destructive step is guarded by a current ``git status`` check and leaves
a stash reference in the result, so nothing is silently dropped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

from launcher.updates import UpdateError, _git_capture, run_update
from runtime.version import _status_paths, clear_version_cache

def _noop_log(*_args, **_kwargs):
    pass


def _root(path=None) -> Path:
    return Path(path or getattr(settings, "BASE_DIR", Path.cwd())).resolve()


def _dirty(root: Path, log) -> list[str]:
    raw = _git_capture(["status", "--porcelain"], root, "Checking worktree")
    paths = _status_paths(raw)
    if not paths:
        log("The worktree is already clean.", "success")
    return paths


def _stash(root: Path, label: str, log) -> str:
    log(f"Saving local changes to git stash: {label}")
    _git_capture(["stash", "push", "--include-untracked", "--message", label], root, "Saving local changes")
    ref = _git_capture(["rev-parse", "--verify", "refs/stash"], root, "Reading stash reference")
    log(f"Saved as stash {ref[:12]}.", "success")
    return ref


def _conflicts(root: Path) -> list[str]:
    raw = _git_capture(["diff", "--name-only", "--diff-filter=U"], root, "Listing conflicts")
    return [line for line in raw.splitlines() if line]


def _resolve_by_preference(root: Path, conflicts: list[str], preference: str, stash_ref: str, log) -> list[str]:
    """Resolve conflicted paths for an explicit 'local' or 'remote' preference.

    During ``git stash pop``, stage 2 (``--ours``) is the freshly updated remote
    code and stage 3 (``--theirs``) is the user's stashed change.
    """
    side = "--theirs" if preference == "local" else "--ours"
    log(f"Resolving {len(conflicts)} conflict(s) in favour of the {preference} side.")
    unresolved: list[str] = []
    for path in conflicts:
        try:
            _git_capture(["checkout", side, "--", path], root, f"Resolving {path}")
            _git_capture(["add", "--", path], root, f"Staging {path}")
        except UpdateError as exc:
            log(f"Could not resolve {path} automatically: {exc}", "warning")
            unresolved.append(path)
    if unresolved:
        return unresolved
    _git_capture(["reset", "--", *conflicts], root, "Unstaging resolved paths")
    _git_capture(["stash", "drop", stash_ref], root, "Dropping applied stash")
    log(f"Resolved {len(conflicts)} conflict(s); local changes are back in the worktree.", "success")
    return []


def _reload_manifests(root: Path, paths: list[str], log):
    if not any(p == ".agentone" or p.startswith(".agentone/") for p in paths):
        return
    log("Reloading manifests after restoring .agentone/ changes...")
    try:
        from registry.management.commands.reload_all import run_reload_all  # pylint: disable=import-outside-toplevel

        result = run_reload_all(str(root))
        log(result.get("summary", "Manifests reloaded."))
        for error in result.get("errors", []) or []:
            log(f"  {error}", "warning")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log(f"Manifest reload failed: {exc}", "warning")


def _schedule_restart(root: Path, update_result: dict, log):
    if update_result.get("status") != "updated" or update_result.get("restart") == "scheduled":
        return
    from launcher.restart import detect_restart_command, request_restart  # pylint: disable=import-outside-toplevel

    command = detect_restart_command(root)
    if command:
        request_restart(command, root=root)
        log(f"Scheduled service restart: {' '.join(command)}", "success")


def undo_local_changes(path=None, log=None) -> dict:
    """Move every local change into a named stash and leave the worktree clean."""
    log = log or _noop_log
    root = _root(path)
    paths = _dirty(root, log)
    if not paths:
        return {"status": "already_clean"}

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ref = _stash(root, f"AgentOne UI: local changes saved {stamp}", log)
    clear_version_cache()
    log("Local changes undone. They remain in git stash if you need them back.", "success")
    return {"status": "undone", "stash_ref": ref, "paths": paths}


def merge_local_changes(path=None, preference: str = "", log=None) -> dict:
    """Stash local changes, update, then reapply them.

    ``preference`` is ``local``, ``remote`` or empty. With an explicit
    preference, conflicting hunks are resolved deterministically; otherwise a
    ``conflict`` status is returned with the paths and stash reference so the
    caller can hand the job to an LLM session.
    """
    log = log or _noop_log
    root = _root(path)
    paths = _dirty(root, log)
    if not paths:
        return {"status": "already_clean"}

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    stash_ref = _stash(root, f"AgentOne UI: merge with update {stamp}", log)
    try:
        # The restart is ours to schedule: a service restart three seconds into
        # an update would kill this worker before the stash is reapplied.
        update_result = run_update(path=str(root), restart=False, log=log)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log(f"Update failed ({exc}); restoring your local changes.", "warning")
        restore_error = ""
        try:
            _git_capture(["stash", "pop", stash_ref], root, "Restoring local changes")
            clear_version_cache()
        except UpdateError as exc_restore:
            restore_error = f" Restoring them also failed: {exc_restore}."
        raise UpdateError(
            f"Update failed: {exc}. Your changes are still in stash {stash_ref}.{restore_error}"
        ) from exc

    try:
        _git_capture(["stash", "pop", stash_ref], root, "Reapplying local changes")
    except UpdateError as exc:
        conflicts = _conflicts(root)
        if not conflicts:
            raise UpdateError(
                f"Could not reapply local changes: {exc}. They are still in stash {stash_ref}."
            ) from exc
        log(f"Reapplying local changes conflicted in: {', '.join(conflicts)}", "warning")
        unresolved = conflicts
        if preference:
            unresolved = _resolve_by_preference(root, conflicts, preference, stash_ref, log)
        if not unresolved:
            _reload_manifests(root, paths, log)
            _schedule_restart(root, update_result, log)
            log("Local changes are still uncommitted; commit them to make future updates straightforward.", "warning")
            return {
                "status": "merged",
                "result": update_result,
                "paths": paths,
                "conflicts_resolved": conflicts,
                "preference": preference,
            }
        return {
            "status": "conflict",
            "result": update_result,
            "paths": paths,
            "conflicts": unresolved,
            "stash_ref": stash_ref,
            "preference": preference,
        }

    _reload_manifests(root, paths, log)
    _schedule_restart(root, update_result, log)
    log("Update complete and local changes reapplied.", "success")
    log("Local changes are still uncommitted; commit them to make future updates straightforward.", "warning")
    return {"status": "merged", "result": update_result, "paths": paths}
