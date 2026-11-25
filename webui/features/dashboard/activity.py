"""Data for the dashboard's live activity overview.

A single card pairs an unfinished query with its newest response and the
session that owns it.  Everything here is read-only: the SSE keys come from the
read-side observable API, and streaming token flushes are covered by the
per-row ``Query:<pk>`` / ``Response:<pk>`` keys the consumer subscribes to.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.utils import timezone

from runtime.observable_queries.conversation import QueryObservables, ResponseObservables

#: After this long without a write, an "active" row is probably orphaned (the
#: recovery scheduler is disabled on some installs).  Surface it, don't hide it.
STALE_AFTER = timedelta(minutes=15)
PREVIEW_LIMIT = 400
#: How many trailing lines of a streamed response to keep in the overview.
OUTPUT_LINES = 4
#: Trailing lines of the triggering prompt to show (at least a couple).
PROMPT_LINES = 3


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _tail_preview(value: Any, limit: int = PREVIEW_LIMIT, lines: int = OUTPUT_LINES) -> str:
    """The last few readable lines, so newly streamed tokens stay visible.

    Response content grows at the end as tokens arrive.  Keeping the *tail*
    (rather than the first line) means an SSE refresh shows the newest text.
    """
    cleaned: list[str] = []
    for raw_line in _text(value).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("```", "#", "---")):
            continue
        line = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)
        line = re.sub(r"[*_`>#]+", "", line).strip()
        line = " ".join(line.split())
        if line:
            cleaned.append(line)
    if not cleaned:
        return ""
    result = "\n".join(cleaned[-lines:])
    if len(result) > limit:
        # Keep the very end (the freshest tokens), not the beginning.
        result = "…" + result[-(limit - 1) :]
    return result


def _prompt_preview(query) -> str:
    """Preview the user message that triggered *query* (source-backed parts)."""
    message = getattr(query, "trigger_message", None)
    if message is None:
        return ""
    texts: list[str] = []
    for part in message.parts.select_related("content").order_by("pk")[:8]:
        if part.content_id is None or str(part.content_type) == "IMAGE":
            continue
        try:
            value = part.content.get()
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        text = _text(value).strip()
        if text:
            texts.append(text)
    return _tail_preview("\n".join(texts), lines=PROMPT_LINES)


@dataclass
class ToolCallView:
    """One tool call, rendered as a chip while its arguments stream in."""

    name: str
    args: str = ""
    complete: bool = True


def _tool_calls(response, limit: int = 4) -> tuple[list[ToolCallView], int]:
    """Tool calls with a readable argument preview, newest last.

    During streaming ``arguments`` is a growing JSON *string* (often truncated
    mid-token); at the end it is parsed into a dict.  Both forms are shown, and
    incomplete ones are flagged so the UI can mark them as still streaming.
    """
    calls = response.tool_calls or []
    views: list[ToolCallView] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or "").strip() or "tool"
        raw = call.get("arguments")
        complete = True
        if isinstance(raw, str):
            text = raw.strip()
            try:
                parsed = json.loads(text) if text else {}
                raw = parsed
            except (TypeError, ValueError):
                complete = False
        if isinstance(raw, dict):
            parts = []
            for key, value in list(raw.items())[:4]:
                value_text = _text(value).strip()
                if len(value_text) > 60:
                    value_text = value_text[:59] + "…"
                parts.append(f"{key}={value_text}" if value_text else key)
            args = " ".join(parts)
        else:
            args = _text(raw).strip()
        if len(args) > 120:
            args = args[:119] + "…"
        views.append(ToolCallView(name=name, args=args, complete=complete))
    return views[:limit], max(0, len(views) - limit)


@dataclass
class ActivityItem:
    """One card in the live overview."""

    query: Any = None
    response: Any = None
    session: Any = None
    agent: Any = None
    workspace: Any = None
    project: Any = None
    parent_session: Any = None
    state: str = "active"
    state_label: str = "Working"
    prompt: str = ""
    output: str = ""
    tools: list[ToolCallView] = field(default_factory=list)
    extra_tools: int = 0
    current_call: str = ""
    needs_approval: bool = False
    model: str = ""
    chars: int = 0
    started: Any = None
    last_update: Any = None
    stale: bool = False
    row_pk: int = 0
    row_kind: str = "query"

    @property
    def is_streaming(self) -> bool:
        return self.state == "active"


@dataclass
class ActivityData:
    items: list[ActivityItem]
    keys: tuple[str, ...]
    active_count: int
    waiting_count: int
    approval_count: int


def _call_context(session_ids: list[int]) -> tuple[dict[int, Any], set[int]]:
    """Latest running call and approval-needing sessions, in two queries."""
    if not session_ids:
        return {}, set()
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from server.models.tasks.agent_task_call import AgentTaskCall

    running: dict[int, Any] = {}
    calls = (
        AgentTaskCall.objects.filter(session_id__in=session_ids, status=TaskCallStatus.ACTIVE)
        .select_related("task_definition")
        .order_by("-created_at", "-pk")
    )
    for call in calls:
        running.setdefault(call.session_id, call)

    approval = set(
        AgentTaskCall.objects.filter(
            session_id__in=session_ids,
            requires_approval=True,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
        ).values_list("session_id", flat=True)
    )
    return running, approval


def _build_item(query, response, running, approval) -> ActivityItem:
    owner = query or response
    session = getattr(owner, "session", None)
    version = getattr(owner, "session_version", None)
    agent = getattr(version, "agent", None) if version else None
    workspace = getattr(version, "workspace", None) if version else None
    project = getattr(session, "parent_project", None) if session else None
    parent = getattr(session, "parent_session", None) if session else None

    query_active = bool(query) and str(query.status) == "ACTIVE"
    response_active = bool(response) and str(response.status) == "ACTIVE"
    is_streaming = query_active or response_active
    if is_streaming:
        state, label = "active", ("Streaming" if response_active else "Working")
    else:
        state, label = "waiting", "Queued"

    call = running.get(session.pk) if session else None
    call_name = ""
    if call is not None:
        definition = getattr(call, "task_definition", None)
        call_name = str(getattr(definition, "name", "") or "")

    started = getattr(query, "created_at", None) or getattr(response, "created_at", None)
    last_update = getattr(response, "updated_at", None) or getattr(query, "updated_at", None)
    if query is not None and query.updated_at and (last_update is None or query.updated_at > last_update):
        last_update = query.updated_at

    output = ""
    if response is not None:
        output = _tail_preview(response.content or "") or (_tail_preview(response.reasoning or "", 400, lines=4) if response.reasoning else "")

    tools, extra_tools = _tool_calls(response) if response else ([], 0)
    # Tokens are only reported once the LLM call finishes; count streamed
    # characters instead so the number moves while new tokens arrive.
    chars = len(response.content or "") + len(response.reasoning or "") if response else 0 + len(json.dumps(response.tool_calls or [])) if response and response.tool_calls else 0
    return ActivityItem(
        query=query,
        response=response,
        session=session,
        agent=agent,
        workspace=workspace,
        project=project,
        parent_session=parent,
        state=state,
        state_label=label,
        prompt=_prompt_preview(query) if query else "",
        output=output,
        tools=tools,
        extra_tools=extra_tools,
        current_call=call_name,
        needs_approval=bool(session and session.pk in approval),
        model=(getattr(response, "model_name", "") or getattr(response, "provider_name", ""))
        if response
        else "",
        chars=chars,
        started=started,
        last_update=last_update,
        stale=bool(last_update and timezone.now() - last_update > STALE_AFTER),
        row_pk=query.pk if query else response.pk,
        row_kind="query" if query else "response",
    )


def build_activity() -> ActivityData:
    """Collect unfinished queries/responses with their session context."""
    query_list = QueryObservables().unfinished()
    response_list = ResponseObservables().unfinished()

    # Newest active response per query (the list is ordered newest first).
    response_by_query: dict[int, Any] = {}
    for response in response_list.rows:
        if response.query_id and response.query_id not in response_by_query:
            response_by_query[response.query_id] = response

    pairs: list[tuple[Any, Any]] = []
    attached_responses: set[int] = set()
    for query in query_list.rows:
        response = response_by_query.get(query.pk)
        if response is None:
            # A retry may have finished one response while the query itself is
            # still ACTIVE; show the latest one so the card has real content.
            response = query.related_response.order_by("-pk").first()
        if response is not None:
            attached_responses.add(response.pk)
        pairs.append((query, response))

    # A response can outlive a terminal query (recovery/resume edge case).
    for response in response_list.rows:
        if response.pk not in attached_responses:
            pairs.append((None, response))

    session_ids = [
        (query or response).session_id
        for query, response in pairs
        if (query or response).session_id
    ]
    running, approval = _call_context(session_ids)
    items = [_build_item(query, response, running, approval) for query, response in pairs]
    items.sort(key=lambda item: (item.query or item.response).pk, reverse=True)

    # The container only owns list membership and the summary counts.  Per-row
    # streaming keys belong to the row components themselves — a 1 Hz token
    # flush publishes just ``Response:<pk>`` and must not redraw this overview.
    keys = list(query_list.keys) + list(response_list.keys) + ["AgentTaskCall"]

    return ActivityData(
        items=items,
        keys=tuple(dict.fromkeys(keys)),
        active_count=sum(item.is_streaming for item in items),
        waiting_count=sum(not item.is_streaming for item in items),
        approval_count=sum(item.needs_approval for item in items),
    )


def build_activity_row(pk: int, kind: str) -> tuple[ActivityItem | None, tuple[str, ...]]:
    """Rebuild one activity row and the SSE keys it alone should watch."""
    from server.models.queries.query import Query
    from server.models.queries.response import Response, ResponseStatus

    query = response = None
    if kind == "query":
        query = (
            Query.objects.select_related(
                "session",
                "session__parent_project",
                "session__parent_session",
                "session_version__agent",
                "session_version__workspace",
                "trigger_message",
            )
            .filter(pk=pk)
            .first()
        )
        if query is None:
            return None, ()
        response = (
            Response.objects.filter(
                query_id=pk,
                status__in=(ResponseStatus.WAITING, ResponseStatus.ACTIVE),
            )
            .select_related(
                "session",
                "session__parent_project",
                "session__parent_session",
                "session_version__agent",
                "session_version__workspace",
            )
            .order_by("-created_at", "-pk")
            .first()
        )
        if response is None:
            response = query.related_response.order_by("-pk").first()
    else:
        response = (
            Response.objects.select_related(
                "query",
                "session",
                "session__parent_project",
                "session__parent_session",
                "session_version__agent",
                "session_version__workspace",
            )
            .filter(pk=pk)
            .first()
        )
        if response is None:
            return None, ()

    owner = query or response
    session_pk = owner.session_id
    running, approval = _call_context([session_pk] if session_pk else [])
    item = _build_item(query, response, running, approval)

    keys = []
    if query is not None:
        keys.append(f"Query:{query.pk}")
    if response is not None:
        keys.append(f"Response:{response.pk}")
    if session_pk:
        keys.extend((f"SessionModel:{session_pk}", f"AgentTaskCall.session:{session_pk}"))
    return item, tuple(dict.fromkeys(keys))
