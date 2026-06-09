import pytest
from server.models.workspace import WorkspaceModel


@pytest.mark.django_db
class TestWorkspaces:
    def test_list_workspaces(self, auth_client):
        resp = auth_client.get('/api/v1/workspaces/')
        assert resp.status_code == 200

    def test_create_workspace(self, auth_client, admin_user):
        resp = auth_client.post('/api/v1/workspaces/', {
            'name': 'test-ws',
            'path': '/tmp/test-ws',
        })
        assert resp.status_code == 201
        assert WorkspaceModel.objects.filter(name='test-ws').exists()

    def test_get_workspace_detail(self, auth_client):
        ws = WorkspaceModel.objects.create(name='detail-ws', path='/tmp/detail')
        resp = auth_client.get(f'/api/v1/workspaces/{ws.id}/')
        assert resp.status_code == 200
        assert 'session_count' in resp.data
