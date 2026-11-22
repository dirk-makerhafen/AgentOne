"""Settings: appearance, preferences, providers and system info."""

from __future__ import annotations

import platform

from django.conf import settings as django_settings
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from runtime.settings import UserSettings
from runtime.settings.settings import (
    VALID_FONT_SIZES,
    VALID_SEND_KEYS,
    VALID_SKINS,
    VALID_THEMES,
)
from server.models.providers.ai_model import AiModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider
from webui.core.components import render_fragment
from webui.core.layout import render_page

#: How long a provider→model mapping survives between the Test click and the
#: cached probe result appearing.
_PROBE_MAPPING_TTL = 600


def _probe_model_key(provider_id: int) -> str:
    return f"webui:probe:provider:{provider_id}"


def _probe_error_key(provider_id: int) -> str:
    return f"webui:probe:error:{provider_id}"


def settings_page(request, tab: str = "appearance"):
    if tab not in ("appearance", "preferences", "providers", "system"):
        tab = "appearance"
    user_settings = UserSettings()
    settings_tabs = [
        ("appearance", "Appearance"),
        ("preferences", "Preferences"),
        ("providers", "Providers"),
        ("system", "System"),
    ]
    context = {
        "tab": tab,
        "active_id": tab,
        "settings_tabs": settings_tabs,
        "user_settings": user_settings,
        "themes": sorted(VALID_THEMES),
        "skins": sorted(VALID_SKINS),
        "font_sizes": sorted(VALID_FONT_SIZES),
        "send_keys": sorted(VALID_SEND_KEYS),
        "models": list(AiModel.objects.order_by("name").values_list("name", flat=True)[:500]),
        "saved": request.GET.get("saved") == "1",
    }
    if tab == "providers":
        rows = _provider_rows()
        context["providers"] = rows
        context["providers_summary"] = _providers_summary(rows)
    elif tab == "system":
        context["system"] = _system_info()
        context["update"] = _update_context(request)
        context["system"]["version"] = context["update"]["version"]
        context["system"]["commit"] = context["update"]["short_commit"]
    elif tab == "preferences":
        try:
            from runtime.power import power_state_summary

            context["power"] = power_state_summary()
        except Exception:  # pylint: disable=broad-exception-caught
            context["power"] = {}
    return render_page(request, "settings", "settings/single.html", context, active_id=tab)


def _provider_probe(provider: ApiProvider) -> dict | None:
    """Return the cached probe result for *provider*, if one was requested."""
    from server.tasks.probe_model import get_cached_result

    model_pk = cache.get(_probe_model_key(provider.pk))
    if not model_pk:
        return None
    result = get_cached_result(int(model_pk))
    if result is not None:
        return result
    error = cache.get(_probe_error_key(provider.pk))
    if error:
        return {"verdict": "failed", "error_message": error}
    # A probe was requested but no result is cached yet: it is either queued or
    # running.  The mapping key expires long before the result key, so this
    # cannot mask an expired result.
    return {"verdict": "running", "model_pk": int(model_pk)}


def _provider_probe_context(provider: ApiProvider) -> dict:
    return {
        "provider_id": provider.pk,
        "probe": _provider_probe(provider),
    }


def settings_provider_probe(request, provider_id: int):
    """Return just the probe row so polling never replaces the whole card."""
    provider = get_object_or_404(ApiProvider, pk=provider_id)
    return render_fragment(
        request,
        "settings/parts/provider_probe.html",
        _provider_probe_context(provider),
    )


