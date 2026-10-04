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

    def test_update_workspace_publishes(self, auth_client, admin_user):
        from unittest.mock import patch

        ws = WorkspaceModel.objects.create(name='upd-ws', path='/tmp/upd')
        with patch("runtime.events.publish_model_event") as mock_publish:
            resp = auth_client.patch(
                f'/api/v1/workspaces/{ws.id}/', {'name': 'upd-ws-2'},
                content_type='application/json',
            )
        assert resp.status_code == 200
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][1] == "update"

    def test_delete_workspace_publishes(self, auth_client, admin_user):
        from unittest.mock import patch

        ws = WorkspaceModel.objects.create(name='del-ws', path='/tmp/del')
        with patch("runtime.events.publish_model_event") as mock_publish:
            resp = auth_client.delete(f'/api/v1/workspaces/{ws.id}/')
        assert resp.status_code == 204
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][1] == "delete"

    def test_create_workspace_publishes(self, auth_client, admin_user):
        from unittest.mock import patch

        with patch("runtime.events.publish_model_event") as mock_publish:
            resp = auth_client.post('/api/v1/workspaces/', {
                'name': 'pub-ws',
                'path': '/tmp/pub-ws',
            })
        assert resp.status_code == 201
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][1] == "create"
