import pytest


@pytest.mark.django_db
class TestMe:
    def test_me_authenticated(self, auth_client):
        resp = auth_client.get('/api/v1/me/')
        assert resp.status_code == 200
        assert resp.data['username'] == 'admin'
        assert 'id' in resp.data
        assert 'is_staff' in resp.data
        assert 'is_superuser' in resp.data
        assert 'date_joined' in resp.data

    def test_me_unauthenticated(self, api_client):
        resp = api_client.get('/api/v1/me/')
        assert resp.status_code in (401, 403)
