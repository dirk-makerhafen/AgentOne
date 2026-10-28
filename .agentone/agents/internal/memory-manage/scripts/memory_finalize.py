"""Advance a memory node's manifest after its synthesizer session finished.

``memory_merge`` spawns one ``memory-manage`` subtask per memory node and
schedules this task with the child's task call as its first argument.  The
framework auto-awaits that call, so this function only runs once the
synthesizer is done and receives its ``final_result`` message.  The manifest is
validated and advanced here — the LLM never touches ``.memory_sources.md``.
"""

from __future__ import annotations

from typing import Any

from runtime.memory.finalize import finalize_memory

#: Keep the synthesizer's summary short in the task result payload.
MAX_RESULT_CHARS = 500


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


def memory_finalize(
    _session: Any,
    result: Any = None,
    target_dir: str = "",
    started_at: float | str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Validate one synthesized node and advance its manifest.

    Args:
        _session: The calling session (bound automatically).
        result: The synthesizer's final result message, resolved by the
            framework from the awaited task call.
        target_dir: Absolute path of the node that was synthesized (the
            directory containing ``.memory_sources.md``).
        started_at: Unix timestamp when synthesis was dispatched; at least one
            output file must be newer than this.

    Returns:
        ``(True, {"status": "success", ...})`` when the manifest advanced,
        otherwise ``(False, {"status": "error", "message": ...})``.
    """
    ok, payload = finalize_memory(target_dir, started_at=started_at)
    if ok:
        summary = _result_text(result)
        if summary:
            payload["synthesizer_result"] = summary
    return ok, payload
