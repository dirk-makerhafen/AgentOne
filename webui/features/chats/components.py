"""Chat UI components (thread, messages, composer, sidebar session rows)."""

from __future__ import annotations

from typing import Any

from webui.core.components import ComponentData, ComponentSpec, register


def _int(raw, default):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _terminal_query(query) -> bool:
    """WAITING is non-terminal: queued calls move WAITING -> ACTIVE -> result."""
    from server.models.queries.query import QueryStatus

    return query.status in (
        QueryStatus.SUCCESS,
        QueryStatus.FAILURE,
        QueryStatus.RATE_LIMITED,
    )


def _terminal_response(response) -> bool:
    """WAITING is non-terminal for responses as well (recovery resumes them)."""
    from server.models.queries.response import ResponseStatus

    return response.status in (ResponseStatus.SUCCESS, ResponseStatus.FAILURE)


def _session(pk: int):
    from server.models.sessions.session import SessionModel

    return SessionModel.objects.select_related(
        "latest_session_version__agent",
        "latest_session_version__agent__latest_agent_version",
        "latest_session_version__agent__latest_agent_version__agent_settings",
        "latest_session_version__pinned_agent_version",
        "latest_session_version__session_settings",
        "latest_session_version__workspace",
        "parent_project",
    ).get(pk=pk)


def _message(pk: int):
    from django.db.models import Prefetch

    from server.models.message import Message, MessagePart

    return (
        Message.objects.select_related("response")
        .prefetch_related(
            Prefetch(
                "parts",
                queryset=MessagePart.objects.select_related(
                    "content",
                    "template_data",
                    "tool_call",
                    "tool_call__task_definition",
                    "tool_call__task_definition_version__task_definition",
                ).order_by("pk"),
            )
        )
        .get(pk=pk)
    )


def _build_chat_header(request, pk, params):
    from webui.features.chats.views import _header_context

    session = _session(pk)
    context = _header_context(session)
    keys = [
        f"SessionModel:{pk}",
        f"Query.session:{pk}",
        f"Response.session:{pk}",
        f"AgentTaskCall.session:{pk}",
    ]
    # The header also renders the agent and project names.
    version = getattr(session, "latest_session_version", None)
    if version is not None and version.agent_id:
        keys.append(f"AgentModel:{version.agent_id}")
    if session.parent_project_id:
        keys.append(f"Project:{session.parent_project_id}")
    return ComponentData(context, tuple(keys))


def _build_chat_thread(request, pk, params):
    from webui.features.chats.parts.thread import DEFAULT_LIMIT, build_thread

    session = _session(pk)
    limit = _int(params.get("limit"), DEFAULT_LIMIT)
    limit = max(1, min(limit, 2000))
    around = _int(params.get("around"), None)
    rows = build_thread(session, limit=limit, end_pk=around)

    from server.models.message import Message

    total = Message.objects.filter(session=session)
    if around is not None:
        total = total.filter(pk__lte=around)
    try:
        total_messages = total.count()
    except Exception:  # pylint: disable=broad-exception-caught
        total_messages = len(rows)

    context = {
        "session": session,
        "rows": rows,
        "thread_limit": limit,
        "thread_around": around,
        "thread_has_older": total_messages > limit,
        "thread_older_limit": min(limit + DEFAULT_LIMIT, 2000),
        # Inline child message/query/response components so a thread refetch (e.g.
        # SSE reset on reload) returns a complete thread in one response instead of
        # fanning out placeholders that must each load separately.
        "inline_children": True,
    }
    return ComponentData(
        context,
        (
            f"Message.session:{pk}",
            f"Query.session:{pk}",
            f"Response.session:{pk}",
            f"SessionModel:{pk}",
        ),
    )


def _build_chat_cards(request, pk, params):
    """The status cards under the thread.

    Kept separate from ``chat-thread`` so a task-call status update only swaps
    the cards instead of re-rendering (and potentially replacing) the whole
    conversation.  Message rows update their own tool cards from
    ``AgentTaskCall:<pk>`` keys.
    """
    from webui.features.chats.parts.cards import build_chat_cards

    session = _session(pk)
    return ComponentData(
        {"session": session, "cards": build_chat_cards(session)},
        (
            f"AgentTaskCall.session:{pk}",
            # build_chat_cards() renders provider/key/model details for parked
            # calls, including their rate-limit state.
            "ApiProvider",
            "ApiKey",
            "AiModel",
        ),
    )


def _build_chat_message(request, pk, params):
    from webui.features.chats.parts.thread import _message_row

    message = _message(pk)
    row = _message_row(message)
    session = message.session
    keys = [f"Message:{pk}", f"MessagePart.message:{pk}"]
    # The message footer renders the linked response's status and token count.
    if message.response_id:
        keys.append(f"Response:{message.response_id}")
    for part in message.parts.all():
        call_id = getattr(part, "tool_call_id", None)
        if call_id:
            keys.append(f"AgentTaskCall:{call_id}")
    return ComponentData(
        # ``live`` gates the raw tool-card SSE trigger: an immutable message
        # must not keep observing its call after the session has ended.
        {"row": row, "session": session, "live": session.is_active},
        tuple(keys),
        immutable=not session.is_active,
        reset=False,
    )


