import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from agents.models.agent import Agent

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
async def test_handle_agent_update_success(test_user, test_agent):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'agent_update',
            'payload': {
                'agent_pk': test_agent.pk,
                'name': 'Updated Agent Name'
            }
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'Agent'
        assert response['name'] == 'Updated Agent Name'
        await test_agent.arefresh_from_db()
        assert test_agent.name == 'Updated Agent Name'
    finally:
        await communicator.disconnect()

@pytest.mark.asyncio
async def test_handle_agent_delete_success(test_user, test_agent):
    agent_pk = test_agent.pk
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'agent_delete',
            'payload': {'agent_pk': agent_pk}
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'AgentDeleted'
        assert response['agent_pk'] == agent_pk
        assert not await Agent.objects.filter(pk=agent_pk).aexists()
    finally:
        await communicator.disconnect()
