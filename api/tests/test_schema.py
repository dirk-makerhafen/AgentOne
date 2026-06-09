import pytest


@pytest.mark.django_db
class TestSchema:
    def test_schema_json(self, auth_client):
        resp = auth_client.get('/api/v1/schema/')
        assert resp.status_code == 200
        assert 'openapi' in resp.data or resp.data.get('info', {}).get('title') == 'AgentOne API'

    def test_swagger_ui(self, auth_client):
        resp = auth_client.get('/api/v1/docs/')
        assert resp.status_code == 200
        assert 'text/html' in resp['Content-Type']

    def test_redoc(self, auth_client):
        resp = auth_client.get('/api/v1/redoc/')
        assert resp.status_code == 200
        assert 'text/html' in resp['Content-Type']
