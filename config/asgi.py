import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import re_path

from webui.core.events import EventsConsumer

# The UI's per-tab event stream is a WebSocket: HTTP/1.1's six-connection cap
# (and Chrome counting EventSource streams against it) starves new tabs once
# five or six are open.  HTTP stays on Django's ASGI application.
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(URLRouter([
        re_path(r"^app/ws/events/$", EventsConsumer.as_asgi()),
    ])),
})
