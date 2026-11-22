"""Component contract tests: cache policy, placeholders, ETags, SSE triggers.

Every element with server-derived state is served from ``/app/c/<name>``.  The
tests here pin the pieces that are easy to regress silently:

* ``render=htmx`` emits placeholders for children, never a nested live tree;
* ``render=full`` emits a complete tree for no-JS clients;
* live components revalidate with an ETag and answer ``204`` when unchanged;
* immutable components get a long-lived cache header and no SSE trigger;
* component wrappers are preserved so parent swaps can keep loaded children.
"""
from __future__ import annotations

import re

import pytest
from django.urls import reverse

from webui.core.components import component_id, component_url

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _disable_webui_login(settings):
    settings.WEBUI_LOGIN_REQUIRED = False


def _chat_session(name="component-session"):
    from server.models.message import Message
    from server.models.enums.message_enums import MessageRole
    from server.tests.dc_test_helpers import create_agent, create_session

    agent, version = create_agent(f"{name}-agent")
    session, sv = create_session(agent, version)
    message = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )
    return agent, version, session, sv, message


def _get(client, name, pk=None, **params):
    args = [name] if pk is None else [name, pk]
    return client.get(reverse("webui:component", args=args) if pk else
                      reverse("webui:component_root", args=args), params)


# ---------------------------------------------------------------------------
# URLs and ids
# ---------------------------------------------------------------------------

def test_component_urls_are_deterministic_and_include_params():
    url = component_url("chat-thread", 5, {"limit": 40}, htmx=True)
    assert url == "/app/c/chat-thread/5?limit=40&render=htmx"
    assert component_url("chat-thread", 5, {"limit": 40}, htmx=False).endswith(
        "/app/c/chat-thread/5?limit=40"
    )
    assert component_url("chats-sidebar", None, {}, htmx=True) == (
        "/app/chats/sidebar?render=htmx"
    )


def test_component_ids_change_with_params():
    first = component_id("chat-thread", 1, {"limit": 40})
    second = component_id("chat-thread", 1, {"limit": 80})
    assert first != second
    assert first.startswith("c-chat-thread-1-")


