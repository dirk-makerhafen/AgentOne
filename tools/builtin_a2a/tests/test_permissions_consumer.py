import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from tools.builtin_a2a.models.a2a_permission import AgentToAgentPermission

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def source_agent_instance(test_user):
    agent = Agent.objects.create(name='Source Agent')
    agent.owners.add(test_user)
    return AgentInstance.objects.create(agent=agent)

@pytest.fixture
def target_agent_instance(test_user):
    agent = Agent.objects.create(name='Target Agent')
    agent.owners.add(test_user)
    return AgentInstance.objects.create(agent=agent)

@pytest.mark.asyncio
async def test_handle_permission_set_success(test_user, source_agent_instance, target_agent_instance):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'a2a_permission_set',
            'payload': {
                'instance_pk': source_agent_instance.pk,
                'target_instance_pk': target_agent_instance.pk,
                'can_send': True
            }
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'InstancePermissionList'
        assert await AgentToAgentPermission.objects.filter(
            source_instance=source_agent_instance,
            target_instance=target_agent_instance,
            can_send=True
        ).aexists()
    finally:
        await communicator.disconnect()
