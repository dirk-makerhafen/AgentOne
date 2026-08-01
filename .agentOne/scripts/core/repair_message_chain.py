"""
Repair message chains corrupted by the compaction fork bug.

All messages not on the active chain (root → highest-PK tail) get
self-referencing ``prev_message`` so they never appear in
``filter(next_messages=None)`` queries.

Usage:
    # Dry-run (default)
    python3 -c "exec(open('.agentone/scripts/core/repair_message_chain.py').read())"

    # Apply fixes
    python3 -c "exec(open('.agentone/scripts/core/repair_message_chain.py').read()); repair_all(dry_run=False)"
"""

from __future__ import annotations

from typing import Any


def _find_active_chain(messages: list) -> set[int]:
    """Walk from lowest-PK root; at forks pick the branch with highest-PK tail."""
    children: dict[int, list[int]] = {}
    roots: set[int] = set()
    for m in messages:
        pid = m.prev_message_id
        children.setdefault(m.pk, [])
        if pid is None:
            roots.add(m.pk)
        else:
            children.setdefault(pid, []).append(m.pk)
    for pid in children:
        children[pid].sort()

    if not roots:
        return set()

    active: set[int] = set()
    stack = [min(roots)]
    while stack:
        mid = stack.pop()
        if mid in active:
            continue
        active.add(mid)
        kids = children.get(mid, [])
        if len(kids) == 1:
            stack.append(kids[0])
        elif len(kids) > 1:
            def _subtree_max(n: int, seen: set[int]) -> int:
                if n in seen:
                    return n
                seen.add(n)
                mx = n
                for c in children.get(n, []):
                    mx = max(mx, _subtree_max(c, seen))
                return mx
            scored = [(k, _subtree_max(k, set())) for k in kids]
            scored.sort(key=lambda x: -x[1])
            stack.append(scored[0][0])
    return active


def _in_cycle(mid: int, prev_map: dict[int, int | None]) -> bool:
    """Return True if *mid* is part of a prev_message cycle."""
    visited: set[int] = set()
    cur: int | None = mid
    while cur is not None:
        if cur in visited:
            return True
        visited.add(cur)
        cur = prev_map.get(cur)
    return False


def repair_session(session_id: int, dry_run: bool = True) -> list[dict[str, Any]]:
    from server.models.sessions.session import SessionModel
    from runtime.session.session import Session
    from server.models.message import Message

    session_model = SessionModel.objects.get(pk=session_id)
    session = Session(session_model=session_model)
    messages = list(session.get_messages().order_by("pk"))
    if not messages:
        return []

    active = _find_active_chain(messages)
    prev_map = {m.pk: m.prev_message_id for m in messages}
    actions: list[dict[str, Any]] = []

    for m in messages:
        mid = m.pk
        if mid in active:
            continue
        in_cycle = _in_cycle(mid, prev_map)
        actions.append({
            "action": "self_ref_orphan_tail",
            "message_id": mid,
            "old_prev": m.prev_message_id,
            "new_prev": mid,
            "in_cycle": in_cycle,
        })
        if not dry_run:
            Message.objects.filter(pk=mid).update(prev_message=mid)

    return actions


def repair_all(dry_run: bool = True) -> list[dict[str, Any]]:
    from server.models.sessions.session import SessionModel
    results: list[dict[str, Any]] = []
    for session in SessionModel.objects.all().iterator():
        actions = repair_session(session.pk, dry_run=dry_run)
        if actions:
            results.append({"session_id": session.pk, "actions": actions})
    return results


if __name__ == "__main__":
    import sys
    dry_run = "--write" not in sys.argv
    print("=== DRY RUN ===" if dry_run else "=== APPLYING FIXES ===")
    for r in repair_all(dry_run=dry_run):
        total = len(r["actions"])
        cycles = sum(1 for a in r["actions"] if a.get("in_cycle"))
        print(f"  Session {r['session_id']}: {total} orphan(s) ({cycles} in cycles)")
