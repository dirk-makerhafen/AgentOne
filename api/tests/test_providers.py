import pytest
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from api.utils import sync_provider_models


@pytest.mark.django_db
class TestProviders:
    def test_list_providers(self, auth_client):
        resp = auth_client.get('/api/v1/providers/')
        assert resp.status_code == 200

    def test_provider_detail(self, auth_client):
        p = ApiProvider.objects.create(name='test-provider')
        resp = auth_client.get(f'/api/v1/providers/{p.id}/')
        assert resp.status_code == 200
        assert resp.data['name'] == 'test-provider'

    def test_list_models(self, auth_client):
        resp = auth_client.get('/api/v1/models/')
        assert resp.status_code == 200

    def test_model_detail(self, auth_client):
        p = ApiProvider.objects.create(name='model-provider')
        m = AiModel.objects.create(name='test-model', api_provider=p)
        resp = auth_client.get(f'/api/v1/models/{m.id}/')
        assert resp.status_code == 200


class FakeModelListResponse:
    def __init__(self, models):
        self._models = models

    def raise_for_status(self):
        pass

    def json(self):
        return {"object": "list", "data": self._models}


def _stub_model_list(monkeypatch, models):
    monkeypatch.setattr(
        "api.utils.requests.get",
        lambda *args, **kwargs: FakeModelListResponse(models),
    )


@pytest.mark.django_db
@pytest.mark.skip(
    reason="sync_provider_models is temporarily disabled "
    "(early `return {}` in api/utils.py); model lists are curated via "
    "models.yaml / providers.yaml instead."
)
class TestSyncProviderModels:
    def test_sync_applies_provider_free_tier_rate_limits(self, monkeypatch):
        provider = ApiProvider.objects.create(
            name="free-tier-provider",
            url="https://example.com/api/v1",
        )
        provider.data = {
            "RPM": 15,
            "RPD": 1500,
            "api_key_url": "https://aistudio.google.com/app/apikey",
        }
        provider.save()
        _stub_model_list(monkeypatch, [{"id": "rate-limit-test-model", "object": "model"}])

        result = sync_provider_models(provider.pk)

        assert result["error"] == ""
        model = AiModel.objects.get(api_provider=provider, name="rate-limit-test-model")
        assert model.limit_request_per_minute == 15
        assert model.limit_request_per_day == 1500

    def test_sync_ignores_provider_limits_without_rate_keys(self, monkeypatch):
        provider = ApiProvider.objects.create(
            name="no-limits", url="http://localhost:11434/v1", is_local=True,
        )
        _stub_model_list(monkeypatch, [{"id": "local:latest", "object": "model"}])

        result = sync_provider_models(provider.pk)

        assert result["created"] == 1
        model = AiModel.objects.get(api_provider=provider, name="local:latest")
        assert model.limit_request_per_minute == 0
        assert model.limit_request_per_day == 0

    def test_sync_splits_cloud_models_off_local_provider(self, monkeypatch):
        local = ApiProvider.objects.create(
            name='local-ollama', url='http://localhost:11434/v1', is_local=True,
        )
        _stub_model_list(monkeypatch, [
            {"id": "probe-local:latest", "object": "model"},
            {"id": "gpt-oss:120b-cloud", "object": "model"},
            {"id": "gemini-3-flash-preview:cloud", "object": "model"},
        ])

        result = sync_provider_models(local.pk)

        assert result["error"] == ""
        assert result["created"] == 3
        cloud = ApiProvider.objects.get(name="Ollama Cloud")

        probe = AiModel.objects.get(api_provider=local, name="probe-local:latest")
        assert probe.is_cloud is False

        gpt = AiModel.objects.get(api_provider=cloud, name="gpt-oss:120b")
        assert gpt.is_cloud is True

        gem = AiModel.objects.get(api_provider=cloud, name="gemini-3-flash-preview")
        assert gem.is_cloud is True

        assert not local.aimodels.filter(name__endswith="-cloud").exists()
        assert not local.aimodels.filter(name__endswith=":cloud").exists()

    def test_sync_reenables_model_still_served(self, monkeypatch):
        local = ApiProvider.objects.create(
            name='local-ollama', url='http://localhost:11434/v1', is_local=True,
        )
        model = AiModel.objects.create(
            api_provider=local, name="probe-local:latest", is_cloud=False, enabled=False,
        )
        _stub_model_list(monkeypatch, [{"id": "probe-local:latest", "object": "model"}])

        result = sync_provider_models(local.pk)

        assert result["updated"] == 1
        model.refresh_from_db()
        assert model.enabled is True

    def test_sync_disables_models_no_longer_served(self, monkeypatch):
        local = ApiProvider.objects.create(
            name='local-ollama', url='http://localhost:11434/v1', is_local=True,
        )
        gone = AiModel.objects.create(
            api_provider=local, name="probe-gone:latest", is_cloud=False,
        )
        _stub_model_list(monkeypatch, [{"id": "probe-other:latest", "object": "model"}])

        result = sync_provider_models(local.pk)

        assert result["created"] == 1
        assert result["stale"] == 1
        gone.refresh_from_db()
        assert gone.enabled is False

    def test_sync_keeps_cloud_models_on_cloud_provider(self, monkeypatch):
        cloud = ApiProvider.objects.create(
            name='Ollama Cloud', url='https://ollama.com/v1', is_local=False,
        )
        model = AiModel.objects.create(
            api_provider=cloud, name="gpt-oss:120b", is_cloud=True, enabled=False,
        )
        _stub_model_list(monkeypatch, [{"id": "gpt-oss:120b", "object": "model"}])

        result = sync_provider_models(cloud.pk)

        assert result["error"] == ""
        assert result["updated"] == 1
        model.refresh_from_db()
        assert model.enabled is True
        assert model.is_cloud is True
