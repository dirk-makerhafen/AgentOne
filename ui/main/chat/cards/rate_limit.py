"""
Rate-limit notification card.

Shown in the composer flyout while this session has AgentTaskCalls parked in
``WAITING_RATELIMIT``.  It tells the user which model/provider is blocked, how
long until the auto-retry, and offers one-click alternatives:

  * switch the session to another API key of the blocked provider,
  * enable automatic key failover for the session (plus an optional max
    wait — if the wait would exceed it, fail over automatically),
  * switch to another provider serving the same model,
  * switch to a different model entirely.

Switching re-pins the session (new session version), re-points the parked
calls to that version and releases them if the new model has capacity.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, List

from django.utils import timezone

from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.tasks.agent_task_call import AgentTaskCall
from ui.app import UiApp
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from runtime.session.session import Session


def _humanize_seconds(seconds: int) -> str:
    """Render a seconds count as ``2m 5s`` / ``45s``."""
    minutes, secs = divmod(int(seconds), 60)
    if minutes and secs:
        return f"{minutes}m {secs}s"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


class RateLimitCard(PyHtmlView):
    # pylint: disable=too-many-ancestors
    DOM_ELEMENT_EXTRAS = 'role="status" aria-live="polite" aria-labelledby="rateLimitHeading"'
    TEMPLATE_STR = '''
        <div class="ratelimit-inner" style="{% if not pyview.pending_count %}display:none{% endif %}">
            <div class="ratelimit-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                <span id="rateLimitHeading">LLM rate limited</span>
                <span class="ratelimit-count">{{ pyview.pending_count }} waiting</span>
            </div>
            {% if pyview.blocked %}
            <div class="ratelimit-block">
                <div class="ratelimit-block-name">{{ pyview.blocked.model }}
                    <span class="ratelimit-block-provider">· {{ pyview.blocked.provider }}</span>
                </div>
                {% if pyview.blocked.wait_text %}
                <div class="ratelimit-wait">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    auto-retrying in {{ pyview.blocked.wait_text }}
                </div>
                {% elif pyview.blocked.resuming %}
                <div class="ratelimit-wait">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
                    Resuming on another API key
                </div>
                {% else %}
                <div class="ratelimit-wait">Waiting for capacity to free up</div>
                {% endif %}
                {% if pyview.blocked.note %}
                <div class="ratelimit-note">{{ pyview.blocked.note }}</div>
                {% endif %}
            </div>
            {% endif %}

            <div class="ratelimit-switch-section"{% if not pyview.blocked %} style="display:none"{% endif %}>
                {% if pyview.keys %}
                <div class="ratelimit-section">API keys for {{ pyview.blocked.provider }}</div>
                {% for key in pyview.keys %}
                <button class="ratelimit-row{% if key.current %} ratelimit-row-current{% endif %}" type="button" onclick="pyview.switch_to_key({{ key.key_id }})" title="Use this key for the session{% if key.current %} (currently in use){% endif %}">
                    <span class="ratelimit-row-icon" aria-hidden="true">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
                    </span>
                    <span class="ratelimit-row-provider">{{ key.label }}</span>
                    <span class="ratelimit-row-meta">{{ key.status_text }}</span>
                </button>
                {% endfor %}
                {% endif %}

                {% if pyview.provider_alternatives %}
                <div class="ratelimit-section">Alternative providers for {{ pyview.blocked.model }}</div>
                {% for alt in pyview.provider_alternatives %}
                <button class="ratelimit-row" type="button" onclick="pyview.switch_to_provider({{ alt.provider_id }})" title="Use {{ alt.provider }} for {{ pyview.blocked.model }}">
                    <span class="ratelimit-row-icon" aria-hidden="true">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="6" y1="8" x2="10" y2="8"/></svg>
                    </span>
                    <span class="ratelimit-row-provider">{{ alt.provider }}</span>
                    <span class="ratelimit-row-meta">{{ alt.keys_text }}</span>
                </button>
                {% endfor %}
                {% endif %}

                {% if pyview.model_alternatives %}
                <div class="ratelimit-section">Or switch model</div>
                {% for alt in pyview.model_alternatives %}
                <button class="ratelimit-row" type="button" onclick="pyview.switch_to_model('{{ alt.name_escaped }}')" title="Switch to {{ alt.name }}">
                    <span class="ratelimit-row-icon" aria-hidden="true">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                    </span>
                    <span class="ratelimit-row-provider">{{ alt.name }}</span>
                    <span class="ratelimit-row-meta">{{ alt.provs_text }}</span>
                </button>
                {% endfor %}
                {% endif %}

                <div class="ratelimit-policy">
                    <button class="ratelimit-row" type="button" onclick="pyview.toggle_auto_failover()" title="Automatically use another key of the same provider when one is rate-limited">
                        <span class="ratelimit-row-icon" aria-hidden="true">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                        </span>
                        <span class="ratelimit-row-provider">Automatic key switching</span>
                        <span class="ratelimit-row-meta">{{ pyview.auto_failover_label }}</span>
                    </button>
                    <label class="ratelimit-maxwait">Max wait
                        <input type="number" min="0" step="5" value="{{ pyview.max_wait_value }}" onchange="pyview.set_max_wait(this.value)" title="If the wait for the current key exceeds this, fail over automatically (0 = no limit)">
                        s
                    </label>
                </div>

                {% if not pyview.provider_alternatives and not pyview.model_alternatives %}
                <div class="ratelimit-none">No alternative provider or model available — add an API key in Settings &rarr; Providers, or wait for the auto-retry.</div>
                {% endif %}
            </div>
        </div>
    '''

    def __init__(self, subject: Session, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._snap: Dict[str, Any] | None = None
        app = UiApp.get_instance()
        if app is not None:
            self._session_id = subject.model.pk
            app.model_observer.unwatch_filter(
                model_class=AgentTaskCall,
                filter={"session_id": self._session_id},
            )
            app.model_observer.watch(
                AgentTaskCall,
                filter={"session_id": self._session_id},
                callback_name="_on_ratelimit_taskcall_updated",
                view=self,
                action="update",
            )

    @property
    def DOM_ELEMENT_CLASS(self):
        return 'rate-limit-card' + (' visible' if self._snapshot["pending_count"] else '')

    @property
    def pending_count(self) -> int:
        return self._snapshot["pending_count"]

    @property
    def blocked(self) -> Dict[str, Any] | None:
        return self._snapshot["blocked"]

    @property
    def provider_alternatives(self) -> List[Dict[str, Any]]:
        return self._snapshot["provider_alternatives"]

    @property
    def model_alternatives(self) -> List[Dict[str, Any]]:
        return self._snapshot["model_alternatives"]

    @property
    def keys(self) -> List[Dict[str, Any]]:
        return self._snapshot["keys"]

    @property
    def auto_failover_label(self) -> str:
        return "On" if self._snapshot["auto_failover"] else "Off"

    @property
    def max_wait_value(self) -> int:
        return self._snapshot["max_wait_value"]

    # ------------------------------------------------------------------
    # Snapshotting — recomputed on every update (each update() and each
    # autoupdate poll), read from the cache during template rendering.
    # ------------------------------------------------------------------

    @property
    def _snapshot(self) -> Dict[str, Any]:
        if self._snap is None:
            self._snap = self._compute()
        return self._snap

    def update(self, *args, **kwargs):
        self._snap = None
        super().update(*args, **kwargs)
        self._sync_autoupdate()

    def _sync_autoupdate(self) -> None:
        """Keep a live countdown running only while calls are parked."""
        if self._snap is None:
            self._snap = self._compute()
        if self._snap["pending_count"]:
            self.set_autoupdate_interval(2)
        else:
            self.set_autoupdate_interval(None)

    def _compute(self) -> Dict[str, Any]:
        from runtime.rate_limiter import KeyFailoverPolicy

        blocked = self._blocked_aimodel()
        policy = (
            self.subject.key_failover_policy()
            if self.subject is not None
            else KeyFailoverPolicy(auto_failover=False, max_wait_seconds=0)
        )
        return {
            "pending_count": self._pending_calls().count(),
            "blocked": self._blocked_info(blocked),
            "provider_alternatives": self._provider_rows(blocked),
            "model_alternatives": self._model_rows(blocked),
            "keys": self._key_rows(blocked),
            "auto_failover": policy.auto_failover,
            "max_wait_value": policy.max_wait_seconds,
        }

    def _pending_calls(self) -> Any:
        """Queryset of this session's WAITING_RATELIMIT calls, FIFO."""
        if self.subject is None:
            return AgentTaskCall.objects.none()
        return AgentTaskCall.objects.filter(
            session=self.subject.model,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        ).order_by("created_at")

    def _blocked_aimodel(self):
        """The model a release would currently attempt — the session's current
        aimodel (after a switch) or, failing that, the first parked call's
        pinned model."""
        if self.subject is None:
            return None
        current = self.subject.aimodel
        if current is not None:
            return current
        call = self._pending_calls().select_related("session_version").first()
        if call is None:
            return None
        from runtime.session.session import Session

        try:
            return Session(
                session_model=call.session,
                pinned_session_version=call.session_version,
            ).aimodel
        except Exception:  # pragma: no cover # pylint: disable=broad-exception-caught - defensive
            return None

    def _blocked_info(self, aimodel) -> Dict[str, Any] | None:
        if aimodel is None:
            return None
        provider = aimodel.api_provider
        wait, resuming = self._session_wait(aimodel)
        info: Dict[str, Any] = {
            "model": aimodel.name,
            "provider": provider.name,
            "wait_text": _humanize_seconds(wait) if wait else "",
            "resuming": resuming,
            "note": "",
        }
        return info

    def _session_wait(self, aimodel) -> tuple[int | None, bool]:
        """(remaining seconds, resuming) for the blocked provider.

        Strict mode (default) reports the wait on the session's own key, so
        the "auto-retrying in Xs" text is accurate — the scheduler waits for
        that exact key rather than rotating.  With auto-failover on, a ready
        sibling key means the call resumes immediately (resuming=True).
        """
        if self.subject is None:
            return (None, False)
        policy = self.subject.key_failover_policy()
        if policy.auto_failover:
            # Any enabled key that is not cooling means the call resumes
            # immediately — no countdown.
            now = timezone.now()
            provider = aimodel.api_provider
            if any(
                not (k.rate_limit_until and k.rate_limit_until > now)
                for k in provider.api_keys.filter(enabled=True)
            ):
                return (None, True)
            return (RateLimitCard._cooldown_wait_seconds(provider), False)

        current = self.subject.current_provider_api_key(aimodel)
        if current is not None:
            if current.rate_limit_until and current.rate_limit_until > timezone.now():
                wait = int((current.rate_limit_until - timezone.now()).total_seconds())
                return (max(wait, 0), False)
            return (None, False)
        return (RateLimitCard._cooldown_wait_seconds(aimodel.api_provider), False)

    def _key_rows(self, aimodel) -> List[Dict[str, Any]]:
        """Enabled keys of the blocked provider, with status badges."""
        if aimodel is None:
            return []
        current = (
            self.subject.current_provider_api_key(aimodel)
            if self.subject is not None
            else None
        )
        now = timezone.now()
        rows: List[Dict[str, Any]] = []
        for key in aimodel.api_provider.api_keys.filter(enabled=True).order_by("pk"):
            is_current = current is not None and key.pk == current.pk
            cooling = bool(key.rate_limit_until and key.rate_limit_until > now)
            bits = []
            if is_current:
                bits.append("current")
            if cooling:
                wait = int((key.rate_limit_until - now).total_seconds())
                bits.append(f"cooling {_humanize_seconds(wait)}")
            elif not is_current:
                bits.append("ready")
            rows.append(
                {
                    "key_id": key.pk,
                    "label": key.comment or f"key {key.pk}",
                    "status_text": " · ".join(bits) if bits else "ready",
                    "current": is_current,
                }
            )
        return rows

    @staticmethod
    def _cooldown_wait_seconds(provider) -> int | None:
        """Seconds until the provider's earliest cooling key is free, or None."""
        now = timezone.now()
        remaining: list[int] = []
        for key in provider.api_keys.filter(enabled=True):
            if key.rate_limit_until and key.rate_limit_until > now:
                remaining.append(int((key.rate_limit_until - now).total_seconds()))
        return min(remaining) if remaining else None

    def _provider_rows(self, aimodel) -> List[Dict[str, Any]]:
        if aimodel is None:
            return []
        from runtime.session.aimodel_picker import sibling_aimodels

        now = timezone.now()
        rows: List[Dict[str, Any]] = []
        for sibling in sibling_aimodels(aimodel):
            provider = sibling.api_provider
            enabled = list(provider.api_keys.filter(enabled=True))
            keys_text = f"{len(enabled)} key" + ("s" if len(enabled) != 1 else "")
            if any(k.rate_limit_until and k.rate_limit_until > now for k in enabled):
                keys_text += " · cooling"
            rows.append(
                {
                    "provider_id": provider.pk,
                    "provider": provider.name,
                    "keys_text": keys_text,
                }
            )
        return rows

    def _model_rows(self, aimodel) -> List[Dict[str, Any]]:
        from runtime.session.aimodel_picker import model_groups

        current = aimodel.name if aimodel is not None else None
        rows: List[Dict[str, Any]] = []
        for group in model_groups():
            if group.name == current:
                continue
            plural = "s" if group.provider_count != 1 else ""
            rows.append(
                {
                    "name": group.name,
                    "name_escaped": group.name.replace("\\", "\\\\").replace("'", "\\'"),
                    "provs_text": f"{group.provider_count} provider{plural}",
                }
            )
            if len(rows) >= 6:
                break
        return rows

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def switch_to_provider(self, provider_id: int) -> None:
        """Pin another provider serving the blocked model, then retry the
        parked calls on it."""
        from runtime.tasks.call_scheduler import CallScheduler

        blocked = self._blocked_aimodel()
        if blocked is None:
            return
        self.subject.set_aimodel_by_provider(blocked.name, int(provider_id))
        CallScheduler.release_waiting_ratelimit_calls(self.subject.model, repoint=True)
        self._refresh_model_chip()
        self.update()

    def switch_to_key(self, key_id: int) -> None:
        """Stick this session to a specific API key of the blocked provider,
        then retry the parked calls on it."""
        from runtime.tasks.call_scheduler import CallScheduler
        from server.models.providers.api_key import ApiKey

        if self.subject is None:
            return
        try:
            key = ApiKey.objects.get(pk=key_id)
        except ApiKey.DoesNotExist:
            return
        self.subject.set_preferred_api_key(key)
        CallScheduler.release_waiting_ratelimit_calls(self.subject.model, repoint=True)
        self.update()

    def toggle_auto_failover(self) -> None:
        """Flip the session's automatic key-switching flag and retry the
        parked calls — enabling it lets the scheduler use any ready key."""
        from runtime.tasks.call_scheduler import CallScheduler

        if self.subject is None:
            return
        self.subject.set_auto_failover_keys(not self.subject.auto_failover_keys_enabled())
        CallScheduler.release_waiting_ratelimit_calls(self.subject.model, repoint=True)
        self.update()

    def set_max_wait(self, value: Any) -> None:
        """Set the max acceptable cooldown wait; exceeding it fails over."""
        from runtime.tasks.call_scheduler import CallScheduler

        if self.subject is None:
            return
        try:
            seconds = max(int(value), 0)
        except (TypeError, ValueError):
            return
        if seconds == self.subject.key_max_wait_seconds():
            return
        self.subject.set_key_max_wait_seconds(seconds if seconds else None)
        CallScheduler.release_waiting_ratelimit_calls(self.subject.model, repoint=True)
        self.update()

    def switch_to_model(self, name: str) -> None:
        """Pin a different model (picker chooses the best provider), then retry
        the parked calls on it."""
        from runtime.tasks.call_scheduler import CallScheduler

        self.subject.set_aimodel_by_name(name)
        CallScheduler.release_waiting_ratelimit_calls(self.subject.model, repoint=True)
        self._refresh_model_chip()
        self.update()

    def _refresh_model_chip(self) -> None:
        """Re-render the composer model chip so it shows the new pin."""
        try:
            wrap = self.parent.composer_box.footer.model_wrap
        except Exception:  # pragma: no cover # pylint: disable=broad-exception-caught - defensive
            return
        wrap.update()

    def _on_ratelimit_taskcall_updated(self, pk: int, action: str, filter_context: dict) -> None:  # pylint: disable=unused-argument
        """Re-render when an AgentTaskCall for this session changes status."""
        self.update()
