import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import re_path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dashboard.settings')

import django
django.setup()

from dashboard.consumers import consumers

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(            [
            re_path(r'ws/agent/(?P<instance_pk>\d+)/$', consumers.AgentConsumer.as_asgi()),
            re_path(r'ws/(?P<user_pk>\d+)/$', consumers.AgentConsumer.as_asgi()),
        ])
    ),
})