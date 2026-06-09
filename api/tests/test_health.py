import pytest


@pytest.mark.django_db
class TestHealth:
    def test_health_endpoint(self, api_client):
        resp = api_client.get('/api/v1/health/')
        assert resp.status_code == 200
        assert 'status' in resp.data
        assert 'database' in resp.data
        assert 'redis' in resp.data