def test_unknown_component_returns_404(client):
    response = client.get("/app/c/does-not-exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# live components: ETag, 204, cache control
# ---------------------------------------------------------------------------

def test_live_component_revalidates_with_etag(client):
    _agent, _version, session, _sv, _message = _chat_session("etag")

    first = _get(client, "chat-header", session.pk, render="htmx")
    assert first.status_code == 200
    assert first["Cache-Control"] == "private, no-cache"
    assert "Cookie" in first["Vary"]
    etag = first["ETag"]

    unchanged = client.get(
        reverse("webui:component", args=["chat-header", session.pk]),
        {"render": "htmx"},
        HTTP_IF_NONE_MATCH=etag,
        HTTP_X_AGENTONE_ETAG="1",
    )
    assert unchanged.status_code == 204
    assert unchanged.content == b""
    assert unchanged["ETag"] == etag


def test_browser_native_etag_revalidation_never_skips_a_lazy_component(client):
    """A bare If-None-Match must return 200 so a placeholder can populate."""
    _agent, _version, session, _sv, _message = _chat_session("native-etag")

    first = _get(client, "chat-header", session.pk, render="htmx")
    browser_revalidation = client.get(
        reverse("webui:component", args=["chat-header", session.pk]),
        {"render": "htmx"},
        HTTP_IF_NONE_MATCH=first["ETag"],
    )
    assert browser_revalidation.status_code == 200
    assert browser_revalidation["ETag"] == first["ETag"]
    assert b'data-component="chat-header"' in browser_revalidation.content


def test_changed_component_returns_a_new_etag(client):
    _agent, _version, session, _sv, _message = _chat_session("etag-change")
    first = _get(client, "chat-header", session.pk, render="htmx")

    from server.models.sessions.session import SessionModel

    SessionModel.objects.filter(pk=session.pk).update(name="renamed header")

    second = client.get(
        reverse("webui:component", args=["chat-header", session.pk]),
        {"render": "htmx"},
        HTTP_IF_NONE_MATCH=first["ETag"],
        HTTP_X_AGENTONE_ETAG="1",
    )
    assert second.status_code == 200
    assert second["ETag"] != first["ETag"]
    assert b"renamed header" in second.content


def test_live_component_carries_sse_triggers_on_the_wrapper(client):
    _agent, _version, session, _sv, _message = _chat_session("triggers")
    response = _get(client, "chat-header", session.pk, render="htmx")
    body = response.content.decode()

    assert 'data-component="chat-header"' in body
    assert f"sse:SessionModel:{session.pk}" in body
    assert f"sse:Query.session:{session.pk}" in body
    assert "sse:reset" in body
    # Wrappers are preserved so a loaded component survives parent swaps.
    assert "hx-preserve" in body
    assert 'hx-swap="outerHTML"' in body


def test_component_wrapper_disinherits_layout_attrs_but_not_boost(client):
    """Children must not inherit the wrapper's swap target/sync.

    A boosted link inside a wrapper used to inherit ``hx-sync="this:replace"``,
    so the wrapper's SSE refetch aborted the link request.  ``hx-boost`` must
    keep inheriting from ``<body>``.
    """
    _agent, _version, session, _sv, _message = _chat_session("disinherit")
    body = _get(client, "chat-header", session.pk, render="htmx").content.decode()
    tag = re.search(r'<div[^>]*data-component="chat-header"[^>]*>', body)
    assert tag is not None
    value = re.search(r'hx-disinherit="([^"]*)"', tag.group(0))
    assert value is not None
    disinherit = value.group(1).split()
    for attr in ("hx-target", "hx-swap", "hx-sync", "hx-push-url",
                 "hx-select", "hx-confirm", "hx-params"):
        assert attr in disinherit
    assert "hx-boost" not in disinherit
    assert "*" not in disinherit
    # ``hx-disinherit`` is checked on the ancestor that owns the attribute, so
    # it cannot stop a parent target from capturing this wrapper's own request.
    assert 'hx-target="this"' in tag.group(0)


def test_immutable_component_gets_a_long_cache_and_no_trigger(client):
    _agent, _version, session, _sv, message = _chat_session("immutable")

    live = _get(client, "chat-message", message.pk, render="htmx")
    assert live["Cache-Control"] == "private, no-cache"
    assert f"sse:Message:{message.pk}" in live.content.decode()

    from server.models.sessions.session import SessionModel

    SessionModel.objects.filter(pk=session.pk).update(is_active=False)
    ended = _get(client, "chat-message", message.pk, render="htmx")
    assert ended["Cache-Control"] == "private, max-age=31536000, immutable"
    assert "sse:" not in ended.content.decode()


@pytest.mark.parametrize(
    "status,immutable",
    [
        ("WAITING", False),
        ("ACTIVE", False),
        ("SUCCESS", True),
        ("FAILURE", True),
        ("RATE_LIMITED", True),
    ],
)
def test_query_card_is_immutable_only_after_a_terminal_status(client, status, immutable):
    """WAITING is a queued state: call_llm moves it to ACTIVE before a result."""
    from server.models.queries.query import Query

    _agent, _version, session, sv, _message = _chat_session(f"query-{status}")
    query = Query.objects.create(session=session, session_version=sv, status=status)

    response = _get(client, "chat-query", query.pk, render="htmx")
    body = response.content.decode()
    if immutable:
        assert response["Cache-Control"] == "private, max-age=31536000, immutable"
        assert "sse:" not in body
    else:
        assert response["Cache-Control"] == "private, no-cache"
        assert f"sse:Query:{query.pk}" in body


@pytest.mark.parametrize(
    "status,immutable",
    [
        ("WAITING", False),
        ("ACTIVE", False),
        ("SUCCESS", True),
        ("FAILURE", True),
    ],
)
def test_response_card_is_immutable_only_after_a_terminal_status(client, status, immutable):
    from server.models.queries.response import Response

    _agent, _version, session, sv, _message = _chat_session(f"response-{status}")
    row = Response.objects.create(session=session, session_version=sv, status=status)

    response = _get(client, "chat-response", row.pk, render="htmx")
    body = response.content.decode()
    if immutable:
        assert response["Cache-Control"] == "private, max-age=31536000, immutable"
        assert "sse:" not in body
    else:
        assert response["Cache-Control"] == "private, no-cache"
        assert f"sse:Response:{row.pk}" in body


def test_keyless_component_does_not_refetch_on_bubbled_clicks(client):
    """A keyless wrapper must not fall back to htmx's default `click` trigger.

    ``chat-panel`` has no SSE keys.  With no explicit trigger, htmx wires its
    hx-get to `click`, so clicking a panel tab bubbled to the wrapper and the
    stale component response replaced the panel the tab had just switched.
    """
    _agent, _version, session, _sv, _message = _chat_session("keyless")
    body = _get(client, "chat-panel", session.pk, render="htmx").content.decode()
    wrapper = re.search(r'<div[^>]*data-component="chat-panel"[^>]*>', body)
    assert wrapper is not None
    assert 'hx-trigger="agentone:none"' in wrapper.group(0)
    assert "click" not in wrapper.group(0)


# ---------------------------------------------------------------------------
# render modes
# ---------------------------------------------------------------------------

def test_htmx_render_inlines_chat_thread_children(client):
    """Chat thread inlines children on htmx renders to avoid N+1 placeholder fan-out."""
    _agent, _version, session, _sv, message = _chat_session("inline-thread")
    response = _get(client, "chat-thread", session.pk, render="htmx")
    body = response.content.decode()

    assert 'data-component="chat-thread"' in body
    assert 'data-component="chat-message"' in body
    # Children are rendered inline as live components, not self-loading placeholders.
    assert "msg-row" in body
    assert f"sse:Message:{message.pk}" in body
    assert 'hx-trigger="load, intersect once"' not in body
    assert "hx-preserve" in body


def test_thread_does_not_reload_for_task_call_status_changes(client):
    """Status cards are their own component, not a reason to swap the thread.

    ``AgentTaskCall.session`` fires for every tool status change.  Keeping it on
    ``chat-thread`` replaced the whole conversation (scroll, open cards, focus)
    just to refresh the queue/approval card.
    """
    _agent, _version, session, _sv, _message = _chat_session("thread-task-keys")
    body = _get(client, "chat-thread", session.pk, render="htmx").content.decode()

    thread = re.search(r'<div[^>]*data-component="chat-thread"[^>]*>', body)
    assert thread is not None
    assert f"sse:AgentTaskCall.session:{session.pk}" not in thread.group(0)
    assert 'data-component="chat-cards"' in body
    cards = re.search(r'<div[^>]*data-component="chat-cards"[^>]*>', body)
    assert cards is not None
    assert f"sse:AgentTaskCall.session:{session.pk}" in cards.group(0)


# ---------------------------------------------------------------------------
# ad-hoc live fragments
# ---------------------------------------------------------------------------

def test_live_fragment_revalidates_with_etag(client):
    """The composer footer must not be swapped when its HTML did not change."""
    _agent, _version, session, _sv, _message = _chat_session("fragment-etag")

    first = client.get(reverse("webui:chat_composer_footer", args=[session.pk]))
    assert first.status_code == 200
    assert first["Cache-Control"] == "private, no-cache"
    assert "Cookie" in first["Vary"]
    etag = first["ETag"]
    assert etag

    unchanged = client.get(
        reverse("webui:chat_composer_footer", args=[session.pk]),
        HTTP_IF_NONE_MATCH=etag,
        HTTP_X_AGENTONE_ETAG="1",
    )
    assert unchanged.status_code == 204
    assert unchanged.content == b""
    assert unchanged["ETag"] == etag


def test_browser_native_etag_revalidation_never_skips_a_lazy_fragment(client):
    """The detail pane stays "Loading…" if its first GET answers 204."""
    _agent, _version, session, _sv, _message = _chat_session("fragment-native-etag")

    url = reverse("webui:chat_composer_footer", args=[session.pk])
    first = client.get(url)
    browser_revalidation = client.get(url, HTTP_IF_NONE_MATCH=first["ETag"])
    assert browser_revalidation.status_code == 200
    assert browser_revalidation.content == first.content


def test_live_fragment_etag_changes_with_state(client):
    _agent, _version, session, _sv, _message = _chat_session("fragment-etag-change")

    first = client.get(reverse("webui:chat_composer_footer", args=[session.pk]))
    etag = first["ETag"]

    from server.models.sessions.session import SessionModel

    SessionModel.objects.filter(pk=session.pk).update(is_paused=True)
    changed = client.get(
        reverse("webui:chat_composer_footer", args=[session.pk]),
        HTTP_IF_NONE_MATCH=etag,
        HTTP_X_AGENTONE_ETAG="1",
    )
    assert changed.status_code == 200
    assert changed["ETag"] != etag
    assert b"Paused" in changed.content


def test_panel_body_fragment_revalidates_with_etag(client):
    _agent, _version, session, _sv, _message = _chat_session("panel-etag")

    url = reverse("webui:chat_panel_tab", args=[session.pk, "details"])
    first = client.get(url)
    assert first.status_code == 200
    etag = first["ETag"]

    unchanged = client.get(url, HTTP_IF_NONE_MATCH=etag, HTTP_X_AGENTONE_ETAG="1")
    assert unchanged.status_code == 204


def test_full_render_inlines_children_without_preserve(client):
    _agent, _version, session, _sv, message = _chat_session("inline")
    response = _get(client, "chat-thread", session.pk)  # render defaults to full
    body = response.content.decode()

    assert 'data-component="chat-thread"' in body
    assert 'data-component="chat-message"' in body
    assert f"sse:Message:{message.pk}" in body
    # Loaded wrappers are preserved; they must not behave as placeholders.
    assert "hx-preserve" in body
    assert 'hx-trigger="load' not in body


def test_full_document_has_no_component_placeholders(client):
    _agent, _version, session, _sv, message = _chat_session("document")
    response = client.get(reverse("webui:chat", args=[session.pk]))
    body = response.content.decode()

    assert response.status_code == 200
    # Full document loads inline components (no placeholder load triggers).
    assert 'hx-trigger="load' not in body
    assert 'data-component="chat-thread"' in body
    assert f"sse:Message:{message.pk}" in body


def test_boosted_shell_only_preserves_placeholders(client):
    _agent, _version, session, _sv, _message = _chat_session("boosted")
    response = client.get(reverse("webui:chat", args=[session.pk]), HTTP_HX_REQUEST="true")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-component="chat-thread"' in body
    # Boosted shells emit placeholders: preserved wrappers that self-load and
    # carry no ETag until the component has rendered.
    for tag in re.findall(r"<div[^>]*hx-trigger=\"load[^\"]*\"[^>]*>", body):
        assert "hx-preserve" in tag
        assert "data-component-etag" not in tag
    # A placeholder never embeds its children; the thread loads them itself.
    assert 'data-component="chat-message"' not in body


# ---------------------------------------------------------------------------
# section sidebars
# ---------------------------------------------------------------------------

def test_every_section_sidebar_route_is_wrapped_as_a_component(client):
    for section in ("dashboard", "chats", "agents", "projects", "workspaces", "skills"):
        response = client.get(reverse(f"webui:{section}_sidebar"), {"render": "htmx"})
        assert response.status_code == 200, section
        body = response.content.decode()
        assert f'data-component="{section}-sidebar"' in body
        assert 'id="sidebar"' in body
        assert 'class="c"' in body


def test_sidebar_component_placeholder_keeps_the_landmark(client):
    from webui.core.components import render_component_ref

    html = render_component_ref(
        {"component_inline": False}, "chats-sidebar", None, {}
    )
    assert 'id="sidebar"' in html
    assert "hx-preserve" in html
    assert 'hx-trigger="load' in html


def test_sidebar_full_render_contains_the_panel(client):
    response = client.get(reverse("webui:chats_sidebar"))
    assert response.status_code == 200
    assert b"webui-brand" in response.content
    assert b"New chat" in response.content


def test_sidebar_htmx_render_inlines_its_rows(client):
    """A list container must not fan out N child loads on an SSE reset."""
    _agent, _version, session, _sv, _message = _chat_session("sidebar-inline")
    response = client.get(reverse("webui:chats_sidebar"), {"render": "htmx"})
    body = response.content.decode()

    assert 'data-component="chat-sidebar-session"' in body
    assert "session-item" in body
    assert 'hx-trigger="load, intersect once"' not in body


# ---------------------------------------------------------------------------
# query detail (lazily loaded chat query card)
# ---------------------------------------------------------------------------

def _source_backed_query(session, sv, user_text, assistant_text):
    """Build the query shape produced by ``build_llm_context``.

    Query parts normally reference a ``MessagePart`` and own no content of
    their own.  The expanded card must still show the text that was sent.
    """
    from server.models.enums.message_enums import MessageRole
    from server.models.message import Message
    from server.models.queries.query import Query

    user_message = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )
    user_message.add_part("message", "text", user_text)
    assistant_message = Message.objects.create(
        role=MessageRole.ASSISTANT, session=session, session_version=sv
    )
    assistant_message.add_part("message", "text", assistant_text)

    query = Query.objects.create(session=session, session_version=sv)
    query.add_message(role=MessageRole.USER, source_message=user_message)
    query.add_message(role=MessageRole.ASSISTANT, source_message=assistant_message)
    return query


