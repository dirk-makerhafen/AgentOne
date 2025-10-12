import pytest
import uuid
import json
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from tools.builtin_memory.models.memory_item import MemoryItem
from tools.definitions.models.tool_definition import ToolDefinition
from systems.models.system import System
from unittest.mock import patch

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
    
    instance = None
    # Use a 'with' block to patch the broadcast method ONLY during the setup of
    # fixture objects (System, AgentInstance). This prevents setup-related
    # messages from interfering with the actual test assertions.
    with patch('core.models.base_model.BaseModel.send_object_to_clients'):
        system, _ = System.objects.get_or_create(name='Test System for Memory Consumer')
        instance = AgentInstance.objects.create(agent=agent, system=system)
        
    return instance

@pytest.fixture
def memory_item(test_agent_instance):
    return MemoryItem.objects.create(
        agentInstance=test_agent_instance,
        agent=test_agent_instance.agent,
        track='PLANS', layer='ST', index=0, content='Initial'
    )

@pytest.mark.asyncio
async def test_handle_memoryitem_update_success(test_user, memory_item):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'memoryitem_update',
            'payload': {
                'instance_pk': memory_item.agentInstance.pk,
                'track': 'PLANS', 
                'layer': 'ST', 
                'index': 0,
                'content': 'updated'
            }
        })
        
        # The model's save() signal will broadcast changes. For a versioned item,
        # this means two messages: one for the old item (archived) and one for the new.
        # We must listen for the new item with the updated content.
        received_new_version = False
        for _ in range(2): 
            response = await communicator.receive_json_from(timeout=5)
            if response.get('object') == 'MemoryItem' and response.get('content') == 'updated':
                assert response['prev_version_id'] == memory_item.pk
                received_new_version = True
                break
        
        assert received_new_version, "Did not receive the updated MemoryItem broadcast."

    finally:
        await communicator.disconnect()