def _provider_rows() -> list[dict]:
    """Provider rows with masked keys for the settings table."""
    now = timezone.now()
    providers = (
        ApiProvider.objects.filter(Q(enabled=True) | Q(api_keys__isnull=False))
        .distinct()
        .prefetch_related("api_keys", "aimodels")
        .order_by("is_local", "name")
    )
    rows = []
    for provider in providers:
        keys = []
        for key in provider.api_keys.all().order_by("-enabled", "pk"):
            cooling = ""
            if key.rate_limit_until and key.rate_limit_until > now:
                cooling = f"cooling {int((key.rate_limit_until - now).total_seconds())}s"
            value = key.key or ""
            display = value if len(value) <= 8 else f"{value[:4]}…{value[-4:]}"
            keys.append(
                {
                    "pk": key.pk,
                    "comment": key.comment or f"key {key.pk}",
                    "display": display,
                    "enabled": key.enabled,
                    "cooling": cooling,
                }
            )
        rows.append(
            {
                "id": provider.pk,
                "name": provider.name,
                "slug": provider.slug,
                "is_local": provider.is_local,
                "model_count": provider.aimodels.filter(enabled=True).count(),
                "has_default": bool(provider.default_api_key),
                "keys": keys,
                "api_key_url": provider.api_key_url,
                "setup": (provider.setup_instructions or "")[:400],
                "probe": _provider_probe(provider),
            }
        )
    return rows


def _providers_summary(rows: list[dict]) -> dict:
    """Compute summary statistics for the providers overview."""
    total = len(rows)
    local = sum(1 for r in rows if r["is_local"])
    remote = total - local
    with_keys = sum(1 for r in rows if r["keys"])
    total_keys = sum(len(r["keys"]) for r in rows)
    healthy = sum(1 for r in rows if r["probe"] and r["probe"].get("verdict") == "healthy")
    failed = sum(1 for r in rows if r["probe"] and r["probe"].get("verdict") == "failed")
    return {
        "total": total,
        "local": local,
        "remote": remote,
        "with_keys": with_keys,
        "total_keys": total_keys,
        "healthy": healthy,
        "failed": failed,
    }


@require_POST
def settings_provider_key(request, provider_id: int):
    """Add, toggle or delete an API key for a provider."""
    provider = get_object_or_404(ApiProvider, pk=provider_id)
    action = request.POST.get("action", "")
    raw_key = request.POST.get("key_id", "")
    if action == "add":
        value = (request.POST.get("key") or "").strip()
        if value:
            ApiKey.objects.create(
                api_provider=provider,
                key=value,
                comment=(request.POST.get("comment") or "").strip(),
            )
    elif action == "toggle" and raw_key.isdigit():
        key = provider.api_keys.filter(pk=int(raw_key)).first()
        if key is not None:
            key.enabled = not key.enabled
            key.save(update_fields=["enabled"])
    elif action == "delete" and raw_key.isdigit():
        provider.api_keys.filter(pk=int(raw_key)).delete()
    if request.headers.get("HX-Request") == "true":
        # The key editor lives in the rightbar detail fragment; refresh that
        # fragment in place instead of navigating away from the current page.
        from webui.features.insights.views import _provider_detail_context

        return render_fragment(
            request,
            "insights/parts/provider_detail.html",
            _provider_detail_context(provider),
        )
    return redirect("/app/settings/providers?saved=1")


@require_POST
def settings_provider_test(request, provider_id: int):
    """Dispatch a smoke test for the provider's best usable model."""
    provider = get_object_or_404(ApiProvider, pk=provider_id)
    try:
        from runtime.test_run import best_usable_model
        from server.tasks.probe_model import probe_model

        model = best_usable_model(provider.pk)
        if model is None:
            cache.set(
                _probe_error_key(provider.pk),
                "No usable enabled model on this provider",
                _PROBE_MAPPING_TTL,
            )
        else:
            cache.delete(_probe_error_key(provider.pk))
            cache.set(_probe_model_key(provider.pk), model.pk, _PROBE_MAPPING_TTL)
            probe_model.delay(model.pk)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        cache.set(_probe_error_key(provider.pk), str(exc), _PROBE_MAPPING_TTL)
    redirect_to = "/app/settings/providers"
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/app/"):
        redirect_to = next_url
    if request.headers.get("HX-Request") == "true":
        return render_fragment(
            request,
            "settings/parts/provider_probe.html",
            _provider_probe_context(provider),
        )
    return redirect(redirect_to)


def _system_info() -> dict:
    from runtime.paths import agentone_home, log_base

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "agentone_home": str(agentone_home()),
        "log_dir": str(django_settings.LOG_DIR or log_base()),
        "base_dir": django_settings.BASE_DIR,
        "database": django_settings.DATABASES.get("default", {}).get("ENGINE", ""),
        "redis": getattr(django_settings, "REDIS_URL", ""),
        "debug": bool(django_settings.DEBUG),
        "timezone": django_settings.TIME_ZONE,
        "display_timezone": str(timezone.get_current_timezone()),
    }


