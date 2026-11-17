"""Turn the ORM conversation into the flat row list the chat template renders.

Rows mirror the legacy ``Messages`` view's ordering:

    user message
      query card(s) triggered by it
        standalone response(s) that have no assistant message yet
    assistant message (renders its own response/reasoning/parts)
    ...

Rendering the whole tail on every event keeps the fragment stateless: there is
no client-side append/merge logic to get wrong, and a missed event only costs
one refresh.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Prefetch

from server.models.enums.message_enums import MessagePartType, MessageRole
from server.models.message import Message, MessagePart
from server.models.queries.query import Query
from server.models.queries.query_message_part import QueryMessagePart
from server.models.queries.response import Response
from webui.core.markdown import render_markdown

DEFAULT_LIMIT = 120


@dataclass
class Row:
    """One visual row in the thread."""

    kind: str  # message | query | response
    obj: Any
    body_html: str = ""
    body_text: str = ""
    images: list[str] = field(default_factory=list)
    reasoning: str = ""
    tools: list[Any] = field(default_factory=list)
    response: Any = None

    @property
    def role(self) -> str:
        return getattr(self.obj, "role", "")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _content_of(part: MessagePart) -> Any:
    try:
        return part.content.get() if part.content_id else ""
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def _status_class(call: Any) -> str:
    """Map a tool-call status to the legacy card-status modifier."""
    detail = str(getattr(call, "status_detail", "") or "").upper()
    if "SUCCESS" in detail:
        return "success"
    if "FAILURE" in detail or "CANCELLED" in detail or "STOPPED" in detail:
        return "failure"
    status = str(getattr(call, "status", "") or "").lower()
    if status in ("success", "failure", "active", "waiting"):
        return status
    if status in ("halted", "ended"):
        return "waiting"
    return status or "waiting"


def _fmt_duration(seconds: float | None) -> str:
    """Format a duration in seconds as a compact human string."""
    if seconds is None:
        return ""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return ""
    seconds = max(seconds, 0)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m {int(seconds % 60):02d}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60:02d}m"


def _call_duration(call: Any) -> str:
    """Elapsed/total duration of a call (empty when it never started)."""
    try:
        start = getattr(call, "created_at", None)
        end = getattr(call, "ended_at", None) or getattr(call, "updated_at", None)
        if start is None or end is None:
            return ""
        return _fmt_duration((end - start).total_seconds())
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def _call_name(call: Any) -> str:
    """Display name of an ``AgentTaskCall`` (never raises)."""
    try:
        definition = getattr(call, "task_definition", None)
        if definition is not None and definition.name:
            return definition.name
        version = getattr(call, "task_definition_version", None)
        definition = getattr(version, "task_definition", None) if version else None
        if definition is not None and definition.name:
            return definition.name
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    pk = getattr(call, "pk", None)
    return f"call #{pk}" if pk is not None else "tool call"


def _status_label(call: Any) -> str:
    """Human-readable status-detail label (falls back to the raw status)."""
    try:
        from server.models.enums.task_enums import TaskCallStatusDetail

        detail = str(getattr(call, "status_detail", "") or "")
        return str(dict(TaskCallStatusDetail.choices).get(detail, detail))
    except Exception:  # pylint: disable=broad-exception-caught
        return str(getattr(call, "status", "") or "")


def _subcall_counts(call: Any) -> dict[str, Any]:
    """Cheap descendant counts for the collapsed tool card."""
    try:
        counts = call.count_subcalls(max_depth=6, max_nodes=500) or {}
    except Exception:  # pylint: disable=broad-exception-caught
        counts = {}
    active = int(counts.get("active", 0) or 0)
    finished = int(counts.get("finished", 0) or 0)
    executing = len(counts.get("executing") or [])
    return {
        "active": active,
        "finished": finished,
        "executing": executing,
        "waiting": max(active - executing, 0),
        "truncated": bool(counts.get("truncated", False)),
    }


def _tool_entry(part: MessagePart) -> dict[str, Any]:
    """Flatten a TOOLCALL part into the fields the tool card renders."""
    call = getattr(part, "tool_call", None)
    entry: dict[str, Any] = {
        "pk": None,
        "name": "tool call",
        "status": "",
        "status_detail": "",
        "status_label": "",
        "status_class": "waiting",
        "body": _as_text(_content_of(part)),
        "duration": "",
        "halted": False,
        "subcalls": {"active": 0, "finished": 0, "executing": 0, "waiting": 0, "truncated": False},
    }
    if call is None:
        return entry
    entry.update(
        {
            "pk": getattr(call, "pk", None),
            "name": _call_name(call),
            "status": str(getattr(call, "status", "") or ""),
            "status_detail": str(getattr(call, "status_detail", "") or ""),
            "status_label": _status_label(call),
            "status_class": _status_class(call),
            "duration": _call_duration(call),
            "halted": str(getattr(call, "status_detail", "") or "") == "HALTED_APPROVAL",
            # Subcall counts are expensive (recursive BFS + many queries); load
            # them lazily via the expanded detail endpoint instead of on every
            # page render, mirroring the heavy argument/result payloads.
            "subcalls": {"active": 0, "finished": 0, "executing": 0, "waiting": 0, "truncated": False},
        }
    )
    return entry


def _subcall_node(call: Any, depth: int) -> dict[str, Any] | None:
    """Template-ready row for one descendant call (never raises)."""
    try:
        if call is None:
            return None
        depth = max(int(depth or 1), 1)
        return {
            "pk": getattr(call, "pk", "?"),
            "name": _call_name(call),
            "status": str(getattr(call, "status", "") or ""),
            "status_detail": str(getattr(call, "status_detail", "") or ""),
            "status_class": _status_class(call),
            "indent": (depth - 1) * 14,
            "duration": _call_duration(call),
            "executing": str(getattr(call, "status", "") or "") == "ACTIVE",
        }
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _resolved_arguments(call: Any) -> list[dict[str, str]]:
    """Flatten the call's stored arguments into key/value rows."""
    try:
        args = call._resolve_call_arguments(  # pylint: disable=protected-access
            timeout=0, allow_partial_results=True
        )
    except Exception:  # pylint: disable=broad-exception-caught
        args = None
    if not isinstance(args, dict):
        return []
    rows: list[dict[str, str]] = []
    for key, value in args.items():
        if key in ("guardrail_reason", "*"):
            continue
        rows.append({"key": str(key), "value": _as_text(value)})
    return rows


