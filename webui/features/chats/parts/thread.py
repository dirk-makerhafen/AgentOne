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
import re
from collections import defaultdict
from dataclasses import dataclass, field
from heapq import heapify, heappop, heappush
from typing import Any

from django.db.models import Prefetch
from django.urls import reverse

from runtime.session.messages import FORK_ANCHOR_PREFIX
from runtime.session_bootstrap import COMPACTION_BOOTSTRAP_SENTINEL
from server.models.enums.message_enums import MessagePartType, MessageRole, MessageType
from server.models.enums.session_enums import SessionType
from server.models.message import Message, MessagePart
from server.models.queries.query import Query
from server.models.queries.query_message_part import QueryMessagePart
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from webui.core.markdown import render_markdown
from webui.features.chats.parts.calls import (
    build_call_references,
    build_payload,
    build_subcall_flow,
    call_duration as _call_duration,
    call_hint,
    call_icon,
    call_kind,
    call_name as _call_name,
    clock as _clock,
    status_class as _status_class,
    status_label as _status_label,
    status_text as _status_text,
    subcall_counts as _subcall_counts,
)

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
    # System cards (compaction / reflection) get a summary line for their
    # collapsed header and pre-rendered HTML for the expanded body.
    card_preview: str = ""
    card_html: str = ""
    compaction_when: str = ""
    compaction_cwd: str = ""
    compaction_bootstrap: list[str] = field(default_factory=list)
    is_final_result: bool = False
    final_result_delivery: dict[str, Any] | None = None
    # Fork anchors are hidden INFO rows whose prev_message points into the
    # parent session.  The renderer keeps one of them and links to that parent.
    is_fork_anchor: bool = False
    fork_parent_session_pk: int | None = None
    fork_parent_message_pk: int | None = None
    fork_parent_name: str = ""
    fork_parent_url: str = ""
    # Reports are produced by an internal fork.  The marker in the observed
    # session has no FK to that fork, so the renderer resolves the newest
    # matching child session and links to it.
    report_session_pk: int | None = None
    report_session_name: str = ""
    report_session_url: str = ""

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


def _is_final_result_part(part: MessagePart) -> bool:
    try:
        data = part.template_data.get() if part.template_data_id else None
    except Exception:  # pylint: disable=broad-exception-caught
        return False
    return isinstance(data, dict) and data.get("final_result") is True


def _fork_anchor_fields(message: Message, body_text: str) -> dict[str, Any]:
    """Fields for the hidden INFO row that grafts a fork onto its parent.

    Older anchors have no structured payload; the ``prev_message`` cross-session
    link is the canonical pointer to the parent message, and ``?around=`` is the
    chat UI's existing jump-to-message convention.
    """
    fields: dict[str, Any] = {
        "is_fork_anchor": (
            message.message_type == MessageType.INFO
            and body_text.startswith(FORK_ANCHOR_PREFIX)
        )
    }
    if not fields["is_fork_anchor"] or not message.prev_message_id:
        return fields

    parent = (
        Message.objects.filter(pk=message.prev_message_id)
        .select_related("session")
        .first()
    )
    if parent is None or parent.session_id == message.session_id:
        return fields

    parent_pk = parent.session_id
    fields.update(
        fork_parent_session_pk=parent_pk,
        fork_parent_message_pk=parent.pk,
        fork_parent_name=parent.session.name or f"Session #{parent_pk}",
        fork_parent_url=f"{reverse('webui:chat', args=[parent_pk])}?around={parent.pk}",
    )
    return fields


_REPORT_FORKS = {
    MessageType.COMPACTION: (SessionType.SUBTASK_COMPACT, "internal:compaction"),
    MessageType.REFLECTION: (SessionType.SUBTASK_HOOK, "internal:reflection"),
}


