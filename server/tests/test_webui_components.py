"""Component contract tests: cache policy, placeholders, ETags, SSE triggers.

Every element with server-derived state is served from ``/app/c/<name>``.  The
tests here pin the pieces that are easy to regress silently:

* ``render=htmx`` emits placeholders for children, never a nested live tree;
* ``render=full`` emits a complete tree for no-JS clients;
* live components revalidate with an ETag and answer ``204`` when unchanged;
* immutable components get a long-lived cache header and no SSE trigger;
* the shell only ever puts ``hx-preserve`` on placeholders.
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
    )
    assert unchanged.status_code == 204
    assert unchanged.content == b""
    assert unchanged["ETag"] == etag


def test_changed_component_returns_a_new_etag(client):
    _agent, _version, session, _sv, _message = _chat_session("etag-change")
    first = _get(client, "chat-header", session.pk, render="htmx")

    from server.models.sessions.session import SessionModel

    SessionModel.objects.filter(pk=session.pk).update(name="renamed header")

    second = client.get(
        reverse("webui:component", args=["chat-header", session.pk]),
        {"render": "htmx"},
        HTTP_IF_NONE_MATCH=first["ETag"],
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
    # The rendered root itself is never preserved; only placeholders are.
    assert "hx-preserve" not in body
    assert 'hx-swap="outerHTML"' in body


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


# ---------------------------------------------------------------------------
# render modes
# ---------------------------------------------------------------------------

def test_htmx_render_emits_placeholders_for_children(client):
    _agent, _version, session, _sv, message = _chat_session("placeholders")
    response = _get(client, "chat-thread", session.pk, render="htmx")
    body = response.content.decode()

    assert 'data-component="chat-thread"' in body
    assert f'data-component="chat-message"' in body
    # Placeholder: loads itself, preserved across the parent swap, no content.
    assert 'hx-trigger="load"' in body
    assert "hx-preserve" in body
    assert "msg-row" not in body


def test_full_render_inlines_children_without_preserve(client):
    _agent, _version, session, _sv, message = _chat_session("inline")
    response = _get(client, "chat-thread", session.pk)  # render defaults to full
    body = response.content.decode()

    assert 'data-component="chat-thread"' in body
    assert 'data-component="chat-message"' in body
    assert f"sse:Message:{message.pk}" in body
    assert "hx-preserve" not in body
    assert 'hx-trigger="load"' not in body


def test_full_document_has_no_component_placeholders(client):
    _agent, _version, session, _sv, message = _chat_session("document")
    response = client.get(reverse("webui:chat", args=[session.pk]))
    body = response.content.decode()

    assert response.status_code == 200
    assert "hx-preserve" not in body
    assert 'data-component="chat-thread"' in body
    assert f"sse:Message:{message.pk}" in body


def test_boosted_shell_only_preserves_placeholders(client):
    _agent, _version, session, _sv, _message = _chat_session("boosted")
    response = client.get(reverse("webui:chat", args=[session.pk]), HTTP_HX_REQUEST="true")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-component="chat-thread"' in body
    # Every hx-preserve sits on a placeholder that also loads itself.
    for tag in re.findall(r"<div[^>]*hx-preserve[^>]*>", body):
        assert 'hx-trigger="load"' in tag
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
    assert 'hx-trigger="load"' in html


def test_sidebar_full_render_contains_the_panel(client):
    response = client.get(reverse("webui:chats_sidebar"))
    assert response.status_code == 200
    assert b"webui-brand" in response.content
    assert b"New chat" in response.content
