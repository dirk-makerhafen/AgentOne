import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from tools.instances.models.tool_instance import ToolInstance
from unittest.mock import patch

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def tool_instance():
    system = System.objects.create(name=f'Test System {uuid.uuid4()}')
    tool_def = ToolDefinition.objects.create(name=f'test-tool-{uuid.uuid4()}', display_name='Test Tool')
    install = ToolInstallation.objects.create(tool_definition=tool_def, system=system)
    return ToolInstance.objects.create(tool_installation=install, status=ToolInstance.ToolInstanceStatusChoices.RUNNING)

@pytest.mark.asyncio
# Patch where the object is looked up (in the consumer module), not where it's defined.
@patch('tools.instances.consumers.tool_instance.stop_tool.delay')
async def test_handle_toolinstance_stop(mock_stop, test_user, tool_instance):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'toolinstance_stop',
            'payload': {'tool_instance_pk': tool_instance.pk}
        })
        await communicator.wait()
        mock_stop.assert_called_once_with(tool_instance.pk)
    finally:
        await communicator.disconnect()
