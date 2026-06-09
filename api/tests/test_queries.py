import pytest
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.queries.query import Query


@pytest.mark.django_db
class TestQueries:
    def test_list_queries(self, auth_client):
        resp = auth_client.get('/api/v1/queries/')
        assert resp.status_code == 200

    def test_get_query_detail(self, auth_client):
        agent = AgentModel.objects.create(name='query-agent')
        session = SessionModel.objects.create(name='query-session')
        sv = SessionVersionModel.objects.create(session=session, agent=agent)
        session.latest_session_version = sv
        session.save()
        query = Query.objects.create(session_version=sv)
        resp = auth_client.get(f'/api/v1/queries/{query.id}/')
        assert resp.status_code == 200
