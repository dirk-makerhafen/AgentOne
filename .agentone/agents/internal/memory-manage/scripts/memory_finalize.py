"""Advance a memory node's manifest after its synthesizer session finished.

``memory_merge`` spawns one ``memory-manage`` subtask per memory node and
schedules this task with the child's task call as its first argument.  The
framework auto-awaits that call, so this function only runs once the
synthesizer is done and receives its ``final_result`` message.  The manifest is
validated and advanced here — the LLM never touches ``.memory_sources.md``.

Frontmatter is repaired in layers so a malformed playbook cannot wedge a node
in ``needs_update`` forever:

1. :mod:`playbook` quotes unsafe plain scalars and re-parses (no LLM).
2. If that fails, a ``memory-manage`` repair subagent rewrites the file and
   this task is chained again behind it.
3. If that also fails, the malformed file is quarantined (content preserved)
   and replaced by a valid empty skeleton so the node can advance.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any

from finalize import FRONTMATTER_ERROR_KINDS, finalize_memory

#: Keep the synthesizer's summary short in the task result payload.
MAX_RESULT_CHARS = 8000

#: One subagent repair attempt, then quarantine.  Prevents an LLM from
#: repeatedly producing the same malformed frontmatter in an endless chain.
MAX_REPAIR_ATTEMPTS = 1

REPAIR_AGENT = "memory-manage"
REPAIR_TASK = "memory_finalize"


def _result_text(result: Any) -> str:
    """Render the resolved synthesizer result as plain text (best effort)."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()[:MAX_RESULT_CHARS]
    parts = getattr(result, "parts", None)
    if parts is None:
        return ""
    try:
        text = "".join(str(part.to_string()) for part in parts.order_by("pk"))
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    return text.strip()[:MAX_RESULT_CHARS]


def _repair_prompt(target_dir: str, payload: dict[str, Any]) -> str:
    """Build the repair subagent's task prompt."""
    kind = payload.get("error_kind")
    filename = (
        "reflection.md" if kind == "playbook_frontmatter" else "improvements.md"
    )
    message = str(payload.get("message") or "malformed YAML frontmatter")
    return f"""You are repairing malformed YAML frontmatter in a memory node.

Target directory: `{target_dir}`
File to repair: `{target_dir}/{filename}`
Parser error: {message}

The file is markdown with YAML frontmatter delimited by `---` lines. Read it and
rewrite ONLY the frontmatter so it parses as valid YAML, preserving every
directive/proposal and its content. A plain scalar containing ": " (or " #")
must be wrapped in whole in double quotes, with internal quotes/backslashes
escaped. Do not drop, reword, or invent rules. Keep the markdown body unchanged.

Write the corrected file, then call `final_result` with a one-line summary.
Never touch `.memory_sources.md`, git metadata, or any other file.
"""


def _spawn_frontmatter_repair(
    _session: Any, target_dir: str, payload: dict[str, Any]
) -> tuple[Any, int] | None:
    """Spawn a single-use repair subtask; return ``(task_call, session_pk)``."""
    from server.models.enums.session_enums import SessionType

    try:
        from memory_merge import _access_overrides
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[memory_finalize] cannot load access overrides: {exc}", file=sys.stderr)
        return None

    try:
        child = _session.spawn_subagent(
            REPAIR_AGENT,
            name=f"memory-repair:{uuid.uuid4().hex[:12]}",
            description=f"repair frontmatter: {target_dir}",
            session_type=SessionType.SUBTASK_DELEGATE,
            group_key="memory:repair",
            allow_internal=True,
            access=_access_overrides(_session, Path(target_dir)),
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[memory_finalize] repair spawn failed: {exc}", file=sys.stderr)
        return None
    if child is None:
        return None
    try:
        call = child.add_user_message(_repair_prompt(target_dir, payload))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[memory_finalize] repair prompt failed: {exc}", file=sys.stderr)
        return None
    return call, child.model.pk


def _with_summary(payload: dict[str, Any], result: Any) -> dict[str, Any]:
    """Attach the synthesizer's short final summary when available."""
    summary = _result_text(result)
    if summary:
        payload["synthesizer_result"] = summary
    return payload


def _try_quarantine(
    target_dir: str, original: dict[str, Any], result: Any
) -> tuple[bool, dict[str, Any]]:
    """Last resort: preserve the bad file and advance the node anyway."""
    ok, payload = finalize_memory(target_dir, allow_quarantine=True)
    if not ok:
        return False, original
    payload["repair"] = "quarantine"
    payload["original_error"] = original
    return True, _with_summary(payload, result)


def memory_finalize(
    _session: Any,
    result: Any = None,
    target_dir: str = "",
    started_at: float | str | None = None,
    attempt: int = 0,
) -> tuple[bool, dict[str, Any]]:
    """Validate one synthesized node and advance its manifest.

    Args:
        _session: The calling session (bound automatically).
        result: The synthesizer's (or repair subagent's) final result message,
            resolved by the framework from the awaited task call.
        target_dir: Absolute path of the node that was synthesized (the
            directory containing ``.memory_sources.md``).
        started_at: Unix timestamp when synthesis was dispatched; at least one
            output file must be newer than this.
        attempt: Internal repair-chain counter.  Callers should leave it at 0.

    Returns:
        ``(True, {"status": "success", ...})`` when the manifest advanced,
        ``(True, {"status": "escalated", ...})`` when a repair subagent was
        dispatched and finalization was chained after it, or
        ``(False, {"status": "error", ...})`` when nothing could advance it.
    """
    try:
        attempt = max(0, int(attempt or 0))
    except (TypeError, ValueError):
        attempt = 0

    ok, payload = finalize_memory(target_dir, started_at=started_at)
    if ok:
        return True, _with_summary(payload, result)

    kind = payload.get("error_kind")
    if kind not in FRONTMATTER_ERROR_KINDS:
        return False, payload

    if attempt >= MAX_REPAIR_ATTEMPTS:
        return _try_quarantine(target_dir, payload, result)

    repair = _spawn_frontmatter_repair(_session, target_dir, payload)
    if repair is None:
        return _try_quarantine(target_dir, payload, result)
    repair_call, repair_session_pk = repair

    retry_task = _session.get_task(REPAIR_TASK) if _session is not None else None
    if retry_task is None:
        return _try_quarantine(target_dir, payload, result)

    # ``repair_call`` is an AgentTaskCall argument: the framework parks the
    # retry in WAITING_DEPENDENCY, awaits the repair subagent, then re-runs this
    # function with its final message as ``result``.  Use a fresh started_at so
    # the subagent's rewrite satisfies the output-freshness check.
    retry = retry_task.delay(
        repair_call,
        target_dir=target_dir,
        started_at=time.time(),
        attempt=attempt + 1,
    )
    return True, {
        "status": "escalated",
        "message": (
            "malformed frontmatter; repair subagent dispatched and "
            "finalization chained after it"
        ),
        "error_kind": kind,
        "attempt": attempt + 1,
        "repair_session_pk": repair_session_pk,
        "repair_call_pk": getattr(repair_call, "pk", None),
        "retry_call_pk": getattr(retry, "pk", None),
        "original_error": payload,
    }
