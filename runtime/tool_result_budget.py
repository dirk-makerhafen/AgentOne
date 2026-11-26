"""Keep oversized tool output out of the LLM prompt.

Three layers, mirroring the pattern used by Hermes:

1. Tools cap their own output (for example ``webFetch`` at 15k chars/page).
2. A single oversized result is persisted to ``<session>/cache/tool-output/``
   and replaced by a short preview plus a ``<persisted-output>`` pointer.
3. After all results of one assistant turn are collected, the aggregate budget
   is enforced: the largest non-persisted results are spilled until the whole
   turn fits.

The read tool is pinned to no limit so persisting its output cannot create a
persist -> read -> persist loop.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

# Lower than Hermes' 100k/200k defaults: AgentOne sessions frequently use
# small/free-tier models where 200k chars is already most of the window.
PER_RESULT_CHARS = 20_000
TURN_BUDGET_CHARS = 80_000
PREVIEW_CHARS = 1_500
STORAGE_DIRNAME = "tool-output"
PINNED_TOOLS = frozenset({"filesystem.read"})

PERSISTED_OUTPUT_TAG = "<persisted-output>"
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


def generate_preview(content: str, max_chars: int = PREVIEW_CHARS) -> tuple[str, bool]:
    """Truncate at the last newline inside ``max_chars``; report if cut."""
    if len(content) <= max_chars:
        return content, False
    preview = content[:max_chars]
    newline = preview.rfind("\n")
    if newline > max_chars // 2:
        preview = preview[:newline + 1]
    return preview, True


def storage_dir_for(session: Any | None = None) -> Path | None:
    """Session-private folder for spilled results, or None if unavailable."""
    if session is not None:
        try:
            from runtime.session_folder import ensure_session_dir  # pylint: disable=import-outside-toplevel

            return ensure_session_dir(session) / "cache" / STORAGE_DIRNAME
        except Exception:  # pylint: disable=broad-exception-caught
            return None
    env_dir = os.environ.get("AGENTONE_SESSION_DIR")
    return Path(env_dir) / "cache" / STORAGE_DIRNAME if env_dir else None


def _safe_filename(tool_name: str, tool_call_id: str) -> str:
    identity = f"{tool_name}-{tool_call_id}"
    stem = _UNSAFE_FILENAME_CHARS.sub("_", identity).strip("._-")[:100].rstrip("._-") or "tool_result"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{stem}_{digest}.txt"


def _persisted_message(preview: str, has_more: bool, original_chars: int, path: str) -> str:
    size = f"{original_chars / 1024:.1f} KB" if original_chars < 1024 * 1024 else f"{original_chars / 1024 / 1024:.1f} MB"
    message = (
        f"{PERSISTED_OUTPUT_TAG}\n"
        f"This tool result was too large ({original_chars:,} characters, {size}).\n"
        f"Full output saved to: {path}\n"
        "Use filesystem.read(path, offset, limit) — or filesystem.grep(path=..., "
        "pattern=...) — to inspect specific sections.\n\n"
        f"Preview (first {len(preview)} chars):\n"
        f"{preview}"
    )
    if has_more:
        message += "\n..."
    return message + f"\n{PERSISTED_OUTPUT_TAG.replace('<', '</')}"


def persist_tool_result(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    content: str,
    tool_name: str,
    tool_call_id: str,
    session: Any | None = None,
    threshold: int | None = None,
    storage_dir: Path | None = None,
) -> str:
    """Persist one oversized result and return its inline replacement.

    Returns the original content when below ``threshold``. If the file cannot
    be written, falls back to an inline-truncated marker so no output is lost
    silently.
    """
    if tool_name in PINNED_TOOLS:
        return content
    limit = PER_RESULT_CHARS if threshold is None else threshold
    if len(content) <= limit or PERSISTED_OUTPUT_TAG in content:
        return content

    preview, has_more = generate_preview(content)
    directory = storage_dir if storage_dir is not None else storage_dir_for(session)
    if directory is None:
        return (
            f"{preview}\n\n[Truncated: tool response was {len(content):,} chars; "
            "no session storage is available to save the full output.]"
        )

    try:
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            pass
        path = directory / _safe_filename(tool_name, tool_call_id)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return (
            f"{preview}\n\n[Truncated: tool response was {len(content):,} chars; "
            f"full output could not be saved: {exc}]"
        )

    return _persisted_message(preview, has_more, len(content), str(path))


def _text_of(content: Any) -> str:
    """Text length for a message content value (str or OpenAI-style parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def enforce_turn_budget(
    tool_messages: list[dict[str, Any]],
    session: Any | None = None,
    storage_dir: Path | None = None,
    budget: int = TURN_BUDGET_CHARS,
) -> list[dict[str, Any]]:
    """Spill the largest non-persisted results until the turn fits.

    Mutates and returns ``tool_messages``. Each message needs ``content``;
    ``tool_call_id`` and ``tool_name`` improve the saved filename. Messages
    with non-string content (image blocks) are left alone.
    """
    def size(msg: dict[str, Any]) -> int:
        return len(_text_of(msg.get("content")))

    total = sum(size(msg) for msg in tool_messages)
    if total <= budget:
        return tool_messages

    candidates = [
        (index, size(msg))
        for index, msg in enumerate(tool_messages)
        if isinstance(msg.get("content"), str) and PERSISTED_OUTPUT_TAG not in msg["content"]
    ]
    candidates.sort(key=lambda item: item[1], reverse=True)

    for index, original_size in candidates:
        if total <= budget:
            break
        msg = tool_messages[index]
        replacement = persist_tool_result(
            content=msg["content"],
            tool_name=str(msg.get("tool_name") or "tool_result"),
            tool_call_id=str(msg.get("tool_call_id") or index),
            session=session,
            threshold=0,
            storage_dir=storage_dir,
        )
        if replacement != msg["content"]:
            total += len(replacement) - original_size
            msg["content"] = replacement
    return tool_messages
