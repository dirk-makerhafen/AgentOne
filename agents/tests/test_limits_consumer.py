import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from agents.models.history_limit import HistoryLimit
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

@pytest.fixture
def history_limit_rule(test_agent_instance):
    return HistoryLimit.objects.create(
        agentInstance=test_agent_instance, group_name='test_group', rule_name='test_rule'
    )

@pytest.mark.asyncio
@patch('agents.models.agent_instance.AgentInstance.send_object_to_clients')
async def test_handle_historylimit_reset_success(mock_send, test_user, history_limit_rule):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'historylimit_reset',
            'payload': {
                'instance_pk': history_limit_rule.agentInstance.pk,
                'rule_name': 'test_group:test_rule'
            }
        })
        await communicator.wait()
        assert not await HistoryLimit.objects.filter(pk=history_limit_rule.pk).aexists()
        mock_send.assert_called_once()
    finally:
        await communicator.disconnect()
