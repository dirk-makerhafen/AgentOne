"""Normalization of the flexible message spec accepted by
:meth:`runtime.session.session.Session.add_user_message`.

The public entry point :func:`normalize_messages` turns the many accepted
shapes into a canonical list of messages::

    [{"role": "user", "parts": [<part>, ...]}, ...]

where every part is a dict with ``part_type``, ``content_type`` and
``content`` (plus optional ``template_data`` / ``tool_call``).

Accepted shapes
---------------
* ``"text"``                      -> one user message with one text part
* ``["a", "b"]``                  -> one user message with two text parts
* ``[<part dict>, "b"]``          -> one user message with two parts
* ``{"content": "hi"}``           -> one user message with one part
* ``{"role": "assistant", "message": "hi"}`` -> one assistant message
* ``[<message dict>, "b"]``       -> two messages (dict + user shorthand)

Message dicts are recognised by a ``role`` / ``message`` / ``parts`` key;
everything else that is a dict is treated as a part.  Mixing message dicts
and part dicts at the same list level is ambiguous and raises ``ValueError``.

The function is pure and free of Django imports so it can be unit tested
without a database.
"""

from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_PART_TYPE = "message"
DEFAULT_CONTENT_TYPE = "text"
DEFAULT_ROLE = "user"

# Keys that mark a dict as a *message* rather than a *part*.
_MESSAGE_KEYS = ("role", "message", "parts")


def normalize_messages(spec: Any) -> List[Dict[str, Any]]:
    """Normalize *spec* into ``[{"role": ..., "parts": [...]}, ...]``.

    Raises ``ValueError`` for empty, ambiguous or malformed specs.
    """
    if spec is None or spec == "" or spec == []:
        raise ValueError("No message or message parts provided")

    if isinstance(spec, str):
        return [_message(DEFAULT_ROLE, [_part_from_str(spec)])]

    if isinstance(spec, dict):
        if _is_message_dict(spec):
            return [_normalize_message(spec)]
        return [_message(DEFAULT_ROLE, [_part_from_dict(spec)])]

    if isinstance(spec, (list, tuple)):
        spec = list(spec)
        if any(_is_message_dict(item) for item in spec):
            if any(_is_part_dict(item) for item in spec):
                raise ValueError("Cannot mix message dicts and part dicts in one list")
            return [_normalize_message(item) for item in spec]
        if not spec:
            raise ValueError("No message or message parts provided")
        return [_message(DEFAULT_ROLE, [_part(item) for item in spec])]

    raise ValueError(f"Unsupported message spec of type {type(spec).__name__}")


def _is_message_dict(item: Any) -> bool:
    return isinstance(item, dict) and any(key in item for key in _MESSAGE_KEYS)


def _is_part_dict(item: Any) -> bool:
    return isinstance(item, dict) and not _is_message_dict(item)


def _message(role: Any, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"role": role, "parts": parts}


def _normalize_message(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return _message(DEFAULT_ROLE, [_part_from_str(item)])
    if isinstance(item, dict):
        role = item.get("role", DEFAULT_ROLE)
        body = item.get("message", item.get("parts", item.get("content", None)))
        return _message(role, _normalize_body(body))
    raise ValueError(f"Unsupported message of type {type(item).__name__}")


def _normalize_body(body: Any) -> List[Dict[str, Any]]:
    if body is None:
        return []
    if isinstance(body, str):
        return [_part_from_str(body)]
    if isinstance(body, dict):
        return [_part_from_dict(body)]
    if isinstance(body, (list, tuple)):
        if any(_is_message_dict(item) for item in body):
            raise ValueError("Nested message lists are not supported")
        return [_part(item) for item in body]
    raise ValueError(f"Unsupported message body of type {type(body).__name__}")


def _part(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return _part_from_str(item)
    if isinstance(item, dict):
        return _part_from_dict(item)
    raise ValueError(f"Unsupported message part of type {type(item).__name__}")


def _part_from_str(content: str) -> Dict[str, Any]:
    return {"part_type": DEFAULT_PART_TYPE, "content_type": DEFAULT_CONTENT_TYPE, "content": content}


def _part_from_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    content = item.get("content", "")
    template_data = item.get("template_data", None)
    part = {
        "part_type": item.get("part_type", item.get("type", DEFAULT_PART_TYPE)),
        "content_type": item.get("content_type") or _infer_content_type(content, template_data),
        "content": content,
    }
    if template_data is not None:
        part["template_data"] = template_data
    if "tool_call" in item:
        part["tool_call"] = item["tool_call"]
    return part


def _infer_content_type(content: Any, template_data: Any) -> str:
    if template_data is not None:
        return "template"
    if isinstance(content, (dict, list)):
        return "json"
    return DEFAULT_CONTENT_TYPE