def _report_session_fields(message: Message) -> dict[str, Any]:
    """Find the internal fork that produced a compaction/reflection report.

    Reflection and compaction forks are tagged with a session type and group
    key, and are always created before the marker they produce.  The newest
    earlier child of that kind is therefore the producing fork, including
    after a compaction retry (each attempt gets its own fork).  Session and
    message PKs come from separate sequences, so use created_at, not pk, to
    order the two tables against each other.
    """
    fork = _REPORT_FORKS.get(message.message_type)
    if fork is None:
        return {}

    child = (
        SessionModel.objects.filter(
            parent_session_id=message.session_id,
            session_type=fork[0],
            group_key=fork[1],
            created_at__lte=message.created_at,
        )
        .order_by("-created_at", "-pk")
        .only("pk", "name")
        .first()
    )
    if child is None:
        return {}
    # Land on the fork's own final message (the source of the report).  Message
    # pks are global, so passing the parent's marker pk here would find no row
    # in the fork and leave the chat at the bottom instead of jumping.
    source_pk = (
        Message.objects.filter(session_id=child.pk)
        .order_by("-pk")
        .values_list("pk", flat=True)
        .first()
    )
    chat_url = reverse("webui:chat", args=[child.pk])
    return {
        "report_session_pk": child.pk,
        "report_session_name": child.name or f"Session #{child.pk}",
        "report_session_url": f"{chat_url}?around={source_pk}" if source_pk else chat_url,
    }


def _final_result_delivery(message: Message) -> dict[str, Any] | None:
    session = getattr(message, "session", None)
    if session is None:
        return None
    parent = getattr(session, "parent_session", None)
    if parent is None:
        return None

    delivery: dict[str, Any] = {
        "parent_pk": parent.pk,
        "parent_name": getattr(parent, "name", "") or f"Session #{parent.pk}",
        "session_type": str(getattr(session, "session_type", "") or ""),
        "mode": "",
        "delivered": False,
        "detail": "",
    }
    try:
        delivery["session_type_display"] = session.get_session_type_display()
    except Exception:  # pylint: disable=broad-exception-caught
        delivery["session_type_display"] = delivery["session_type"] or "Subsession"

    if session.session_type not in (
        SessionType.SUBTASK_FORK,
        SessionType.SUBTASK_DELEGATE,
        SessionType.SUBTASK_COMPACT,
        SessionType.SUBTASK_HOOK,
    ):
        delivery["detail"] = "Final result ends this subsession; no automatic parent delivery."
        return delivery

    try:
        from server.models.agent_task_call import AgentTaskCall

        calls = (
            AgentTaskCall.objects.select_related("task_definition")
            .filter(session=parent, task_definition__name="ingest_subagent_result")
            .order_by("-pk")[:50]
        )
        call = None
        for candidate in calls:
            args = getattr(candidate, "carguments_json", None)
            if isinstance(args, dict) and args.get("child_session_pk") == session.pk:
                call = candidate
                break
    except Exception:  # pylint: disable=broad-exception-caught
        call = None

    if call is None:
        delivery["detail"] = "No subagent result delivery call found for this subsession."
        return delivery

    args = getattr(call, "carguments_json", None)
    execute_turn = bool(args.get("execute_turn")) if isinstance(args, dict) else False
    delivery["mode"] = "immediate" if execute_turn else "passive"
    delivery["delivered"] = True
    detail = "Injected into parent session"
    detail += " and parent turn triggered" if execute_turn else " (passive delivery)"
    delivery["detail"] = detail + "."
    return delivery


def _query_part_text(part: QueryMessagePart) -> str:
    """Readable text for one query part, including source-backed parts.

    Query parts normally point at a ``MessagePart`` instead of storing their
    own content.  Reusing the model's renderer keeps the expanded query card
    in sync with what was actually sent to the model (templates, JSON, tool
    calls) instead of only looking at the part's (usually empty) own content.
    """
    try:
        blocks = part.to_content_blocks(fail_on_error=False)
    except Exception:  # pylint: disable=broad-exception-caught
        source = getattr(part, "source_message_part", None) or part
        return _as_text(_content_of(source))

    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            texts.append(_as_text(block))
            continue
        kind = block.get("type")
        if kind == "text":
            text = block.get("text", "")
        elif kind == "image_url":
            text = "[image]"
        elif kind == "reasoning":
            text = "[reasoning]\n" + str(block.get("text", ""))
        elif kind == "function":
            text = json.dumps(block, indent=2, ensure_ascii=False, default=str)
        else:
            text = _as_text(block)
        if text and str(text).strip():
            texts.append(str(text).rstrip())
    return "\n\n".join(texts)


