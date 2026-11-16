"""Middleware for the server-rendered UI.

The legacy pyHtmlGui entry point was login-protected.  The new UI lives under
``/app/`` and must keep the same protection even when it is linked directly
(not through the ``/`` redirect).  Fragment and SSE endpoints are covered too.

htmx navigation is a special case: returning a 302 would make the XHR follow
the redirect and swap the login page into ``<body>``.  Instead, htmx requests
get a tiny ``HX-Redirect`` response, which makes the browser perform a real
navigation to the login page.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse


class WebuiLoginRequiredMiddleware:
    """Redirect anonymous requests for ``/app/`` to the login page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            getattr(settings, "WEBUI_LOGIN_REQUIRED", True)
            and request.path.startswith("/app/")
            and not request.user.is_authenticated
            and not request.path.startswith("/app/sse/")
        ):
            redirect = redirect_to_login(request.get_full_path())
            if request.headers.get("HX-Request") == "true":
                response = HttpResponse(status=204)
                response["HX-Redirect"] = redirect.url
                return response
            return redirect
        return self.get_response(request)
