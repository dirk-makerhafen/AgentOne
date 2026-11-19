"""Middleware for the server-rendered UI.

The legacy  entry point was login-protected.  The new UI lives under
``/app/`` and must keep the same protection even when it is linked directly
(not through the ``/`` redirect).  Fragment and SSE endpoints are covered too.

htmx navigation is a special case: returning a 302 would make the XHR follow
the redirect and swap the login page into ``<body>``.  Instead, htmx requests
get a tiny ``HX-Redirect`` response, which makes the browser perform a real
navigation to the login page.

Boosted navigation also gets an explicit ``HX-Push-Url``.  htmx normally
pushes the URL for boosted links from the clicked element's internal state, but
component/SSE swaps can replace that element while the boosted request is in
flight (cleanup drops the ``boosted`` flag), leaving the content swapped to the
new page with the old URL still in the address bar.  The response header wins
over DOM state, so the history update is stable.
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
        response = self.get_response(request)
        if (
            request.headers.get("HX-Boosted") == "true"
            and 200 <= response.status_code < 400
            and not response.has_header("HX-Push-Url")
            and not response.has_header("HX-Replace-Url")
        ):
            response["HX-Push-Url"] = request.get_full_path()
        return response
