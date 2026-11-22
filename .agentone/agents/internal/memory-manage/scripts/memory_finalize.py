"""Advance a memory node's manifest after both synthesizer sessions finish.

``memory_merge`` spawns two ``memory-manage`` subtasks per memory node (one for
``memory.md``, one for ``reflections.md``) and schedules this task with both
task calls as its first arguments.  The framework auto-awaits them, so this
function only runs once both synthesizers are done.  The manifest is validated
and advanced here — the LLM never touches ``.memory_sources.md``.
"""

from __future__ import annotations

from typing import Any

from finalize import finalize_memory

#: Keep the synthesizer's summary short in the task result payload.
MAX_RESULT_CHARS = 8000


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
    memory_result: Any = None,
    reflections_result: Any = None,
    target_dir: str = "",
    started_at: float | str | None = None,
    attempt: int = 0,
) -> tuple[bool, dict[str, Any]]:
    """Validate one synthesized node and advance its manifest.

    Args:
        _session: The calling session (bound automatically).
        memory_result: The memory synthesizer's ``final_result`` message.
        reflections_result: The reflections synthesizer's ``final_result``.
        target_dir: Absolute path of the node that was synthesized.
        started_at: Unix timestamp when synthesis was dispatched; both output
            files must be newer than this.
        attempt: Kept for backward-compatible task signatures; unused.

    Returns:
        ``(True, {"status": "success", ...})`` when the manifest advanced, or
        ``(False, {"status": "error", ...})`` when it could not.
    """
    del _session, attempt
    ok, payload = finalize_memory(target_dir, started_at=started_at)
    if ok:
        summaries = {
            kind: text
            for kind, result in (
                ("memory", memory_result),
                ("reflections", reflections_result),
            )
            if (text := _result_text(result))
        }
        if summaries:
            payload["synthesizer_results"] = summaries
            payload["synthesizer_result"] = "; ".join(
                f"{kind}: {text}" for kind, text in summaries.items()
            )
    return ok, payload