def _call_result(call: Any) -> str:
    """Result payload of a call (empty while it is still running)."""
    try:
        result = call.get_result(timeout=0, allow_partial_results=True)
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    if result is None:
        return ""
    return _as_text(result)


def build_call_detail(call: Any, full: bool = False) -> dict[str, Any]:
    """Everything the expanded tool card shows.

    Only fetched when the user opens a card (``toggle once``), so the heavy
    argument/result payloads never enter the initial page.  ``full`` loads the
    finished branches of the sub-call tree on demand.
    """
    counts = _subcall_counts(call)
    nodes: list[dict[str, Any]] = []
    seen: set[Any] = set()

    # Currently-executing descendants are pinned first, even past walk caps.
    try:
        pins = call.get_executing_subcalls() or []
    except Exception:  # pylint: disable=broad-exception-caught
        pins = []
    for pin in pins:
        node = _subcall_node(pin.get("call"), pin.get("depth", 1))
        if node is None:
            continue
        seen.add(node["pk"])
        nodes.append(node)

    try:
        tree = call.get_subcall_tree(
            max_depth=6,
            max_nodes=400 if full else 150,
            active_only=not full,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        tree = []
    for entry in tree:
        node = _subcall_node(entry.get("call"), entry.get("depth", 1))
        if node is None or node["pk"] in seen:
            continue
        seen.add(node["pk"])
        nodes.append(node)

    return {
        "call": call,
        "arguments": _resolved_arguments(call),
        "result": _call_result(call),
        "subcalls": nodes,
        "counts": counts,
        "halted": str(getattr(call, "status_detail", "") or "") == "HALTED_APPROVAL",
        "full": full,
    }


def _message_row(message: Message) -> Row:
    parts = list(message.parts.all())
    body: list[str] = []
    images: list[str] = []
    reasoning: list[str] = []
    tools: list[Any] = []

    for part in parts:
        content = _content_of(part)
        if part.content_type == "IMAGE":
            if isinstance(content, str) and content:
                images.append(content)
        elif part.type == MessagePartType.REASONING:
            text = _as_text(content)
            if text:
                reasoning.append(text)
        elif part.type == MessagePartType.TOOLCALL:
            tools.append(_tool_entry(part))
            # For user messages, TOOLCALL parts represent slash commands (e.g. /help, /compact)
            # Include them in the body so they render in the chat
            if message.role == MessageRole.USER:
                text = _as_text(content)
                if text:
                    body.append(text)
        else:
            text = _as_text(content)
            if text:
                body.append(text)

    row = Row(kind="message", obj=message, images=images, tools=tools)

    response = getattr(message, "response", None)
    if response is not None and getattr(response, "reasoning", ""):
        row.reasoning = response.reasoning
    elif reasoning:
        row.reasoning = "\n\n".join(reasoning)

    if message.role == MessageRole.ASSISTANT:
        row.body_text = "\n\n".join(body)
        row.body_html = render_markdown(row.body_text)
    else:
        row.body_text = "\n".join(body)
    return row


def build_thread(session_model, limit: int = DEFAULT_LIMIT, end_pk: int | None = None) -> list[Row]:
    """Return the last *limit* turns as a flat list of :class:`Row` objects.

    ``end_pk`` caps the window at (and includes) that message, which lets the
    chat table-of-contents jump to an older compaction boundary.
    """
    messages_qs = Message.objects.filter(session=session_model)
    if end_pk is not None:
        messages_qs = messages_qs.filter(pk__lte=end_pk)
    messages = list(
        messages_qs
        .select_related("response")
        .prefetch_related(
            Prefetch(
                "parts",
                queryset=MessagePart.objects.select_related(
                    "content", "template_data",
                    "tool_call",
                    "tool_call__task_definition",
                    "tool_call__task_definition_version__task_definition",
                ).order_by("pk"),
            )
        )
        .order_by("-pk")[:limit]
    )
    messages.reverse()
    if not messages:
        return []

    message_pks = [message.pk for message in messages]
    queries = list(
        Query.objects.filter(
            session=session_model,
            trigger_message_id__in=message_pks,
        ).order_by("-pk")
    )
    queries_by_message: dict[int, list[Query]] = {}
    for query in queries:
        queries_by_message.setdefault(query.trigger_message_id, []).append(query)

    responses = list(
        Response.objects.filter(query_id__in=[query.pk for query in queries]).order_by("pk")
    )
    latest_by_query: dict[int, Response] = {}
    for response in responses:
        latest_by_query[response.query_id] = response

    # A response that already backs an assistant message is rendered by that
    # message; only unanchored ones (still streaming, or orphaned) get a row.
    # However, we always include standalone response rows even when the session
    # is inactive/archived, so that response models are always rendered.
    anchored = set(
        Message.objects.filter(response_id__in=[response.pk for response in responses])
        .values_list("response_id", flat=True)
    )
    standalone_by_query: dict[int, list[Response]] = {}
    for response in responses:
        if response.pk not in anchored:
            standalone_by_query.setdefault(response.query_id, []).append(response)

    rows: list[Row] = []
    for message in messages:
        rows.append(_message_row(message))
        for query in queries_by_message.get(message.pk, []):
            rows.append(Row("query", query, response=latest_by_query.get(query.pk)))
            for response in standalone_by_query.get(query.pk, []):
                rows.append(
                    Row(
                        kind="response",
                        obj=response,
                        body_html=render_markdown(response.content or ""),
                        reasoning=response.reasoning or "",
                    )
                )
    # If the session is inactive/archived and there are responses but no standalone
    # rows were generated (because all are anchored), still include the anchored
    # responses as standalone rows so the response model is rendered.
    if not standalone_by_query and responses and session_model.is_active is False:
        for response in responses:
            rows.append(
                Row(
                    kind="response",
                    obj=response,
                    body_html=render_markdown(response.content or ""),
                    reasoning=response.reasoning or "",
                )
            )
    return rows


def build_query_detail(query: Query) -> list[dict[str, Any]]:
    """Return the prompt messages of *query* for the expanded card.

    Only called when the user opens a query card, so the (often large) prompt
    context is never rendered into the initial page.
    """
    query_messages = (
        query.related_query_messages.order_by("pk")
        .prefetch_related(
            Prefetch(
                "query_message_parts",
                queryset=QueryMessagePart.objects.select_related("content").order_by("pk"),
            )
        )
    )
    items: list[dict[str, Any]] = []
    for query_message in query_messages:
        texts: list[str] = []
        for part in query_message.query_message_parts.all():
            if part.content_type == "IMAGE":
                texts.append("[image]")
                continue
            text = _as_text(_content_of(part))
            if text:
                texts.append(text)
        items.append(
            {
                "role": query_message.role,
                "text": "\n\n".join(texts),
                "tokens": query_message.tokens,
            }
        )
    return items
