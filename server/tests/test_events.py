"""Tests for ``webui.core.events`` — the per-tab event socket and watch endpoint."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from channels.testing import WebsocketCommunicator
from django.urls import reverse

from webui.core import events


@pytest.fixture
def auth_client(client, db):
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user("sse-user", password="x")
    client.force_login(user)
    return client


def _watch(client, payload):
    return client.post(
        reverse("webui:sse_watch"),
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_frame_format():
    assert events._frame("Message:1", "{}") == "event: Message:1\ndata: {}\n\n"


def test_ws_message_format():
    assert json.loads(events._ws_message("Message:1", '{"pk": 1}')) == {
        "event": "Message:1",
        "data": '{"pk": 1}',
    }


def test_ws_url_is_reversible():
    assert reverse("webui:events_ws") == "/app/ws/events/"


def test_event_name_extracts_the_key():
    parsed = events._event_name('{"key": "Message:1", "pk": 1}')
    assert parsed is not None
    assert parsed[0] == "Message:1"
    assert json.loads(parsed[1])["pk"] == 1


@pytest.mark.parametrize("payload", ["", "not json", "{}", '{"key": 5}'])
def test_event_name_ignores_malformed_payloads(payload):
    assert events._event_name(payload) is None


def test_stream_requires_a_valid_client_id(client):
    assert client.get(reverse("webui:sse")).status_code == 400
    assert client.get(reverse("webui:sse"), {"client": "short"}).status_code == 400
    assert client.get(reverse("webui:sse"), {"client": "x" * 65}).status_code == 400


def test_stream_accepts_a_uuid_client_id(auth_client):
    response = auth_client.get(
        reverse("webui:sse"), {"client": "0b9c1d2e-aaaa-bbbb-cccc-1234567890ab"}
    )
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache, no-transform"
    assert response["X-Accel-Buffering"] == "no"


@pytest.mark.django_db
def test_watch_registers_the_keys(auth_client):
    with patch.object(events, "register_client", return_value=["A:1", "B:2"]) as register:
        response = _watch(auth_client, {"client": "client-1234", "keys": ["A:1", "B:2"]})
    assert response.status_code == 200
    assert response.json() == {"keys": ["A:1", "B:2"]}
    register.assert_called_once_with("client-1234", ["A:1", "B:2"])


@pytest.mark.django_db
def test_watch_echoes_only_the_keys_that_were_stored(auth_client):
    import fakeredis
    from server.models import observables

    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch.object(observables, "get_redis", return_value=redis):
        response = _watch(
            auth_client,
            {"client": "client-1234", "keys": ["A:1", "has space", "A:1"]},
        )
    assert response.status_code == 200
    assert response.json() == {"keys": ["A:1"]}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"client": "bad id!"},
        {"client": "client-1234", "keys": "A:1"},
        {"client": "client-1234", "keys": ["x"] * (events.MAX_WATCH_KEYS + 1)},
    ],
)
@pytest.mark.django_db
def test_watch_rejects_malformed_payloads(auth_client, payload):
    assert _watch(auth_client, payload).status_code == 400


@pytest.mark.django_db
def test_watch_accepts_a_page_with_many_observable_keys(auth_client):
    # 80 sidebar rows (4 keys each) plus a 120-message thread (2 keys each)
    # already exceeds the old 500-key cap and silently lost the whole sync.
    keys = [f"A:{i}" for i in range(600)]
    with patch.object(events, "register_client", return_value=keys) as register:
        response = _watch(auth_client, {"client": "client-1234", "keys": keys})
    assert response.status_code == 200
    register.assert_called_once_with("client-1234", keys)


@pytest.mark.django_db
def test_watch_rejects_invalid_json(auth_client):
    response = auth_client.post(
        reverse("webui:sse_watch"), data="{", content_type="application/json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_watch_drops_non_string_keys(auth_client):
    with patch.object(events, "register_client", return_value=["A:1"]) as register:
        response = _watch(auth_client, {"client": "client-1234", "keys": ["A:1", 5, None]})
    assert response.status_code == 200
    register.assert_called_once_with("client-1234", ["A:1"])


@pytest.mark.django_db
def test_watch_requires_authentication(client):
    response = _watch(client, {"client": "client-1234", "keys": []})
    assert response.status_code == 403


class _FakePubSub:
    """A pubsub that yields a few frames, then waits until cancelled."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.subscribed = []
        self.unsubscribed = []
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel):
        self.unsubscribed.append(channel)

    async def aclose(self):
        self.closed = True

    async def get_message(self, ignore_subscribe_messages=True, timeout=None):
        if self.payloads:
            return {"data": self.payloads.pop(0)}
        await asyncio.Event().wait()
        return None