def test_query_detail_uses_source_part_content(client):
    from webui.features.chats.parts.thread import build_query_detail

    _agent, _version, session, sv, _message = _chat_session("query-detail")
    query = _source_backed_query(session, sv, "question text", "answer text")

    detail = build_query_detail(query)

    assert [item["text"] for item in detail] == ["question text", "answer text"]


def test_query_detail_endpoint_renders_source_part_content(client):
    _agent, _version, session, sv, _message = _chat_session("query-detail-view")
    query = _source_backed_query(session, sv, "question text", "answer text")

    response = client.get(reverse("webui:query_detail", args=[query.pk]))

    assert response.status_code == 200
    body = response.content.decode()
    assert "question text" in body
    assert "answer text" in body


# ---------------------------------------------------------------------------
# dashboard live activity
# ---------------------------------------------------------------------------

def _active_query(session, sv, message, *, status="ACTIVE", response_status="ACTIVE"):
    from server.models.queries.query import Query
    from server.models.queries.response import Response

    query = Query.objects.create(
        session=session, session_version=sv, trigger_message=message, status=status
    )
    response = Response.objects.create(
        query=query,
        session=session,
        session_version=sv,
        status=response_status,
        model_name="test-model",
        prompt_tokens=1200,
        completion_tokens=340,
        content="Working on the answer right now",
    )
    return query, response


