import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def test_agent(test_user):
    agent = Agent.objects.create(name='Test Agent')
    agent.owners.add(test_user)
    return agent

@pytest.mark.asyncio
async def test_handle_agentinstance_create_success(test_user, test_agent):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'agentinstance_create',
            'payload': {'agent_pk': test_agent.pk}
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'AgentInstance'
        assert await AgentInstance.objects.filter(agent=test_agent).aexists()
    finally:
        await communicator.disconnect()