_COMPACTION_WHEN_RE = re.compile(
    r"^\s*It is now\s+(?P<when>.+?),\s+your working dir is ['\"](?P<cwd>.*?)['\"]\.?\s*$"
)
_COMPACTION_PREAMBLE = "Old messages before this summary"
_REFLECTION_PREFIX = "Reflection report:"


def _card_preview(text: str, limit: int = 110) -> str:
    """One short, markup-free line for a collapsed card's subtitle."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "```")):
            continue
        line = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)
        line = re.sub(r"[*_`>#]+", "", line).strip()
        if not line:
            continue
        if len(line) > limit:
            return line[: limit - 1].rstrip() + "…"
        return line
    return ""


def _parse_compaction(parts: list[str]) -> dict[str, Any]:
    """Split a compaction marker into header metadata and display sections."""
    when = cwd = ""
    summary_lines: list[str] = []
    bootstrap: list[str] = []
    in_bootstrap = False

    for text in parts:
        if COMPACTION_BOOTSTRAP_SENTINEL in text or text.lstrip().startswith("[Session bootstrap"):
            in_bootstrap = True
        if in_bootstrap:
            if text.strip():
                bootstrap.append(text.strip())
            continue
        match = _COMPACTION_WHEN_RE.match(text)
        if match and not when:
            when = match.group("when").strip()
            cwd = match.group("cwd").strip()
            continue
        if text.strip().startswith(_COMPACTION_PREAMBLE):
            continue
        summary_lines.append(text)

    summary = "\n".join(summary_lines).strip()
    return {
        "preview": _card_preview(summary) or "Earlier messages folded into this summary",
        "html": render_markdown(summary),
        "when": when,
        "cwd": cwd,
        "bootstrap": bootstrap,
    }


def _parse_reflection(text: str) -> tuple[str, str]:
    """Strip the storage preamble and render the report for the chat card."""
    body = text.lstrip()
    if body.startswith(_REFLECTION_PREFIX):
        body = body[len(_REFLECTION_PREFIX):].lstrip("\r\n")
    return _card_preview(body), render_markdown(body)


def _tool_entry_for_call(call: Any, body: str = "") -> dict[str, Any]:
    """Fields the live tool summary renders for one call.

    Kept separate from :func:`_tool_entry` so the ``chat-tool-summary``
    component can refresh just the summary row without re-rendering (and
    therefore replacing) the whole message.
    """
    entry: dict[str, Any] = {
        "pk": getattr(call, "pk", None),
        "name": "tool call",
        "icon": "⚙",
        "kind": "tool",
        "hint": "",
        "status": "",
        "status_detail": "",
        "status_label": "",
        "status_text": "",
        "status_class": "waiting",
        "body": body,
        "duration": "",
        "halted": False,
        "subcalls": {"active": 0, "finished": 0, "executing": 0, "waiting": 0, "truncated": False},
    }
    if call is None:
        return entry
    entry.update(
        {
            "name": _call_name(call),
            "icon": call_icon(call),
            "kind": call_kind(call),
            "hint": call_hint(call),
            "status": str(getattr(call, "status", "") or ""),
            "status_detail": str(getattr(call, "status_detail", "") or ""),
            "status_label": _status_label(call),
            "status_text": _status_text(call),
            "status_class": _status_class(call),
            "duration": _call_duration(call),
            "halted": str(getattr(call, "status_detail", "") or "") == "HALTED_APPROVAL",
        }
    )
    # The collapsed summary shows a "N running/queued/subtasks" chip.  Only
    # non-ended calls can change, so they are the only ones worth walking
    # (a finished tree is static and its full list lives in the detail pane).
    if entry["status"] != "ENDED":
        entry["subcalls"] = _subcall_counts(call)
    return entry


def _tool_entry(part: MessagePart) -> dict[str, Any]:
    """Flatten a TOOLCALL part into the fields the tool card renders."""
    return _tool_entry_for_call(getattr(part, "tool_call", None), _as_text(_content_of(part)))


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
            "status_text": _status_text(call),
            "depth": depth,
            "prefix": "├─ ",
            "started": _clock(getattr(call, "created_at", None)),
            "duration": _call_duration(call),
            "executing": str(getattr(call, "status", "") or "") == "ACTIVE",
        }
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _subcall_parent_pk(call: Any) -> Any:
    """The call pk that directly launched *call* (None for unattached rows)."""
    run = getattr(call, "parent_taskrun", None)
    if run is None:
        return None
    return getattr(run, "agent_task_call_id", None)


def _created_sort_key(call: Any) -> tuple[bool, Any, int]:
    created = getattr(call, "created_at", None)
    return (created is None, created, int(getattr(call, "pk", 0) or 0))


def _ordered_subcall_rows(root_pk: Any, tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn the model's BFS tree into a chronological depth-first flow.

    The BFS list interleaves siblings' subtrees (all depth-1 rows, then all
    depth-2 rows), which reads as a flat list rather than a sequence.  Group by
    the launching call, sort siblings by creation time, then walk depth-first so
    each row gets a ``├─``/``└─`` prefix that mirrors the actual call flow.
    """
    children: dict[Any, list[Any]] = {}
    for entry in tree:
        call = entry.get("call") if isinstance(entry, dict) else None
        if call is None or getattr(call, "pk", None) is None:
            continue
        children.setdefault(_subcall_parent_pk(call), []).append(call)
    for kids in children.values():
        kids.sort(key=_created_sort_key)

    rows: list[dict[str, Any]] = []
    seen: set[Any] = set()

    def walk(parent_pk: Any, ancestor_last: list[bool]) -> None:
        siblings = children.get(parent_pk, [])
        for index, child in enumerate(siblings):
            child_pk = getattr(child, "pk", None)
            if child_pk in seen:
                continue
            seen.add(child_pk)
            is_last = index == len(siblings) - 1
            prefix = "".join("   " if last else "│  " for last in ancestor_last)
            prefix += "└─ " if is_last else "├─ "
            node = _subcall_node(child, len(ancestor_last) + 1)
            if node is None:
                continue
            node["prefix"] = prefix
            rows.append(node)
            walk(child_pk, ancestor_last + [is_last])

    walk(root_pk, [])

    # Defensive: a row whose ancestor was pruned by the walk cap is still worth
    # showing rather than silently dropping it.
    for kids in children.values():
        for child in kids:
            child_pk = getattr(child, "pk", None)
            if child_pk in seen:
                continue
            seen.add(child_pk)
            node = _subcall_node(child, 1)
            if node is not None:
                rows.append(node)
    return rows


