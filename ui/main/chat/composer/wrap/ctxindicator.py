from __future__ import annotations
from typing import TYPE_CHECKING, Any
from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter


_RING_CIRCUMFERENCE = 2 * 3.141592653589793 * 9.75


def _fmt_tokens(n: int) -> str:
    """Compact token count matching the existing tooltip style (23.6M, 544.0k)."""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 10_000_000:
        return f"{n / 1_000_000:.0f}M"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}k"
    return str(n)


class CtxIndicatorWrap(PyHtmlView):
    DOM_ELEMENT_CLASS = 'ctx-indicator-wrap'
    TEMPLATE_STR = '''
        <button class="ctx-indicator" id="ctxIndicator" type="button" aria-label="Context window usage" aria-describedby="ctxTooltip">
            <span class="ctx-ring">
                <svg class="ctx-ring-svg" viewBox="0 0 24 24" aria-hidden="true"><circle class="ctx-ring-track" cx="12" cy="12" r="9.75"></circle><circle class="ctx-ring-value" id="ctxRingValue" cx="12" cy="12" r="9.75" stroke-dasharray="61.26" stroke-dashoffset="{{ pyview.ring_offset }}"></circle></svg>
                <span class="ctx-ring-center" id="ctxPercent">{{ pyview.percent_label }}</span>
            </span>
        </button>
        <div class="ctx-tooltip ctx-tooltip-active1" id="ctxTooltip" role="tooltip" aria-hidden="false">
            <div class="ctx-tooltip-title">Context window</div>
            <div class="ctx-tooltip-line" id="ctxTooltipUsage">{{ pyview.usage_line }}</div>
            <div class="ctx-tooltip-line" id="ctxTooltipTokens">
                {% for line in pyview.tokens_line %}
                    {{line}}<br>
                {% endfor %}
            </div>
            <div class="ctx-tooltip-line" id="ctxTooltipThreshold" style="display: none;"></div>
            <div class="ctx-tooltip-line" id="ctxTooltipCost" style="display:none"></div>
            <div class="ctx-tooltip-compress" id="ctxTooltipCompress" style="display:none">
                <button class="ctx-compress-btn" id="ctxCompressBtn" type="button" style="display: none;"></button>
            </div>
        </div>
    '''
    def __init__(self, subject:Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
        # Redis observable path: session-scoped Query key.  The old
        # ModelObserver watch used an empty filter (all sessions) with an
        # in-callback session check; subscribing to our own session's key
        # delivers exactly the events we act on.
        try:
            from ui.lib.model_view import orm_subscribe

            session_id = getattr(getattr(subject, "model", None), "pk", None)
            if session_id is not None:
                orm_subscribe(
                    self, f"Query.session:{session_id}", self._on_orm_event
                )
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _usage(self) -> dict[str, Any]:
        return self.subject.context_usage()
        
    @property
    def percent_label(self) -> str:
        usage = self._usage()
        return f"{usage.get('used_context_percent', 0.0):.0f}%"

    @property
    def ring_offset(self) -> str:
        usage = self._usage()
        if usage.get("used_context_percent", 0.0) == 0:
            return f"{_RING_CIRCUMFERENCE:.2f}"
        frac = max(0.0, min(1.0, usage.get("used_context_percent", 0.0) / 100.0))
        return f"{_RING_CIRCUMFERENCE * (1.0 - frac):.2f}"

    @property
    def usage_line(self) -> str:
        usage = self._usage()
        line = f"{_fmt_tokens(usage.get('used_context_tokens', 0))}"
        window = usage.get("max_context_tokens", 0)
        if window:
            line += f" of {_fmt_tokens(window)} used"
        return line

    @property
    def tokens_line(self) -> list[str]:
        usage = self._usage()
        return [
            f"Send: {_fmt_tokens(usage.get('tokens_send', 0))} · Received: {_fmt_tokens(usage.get('tokens_received', 0))}",
            f"Cache Hit/Miss: {_fmt_tokens(usage.get('tokens_cached', 0))} / {_fmt_tokens(usage.get('tokens_send', 0)-usage.get('tokens_cached', 0))} · {usage.get('cache_hit_rate',0):.0f}%",
            f"Reasoning: {_fmt_tokens(usage.get('tokens_reasoning', 0))} · {usage.get('tokens_reasoning_percent',0):.0f}%",
        ]

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:
        """Redis observable callback: token counts changed, refresh the ring."""
        if model == "Query" and action == "update":
            try:
                self.update()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
