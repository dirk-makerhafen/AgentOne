"""Shared implementation of the memory-improvement proposal flow.

Proposals live in ``improvements.md`` files written by the memory synthesizer
(``.agentone/agents/internal/memory-manage/scripts/playbook.py``).  They are
the upper rungs of the capability ladder: a prompt edit, a skill, a tool, a
standalone script, or a harness fix.  The memory loop never applies them.

This module owns the parts that must not drift between the ``memory_improvements``
agent tool and the Memory UI:

* which ``improvements.md`` files are in scope;
* deduplication by proposal fingerprint (most specific scope wins);
* filing a proposal as a **backlog** work item, and detecting an already-filed
  one via the stable body marker.

Nothing here writes code, edits a manifest, or changes a proposal's status.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Optional

#: Proposals that should become visible work.  Prompt edits are included:
#: they still need a human/assistant decision, and a backlog item is the only
#: durable reminder.  Nothing here is auto-applied or auto-promoted.
QUEUEABLE_KINDS = ("prompt", "system_prompt", "skill", "tool", "script", "harness")

#: Hard cap on scanned files, so a huge memory tree cannot stall a turn.
MAX_FILES = 500

#: Marker appended to a work item body; dedupe relies on it staying stable.
MARKER = "[agentone-improvement:{fingerprint}]"
MARKER_PREFIX = "[agentone-improvement:"

_MARKER_RE = re.compile(re.escape(MARKER_PREFIX) + r"([^\]\s]+)\]")


def schema_module() -> Any:
    """Return the memory-manage ``playbook`` schema module."""
    from runtime.memory_playbook import schema_module as _schema_module

    return _schema_module()


# ---------------------------------------------------------------------------
# Discovery / collection
# ---------------------------------------------------------------------------


def proposal_files(
    roots: Iterable[tuple[str, Any]],
) -> list[tuple[str, Path]]:
    """Return ``(scope_label, path)`` for every improvements.md under *roots*.

    *roots* is an iterable of ``(label, memory_root)`` pairs, most specific
    first.  The order is preserved: callers rely on it for deduplication.
    """
    schema = schema_module()
    found: list[tuple[str, Path]] = []
    for label, root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob(schema.IMPROVEMENTS_FILENAME)):
            found.append((label, path))
            if len(found) >= MAX_FILES:
                return found
    return found


def collect_proposals(
    roots: Iterable[tuple[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load every proposal in scope; return ``(proposals, warnings)``.

    The same proposal consolidated at several layers appears once: the first
    (most specific) scope wins.
    """
    schema = schema_module()
    proposals: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for label, path in proposal_files(roots):
        try:
            loaded = schema.load_improvements(path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            warnings.append(f"{path}: {exc}")
            continue
        for proposal in loaded.get("proposals") or []:
            fingerprint = str(proposal.get("fingerprint") or "")
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            proposals.append(
                {**proposal, "source": label, "path": Path(path).as_posix()}
            )
    return proposals, warnings


def select_proposals(
    proposals: list[dict[str, Any]],
    fingerprints: Optional[Iterable[str]] = None,
    kinds: Optional[Iterable[str]] = None,
) -> list[dict[str, Any]]:
    """Filter *proposals* by fingerprint/id and kind, dropping retired ones."""
    wanted = {str(item).strip() for item in (fingerprints or []) if str(item).strip()}
    kind_set = {str(item).strip() for item in (kinds or []) if str(item).strip()}
    out = []
    for proposal in proposals:
        if proposal.get("status") == "retired":
            continue
        if (
            wanted
            and proposal.get("fingerprint") not in wanted
            and proposal.get("id") not in wanted
        ):
            continue
        if kind_set and proposal.get("kind") not in kind_set:
            continue
        out.append(proposal)
    return out


# ---------------------------------------------------------------------------
# Work-item rendering
# ---------------------------------------------------------------------------


def proposal_body(proposal: dict[str, Any]) -> str:
    """Return the work-item body for *proposal* (including its dedupe marker)."""
    lines = [
        f"Improvement proposal `{proposal.get('id')}` "
        f"(kind: {proposal.get('kind')}, scope: {proposal.get('scope')}).",
        "",
        f"**Summary:** {proposal.get('summary') or '(none)'}",
        "",
        f"**Detail:** {proposal.get('detail') or '(none)'}",
    ]
    if proposal.get("trigger"):
        lines += ["", f"**Trigger:** {proposal['trigger']}"]
    if proposal.get("acceptance"):
        lines += ["", f"**Acceptance:** {proposal['acceptance']}"]
    evidence = proposal.get("evidence") or []
    if evidence:
        lines += ["", "**Evidence:** " + ", ".join(str(item) for item in evidence)]
    lines += [
        "",
        f"Source: `{proposal.get('path')}`",
        "",
        "This item was filed from a memory improvement proposal. Implement the",
        "change described above (and its acceptance check). Do not silently",
        "broaden the scope; file a follow-up instead.",
        "",
        MARKER.format(fingerprint=proposal.get("fingerprint")),
    ]
    return "\n".join(lines)


def proposal_title(proposal: dict[str, Any]) -> str:
    """Return the work-item title for *proposal* (capped at the field limit)."""
    summary = " ".join(str(proposal.get("summary") or "").split())
    title = f"[self-improvement/{proposal.get('kind')}] {summary}"
    return title[:255]


# ---------------------------------------------------------------------------
# Queued state
# ---------------------------------------------------------------------------


def queued_work_items() -> dict[str, dict[str, Any]]:
    """Return ``fingerprint -> {id, title, status}`` for already-filed proposals.

    One query: every work item created by this flow carries the marker in its
    body.  A malformed marker is ignored rather than breaking the page.
    """
    try:
        from server.models.workitems.work_item import WorkItem
    except Exception:  # pragma: no cover - import cannot fail in a live app
        return {}

    out: dict[str, dict[str, Any]] = {}
    rows = (
        WorkItem.objects.filter(body__contains=MARKER_PREFIX)
        .values_list("pk", "title", "status", "body")
    )
    for pk, title, status, body in rows:
        for fingerprint in _MARKER_RE.findall(body or ""):
            out.setdefault(
                fingerprint,
                {"id": pk, "title": title or f"Work item {pk}", "status": status},
            )
    return out


def queued_fingerprints() -> set[str]:
    """Return the set of proposal fingerprints that already have a work item."""
    return set(queued_work_items())


# ---------------------------------------------------------------------------
# Queueing
# ---------------------------------------------------------------------------


def queue_proposals(
    proposals: list[dict[str, Any]],
    project: Any = None,
    fingerprints: Optional[Iterable[str]] = None,
    kinds: Optional[Iterable[str]] = None,
    limit: int = 50,
    existing: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """File selected *proposals* as backlog work items.

    Returns ``(created, skipped)``.  Items are deduped by the body marker, so
    calling this twice does not duplicate work.  ``existing`` lets a caller
    pass a preloaded :func:`queued_work_items` map to avoid one query per row.
    """
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem

    selected = select_proposals(proposals, fingerprints, kinds)
    try:
        cap = max(0, int(limit))
    except (TypeError, ValueError):
        cap = 50
    selected = selected[:cap] if cap else selected

    queued = queued_work_items() if existing is None else existing
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for proposal in selected:
        if proposal.get("kind") not in QUEUEABLE_KINDS:
            skipped.append(
                {
                    "id": proposal.get("id"),
                    "reason": f"unknown proposal kind {proposal.get('kind')!r}",
                }
            )
            continue

        fingerprint = str(proposal.get("fingerprint") or "")
        current = queued.get(fingerprint)
        if current is not None:
            skipped.append(
                {
                    "id": proposal.get("id"),
                    "reason": "already queued",
                    "work_item_id": current.get("id"),
                }
            )
            continue

        item = WorkItem.objects.create(
            project=project,
            title=proposal_title(proposal),
            body=proposal_body(proposal),
            priority=60,
            status=WorkItemStatus.BACKLOG,
        )
        queued[fingerprint] = {
            "id": item.pk,
            "title": item.title,
            "status": item.status,
        }
        created.append(
            {
                "id": proposal.get("id"),
                "work_item_id": item.pk,
                "title": item.title,
            }
        )

    return created, skipped
