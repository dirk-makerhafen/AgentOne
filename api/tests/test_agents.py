import pytest
from server.models.agents.agent import AgentModel


@pytest.mark.django_db
class TestAgents:
    def test_list_agents(self, auth_client):
        resp = auth_client.get('/api/v1/agents/')
        assert resp.status_code == 200

    def test_list_agents_pagination(self, auth_client):
        for i in range(5):
            AgentModel.objects.create(name=f'paginate-agent-{i}')
        resp = auth_client.get('/api/v1/agents/?page_size=2')
        assert resp.status_code == 200
        assert len(resp.data['results']) == 2
        assert resp.data['count'] == 5

    def test_list_agents_search(self, auth_client):
        AgentModel.objects.create(name='searchable-agent')
        AgentModel.objects.create(name='other-agent')
        resp = auth_client.get('/api/v1/agents/?search=searchable')
        assert resp.status_code == 200
        assert len(resp.data['results']) == 1

    def test_create_agent(self, auth_client):
        resp = auth_client.post('/api/v1/agents/', {'name': 'test-agent'})
        assert resp.status_code == 201
        assert AgentModel.objects.filter(name='test-agent').exists()

    def test_create_agent_empty_name(self, auth_client):
        resp = auth_client.post('/api/v1/agents/', {'name': ''})
        assert resp.status_code == 400

    def test_create_agent_no_body(self, auth_client):
        resp = auth_client.post('/api/v1/agents/', {}, format='json')
        assert resp.status_code == 400

    def test_get_agent_detail(self, auth_client):
        agent = AgentModel.objects.create(name='detail-agent')
        resp = auth_client.get(f'/api/v1/agents/{agent.id}/')
        assert resp.status_code == 200
        assert resp.data['name'] == 'detail-agent'

    def test_get_agent_not_found(self, auth_client):
        resp = auth_client.get('/api/v1/agents/99999/')
        assert resp.status_code == 404

    def test_delete_agent(self, auth_client):
        agent = AgentModel.objects.create(name='delete-agent')
        resp = auth_client.delete(f'/api/v1/agents/{agent.id}/')
        assert resp.status_code == 204
        assert not AgentModel.objects.filter(name='delete-agent').exists()

    def test_delete_agent_not_found(self, auth_client):
        resp = auth_client.delete('/api/v1/agents/99999/')
        assert resp.status_code == 404

    def test_agent_capabilities_not_found(self, auth_client):
        resp = auth_client.get('/api/v1/agents/99999/commands/')
        assert resp.status_code == 404

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get('/api/v1/agents/')
        assert resp.status_code in (401, 403)
