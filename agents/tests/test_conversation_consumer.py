import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from tools.definitions.models.tool_definition import ToolDefinition
from unittest.mock import patch
from systems.models.system import System

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def builtin_tools():
    tools_to_create = [
        'filesystem', 'memory', 'python', 'a2a', 
        'userinteraction', 'shell', 'subscriptions'
    ]
    created_tools = []
    for tool_name in tools_to_create:
        tool, _ = ToolDefinition.objects.get_or_create(name=tool_name, is_builtin=True)
        created_tools.append(tool)
    return created_tools

@pytest.fixture
def test_agent_instance(test_user, builtin_tools):
    agent = Agent.objects.create(name='Test Agent')
    agent.owners.add(test_user)
    agent.available_tools.set(builtin_tools)
    system = System.objects.create(name=f'Test System {uuid.uuid4()}')
    return AgentInstance.objects.create(agent=agent, system=system)

@pytest.mark.asyncio
@patch('agents.models.agent_instance.AgentInstance.start_or_continue')
async def test_handle_conversationmessage_add_success(mock_start, test_user, test_agent_instance):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'conversationmessage_add',
            'payload': {
                'instance_pk': test_agent_instance.pk,
                'message': 'New user message'
            }
        })
        await communicator.wait()
        response = await communicator.receive_json_from(timeout=2)
        print(response)
        assert await test_agent_instance.conversationMessages.filter(
            raw_data__contains='New user message'
        ).aexists()
        mock_start.assert_called_once()
    finally:
        await communicator.disconnect()
