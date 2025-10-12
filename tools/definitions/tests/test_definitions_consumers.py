import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from unittest.mock import patch

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def test_system():
    return System.objects.create(name='Test System')

@pytest.fixture
def tool_definition():
    return ToolDefinition.objects.create(name='test-tool', display_name='Test Tool')

@pytest.mark.asyncio
@patch('tools.definitions.consumers.tool_installation.install_tool.delay')
async def test_handle_toolinstallation_create_success(mock_install, test_user, tool_definition, test_system):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        systemresponse = await communicator.receive_json_from(timeout=2)
        await communicator.send_json_to({
            'type': 'toolinstallation_create',
            'payload': {
                'tool_definition_pk': tool_definition.pk,
                'system_pk': test_system.pk
            }
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'ToolInstallation'
        
        install = await ToolInstallation.objects.aget(tool_definition=tool_definition, system=test_system)
        mock_install.assert_called_once_with(install.pk)
    finally:
        await communicator.disconnect()
