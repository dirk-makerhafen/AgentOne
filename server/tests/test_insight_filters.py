"""Tests for the GET-driven filters on the insights/settings tables."""
import pytest
from django.test import RequestFactory

from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from webui.features.insights.views import _models_context, _providers_context
from webui.features.settings.views import _provider_rows


def _context(builder, path, **params):
    return builder(RequestFactory().get(path, params))


@pytest.mark.django_db
def test_insights_providers_hides_keyless_by_default():
    with_key = ApiProvider.objects.create(name="With key")
    ApiKey.objects.create(api_provider=with_key, key="sk-one")
    ApiProvider.objects.create(name="No key")

    default = _context(_providers_context, "/app/insights/providers")
    assert [row["name"] for row in default["providers"]] == ["With key"]
    assert default["show_keyless"] is False

    shown = _context(_providers_context, "/app/insights/providers", show_keyless="1")
    assert sorted(row["name"] for row in shown["providers"]) == ["No key", "With key"]
    assert shown["show_keyless"] is True


@pytest.mark.django_db
def test_insights_models_filters_key_and_free():
    keyed = ApiProvider.objects.create(name="Keyed")
    ApiKey.objects.create(api_provider=keyed, key="sk-free")
    keyless = ApiProvider.objects.create(name="Keyless")

    free = AiModelOffering.objects.create(
        api_provider=keyed, name="Free keyed", is_free=True
    )
    AiModelOffering.objects.create(
        api_provider=keyless, name="Free keyless", is_free=True
    )
    AiModelOffering.objects.create(
        api_provider=keyed, name="Paid keyed", is_free=False
    )
    assert free.name == "Free keyed"

    default = _context(_models_context, "/app/insights/models")
    assert [row["name"] for row in default["models"]] == ["Free keyed"]
    assert default["show_no_key"] is False
    assert default["hide_nonfree"] is True

    with_keyless = _context(
        _models_context, "/app/insights/models", show_no_key="1", hide_nonfree="0"
    )
    assert sorted(row["name"] for row in with_keyless["models"]) == [
        "Free keyed",
        "Free keyless",
        "Paid keyed",
    ]


@pytest.mark.django_db
def test_insights_models_excludes_disabled_offerings():
    provider = ApiProvider.objects.create(name="Disabled filter")
    ApiKey.objects.create(api_provider=provider, key="sk-visible")
    AiModelOffering.objects.create(
        api_provider=provider, name="Live model", is_free=True, canonical_id="dev/shared"
    )
    AiModelOffering.objects.create(
        api_provider=provider, name="A dead variant", is_free=True,
        canonical_id="dev/shared", enabled=False,
    )
    AiModelOffering.objects.create(
        api_provider=provider, name="Dead model", is_free=True, enabled=False
    )

    # Disabled rows must stay hidden even when both filters are relaxed.
    rows = _context(
        _models_context, "/app/insights/models", show_no_key="1", hide_nonfree="0"
    )["models"]
    assert [row["name"] for row in rows] == ["Live model"]
    assert all(row["enabled"] for row in rows)


@pytest.mark.django_db
def test_insights_models_page_hides_disabled_badge(client, _open_webui):
    provider = ApiProvider.objects.create(name="Disabled page")
    AiModelOffering.objects.create(api_provider=provider, name="Visible", is_free=True)
    AiModelOffering.objects.create(
        api_provider=provider, name="Hidden", is_free=True, enabled=False
    )

    response = client.get("/app/insights/models", {"show_no_key": "1", "hide_nonfree": "0"})
    assert response.status_code == 200
    assert b"Visible" in response.content
    assert b"Hidden" not in response.content
    assert b'key-missing">disabled' not in response.content