def _auth_app(user):
    """Skip AuthMiddlewareStack in unit tests; inject the scope user directly."""
    consumer = events.EventsConsumer.as_asgi()

    async def app(scope, receive, send):
        scope["user"] = user
        await consumer(scope, receive, send)

    return app


async def _assert_ws_close(app, path, expected_code):
    comm = WebsocketCommunicator(app, path)
    connected, _ = await comm.connect()
    assert connected is True
    message = await comm.receive_output()
    assert message["type"] == "websocket.close"
    assert message["code"] == expected_code
    await comm.disconnect()


def test_ws_rejects_invalid_client_id():
    asyncio.run(_assert_ws_close(
        events.EventsConsumer.as_asgi(),
        "/app/ws/events/?client=short",
        4400,
    ))


def test_ws_rejects_anonymous_user():
    asyncio.run(_assert_ws_close(
        _auth_app(SimpleNamespace(is_authenticated=False)),
        "/app/ws/events/?client=client-1234",
        4401,
    ))


@pytest.mark.django_db(transaction=True)
def test_ws_accepts_a_real_session_cookie():
    from config.asgi import application
    from django.contrib.auth import get_user_model
    from django.test import Client

    user = get_user_model().objects.create_user("ws-user", password="x")
    web = Client()
    web.force_login(user)
    session_cookie = web.cookies["sessionid"].value
    pubsub = _FakePubSub([])
    redis = SimpleNamespace(pubsub=lambda: pubsub, aclose=AsyncMock())

    async def scenario():
        comm = WebsocketCommunicator(
            application,
            "/app/ws/events/?client=client-1234",
            headers=[(b"cookie", f"sessionid={session_cookie}".encode())],
        )
        connected, code = await comm.connect()
        if connected:
            await comm.disconnect()
        return connected, code

    with patch.object(events.aioredis, "from_url", return_value=redis), \
            patch.object(events, "reset_client"):
        connected, code = asyncio.run(scenario())
    assert connected, f"websocket rejected with code {code}"


@pytest.mark.django_db
def test_ws_sends_reset_then_fanned_out_events():
    key_json = json.dumps({"key": "Message:1", "pk": 1})
    pubsub = _FakePubSub([key_json])
    redis = SimpleNamespace(pubsub=lambda: pubsub, aclose=AsyncMock())

    async def scenario():
        comm = WebsocketCommunicator(
            _auth_app(SimpleNamespace(is_authenticated=True)),
            "/app/ws/events/?client=client-1234",
        )
        connected, _ = await comm.connect()
        assert connected is True
        messages = [await comm.receive_json_from(), await comm.receive_json_from()]
        await comm.disconnect()
        return messages

    with patch.object(events.aioredis, "from_url", return_value=redis), \
            patch.object(events, "mark_seen", return_value=True), \
            patch.object(events, "reset_client") as reset:
        messages = asyncio.run(scenario())

    assert messages == [
        {"event": "reset", "data": "{}"},
        {"event": "Message:1", "data": key_json},
    ]
    assert pubsub.subscribed == ["agentone:sse:client-1234"]
    assert pubsub.unsubscribed == ["agentone:sse:client-1234"]
    assert pubsub.closed is True
    reset.assert_called_once_with("client-1234")
