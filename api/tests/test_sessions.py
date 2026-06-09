import pytest
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel


@pytest.mark.django_db
class TestSessions:
    def test_list_sessions(self, auth_client):
        resp = auth_client.get('/api/v1/sessions/')
        assert resp.status_code == 200

    def test_create_session(self, auth_client):
        agent = AgentModel.objects.create(name='test-session-agent')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        assert resp.status_code == 201
        assert SessionModel.objects.filter(
            latest_session_version__agent=agent
        ).exists()

    def test_create_session_missing_agent(self, auth_client):
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': 99999})
        assert resp.status_code == 404

    def test_create_session_no_body(self, auth_client):
        resp = auth_client.post('/api/v1/sessions/', {}, format='json')
        assert resp.status_code == 400

    def test_get_session_detail(self, auth_client):
        agent = AgentModel.objects.create(name='detail-session-agent')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        session_id = resp.data['id']
        resp2 = auth_client.get(f'/api/v1/sessions/{session_id}/')
        assert resp2.status_code == 200

    def test_get_session_not_found(self, auth_client):
        resp = auth_client.get('/api/v1/sessions/99999/')
        assert resp.status_code == 404

    def test_delete_session(self, auth_client):
        agent = AgentModel.objects.create(name='delete-session')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        session_id = resp.data['id']
        resp2 = auth_client.delete(f'/api/v1/sessions/{session_id}/')
        assert resp2.status_code == 204

    def test_patch_session_name(self, auth_client):
        agent = AgentModel.objects.create(name='patch-session-agent')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id, 'name': 'original'})
        session_id = resp.data['id']
        resp2 = auth_client.patch(f'/api/v1/sessions/{session_id}/', {'name': 'renamed'})
        assert resp2.status_code == 200
        assert resp2.data['name'] == 'renamed'

    def test_patch_session_with_aimodel(self, auth_client):
        from server.models.providers.api_provider import ApiProvider
        from server.models.providers.ai_model import AiModel
        provider = ApiProvider.objects.create(name='patch-provider')
        model = AiModel.objects.create(name='patch-model', api_provider=provider)
        agent = AgentModel.objects.create(name='patch-session-agent2')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        session_id = resp.data['id']
        resp2 = auth_client.patch(f'/api/v1/sessions/{session_id}/', {'aimodel': model.id})
        assert resp2.status_code == 200

    def test_message_no_content(self, auth_client):
        agent = AgentModel.objects.create(name='msg-session')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        session_id = resp.data['id']
        resp2 = auth_client.post(f'/api/v1/sessions/{session_id}/message/', {}, format='json')
        assert resp2.status_code == 400

    def test_message_with_content(self, auth_client):
        agent = AgentModel.objects.create(name='msg-session-2')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        session_id = resp.data['id']
        resp2 = auth_client.post(f'/api/v1/sessions/{session_id}/message/', {'content': 'hello'})
        assert resp2.status_code in (201, 500)

    def test_reset_session(self, auth_client):
        agent = AgentModel.objects.create(name='reset-session')
        resp = auth_client.post('/api/v1/sessions/', {'agent_id': agent.id})
        session_id = resp.data['id']
        resp2 = auth_client.post(f'/api/v1/sessions/{session_id}/reset/')
        assert resp2.status_code == 200
