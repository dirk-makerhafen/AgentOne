import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from django.utils import timezone
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from unittest.mock import patch

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def test_agent_instance(test_user):
    agent = Agent.objects.create(name='Test Agent')
    agent.owners.add(test_user)
    return AgentInstance.objects.create(agent=agent)

@pytest.fixture
def fs_log_entry(test_agent_instance):
    now = timezone.now()
    return FsLogEntry.objects.create(
        agentInstance=test_agent_instance,
        agent=test_agent_instance.agent,
        path='/test/file.txt',
        is_newest_version=True,
        # Add required datetime fields to prevent AttributeError on .isoformat()
        fs_created=now,
        fs_modified=now,
        fs_lastread=now
    )

@pytest.mark.asyncio
async def test_handle_filesystem_list_success(test_user, fs_log_entry):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'filesystem_list',
            'payload': {'instance_pk': fs_log_entry.agentInstance.pk}
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'InitialFilesystemState'
        assert len(response['items']) == 1
    finally:
        await communicator.disconnect()
