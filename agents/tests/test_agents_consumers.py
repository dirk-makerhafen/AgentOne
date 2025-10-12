import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application
from asgiref.sync import sync_to_async

# Mark all tests in this module as asynchronous, required for Channels testing
pytestmark = pytest.mark.asyncio

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_placeholder_agent_consumer():
    """
    Placeholder test for agents app consumers. Connects to a valid WebSocket route.
    """
    from django.contrib.auth.models import User # Import User model
    user = await sync_to_async(User.objects.create_user)(username='testuser', password='password') # Create a user
    communicator = WebsocketCommunicator(application, f"/ws/{user.pk}/") # Use the user's PK in the URL
    connected, subprotocol = await communicator.connect()
    assert connected
    await communicator.disconnect()
