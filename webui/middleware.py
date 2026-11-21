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

A second middleware switches the display timezone to the browser's IANA zone
(cookie written by the inline bootstrap in ``layout/base.html``).  Django's
``|date``/``|timesince`` filters and our ``|clock`` filter all read the active
timezone, so one activation covers every fragment without touching templates.
Storage and Celery keep using UTC.
"""

from __future__ import annotations

import re
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.utils import timezone


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


#: Written by the inline bootstrap in ``webui/core/templates/layout/base.html``.
#: A plain cookie (not session storage) also reaches component/SSE requests.
TIMEZONE_COOKIE = "agentone_timezone"
_TIMEZONE_RE = re.compile(r"^[A-Za-z0-9_+.-]+(?:/[A-Za-z0-9_+.-]+)*$")


@lru_cache(maxsize=256)
def _browser_timezone(name: str) -> ZoneInfo | None:
    """Resolve an IANA zone name from the cookie, or ``None`` if unusable."""
    if not name or len(name) > 64 or not _TIMEZONE_RE.fullmatch(name):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


class UserTimezoneMiddleware:
    """Render webui times in the browser's local timezone (storage stays UTC)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        name = request.COOKIES.get(TIMEZONE_COOKIE, "")
        zone = _browser_timezone(name) or settings.TIME_ZONE
        with timezone.override(zone):
            return self.get_response(request)
