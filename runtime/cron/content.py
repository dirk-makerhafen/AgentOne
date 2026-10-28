"""Content handling for cron job messages.

A cron job stores its message as a :class:`GenericContent`.  The shape
depends on the dispatch target:

* ``function_type`` set (task/tool/command): the message is a JSON object
  holding the keyword arguments for the target.
* ``function_type`` empty: the message is plain text sent through
  ``ingest_user_message``.

All save paths (UI, assistant tools, loader) go through
:func:`build_cron_message` so the stored content type always matches the
dispatch target.
"""
from __future__ import annotations

import json
from typing import Any

from server.models.content import GenericContent


def normalize_function_type(function_type: Any) -> str:
    """Return a stripped ``function_type`` string (``""`` when unset)."""
    return str(function_type or "").strip()


def build_cron_message(message: Any, function_type: Any = "") -> GenericContent | None:
    """Return the ``GenericContent`` row for *message*.

    ``message`` may be a string (as typed in the UI/markdown), a mapping
    (parsed YAML/JSON), or ``None``.  Raises ``ValueError`` when a function
    target is selected but the message is not a JSON object.

    An empty message with a function target yields empty kwargs (``{}``);
    an empty message without one yields ``None``.
    """
    ftype = normalize_function_type(function_type)
    text: str | None
    if message is None:
        text = ""
    elif isinstance(message, str):
        text = message
    else:
        text = None  # mapping/list from YAML frontmatter

    if ftype:
        data: Any
        if text is None:
            data = message
        elif not text.strip():
            data = {}
        else:
            try:
                data = json.loads(text)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Message must be valid JSON when a function is selected."
                ) from exc
        if not isinstance(data, dict):
            raise ValueError(
                "Message must be a JSON object when a function is selected."
            )
        return GenericContent.from_data(data)

    if text is None:
        text = json.dumps(message)
    if not text:
        return None
    return GenericContent.from_text(text)
