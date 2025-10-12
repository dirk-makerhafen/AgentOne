import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from systems.models.system import System

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def test_system():
    return System.objects.create(name='Test System')

@pytest.mark.asyncio
async def test_handle_system_update_success(test_user, test_system):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        await communicator.send_json_to({
            'type': 'system_update',
            'payload': {
                'system_pk': test_system.pk,
                'data': {'name': 'Updated System'}
            }
        })
        response = await communicator.receive_json_from(timeout=2)
        print(response)
        response = await communicator.receive_json_from(timeout=2)
        print(response)
        assert response['object'] == 'System'
        assert response['name'] == 'Updated System'
        
        # Refresh the object from the database before the final assertion
        await test_system.arefresh_from_db()
        assert test_system.name == 'Updated System'
    finally:
        await communicator.disconnect()
