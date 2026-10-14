from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from server.models.queries.response import Response
    from ui.main.chat.messages.assistant_message import AssistantMessageView


def _fmt_num(value, digits: int = 2) -> str:
    try:
        if value is None:
            return ""
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


class ResponseView(ModelView):
    """Collapsible LLM-response card, styled like the query card.

    The header carries the timing/token stats that used to live inline on
    the assistant message (response tokens, time to first token, reasoning
    time, message time, total time, tokens/sec); the detail shows the token
    breakdown plus the raw reasoning/content of the response.
    """

    DOM_ELEMENT_CLASS = "msg-row query-row"
    TEMPLATE_STR = '''
        <div class="query-card response-card {% if pyview.subject.status == "ACTIVE" %}query-active{% endif %} {% if pyview.is_open %}open{% endif %}">
            <div class="query-card-header" onclick="pyview.toggle()">
                <span class="card-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2 2z"></path></svg>
                </span>
                <span class="card-title">Response</span>
                <span class="card-sub" title="{{ pyview.summary_title }}">{{ pyview.provider_model_label }}</span>
                {% if pyview.subject.completion_tokens %}
                    <span class="card-meta" title="Response tokens">{{pyview.subject.completion_tokens}}tkn</span>
                {% endif %}
                {% if pyview.subject.time_to_first_token %}
                    <span class="card-meta" title="Time to first token">first {{pyview.ttft_str}}s</span>
                {% endif %}
                {% if pyview.subject.reasoning_time %}
                    <span class="card-meta" title="Reasoning time">think {{pyview.reasoning_str}}s</span>
                {% endif %}
                {% if pyview.message_time_str %}
                    <span class="card-meta" title="Message time">msg {{pyview.message_time_str}}s</span>
                {% endif %}
                {% if pyview.subject.total_time %}
                    <span class="card-meta" title="Total time">total {{pyview.total_str}}s</span>
                {% endif %}
                {% if pyview.tps_str %}
                    <span class="card-meta" title="Tokens/second while generating (tokens/second overall)">{{pyview.tps_str}}tkn/s</span>
                {% endif %}
                <span class="card-meta" title="Last update: {{ pyview.subject.updated_at }}">{{ pyview.updated_str }}</span>
                <span class="card-status {{ pyview.subject.status|lower }}">{{ pyview.subject.status }}</span>
                <span class="card-toggle">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </span>
            </div>
            <div class="query-card-detail">
                <div class="query-card-messages">
                    <div class="query-message query-message-system">
                        <div class="query-message-role">Usage</div>
                        <div class="query-message-content">{{ pyview.usage_label }}</div>
                    </div>
                    {% if pyview.subject.finish_reason %}
                        <div class="query-message query-message-system">
                            <div class="query-message-role">Finish</div>
                            <div class="query-message-content">{{ pyview.subject.finish_reason }}</div>
                        </div>
                    {% endif %}
                    {% if pyview.is_open %}
                        {% if pyview.subject.reasoning %}
                            <div class="query-message query-message-assistant">
                                <div class="query-message-role">Reasoning</div>
                                <div class="query-message-content">{{ pyview.subject.reasoning }}</div>
                            </div>
                        {% endif %}
                        {% if pyview.subject.content %}
                            <div class="query-message query-message-assistant">
                                <div class="query-message-role">Content</div>
                                <div class="query-message-content" id="response_body_{{pyview.subject.pk}}">{{ pyview.subject.content }}</div>
                            </div>
                            <script>
                                el = document.getElementById('response_body_{{pyview.subject.pk}}')
                                if (el) { el.innerHTML = marked.parse(el.innerHTML); }
                            </script>
                        {% endif %}
                        {% for tc in pyview.formatted_tool_calls %}
                            <div class="query-message query-message-tool">
                                <div class="query-message-role">Tool: {{ tc.name }}</div>
                                <div class="query-message-content">{{ tc.args_str }}</div>
                            </div>
                        {% endfor %}
                    {% endif %}
                </div>

                <div class="query-card-foot">
                    <span class="query-tokens">{{ pyview.usage_label }}</span>
                    <span class="query-time" title="{{ pyview.subject.updated_at }}">{{ pyview.subject.updated_at }}</span>
                </div>
            </div>

        </div>
    '''

    def __init__(self, subject: Response, parent: AssistantMessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_open = False

    def toggle(self):
        self.is_open = not self.is_open
        if self.is_open:
            try:
                self.subject.refresh_from_db()
            except Exception:
                pass
        self.update()

    @property
    def provider_model_label(self) -> str:
        try:
            provider = (getattr(self.subject, "provider_name", "") or "").strip()
            model = (getattr(self.subject, "model_name", "") or "").strip()
            if provider and model:
                return f"{provider} · {model}"
            if provider or model:
                return provider or model
            aimodel = getattr(self.subject, "aimodel", None)
            if aimodel is not None and getattr(aimodel, "name", ""):
                return aimodel.name
        except Exception:
            pass
        return ""

    @property
    def summary_title(self) -> str:
        try:
            return self.provider_model_label or f"Response #{getattr(self.subject, 'pk', '?')}"
        except Exception:
            return ""

    @property
    def updated_str(self) -> str:
        try:
            updated_at = getattr(self.subject, "updated_at", None)
            return updated_at.strftime("%H:%M:%S") if updated_at is not None else ""
        except Exception:
            return ""

    @property
    def ttft_str(self) -> str:
        return _fmt_num(getattr(self.subject, "time_to_first_token", None))

    @property
    def reasoning_str(self) -> str:
        return _fmt_num(getattr(self.subject, "reasoning_time", None))

    @property
    def total_str(self) -> str:
        return _fmt_num(getattr(self.subject, "total_time", None))

    @property
    def message_time_str(self) -> str:
        """Generation time minus reasoning time (pure message time)."""
        try:
            gen = getattr(self.subject, "token_generation_time", None) or 0
            reasoning = getattr(self.subject, "reasoning_time", None) or 0
            if gen and reasoning:
                return _fmt_num(float(gen) - float(reasoning))
        except Exception:
            pass
        return ""

    @property
    def tps_str(self) -> str:
        """'gen (overall)' tokens per second, as shown on assistant messages before."""
        try:
            tokens = getattr(self.subject, "completion_tokens", None) or 0
            gen = getattr(self.subject, "token_generation_time", None) or 0
            total = getattr(self.subject, "total_time", None) or 0
            if tokens and gen and total:
                return f"{_fmt_num(tokens / gen)}({_fmt_num(tokens / total)})"
        except Exception:
            pass
        return ""

    @property
    def formatted_tool_calls(self) -> list[dict[str, str]]:
        """Tool calls of this response as display-ready dicts (never raises)."""
        import json

        try:
            calls = getattr(self.subject, "tool_calls", None) or []
            if isinstance(calls, dict):
                calls = [calls]
            if not isinstance(calls, (list, tuple)):
                return []
            formatted = []
            for tc in calls:
                if not isinstance(tc, dict):
                    text = str(tc or "").strip()
                    if text:
                        formatted.append({"name": text, "args_str": "", "id": ""})
                    continue
                args = tc.get("arguments", "")
                if isinstance(args, (dict, list)):
                    try:
                        args_str = json.dumps(args, indent=2, default=str)
                    except (TypeError, ValueError):
                        args_str = str(args)
                else:
                    args_str = str(args or "")
                name = str(tc.get("name", "") or "").strip()
                if name or args_str.strip():
                    formatted.append({
                        "name": name or "?",
                        "args_str": args_str,
                        "id": str(tc.get("id", "") or ""),
                    })
            return formatted
        except Exception:
            return []

    @property
    def usage_label(self) -> str:
        try:
            prompt = getattr(self.subject, "prompt_tokens", 0) or 0
            completion = getattr(self.subject, "completion_tokens", 0) or 0
            cached = getattr(self.subject, "cached_tokens", 0) or 0
            reasoning = getattr(self.subject, "reasoning_tokens", 0) or 0
            label = f"{prompt} in · {completion} out"
            extras = []
            if cached:
                extras.append(f"{cached} cached")
            if reasoning:
                extras.append(f"{reasoning} reasoning")
            if extras:
                label += f" ({', '.join(extras)})"
            return label
        except Exception:
            return ""