def _build_chat_query(request, pk, params):
    from server.models.queries.query import Query
    from webui.features.chats.parts.thread import Row

    query = Query.objects.select_related("session").get(pk=pk)
    response = query.related_response.order_by("-pk").first()
    row = Row("query", query, response=response)
    return ComponentData(
        {"row": row, "session": query.session},
        (f"Query:{pk}", f"Query.session:{query.session_id}", f"Response.query:{pk}"),
        immutable=_terminal_query(query),
        reset=False,
    )


def _build_chat_response(request, pk, params):
    from server.models.queries.response import Response
    from webui.core.markdown import render_markdown
    from webui.features.chats.parts.thread import Row

    response = Response.objects.select_related("session").get(pk=pk)
    row = Row(
        "response",
        response,
        body_html=render_markdown(response.content or ""),
        reasoning=response.reasoning or "",
    )
    return ComponentData(
        {"row": row, "session": response.session},
        (f"Response:{pk}", f"Response.session:{response.session_id}"),
        immutable=_terminal_response(response),
        reset=False,
    )


def _build_chat_toc(request, pk, params):
    from webui.features.chats.session_ui import compaction_segments

    session = _session(pk)
    return ComponentData(
        {"session": session, "toc_segments": compaction_segments(session)},
        (f"Message.session:{pk}",),
    )


def _build_chat_composer(request, pk, params):
    from webui.core.layout import send_key
    from webui.features.chats.session_ui import command_options, composer_config, composer_state

    session = _session(pk)
    context = {"session": session, "send_key": send_key(), "commands": command_options(session)}
    context.update(composer_config(session))
    context.update(composer_state(session))
    return ComponentData(context)


def _build_chat_panel(request, pk, params):
    from webui.features.chats.views import _panel_context

    session = _session(pk)
    tab = params.get("tab") or "details"
    context = _panel_context(session, tab, request)
    return ComponentData(context)


def _visible_child_session_ids(parent_id: int, *, include_archived: bool) -> list[int]:
    from webui.features.chats.sidebar import visible_child_session_ids

    return visible_child_session_ids(parent_id, include_archived=include_archived)


def _build_chat_sidebar_session(request, pk, params):
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from server.models.project import Project
    from server.models.queries.query import Query, QueryStatus
    from server.models.sessions.session import SessionModel
    from server.models.tasks.agent_task_call import AgentTaskCall
    from webui.features.chats.sidebar import SESSION_TREE_MAX_DEPTH

    session = (
        SessionModel.objects.select_related(
            "latest_session_version__agent",
            "latest_session_version__workspace",
            "parent_project",
        )
        .get(pk=pk)
    )
    active_id = _int(params.get("active"), None)
    section = params.get("section") or "chats"
    archived = str(params.get("archived", "")).lower() in ("1", "true", "yes")
    depth = max(0, _int(params.get("depth"), 0))
    session.tree_depth = depth

    is_streaming = Query.objects.filter(
        session_version__session_id=pk, status=QueryStatus.ACTIVE
    ).exists() or AgentTaskCall.objects.filter(session_id=pk).exclude(status=TaskCallStatus.ENDED).exists()
    needs_approval = AgentTaskCall.objects.filter(
        session_id=pk,
        requires_approval=True,
        status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
    ).exists()

    child_depth = depth + 1
    child_pks = []
    if child_depth <= SESSION_TREE_MAX_DEPTH:
        child_pks = _visible_child_session_ids(pk, include_archived=archived)

    context = {
        "s": session,
        "active_id": active_id,
        "section": section,
        "archived": archived,
        "is_streaming": is_streaming,
        "needs_approval": needs_approval,
        "projects": list(Project.objects.order_by("name")),
        "child_pks": child_pks,
        "child_depth": child_depth,
    }
    keys = (
        f"SessionModel:{pk}",
        f"Query.session:{pk}",
        f"AgentTaskCall.session:{pk}",
        f"SessionModel.parent_session:{pk}@is_archived:{'true' if archived else 'false'}",
        # The row also renders workspace/agent names and the project list.
        "WorkspaceModel",
        "AgentModel",
        "Project",
    )
    return ComponentData(context, keys, reset=False)


def register_chat_components():
    register(ComponentSpec("chat-header", "chats/parts/header.html", _build_chat_header))
    register(ComponentSpec("chat-thread", "chats/parts/thread.html", _build_chat_thread))
    register(ComponentSpec("chat-cards", "chats/parts/cards.html", _build_chat_cards))
    register(ComponentSpec("chat-message", "chats/parts/message.html", _build_chat_message))
    register(ComponentSpec("chat-query", "chats/parts/query.html", _build_chat_query))
    register(ComponentSpec("chat-response", "chats/parts/response.html", _build_chat_response))
    register(ComponentSpec("chat-toc", "chats/parts/toc.html", _build_chat_toc))
    register(ComponentSpec("chat-composer", "chats/parts/composer.html", _build_chat_composer))
    register(ComponentSpec("chat-panel", "chats/rightbar.html", _build_chat_panel))
    register(ComponentSpec("chat-sidebar-session", "chats/parts/sidebar_session.html", _build_chat_sidebar_session))
