import pytest
from server.models.system import System


@pytest.mark.django_db
class TestSystems:
    def test_list_systems(self, auth_client):
        resp = auth_client.get('/api/v1/systems/')
        assert resp.status_code == 200

    def test_system_detail(self, auth_client):
        s = System.objects.create(name='test-system', status='online',
                                   executor_mode='LOCAL', os='OSX')
        resp = auth_client.get(f'/api/v1/systems/{s.id}/')
        assert resp.status_code == 200