def build_call_subcalls(call: Any, full: bool = False) -> dict[str, Any]:
    """The live sub-task flow for one tool card.

    Split out of :func:`build_call_detail` so a descendant status change
    refreshes only this list (plus the summary chip) instead of swapping the
    whole arguments/result pane.  ``full`` also loads finished branches and
    framework plumbing; the default walk keeps the meaningful, unfinished work.
    """
    return build_subcall_flow(call, full=full)


def _resolved_arguments(call: Any) -> list[dict[str, Any]]:
    """Flatten the call's stored arguments into key/payload rows."""
    try:
        args = call._resolve_call_arguments(  # pylint: disable=protected-access
            timeout=0, allow_partial_results=True
        )
    except Exception:  # pylint: disable=broad-exception-caught
        args = None
    if not isinstance(args, dict):
        return []
    cache: dict[Any, Any] = {}
    rows: list[dict[str, Any]] = []
    for key, value in args.items():
        if key in ("guardrail_reason", "*"):
            continue
        rows.append(
            {"key": str(key), "payload": build_payload(value, cache=cache)}
        )
    return rows


def _call_result(call: Any) -> dict[str, Any] | None:
    """Structured result payload (empty while the call is still running)."""
    try:
        result = call.get_result(
            timeout=0, recursive=False, allow_partial_results=True
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    if result is None:
        return None
    return build_payload(result)


def build_call_detail(call: Any, full: bool = False) -> dict[str, Any]:
    """The input/output panes of an expanded tool card.

    Only fetched when the user opens a card (``toggle once``), so the heavy
    argument/result payloads never enter the initial page.  The sub-task flow is
    a separate live component (:func:`build_call_subcalls`); ``full`` is passed
    through so that component also expands finished branches.
    """
    return {
        "call": call,
        "arguments": _resolved_arguments(call),
        "result": _call_result(call),
        "references": build_call_references(call),
        "session": getattr(call, "session", None),
        "halted": str(getattr(call, "status_detail", "") or "") == "HALTED_APPROVAL",
        "full": full,
    }


def _message_row(message: Message) -> Row:
    parts = list(message.parts.all())
    body: list[str] = []
    images: list[str] = []
    reasoning: list[str] = []
    tools: list[Any] = []
    is_final_result = False

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
            # User slash commands are rendered as tool cards; avoid duplicating
            # raw command text in the message body.
        else:
            text = _as_text(content)
            if text:
                body.append(text)
            if not is_final_result and part.type == MessagePartType.MESSAGE and part.content_type == "TEXT":
                is_final_result = _is_final_result_part(part)

    row = Row(
        kind="message",
        obj=message,
        images=images,
        tools=tools,
        is_final_result=is_final_result,
        final_result_delivery=_final_result_delivery(message) if is_final_result else None,
    )

    response = getattr(message, "response", None)
    if response is not None and getattr(response, "reasoning", ""):
        row.reasoning = response.reasoning
    elif reasoning:
        row.reasoning = "\n\n".join(reasoning)

    if message.message_type == MessageType.COMPACTION:
        row.body_text = "\n".join(body)
        details = _parse_compaction(body)
        row.card_preview = details["preview"]
        row.card_html = details["html"]
        row.compaction_when = details["when"]
        row.compaction_cwd = details["cwd"]
        row.compaction_bootstrap = details["bootstrap"]
    elif message.message_type == MessageType.REFLECTION:
        row.body_text = "\n".join(body)
        row.card_preview, row.card_html = _parse_reflection(row.body_text)
    elif message.role == MessageRole.ASSISTANT:
        row.body_text = "\n\n".join(body)
        row.body_html = render_markdown(row.body_text)
    else:
        row.body_text = "\n".join(body)

    for name, value in _fork_anchor_fields(message, row.body_text).items():
        setattr(row, name, value)
    for name, value in _report_session_fields(message).items():
        setattr(row, name, value)
    return row


def _chain_ordered_pks(session_model, end_pk: int | None = None) -> list[int]:
    """Return message pks in conversation order, not creation order.

    The canonical order is the ``prev_message`` chain: session bootstrap
    messages are created *after* the first user message but spliced in front of
    it, so their pks are newer than their position in the conversation.  A
    topological walk keeps pk order wherever the chain allows it (which also
    covers older sessions whose messages have no links at all), and any
    dangling links or cycles degrade to pk order instead of losing messages.
    """
    links = Message.objects.filter(session=session_model).order_by("pk").values_list("pk", "prev_message_id")
    if end_pk is not None:
        links = links.filter(pk__lte=end_pk)
    pairs = list(links)
    pks = [pk for pk, _ in pairs]
    known = set(pks)

    children: dict[int, list[int]] = defaultdict(list)
    indegree: dict[int, int] = {}
    for pk, prev in pairs:
        # Only links inside this session constrain the UI order: forks anchor
        # their first message to a parent message in another session.
        if prev in known and prev != pk:
            children[prev].append(pk)
            indegree[pk] = 1
        else:
            indegree[pk] = 0

    ready = [pk for pk in pks if indegree[pk] == 0]
    heapify(ready)
    ordered: list[int] = []
    while ready:
        pk = heappop(ready)
        ordered.append(pk)
        for child in children[pk]:
            indegree[child] -= 1
            if indegree[child] == 0:
                heappush(ready, child)
    if len(ordered) != len(pks):
        seen = set(ordered)
        ordered.extend(pk for pk in pks if pk not in seen)
    return ordered


def _query_anchor_pk(query: Query, messages: list[Message], index_by_pk: dict[int, int]) -> int | None:
    """Return the message row a query card should be drawn after.

    ``Query.trigger_message`` is the message that started the turn, but an
    auto-compaction can splice its INFO notices into the chain *after* that
    message and *before* the query is created.  Anchoring strictly on the
    trigger would draw the query above "Compaction successful".  Use creation
    time to advance the anchor to the newest message that already existed when
    the query started, without touching the trigger pointer the LLM context
    walk depends on.
    """
    trigger_index = index_by_pk.get(query.trigger_message_id)
    if trigger_index is None:
        return None
    anchor_pk = query.trigger_message_id
    query_at = query.created_at
    if query_at is None:
        return anchor_pk
    for message in messages[trigger_index + 1:]:
        if message.created_at is not None and message.created_at <= query_at:
            anchor_pk = message.pk
    return anchor_pk


def build_thread(
    session_model,
    limit: int = DEFAULT_LIMIT,
    end_pk: int | None = None,
    around_pk: int | None = None,
) -> list[Row]:
    """Return the last *limit* turns as a flat list of :class:`Row` objects.

    ``end_pk`` caps the window at (and includes) that message, which lets the
    chat table-of-contents jump to an older compaction boundary.

    ``around_pk`` is a scroll anchor, not a cut-off: the anchor is kept together
    with the newest messages so scrolling down from a jump still reaches the
    end of the conversation.
    """
    ordered_pks = _chain_ordered_pks(session_model, end_pk)
    selected_pks = ordered_pks[-limit:]
    if around_pk is not None:
        pk_index = {pk: index for index, pk in enumerate(ordered_pks)}
        index = pk_index.get(around_pk)
        if index is not None and index < len(ordered_pks) - limit:
            # Anchor is older than the tail.  Include its preceding context and
            # everything up to the newest message when that stays bounded; for
            # very long conversations keep the tail plus the anchor window so
            # the jump target and the latest messages are both reachable.
            start = max(0, index - max(1, limit // 2) + 1)
            if len(ordered_pks) - start <= limit * 2:
                selected_pks = ordered_pks[start:]
            else:
                wanted = set(ordered_pks[start:index + 1]) | set(selected_pks)
                selected_pks = [pk for pk in ordered_pks if pk in wanted]
    if not selected_pks:
        return []

    messages = list(
        Message.objects.filter(pk__in=selected_pks)
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
    )
    position = {pk: index for index, pk in enumerate(selected_pks)}
    messages.sort(key=lambda message: position[message.pk])

    message_pks = [message.pk for message in messages]
    queries = list(
        Query.objects.filter(
            session=session_model,
            trigger_message_id__in=message_pks,
        ).order_by("pk")
    )
    index_by_pk = {pk: index for index, pk in enumerate(message_pks)}
    queries_by_message: dict[int, list[Query]] = {}
    for query in queries:
        anchor_pk = _query_anchor_pk(query, messages, index_by_pk)
        if anchor_pk is not None:
            queries_by_message.setdefault(anchor_pk, []).append(query)

    responses = list(
        Response.objects.filter(query_id__in=[query.pk for query in queries]).order_by("pk")
    )
    latest_by_query: dict[int, Response] = {}
    for response in responses:
        latest_by_query[response.query_id] = response

    # A response that already backs an assistant message is rendered by that
    # message; only unanchored ones (still streaming, or orphaned) get a row.
    # Archived sessions are no exception: appending the anchored responses at
    # the end duplicates the whole conversation a second time.
    anchored = set(
        Message.objects.filter(response_id__in=[response.pk for response in responses])
        .values_list("response_id", flat=True)
    )
    standalone_by_query: dict[int, list[Response]] = {}
    for response in responses:
        if response.pk not in anchored:
            standalone_by_query.setdefault(response.query_id, []).append(response)

    rows: list[Row] = []
    seen_fork_anchor = False
    for message in messages:
        row = _message_row(message)
        if row.is_fork_anchor:
            # A reused child session can accumulate several anchors (one per
            # colliding subtask call).  Show one notice, not a stack of them.
            if seen_fork_anchor:
                continue
            seen_fork_anchor = True
        rows.append(row)
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
                queryset=QueryMessagePart.objects.select_related(
                    "content",
                    "template_data",
                    "source_message_part__content",
                    "source_message_part__template_data",
                    "source_message_part__tool_call__task_definition",
                ).order_by("pk"),
            )
        )
    )
    items: list[dict[str, Any]] = []
    for query_message in query_messages:
        texts: list[str] = []
        for part in query_message.query_message_parts.all():
            text = _query_part_text(part)
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