@pytest.mark.django_db
def test_settings_providers_filters_key_and_free_offerings():
    keyed = ApiProvider.objects.create(name="Keyed")
    ApiKey.objects.create(api_provider=keyed, key="sk-one")
    free_keyless = ApiProvider.objects.create(name="Free keyless")
    AiModelOffering.objects.create(
        api_provider=free_keyless, name="Free model", is_free=True
    )
    ApiProvider.objects.create(name="Plain keyless")

    default = _provider_rows()
    assert len(default) == 3

    no_keyless = _provider_rows(hide_keyless=True)
    assert [row["name"] for row in no_keyless] == ["Keyed"]

    no_free = _provider_rows(hide_no_free=True)
    assert [row["name"] for row in no_free] == ["Free keyless"]

    both = _provider_rows(hide_keyless=True, hide_no_free=True)
    assert both == []

    # A free offering that is disabled does not count as free: the filter and
    # the "N free" column must agree.
    disabled_free = ApiProvider.objects.create(name="Disabled free")
    AiModelOffering.objects.create(
        api_provider=disabled_free, name="Dead free", is_free=True, enabled=False
    )
    assert "Disabled free" not in [row["name"] for row in _provider_rows(hide_no_free=True)]
    row = next(r for r in _provider_rows() if r["name"] == "Disabled free")
    assert (row["model_count"], row["free_model_count"]) == (0, 0)


@pytest.fixture
def _open_webui(settings):
    """The insights/settings pages need auth disabled to render in tests."""
    settings.WEBUI_LOGIN_REQUIRED = False


@pytest.mark.django_db
def test_filter_checkboxes_render_with_defaults(client, _open_webui):
    providers = client.get("/app/insights/providers")
    assert providers.status_code == 200
    assert b'name="show_keyless" value="1"' in providers.content
    assert b'Show providers without keys' in providers.content
    # Default: unchecked — only providers with keys are listed.
    assert b'name="show_keyless" value="1" checked' not in providers.content

    models = client.get("/app/insights/models")
    assert models.status_code == 200
    assert b'name="show_no_key" value="1"' in models.content
    assert b'name="hide_nonfree" value="1" checked' in models.content

    checked_models = client.get("/app/insights/models", {"show_no_key": "1", "hide_nonfree": "0"})
    assert b'name="show_no_key" value="1" checked' in checked_models.content
    assert b'name="hide_nonfree" value="1" checked' not in checked_models.content

    settings = client.get("/app/settings/providers")
    assert settings.status_code == 200
    assert b'Hide providers without apikey' in settings.content
    assert b'Hide providers without any free offerings' in settings.content

    checked_settings = client.get(
        "/app/settings/providers", {"hide_keyless": "1", "hide_no_free": "1"}
    )
    assert b'name="hide_keyless" value="1" checked' in checked_settings.content
    assert b'name="hide_no_free" value="1" checked' in checked_settings.content


@pytest.mark.django_db
def test_hide_no_free_never_shows_zero_free(client, _open_webui):
    real = ApiProvider.objects.create(name="Real free")
    AiModelOffering.objects.create(api_provider=real, name="Live free", is_free=True)
    stale = ApiProvider.objects.create(name="Stale free")
    AiModelOffering.objects.create(
        api_provider=stale, name="Dead free", is_free=True, enabled=False
    )
    plain = ApiProvider.objects.create(name="Plain")
    AiModelOffering.objects.create(api_provider=plain, name="Paid", is_free=False)

    response = client.get("/app/settings/providers", {"hide_no_free": "1"})
    assert response.status_code == 200
    assert b"Real free" in response.content
    assert b"Stale free" not in response.content
    assert b"Plain" not in response.content
    assert b"(0 free)" not in response.content


@pytest.mark.django_db
def test_provider_detail_hides_disabled_models(client, _open_webui):
    provider = ApiProvider.objects.create(name="Detail filter")
    AiModelOffering.objects.create(api_provider=provider, name="Live model", is_free=True)
    AiModelOffering.objects.create(
        api_provider=provider, name="Dead model", is_free=True, enabled=False
    )

    response = client.get(f"/app/insights/providers/{provider.pk}/detail")
    assert response.status_code == 200
    assert b"Live model" in response.content
    assert b"Dead model" not in response.content
    assert b"key-missing\">disabled" not in response.content


