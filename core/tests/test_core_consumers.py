import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application
from asgiref.sync import sync_to_async

pytestmark = pytest.mark.asyncio

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_placeholder_core_consumer():
    """
    Placeholder test for core app consumers (e.g., prompts).
    """
    from asgiref.sync import sync_to_async
    from django.contrib.auth.models import User # Import User model
    user = await sync_to_async(User.objects.create_user)(username='testuser_core', password='password') # Create a user
    communicator = WebsocketCommunicator(application, f"/ws/{user.pk}/") # Use the user's PK in the URL
    connected, subprotocol = await communicator.connect()
    assert connected
    await communicator.disconnect()