def _is_staff(request) -> bool:
    return bool(getattr(request.user, "is_staff", False))


def _forbidden() -> HttpResponse:
    return HttpResponse("Only staff members can update AgentOne.", status=403)


def _update_context(request) -> dict:
    """Context for the Settings → System update card and its htmx fragment."""
    from launcher.update_state import current_run, reconcile_stale_run
    from runtime.version import update_status

    try:
        status = update_status()
    except Exception:  # pylint: disable=broad-exception-caught
        status = {
            "version": "unknown", "release": "", "short_commit": "", "branch": "",
            "dirty": False, "is_git": False, "remote_short_commit": "",
            "available": False, "commit": "", "remote_commit": "",
        }

    reconcile_stale_run()
    run = current_run()
    running = bool(run and run.get("status") == "running")
    return {
        "version": status["version"],
        "release": status["release"],
        "short_commit": status["short_commit"],
        "branch": status["branch"],
        "dirty": status["dirty"],
        "is_git": status["is_git"],
        "remote_short_commit": status["remote_short_commit"],
        "update_available": status["available"],
        "run": run,
        "is_running": running,
        "is_staff": _is_staff(request),
        "can_update": bool(
            _is_staff(request) and status["is_git"] and not status["dirty"] and not running
        ),
        "status_url": reverse("webui:settings_update_status"),
        "check_url": reverse("webui:settings_update_check"),
        "run_url": reverse("webui:settings_update_run"),
    }


def _update_panel(request) -> HttpResponse:
    response = render(request, "settings/update_panel.html", {"update": _update_context(request)})
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def settings_update_status(request):
    """Poll target while an update is running (the panel drops itself when done)."""
    if not _is_staff(request):
        return _forbidden()
    return _update_panel(request)


@require_POST
def settings_update_check(request):
    """Discard the cached remote check and re-query GitHub (POST = CSRF-safe)."""
    if not _is_staff(request):
        return _forbidden()
    from runtime.version import update_status

    update_status(refresh=True)
    return _update_panel(request)


@require_POST
def settings_update_run(request):
    """Queue the full update pipeline as a background Celery task."""
    if not _is_staff(request):
        return _forbidden()

    from launcher import update_state
    from launcher.tasks import update_agentone
    from runtime.version import get_version_info

    active = update_state.current_run()
    if active and active.get("status") == "running":
        return _update_panel(request)
    if not update_state.reserve_queue():
        return _update_panel(request)

    record = update_state.start_run(get_version_info()["version"])
    try:
        update_agentone.delay(record["id"])
    except Exception as exc:  # pylint: disable=broad-exception-caught
        update_state.finish_run(record["id"], "failed", error=f"Could not queue update: {exc}")
        update_state.release_queue()
    return _update_panel(request)


@require_POST
def settings_save(request, tab: str):
    user_settings = UserSettings()
    post = request.POST

    if tab == "appearance":
        if post.get("theme") in VALID_THEMES:
            user_settings.theme = post["theme"]
        if post.get("skin") in VALID_SKINS:
            user_settings.skin = post["skin"]
        if post.get("font_size") in VALID_FONT_SIZES:
            user_settings.font_size = post["font_size"]
        user_settings.workspace_panel_open = post.get("workspace_panel_open") == "on"

    elif tab == "preferences":
        if post.get("send_key") in VALID_SEND_KEYS:
            user_settings.send_key = post["send_key"]
        user_settings.default_model = (post.get("default_model") or "").strip()
        user_settings.prevent_sleep_when_local_ai = (
            post.get("prevent_sleep_when_local_ai") == "on"
        )
        for field in (
            "min_battery_pct_for_caffeinate",
            "pause_local_ai_below_battery_pct",
            "sleep_guard_release_delay_minutes",
        ):
            raw = post.get(field)
            if raw is not None and str(raw).isdigit():
                setattr(user_settings, field, int(raw))

    return redirect(f"/app/settings/{tab}?saved=1")
