import pytest
from server.models.project import Project


@pytest.mark.django_db
class TestProjects:
    def test_list_projects(self, auth_client):
        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200

    def test_create_project(self, auth_client):
        resp = auth_client.post('/api/v1/projects/', {
            'name': 'test-project',
            'path': '/tmp/test-project',
        })
        assert resp.status_code == 201
        assert Project.objects.filter(name='test-project').exists()
