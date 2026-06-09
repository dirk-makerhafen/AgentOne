import pytest
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel


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
