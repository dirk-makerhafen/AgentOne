"""List and file improvement proposals produced by the memory synthesizer.

The synthesizer writes ``improvements.md`` next to ``reflection.md``.  Those
proposals are the *upper rungs* of the capability ladder — a prompt edit, a
skill, a tool, a standalone script, or a harness fix.  They are never applied
by the memory loop.  This tool is the deliberate step between "proposed" and
"someone is working on it":

* ``action="list"`` (default) walks the session's memory scopes and returns
  the proposals it finds, without touching the database.
* ``action="queue"`` files selected proposals as **backlog** work items.  A
  backlog item does not dispatch; a human (or an assistant) promotes it to
  ``ready`` after reviewing the spec.  Items are deduped by proposal
  fingerprint, so running the queue twice does not duplicate work.

The scan/queue implementation lives in :mod:`runtime.memory_improvements` so
the Memory UI files exactly the same items.  Nothing here writes code, edits a
manifest, or changes a proposal's status.
"""

from __future__ import annotations

from typing import Any, Optional


def _collect(session: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Return ``(proposals, warnings)`` for the session's memory scopes."""
    from runtime.memory_improvements import collect_proposals
    from runtime.memory_playbook import scope_roots

    roots = [(label, root) for _kind, label, root in scope_roots(session)]
    return collect_proposals(roots)


def memory_improvements(
    _session: Any,
    action: str = "list",
    fingerprints: Optional[list[str]] = None,
    kinds: Optional[list[str]] = None,
    limit: int = 50,
    project: str = "",
) -> tuple[bool, dict[str, Any]]:
    """List improvement proposals, or file them as backlog work items.

    Proposals come from ``improvements.md`` files written by the memory
    synthesizer.  Use the default ``list`` action to inspect them; use
    ``queue`` to turn them into backlog work items.  Queued items are
    deliberately **not** ready: promoting one is a human decision.  Prompt
    edits are queued too, because a proposal that nobody sees is not a
    proposal.

    Args:
        _session: The calling session (bound automatically).
        action: ``"list"`` (default) or ``"queue"``.
        fingerprints: Optional list of proposal IDs or fingerprints to
            restrict the action to.  Empty means everything in scope.
        kinds: Optional list of kinds to restrict to (e.g.
            ``["harness", "skill"]``).  Empty means all kinds.
        limit: Maximum number of proposals to return or file.
        project: Project name for the created work items.  Defaults to the
            current session's project.

    Returns:
        ``(True, {...})`` with the proposals (``list``) or the created and
        skipped items (``queue``).  ``(False, {...})`` on a bad action.
    """
    from runtime.memory_improvements import queue_proposals, select_proposals

    action = str(action or "list").strip().lower()
    if action not in ("list", "queue"):
        return False, {"error": "action must be 'list' or 'queue'."}

    proposals, warnings = _collect(_session)
    selected = select_proposals(proposals, fingerprints, kinds)
    try:
        cap = max(0, int(limit))
    except (TypeError, ValueError):
        cap = 50
    selected = selected[:cap] if cap else selected

    if action == "list":
        return True, {
            "status": "success",
            "count": len(selected),
            "proposals": [
                {
                    key: proposal.get(key)
                    for key in (
                        "id",
                        "fingerprint",
                        "kind",
                        "scope",
                        "status",
                        "summary",
                        "source",
                        "path",
                    )
                }
                for proposal in selected
            ],
            "warnings": warnings,
        }

    project_obj, project_error = _resolve_project(_session, project)
    if project_error:
        return False, {"error": project_error}

    created, skipped = queue_proposals(
        proposals,
        project=project_obj,
        fingerprints=fingerprints,
        kinds=kinds,
        limit=cap,
    )
    return True, {
        "status": "success",
        "created": created,
        "skipped": skipped,
        "warnings": warnings,
        "count": len(created),
    }


def _resolve_project(_session: Any, name: str) -> tuple[Any, str]:
    """Return ``(project, error)``; the default is the session's project."""
    current = _session.get_project()
    name = str(name or "").strip()
    if not name:
        return current, ""
    from server.models.project import Project

    project = Project.objects.filter(name=name).first()
    if project is None:
        return None, f"No project named '{name}'."
    return project, ""
