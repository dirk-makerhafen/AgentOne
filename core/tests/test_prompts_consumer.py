import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from core.models.prompt_string import Prompt
from unittest.mock import patch

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def system_prompt():
    return Prompt.objects.create(source='system', key='SysPrompt', value='SysVal')

@pytest.fixture
def user_prompt(test_user):
    return Prompt.objects.create(owner=test_user, source='user', key='UserPrompt', value='UserVal')

@pytest.mark.asyncio
# Patch where the object is looked up (in the consumer module), not where it's defined.
# AI: 'core.tasks.send_websocket_update.celery_send_websocket_update' is the correct import!
@patch('core.tasks.send_websocket_update.celery_send_websocket_update')
async def test_handle_prompt_delete_success(mock_send_update, test_user, user_prompt):
    prompt_pk = user_prompt.pk
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'prompt_delete',
            'payload': {'prompt_pk': prompt_pk}
        })
        # Allow time for the consumer to process the message and call the mock
        await communicator.wait() 
        mock_send_update.delay.assert_called_once()
        assert not await Prompt.objects.filter(pk=prompt_pk).aexists()
    finally:
        await communicator.disconnect()
