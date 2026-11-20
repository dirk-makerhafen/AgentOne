"""Tests for ``webui.core.events`` — the per-tab SSE stream and watch endpoint."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
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
    with patch.object(events, "register_client") as register:
        response = _watch(auth_client, {"client": "client-1234", "keys": ["A:1", "B:2"]})
    assert response.status_code == 200
    assert response.json() == {"keys": ["A:1", "B:2"]}
    register.assert_called_once_with("client-1234", ["A:1", "B:2"])


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
    with patch.object(events, "register_client") as register:
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
    with patch.object(events, "register_client") as register:
        response = _watch(auth_client, {"client": "client-1234", "keys": ["A:1", 5, None]})
    assert response.status_code == 200
    register.assert_called_once_with("client-1234", ["A:1"])


@pytest.mark.django_db
def test_watch_requires_authentication(client):
    response = _watch(client, {"client": "client-1234", "keys": []})
    assert response.status_code == 403
