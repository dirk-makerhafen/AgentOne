from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.messages.message import MessageView
from server.models.queries.query import Query


def _fmt_duration(seconds: float | None) -> str:
    """Format a duration in seconds as a compact human string."""
    if seconds is None:
        return ""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m {int(seconds % 60):02d}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60:02d}m"


def _fmt_clock(value) -> str:
    """Format a datetime as HH:MM:SS (empty string when missing)."""
    if value is None:
        return ""
    try:
        return value.strftime("%H:%M:%S")
    except Exception:
        return ""


class QueryView(ModelView):
    DOM_ELEMENT_CLASS = "msg-row query-row"
    TEMPLATE_STR = '''
        <div class="query-card {% if pyview.subject.status == "ACTIVE" %}query-active{% endif %} {% if pyview.is_open %}open{% endif %}">
            <div class="query-card-header" onclick="pyview.toggle()">
                <span class="card-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                </span>
                <span class="card-title">Query</span>
                <span class="card-sub" title="{{ pyview.summary_title }}">{{ pyview.provider_model_label }}</span>
                <span class="card-meta" title="API key used for this query">{{ pyview.apikey_label }}</span>
                <span class="card-meta" title="Prompt tokens">{{ pyview.subject.tokens or 0 }} tok</span>
                <span class="card-meta" title="Last update: {{ pyview.subject.updated_at }}">{{ pyview.updated_str }}</span>
                {% if pyview.show_duration %}
                    <span class="card-meta" title="Time the query took so far / in total">{{ pyview.duration_str }}</span>
                {% endif %}
                <span class="card-status {{ pyview.subject.status|lower }}">{{ pyview.subject.status }}</span>
                <span class="card-toggle">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </span>
            </div>
            <div class="query-card-detail">
                <div class="query-card-messages">
                    {% if pyview.is_open %}
                        {% for qm in pyview.messages %}
                            <div class="query-message query-message-{{ qm.role }}">
                                <div class="query-message-role">{{ qm.role }}</div>
                                <div class="query-message-content">{{ qm.to_openai_message(pyview.requires_reasoning_echo) }}</div>
                                <span class="query-message-tokens">{{ qm.tokens or 0 }} tok</span>
                            </div>
                        {% endfor %}
                    {% endif %}
                </div>

                <div class="query-card-foot">
                    <span class="query-tokens">{{ pyview.subject.tokens or 0 }} tokens</span>
                    <span class="query-tokens">{{ pyview.provider_model_label }}</span>
                    <span class="query-tokens">{{ pyview.apikey_label }}</span>
                    <span class="query-time" title="{{ pyview.subject.created_at }}">{{ pyview.subject.created_at }}</span>
                </div>
            </div>

        </div>
    '''
    def __init__(self, subject: Query, parent: MessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.requires_reasoning_echo = False
        self.messages = []
        self.is_open = False
        # Set by Messages._refresh_turns: a collapsed turn hides its query
        # rows entirely (the assistant turn bar stays as the representative).
        self.turn_collapsed = False
        try:
            node = getattr(self, "parent", None)
            seen = 0
            pk = getattr(subject, "pk", None)
            while node is not None and seen < 8 and pk is not None:
                if type(node).__name__ == "Messages":
                    for apk, qpks in (node._turn_queries or {}).items():
                        if pk in (qpks or []):
                            self.turn_collapsed = bool(node._turn_effective(apk))
                            break
                    break
                node = getattr(node, "parent", None)
                seen += 1
        except Exception:
            pass

    def toggle(self):
        self.is_open = not self.is_open
        if self.is_open:
            aimodel = self.subject.session_version.get_runtime().aimodel
            self.requires_reasoning_echo = aimodel and aimodel.requires_reasoning_echo
            self.messages = list(self.subject.related_query_messages.order_by("pk").all())
        self.update()

    @property
    def _latest_response(self):
        """The response produced for this query, if any (never raises)."""
        try:
            rel = getattr(self.subject, "related_response", None)
            if rel is None:
                return None
            if hasattr(rel, "order_by"):
                return rel.order_by("-pk").first()
            return rel
        except Exception:
            return None

    @property
    def provider_name(self) -> str:
        try:
            resp = self._latest_response
            if resp is not None and getattr(resp, "provider_name", ""):
                return resp.provider_name
            aimodel = getattr(resp, "aimodel", None) if resp is not None else None
            if aimodel is not None:
                provider = getattr(aimodel, "api_provider", None)
                if provider is not None and getattr(provider, "name", ""):
                    return provider.name
            sv = getattr(self.subject, "session_version", None)
            if sv is not None:
                try:
                    aimodel = sv.get_runtime().aimodel
                except Exception:
                    aimodel = None
                if aimodel is not None:
                    provider = getattr(aimodel, "api_provider", None)
                    if provider is not None and getattr(provider, "name", ""):
                        return provider.name
        except Exception:
            pass
        return ""

    @property
    def model_name(self) -> str:
        try:
            resp = self._latest_response
            if resp is not None and getattr(resp, "model_name", ""):
                return resp.model_name
            if resp is not None and getattr(resp, "aimodel", None) is not None:
                name = getattr(resp.aimodel, "name", "")
                if name:
                    return name
        except Exception:
            pass
        return ""

    @property
    def provider_model_label(self) -> str:
        provider = self.provider_name
        model = self.model_name
        if provider and model:
            return f"{provider} · {model}"
        return provider or model or self.agent_label

    @property
    def agent_label(self) -> str:
        try:
            sv = getattr(self.subject, "session_version", None)
            agent = getattr(sv, "agent", None) if sv is not None else None
            if agent is not None and getattr(agent, "name", ""):
                return agent.name
        except Exception:
            pass
        return ""

    @property
    def summary_title(self) -> str:
        parts = [p for p in (self.agent_label, self.provider_name, self.model_name) if p]
        return " · ".join(parts)

    @property
    def apikey_label(self) -> str:
        try:
            apikey_id = getattr(self.subject, "apikey_id", None)
            if apikey_id is None:
                return "key —"
            comment = ""
            try:
                apikey = getattr(self.subject, "apikey", None)
                comment = (getattr(apikey, "comment", "") or "").strip()
            except Exception:
                comment = ""
            if comment:
                return f"key #{apikey_id} {comment}"
            return f"key #{apikey_id}"
        except Exception:
            return "key —"

    @property
    def updated_str(self) -> str:
        try:
            return _fmt_clock(self.subject.updated_at)
        except Exception:
            return ""

    @property
    def show_duration(self) -> bool:
        """Show the elapsed/total time once the query started or finished."""
        try:
            return (getattr(self.subject, "status", "") or "") in ("ACTIVE", "SUCCESS", "FAILURE")
        except Exception:
            return False

    @property
    def duration_str(self) -> str:
        try:
            start = getattr(self.subject, "created_at", None)
            end = getattr(self.subject, "updated_at", None)
            if start is None or end is None:
                return ""
            return _fmt_duration((end - start).total_seconds())
        except Exception:
            return ""
