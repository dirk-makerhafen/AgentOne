import pytest


@pytest.mark.django_db
class TestHealth:
    def test_health_endpoint(self, api_client, monkeypatch):
        monkeypatch.setattr(
            "runtime.version.get_version_info",
            lambda: {
                "version": "0.1.0+abc1234",
                "short_commit": "abc1234",
                "branch": "main",
            },
        )
        resp = api_client.get('/api/v1/health/')
        assert resp.status_code == 200
        assert 'status' in resp.data
        assert 'database' in resp.data
        assert 'redis' in resp.data
        assert resp.data['version'] == '0.1.0+abc1234'
        assert resp.data['commit'] == 'abc1234'
