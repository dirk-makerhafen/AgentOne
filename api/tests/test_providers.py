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
class TestSyncProviderModels:
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
        assert probe.self_hosted is True
        assert probe.is_cloud is False

        gpt = AiModel.objects.get(api_provider=cloud, name="gpt-oss:120b")
        assert gpt.self_hosted is False
        assert gpt.is_cloud is True

        gem = AiModel.objects.get(api_provider=cloud, name="gemini-3-flash-preview")
        assert gem.self_hosted is False
        assert gem.is_cloud is True

        assert not local.aimodels.filter(name__endswith="-cloud").exists()
        assert not local.aimodels.filter(name__endswith=":cloud").exists()

    def test_sync_reenables_model_still_served(self, monkeypatch):
        local = ApiProvider.objects.create(
            name='local-ollama', url='http://localhost:11434/v1', is_local=True,
        )
        model = AiModel.objects.create(
            api_provider=local, name="probe-local:latest", self_hosted=True, enabled=False,
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
            api_provider=local, name="probe-gone:latest", self_hosted=True,
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
