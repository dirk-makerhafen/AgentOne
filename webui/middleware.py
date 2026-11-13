"""Middleware for the server-rendered UI.

The legacy pyHtmlGui entry point was login-protected.  The new UI lives under
``/app/`` and must keep the same protection even when it is linked directly
(not through the ``/`` redirect).  Fragment and SSE endpoints are covered too.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.views import redirect_to_login


class WebuiLoginRequiredMiddleware:
    """Redirect anonymous requests for ``/app/`` to the login page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            getattr(settings, "WEBUI_LOGIN_REQUIRED", True)
            and request.path.startswith("/app/")
            and not request.user.is_authenticated
        ):
            return redirect_to_login(request.get_full_path())
        return self.get_response(request)
