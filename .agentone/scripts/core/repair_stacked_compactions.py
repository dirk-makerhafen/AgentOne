"""
Repair message chains corrupted by the compaction PK-sort bug.

Symptom: compaction boundary markers got stacked in a contiguous run far
from the conversation tail (because ``compacted_messages.sort(key=pk)``
picked a mid-chain marker as "newest compacted").  As a result the first
COMPACTION marker when walking back from the tail sits hundreds of
messages away, so ``build_llm_context`` keeps the whole history in every
request, the context never shrinks, compaction fires after every turn and
the LLM prefix cache collapses.

Repair: reinsert the newest marker at the correct boundary (``keep_count``
messages from the tail), reconnect the old history across the marker run,
and self-reference every other stacked marker so the chain stays a single
linear list with exactly one tail.

Usage:
    # Dry-run (default)
    python3 -c "exec(open('.agentone/scripts/core/repair_stacked_compactions.py').read())"

    # Apply to every affected session
    python3 -c "exec(open('.agentone/scripts/core/repair_stacked_compactions.py').read()); repair_all(dry_run=False)"

    # Apply to one session
    python3 -c "exec(open('.agentone/scripts/core/repair_stacked_compactions.py').read()); repair_session(203, dry_run=False)"
"""

from __future__ import annotations

from typing import Any

from server.models.enums.message_enums import MessagePartType


def _walk_from_tail(messages: list) -> list:
    """Return the linear chain as a list of Message, newest first.

    Starts at the message with no ``next_messages`` children (the tail) and
    follows ``prev_message`` until the head.  Returns [] if the chain is not
    linear (no single tail, or a prev cycle).
    """
    children: dict[int, list[int]] = {}
    for m in messages:
        children.setdefault(m.pk, [])
        if m.prev_message_id is not None:
            children.setdefault(m.prev_message_id, []).append(m.pk)
    tails = [m for m in messages if not children.get(m.pk)]
    if len(tails) != 1:
        return []
    prev_map = {m.pk: m.prev_message_id for m in messages}
    by_id = {m.pk: m for m in messages}

    path: list = []
    seen: set[int] = set()
    cur = by_id[tails[0].pk]
    while cur is not None and cur.pk not in seen:
        seen.add(cur.pk)
        path.append(cur)
        cur = by_id.get(cur.prev_message_id) if cur.prev_message_id is not None else None
    return path


def _markers_in(messages: list) -> set[int]:
    ids = [m.pk for m in messages]
    from server.models.message import MessagePart

    comp = set(
        MessagePart.objects.filter(
            message_id__in=ids, type=MessagePartType.COMPACTION
        ).values_list("message_id", flat=True)
    )
    return comp


def repair_session(session_id: int, keep_count: int = 20, dry_run: bool = True) -> dict[str, Any]:
    """Repair stacked-compaction corruption in one session.

    Returns a dict describing the planned/applied changes.
    """
    from server.models.sessions.session import SessionModel
    from runtime.session.session import Session
    from server.models.message import Message

    session_model = SessionModel.objects.get(pk=session_id)
    session = Session(session_model=session_model)
    messages = list(session.get_messages().order_by("pk"))
    if not messages:
        return {"session_id": session_id, "status": "no_messages"}

    path = _walk_from_tail(messages)
    if not path:
        return {"session_id": session_id, "status": "chain_not_linear", "note": "run repair_message_chain first"}

    comp = _markers_in(path)
    marker_positions = [i for i, m in enumerate(path) if m.pk in comp]
    if not marker_positions:
        return {"session_id": session_id, "status": "no_markers"}

    first = marker_positions[0]
    if first <= keep_count:
        return {
            "session_id": session_id,
            "status": "ok",
            "first_marker_pos": first,
            "markers": len(marker_positions),
        }

    keep_count = min(keep_count, len(path) - 1)

    # Contiguous marker run starting at `first`.
    last = first
    while last + 1 < len(path) and path[last + 1].pk in comp:
        last += 1

    marker = path[first]
    stacked = path[first : last + 1]
    below = path[last + 1] if last + 1 < len(path) else None
    above = path[first - 1]

    kept_oldest = path[keep_count - 1]
    boundary_prev = path[keep_count]

    plan = {
        "session_id": session_id,
        "status": "repair",
        "tail": path[0].pk,
        "marker": marker.pk,
        "marker_run": [m.pk for m in stacked],
        "below": below.pk if below else None,
        "above": above.pk,
        "kept_oldest": kept_oldest.pk,
        "boundary_prev": boundary_prev.pk,
        "reinsert_after": boundary_prev.pk,
        "orphan_count": len(stacked) - 1,
    }

    if dry_run:
        return plan

    from django.db import transaction

    with transaction.atomic():
        # 1. Reinsert the marker at the boundary: boundary_prev -> marker -> kept_oldest.
        Message.objects.filter(pk=kept_oldest.pk).update(prev_message=marker)
        Message.objects.filter(pk=marker.pk).update(prev_message=boundary_prev)
        # 2. Reconnect the old history across the marker run.
        if below is not None:
            Message.objects.filter(pk=above.pk).update(prev_message=below)
        else:
            Message.objects.filter(pk=above.pk).update(prev_message=None)
        # 3. Orphan every other stacked marker (self-reference -> never a tail).
        for m in stacked:
            if m.pk != marker.pk:
                Message.objects.filter(pk=m.pk).update(prev_message=m.pk)

    return plan


def repair_all(dry_run: bool = True, keep_count: int = 20) -> list[dict[str, Any]]:
    from server.models.sessions.session import SessionModel

    results: list[dict[str, Any]] = []
    for session in SessionModel.objects.all().iterator():
        res = repair_session(session.pk, keep_count=keep_count, dry_run=dry_run)
        if res.get("status") in ("repair", "ok"):
            results.append(res)
    return results


if __name__ == "__main__":
    import sys

    dry_run = "--write" not in sys.argv
    print("=== DRY RUN ===" if dry_run else "=== APPLYING FIXES ===")
    for r in repair_all(dry_run=dry_run):
        if r.get("status") == "repair":
            print(
                f"  Session {r['session_id']}: marker {r['marker']} "
                f"run={r['marker_run']} -> reinsert after {r['reinsert_after']}, "
                f"orphan {r['orphan_count']} stacked marker(s)"
            )
        elif r.get("status") == "ok":
            print(f"  Session {r['session_id']}: already ok (first marker at pos {r['first_marker_pos']})")