@pytest.mark.django_db
def test_provider_detail_hide_nonfree_defaults_to_budget(client, _open_webui):
    provider = ApiProvider.objects.create(name="Budget detail")
    AiModelOffering.objects.create(api_provider=provider, name="Free model", is_free=True)
    AiModelOffering.objects.create(api_provider=provider, name="Paid model", is_free=False)
    url = f"/app/insights/providers/{provider.pk}/detail"

    def shown():
        response = client.get(url)
        assert response.status_code == 200
        assert b"Hide non-free models" in response.content
        return (
            b"Free model" in response.content,
            b"Paid model" in response.content,
            b'value="1" checked' in response.content,
        )

    # No key at all: free only.
    assert shown() == (True, False, True)

    # -1 (unconfigured) and 0 budgets stay free-only.
    key = ApiKey.objects.create(api_provider=provider, key="sk-test", budget=-1)
    assert shown() == (True, False, True)
    key.budget = 0
    key.save(update_fields=["budget"])
    assert shown() == (True, False, True)

    # A positive budget is the only default that shows paid models.
    key.budget = 5
    key.save(update_fields=["budget"])
    assert shown() == (True, True, False)

    # An explicit GET choice overrides the default in both directions.
    assert b"Paid model" not in client.get(url, {"hide_nonfree": "1"}).content
    limited = ApiKey.objects.create(api_provider=provider, key="sk-free", budget=0)
    limited.enabled = False
    limited.save(update_fields=["enabled"])
    assert b"Paid model" in client.get(url, {"hide_nonfree": "0"}).content


@pytest.mark.django_db
def test_provider_detail_post_forms_preserve_model_filter(client, _open_webui):
    provider = ApiProvider.objects.create(name="Filter persistence")
    AiModelOffering.objects.create(api_provider=provider, name="Free model", is_free=True)
    AiModelOffering.objects.create(api_provider=provider, name="Paid model", is_free=False)
    url = f"/app/settings/providers/{provider.pk}/models"

    response = client.post(
        url,
        {"action": "add", "provider_model_id": "extra", "hide_nonfree": "0"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert b"Paid model" in response.content

    response = client.post(
        url,
        {"action": "add", "provider_model_id": "extra-2", "hide_nonfree": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert b"Paid model" not in response.content
    assert b"Free model" in response.content


@pytest.mark.django_db
def test_settings_providers_shows_free_model_count(client, _open_webui):
    provider = ApiProvider.objects.create(name="Counted models")
    AiModelOffering.objects.create(api_provider=provider, name="Free one", is_free=True)
    AiModelOffering.objects.create(api_provider=provider, name="Free two", is_free=True)
    AiModelOffering.objects.create(api_provider=provider, name="Paid", is_free=False)
    AiModelOffering.objects.create(
        api_provider=provider, name="Disabled free", is_free=True, enabled=False
    )

    row = next(r for r in _provider_rows() if r["name"] == "Counted models")
    assert row["model_count"] == 3
    assert row["free_model_count"] == 2

    response = client.get("/app/settings/providers")
    assert response.status_code == 200
    assert b"3 (2 free)" in response.content
    assert b'data-sort-key="models" data-sort-value="3"' in response.content


@pytest.mark.django_db
def test_apikey_budget_is_a_free_usage_indicator():
    key = ApiKey.objects.create(api_provider=ApiProvider.objects.create(name="Budget"), key="sk-b")
    assert key.budget == -1
    assert key.is_free_only is False

    key.budget = 0
    key.save(update_fields=["budget"])
    key.refresh_from_db()
    assert key.is_free_only is True

    key.budget = 50
    key.save(update_fields=["budget"])
    key.refresh_from_db()
    assert key.is_free_only is False
