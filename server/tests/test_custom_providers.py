"""Tests for UI-created custom providers and their model offerings."""
from types import SimpleNamespace

import pytest
import requests

from registry.custom_providers import fetch_provider_model_ids, upsert_offering
from runtime.session.aimodel_picker import available_aimodels
from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider


@pytest.fixture
def _open_webui(settings):
    """The settings pages need auth disabled to render in tests."""
    settings.WEBUI_LOGIN_REQUIRED = False


def _response(payload, status_code=200):
    return SimpleNamespace(
        status_code=status_code,
        raise_for_status=lambda: None,
        json=lambda: payload,
    )


@pytest.mark.django_db
def test_add_local_custom_provider_from_settings(client, _open_webui):
    response = client.post(
        "/app/settings/providers/add",
        {
            "name": "Local OMLX",
            "url": "http://127.0.0.1:8000/v1/",
            "is_local": "1",
            "keyless": "1",
        },
    )
    assert response.status_code == 302

    provider = ApiProvider.objects.get(name="Local OMLX")
    assert provider.url == "http://127.0.0.1:8000/v1"
    assert provider.is_custom is True
    assert provider.is_local is True
    assert provider.default_api_key == "local"
    assert provider.usable is True

    page = client.get("/app/settings/providers")
    assert b"Local OMLX" in page.content
    assert b">custom<" in page.content


@pytest.mark.django_db
def test_invalid_provider_url_shows_error(client, _open_webui):
    response = client.post(
        "/app/settings/providers/add",
        {"name": "Bad", "url": "not-a-url", "keyless": "1"},
    )
    assert response.status_code == 302
    assert ApiProvider.objects.filter(name="Bad").exists() is False
    assert b"http(s)" in client.get(response.url).content


@pytest.mark.django_db
def test_manual_model_creates_routable_offering(client, _open_webui):
    provider = ApiProvider.objects.create(
        name="Manual models", url="http://127.0.0.1:1234/v1", is_local=True
    )
    ApiKey.objects.create(api_provider=provider, key="sk-local")

    response = client.post(
        f"/app/settings/providers/{provider.pk}/models",
        {
            "action": "add",
            "provider_model_id": "gemma-4-26B-A4B-it-MLX-4bit",
            "name": "Gemma 4",
            "is_free": "1",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"Model added." in response.content
    assert b"Gemma 4" in response.content

    offering = AiModelOffering.objects.get(provider_model_id="gemma-4-26B-A4B-it-MLX-4bit")
    assert offering.name == "Gemma 4"
    assert offering.model.name == "Gemma 4"
    assert offering.enabled is True
    assert offering.is_cloud is False
    assert offering.is_free is True
    provider.refresh_from_db()
    assert provider.is_custom is True
    assert any(row.pk == offering.pk for row in available_aimodels())

    # Re-adding is idempotent and re-enables a manually disabled row.
    offering.enabled = False
    offering.save(update_fields=["enabled"])
    response = client.post(
        f"/app/settings/providers/{provider.pk}/models",
        {"action": "add", "provider_model_id": "gemma-4-26B-A4B-it-MLX-4bit"},
        HTTP_HX_REQUEST="true",
    )
    assert b"re-enabled" in response.content
    offering.refresh_from_db()
    assert offering.enabled is True
    assert AiModelOffering.objects.filter(api_provider=provider).count() == 1


@pytest.mark.django_db
def test_load_models_button_has_pending_and_result_feedback(client, _open_webui):
    provider = ApiProvider.objects.create(
        name="Feedback", url="http://127.0.0.1:1/v1", is_local=True
    )
    detail = client.get(f"/app/insights/providers/{provider.pk}/detail")
    assert detail.status_code == 200
    assert b'hx-indicator="#model-load-status-' in detail.content
    assert b"Loading models" in detail.content
    assert b'hx-disabled-elt="this"' in detail.content

    # The result is rendered next to the button, not only at the top of the panel.
    response = client.post(
        f"/app/settings/providers/{provider.pk}/models",
        {"action": "add", "provider_model_id": "one"},
        HTTP_HX_REQUEST="true",
    )
    body = response.content.decode()
    assert body.index("Manage models") < body.index("Model added.") < body.index(
        "Load models from API"
    )


@pytest.mark.django_db
def test_load_models_from_api_creates_offerings(client, _open_webui, monkeypatch):
    provider = ApiProvider.objects.create(
        name="Discoverable", url="http://127.0.0.1:1234", is_local=True
    )
    ApiKey.objects.create(api_provider=provider, key="sk-local")
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers))
        if url == "http://127.0.0.1:1234/v1/models":
            return _response({"data": [{"id": "one"}, {"id": "two"}]})
        return _response({}, status_code=404)

    monkeypatch.setattr("registry.custom_providers.requests.get", fake_get)

    response = client.post(
        f"/app/settings/providers/{provider.pk}/models",
        {"action": "load"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"Found 2 model(s); added 2 new offering(s)." in response.content
    assert [call[0] for call in calls] == [
        "http://127.0.0.1:1234/models",
        "http://127.0.0.1:1234/v1/models",
    ]
    assert calls[0][1] == {"Authorization": "Bearer sk-local"}
    assert sorted(
        provider.offerings.values_list("provider_model_id", flat=True)
    ) == ["one", "two"]
    assert all(not offering.is_cloud for offering in provider.offerings.all())

    # A second load reuses the rows rather than duplicating them.
    response = client.post(
        f"/app/settings/providers/{provider.pk}/models",
        {"action": "load"},
        HTTP_HX_REQUEST="true",
    )
    assert b"added 0 new offering(s)" in response.content
    assert provider.offerings.count() == 2


@pytest.mark.django_db
def test_fetch_models_reports_connection_errors(monkeypatch):
    provider = ApiProvider.objects.create(name="Down", url="http://127.0.0.1:1/v1")

    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr("registry.custom_providers.requests.get", fake_get)
    ids, error = fetch_provider_model_ids(provider)
    assert ids == []
    assert "connection refused" in error


@pytest.mark.django_db
def test_manual_model_id_is_required():
    provider = ApiProvider.objects.create(name="Required")
    with pytest.raises(ValueError, match="Model id is required"):
        upsert_offering(provider, "  ")
