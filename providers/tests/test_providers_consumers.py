import pytest
import uuid
from channels.testing import WebsocketCommunicator
from config.asgi import application
from django.contrib.auth.models import User
from providers.models.api_provider import ApiProvider
from providers.models.ai_model import AiModel
from providers.models.api_key import ApiKey

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def test_user():
    return User.objects.create_user(username=f'testuser_{uuid.uuid4()}', password='password')

@pytest.fixture
def api_provider():
    # Use UUID to ensure the name is unique for each test run
    return ApiProvider.objects.create(name=f'Test Provider {uuid.uuid4()}')

@pytest.mark.asyncio
async def test_handle_provider_create_success(test_user):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        provider_name = f"New Provider {uuid.uuid4()}"
        await communicator.send_json_to({
            'type': 'provider_create',
            'payload': {'name': provider_name, "url": "some url"}
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'ApiProvider'
        assert await ApiProvider.objects.filter(name=provider_name).aexists()
    finally:
        await communicator.disconnect()

@pytest.mark.asyncio
async def test_handle_aimodel_create_success(test_user, api_provider):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    assert connected
    try:
        model_name = f"New Model {uuid.uuid4()}"
        api_provider_response = await communicator.receive_json_from(timeout=2) # the mock creates a save event that send the Provider to us
        await communicator.send_json_to({
            'type': 'aimodel_create',
            'payload': {
                'provider_pk': api_provider.pk,
                'model_name': model_name
            }
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'AiModel'
        assert await AiModel.objects.filter(name=model_name, apiProvider=api_provider).aexists()
    finally:
        await communicator.disconnect()

@pytest.mark.asyncio
async def test_handle_apikey_create_success(test_user, api_provider):
    communicator = WebsocketCommunicator(application, f"/ws/{test_user.pk}/")
    connected, _ = await communicator.connect()
    api_provider_response = await communicator.receive_json_from(timeout=2) # the mock creates a save event that send the Provider to us
    assert connected
    try:
        key = f"new_key_{uuid.uuid4()}"
        await communicator.send_json_to({
            'type': 'apikey_create',
            'payload': {
                'provider_pk': api_provider.pk,
                'key': key
            }
        })
        response = await communicator.receive_json_from(timeout=2)
        assert response['object'] == 'ApiKey'
        assert await ApiKey.objects.filter(key=key, apiProvider=api_provider).aexists()
    finally:
        await communicator.disconnect()