def test_dashboard_activity_shows_running_query_with_session_details(client):
    from server.models.enums.message_enums import MessageRole
    from server.models.message import Message
    from server.models.project import Project

    agent, _version, session, sv, _message = _chat_session("dash-activity")
    session.name = "research run"
    session.parent_project = Project.objects.create(name="Atlas")
    session.save()
    trigger = Message.objects.create(
        role=MessageRole.USER, session=session, session_version=sv
    )
    trigger.add_part("message", "text", "What is the deployment status?")
    query, response = _active_query(session, sv, trigger)

    result = _get(client, "dashboard-activity", render="htmx")
    body = result.content.decode()

    assert result.status_code == 200
    assert 'data-component="dashboard-activity"' in body
    assert f'sse:Query:{query.pk}' in body
    assert f'sse:Response:{response.pk}' in body
    assert "sse:SessionModel" in body
    assert "research run" in body
    assert "Atlas" in body
    assert agent.name in body
    assert "What is the deployment status?" in body
    assert "Working on the answer right now" in body
    assert "test-model" in body
    assert "1,540" in body  # prompt + completion tokens
    assert "Streaming" in body
    assert reverse("webui:chat", args=[session.pk]) in body
    assert reverse("webui:query_detail", args=[query.pk]) not in body
    assert reverse("webui:response_detail", args=[response.pk]) not in body
    assert "started" in body and "updated" in body


