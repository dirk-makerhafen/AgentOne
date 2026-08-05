"""
Shared normalization for LLM tool-call arguments.

LLMs sometimes double-escape non-ASCII characters in tool arguments:
instead of emitting ``{"path": "...Kontoschließung.md"}`` they emit
``{"path": "...Kontoschlie\\u00dfung.md"}`` — a literal ``\\u00df``
(six characters) that survives a single ``json.loads()`` as the text
``\\u00df``.  The filesystem has the real ``ß`` (``\\xc3\\x9f``), so the
tool then fails with "File not found".

``decode_literal_unicode_escapes`` re-decodes only ``\\uXXXX`` /
``\\UXXXXXXXX`` sequences and leaves all other backslash sequences
untouched (no mangling of ``\\n``, ``\\t`` or Windows-style paths).
"""

from __future__ import annotations

import re
from typing import Any

_UNICODE_ESC_4 = re.compile(r"\\u([0-9a-fA-F]{4})")
_UNICODE_ESC_8 = re.compile(r"\\U([0-9a-fA-F]{8})")


def _decode_match(match: re.Match) -> str:
    codepoint = int(match.group(1), 16)
    if 0xD800 <= codepoint <= 0xDFFF:
        return match.group(0)
    try:
        return chr(codepoint)
    except ValueError:
        return match.group(0)


def decode_literal_unicode_escapes(value: str) -> str:
    """Decode literal ``\\uXXXX`` / ``\\UXXXXXXXX`` sequences in a string.

    Only ``\\u``/``\\U`` escapes are decoded; all other backslash sequences
    are preserved verbatim.
    """
    if "\\u" not in value and "\\U" not in value:
        return value
    result = _UNICODE_ESC_4.sub(_decode_match, value)
    result = _UNICODE_ESC_8.sub(_decode_match, result)
    return result


def normalize_tool_arguments(arguments: Any) -> Any:
    """Recursively decode literal unicode escapes in all string values.

    Works on dicts / lists / tuples / strings.  Non-strings pass through
    unchanged.
    """
    if isinstance(arguments, dict):
        return {k: normalize_tool_arguments(v) for k, v in arguments.items()}
    if isinstance(arguments, list):
        return [normalize_tool_arguments(v) for v in arguments]
    if isinstance(arguments, tuple):
        return tuple(normalize_tool_arguments(v) for v in arguments)
    if isinstance(arguments, str):
        return decode_literal_unicode_escapes(arguments)
    return arguments
