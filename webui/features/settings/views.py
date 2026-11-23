"""Settings: appearance, preferences, providers and system info."""

from __future__ import annotations

import platform

from django import forms
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.validators import UnicodeUsernameValidator
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


class UsernameChangeForm(forms.Form):
    """Rename the signed-in account without touching its password or data."""

    username = forms.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
        strip=True,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_username(self):
        username = self.cleaned_data["username"]
        taken = get_user_model().objects.filter(username=username)
        if self.user is not None:
            taken = taken.exclude(pk=self.user.pk)
        if taken.exists():
            raise forms.ValidationError("That username is already taken.")
        return username


def settings_page(request, tab: str = "appearance", *, username_form=None, password_form=None):
    if tab not in ("appearance", "preferences", "providers", "system", "account"):
        tab = "appearance"
    account_user = request.user if request.user.is_authenticated else None
    if account_user is not None:
        if username_form is None:
            username_form = UsernameChangeForm(
                user=account_user, initial={"username": account_user.username}
            )
        if password_form is None:
            password_form = PasswordChangeForm(account_user)
    user_settings = UserSettings()
    settings_tabs = [
        ("appearance", "Appearance"),
        ("preferences", "Preferences"),
        ("providers", "Providers"),
        ("system", "System"),
        ("account", "Account"),
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
        "account_user": account_user,
        "username_form": username_form,
        "password_form": password_form,
        "account_saved": request.GET.get("account_saved", ""),
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
        .prefetch_related("api_keys", "offerings")
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
                "model_count": provider.offerings.filter(enabled=True).count(),
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
            "dirty": False, "dirty_paths": [], "dirty_kind": "clean",
            "is_git": False, "remote_short_commit": "",
            "available": False, "commit": "", "remote_commit": "",
        }

    from runtime.paths import agentone_home

    reconcile_stale_run()
    run = current_run()
    running = bool(run and run.get("status") == "running")
    dirty_paths = list(status.get("dirty_paths") or [])
    manifest_paths = [p for p in dirty_paths if p == ".agentone" or p.startswith(".agentone/")]
    other_paths = [p for p in dirty_paths if p not in manifest_paths]
    preference = (request.POST.get("preference") or "").strip()
    if run and run.get("action") == "merge":
        preference = (run.get("result") or {}).get("preference") or preference
    return {
        "version": status["version"],
        "release": status["release"],
        "short_commit": status["short_commit"],
        "branch": status["branch"],
        "dirty": status["dirty"],
        "dirty_paths": dirty_paths,
        "dirty_path_preview": dirty_paths[:8],
        "dirty_path_extra": max(0, len(dirty_paths) - 8),
        "dirty_kind": status.get("dirty_kind", "clean"),
        "dirty_manifest_paths": manifest_paths,
        "dirty_other_paths": other_paths,
        "home_dir": str(agentone_home()),
        "is_git": status["is_git"],
        "remote_short_commit": status["remote_short_commit"],
        "update_available": status["available"],
        "run": run,
        "is_running": running,
        "is_staff": _is_staff(request),
        "can_update": bool(
            _is_staff(request) and status["is_git"] and not status["dirty"] and not running
        ),
        "resolve_busy": bool(running and run and run.get("action") in ("undo", "merge")),
        "merge_preference": preference if preference in ("local", "remote") else "",
        "status_url": reverse("webui:settings_update_status"),
        "check_url": reverse("webui:settings_update_check"),
        "run_url": reverse("webui:settings_update_run"),
        "migrate_url": reverse("webui:settings_dirty_migrate"),
        "undo_url": reverse("webui:settings_dirty_undo"),
        "merge_url": reverse("webui:settings_dirty_merge"),
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


def _dirty_status():
    from runtime.version import update_status

    return update_status()


@require_POST
def settings_dirty_migrate(request):
    """Open a coding chat that moves install-dir .agentone edits to ~/.agentone."""
    if not _is_staff(request):
        return _forbidden()
    from runtime.paths import agentone_home

    status = _dirty_status()
    if not status.get("dirty"):
        return redirect("/app/settings/system")
    paths = [p for p in (status.get("dirty_paths") or []) if p == ".agentone" or p.startswith(".agentone/")]
    if not paths:
        return redirect("/app/settings/system")

    from .sessions import start_migration_session

    session_id = start_migration_session(
        paths,
        install_dir=str(django_settings.BASE_DIR),
        home_dir=str(agentone_home()),
    )
    if session_id:
        return redirect("webui:chat", session_id=session_id)
    return redirect("/app/settings/system?error=migration-session")


def _queue_dirty_action(request, action: str) -> HttpResponse:
    """Queue stash/undo/merge work and return the refreshed update panel."""
    if not _is_staff(request):
        return _forbidden()

    from launcher import update_state
    from launcher.tasks import resolve_local_changes

    status = _dirty_status()
    if not status.get("dirty"):
        return _update_panel(request)
    active = update_state.current_run()
    if active and active.get("status") == "running":
        return _update_panel(request)
    if not update_state.reserve_queue():
        return _update_panel(request)

    preference = (request.POST.get("preference") or "").strip()
    if action == "merge" and preference not in ("local", "remote"):
        preference = ""
    record = update_state.start_run(status["version"], action=action)
    try:
        resolve_local_changes.delay(record["id"], action, preference)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        update_state.finish_run(record["id"], "failed", error=f"Could not queue task: {exc}")
        update_state.release_queue()
    return _update_panel(request)


@require_POST
def settings_dirty_undo(request):
    """Stash all local changes so the worktree is clean again (recoverable)."""
    return _queue_dirty_action(request, "undo")


@require_POST
def settings_dirty_merge(request):
    """Update, then reapply local changes; conflicts open a chat."""
    return _queue_dirty_action(request, "merge")


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


@login_required
@require_POST
def account_username_change(request):
    """Change the signed-in user's username (same account, same sessions)."""
    form = UsernameChangeForm(request.POST, user=request.user)
    if form.is_valid():
        request.user.username = form.cleaned_data["username"]
        request.user.save(update_fields=["username"])
        return redirect("/app/settings/account?account_saved=username")
    return settings_page(request, "account", username_form=form)


@login_required
@require_POST
def account_password_change(request):
    """Change the signed-in user's password, keeping the current session."""
    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        return redirect("/app/settings/account?account_saved=password")
    return settings_page(request, "account", password_form=form)