def test_dashboard_activity_shows_tail_of_streaming_response(client):
    """The overview shows the newest lines, not the first line of the answer."""
    _agent, _version, session, sv, message = _chat_session("dash-tail")
    _query, response = _active_query(session, sv, message)
    response.content = "\n".join(
        [
            "Intro paragraph that was written first",
            "Some middle detail about the deployment",
            "Still waiting on the staging results",
            "Checking the second cluster now",
            "All three nodes are healthy and the rollout is done",
        ]
    )
    response.save()

    body = _get(client, "dashboard-activity", render="htmx").content.decode()

    assert "All three nodes are healthy" in body
    assert "Checking the second cluster now" in body
    assert "Intro paragraph that was written first" not in body
    assert "Some middle detail" not in body


def test_dashboard_activity_terminal_query_is_hidden_and_etag_is_stable(client):
    from server.models.queries.response import ResponseStatus

    _agent, _version, session, sv, message = _chat_session("dash-quiet")
    query, response = _active_query(
        session, sv, message, status="SUCCESS", response_status=ResponseStatus.SUCCESS
    )

    first = _get(client, "dashboard-activity", render="htmx")
    body = first.content.decode()
    assert b"All quiet" in first.content
    assert f"Query:{query.pk}" not in body
    assert f"Response:{response.pk}" not in body
    assert first["Cache-Control"] == "private, no-cache"

    unchanged = client.get(
        reverse("webui:component_root", args=["dashboard-activity"]),
        {"render": "htmx"},
        HTTP_IF_NONE_MATCH=first["ETag"],
        HTTP_X_AGENTONE_ETAG="1",
    )
    assert unchanged.status_code == 204
