import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestAuth:
    def test_unauthenticated_health(self, api_client):
        resp = api_client.get('/api/v1/health/')
        assert resp.status_code == 200

    def test_unauthenticated_agents(self, api_client):
        resp = api_client.get('/api/v1/agents/')
        assert resp.status_code in (401, 403)

    def test_jwt_token_obtain(self, api_client, admin_user):
        resp = api_client.post('/api/v1/auth/token/', {
            'username': 'admin',
            'password': 'adminpass',
        })
        assert resp.status_code == 200
        assert 'access' in resp.data
        assert 'refresh' in resp.data

    def test_jwt_token_invalid(self, api_client):
        resp = api_client.post('/api/v1/auth/token/', {
            'username': 'bad',
            'password': 'creds',
        })
        assert resp.status_code == 401

    def test_jwt_authenticated_access(self, api_client, admin_user):
        resp = api_client.post('/api/v1/auth/token/', {
            'username': 'admin',
            'password': 'adminpass',
        })
        token = resp.data['access']
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp2 = api_client.get('/api/v1/agents/')
        assert resp2.status_code == 200
