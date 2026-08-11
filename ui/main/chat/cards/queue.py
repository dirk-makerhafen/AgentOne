from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.enums.task_enums import TaskCallStatusDetail
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from runtime.session.session import Session


class QueueCard(PyHtmlView):
    DOM_ELEMENT_CLASS = 'queue-card'
    DOM_ELEMENT_EXTRAS = 'role="region" aria-label="Queued messages" aria-live="polite"'
    TEMPLATE_STR = '''
        <div id="queueChips" class="queue-card-inner">
            <div class="queue-card-header">
                <span title="Sends automatically after the current response completes">{{ pyview.queue_count }} queued</span>
                <span class="queue-card-header-actions">
                    <button class="queue-card-btn" onclick="pyview.combineAll()" title="Combine all into one message">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M12 2L2 7l10 5 10-5-10-5z"></path><path d="M2 17l10 5 10-5"></path><path d="M2 12l10 5 10-5"></path></svg>
                        Combine
                    </button>
                    <button class="queue-card-icon-btn" onclick="pyview.clearAll()" title="Clear all queued messages" aria-label="Clear all queued messages">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                    <button class="queue-card-icon-btn" onclick="pyview.hideCard()" title="Hide queue (click the queue pill to show again)" aria-label="Hide queue panel">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </button>
                </span>
            </div>
            {% for call in pyview.queued_calls %}
            <div class="queue-card-row" role="listitem" draggable="true">
                <span class="queue-card-drag" aria-hidden="true">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
                </span>
                <span class="queue-card-text" contenteditable="true" role="textbox" aria-label="Queued message — edit in place" draggable="false">{{  call.carguments_json }}</span>
                <span class="queue-card-badges">
                    <span title="Model: {{ pyview.call_model_name(call) }}">{{ pyview.call_model_name(call) }}</span>
                </span>
                <button class="queue-card-icon-btn" onclick="pyview.cancelCall({{ call.pk }})" aria-label="Cancel queued message" draggable="false" title="Remove from queue">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            {% endfor %}
        </div>
    '''

    def __init__(self, subject: Session, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        if getattr(self.parent, 'live_session', None):
            self.add_observable(self.parent.live_session)

    @property
    def queued_calls(self):
        from server.models.tasks.agent_task_call import AgentTaskCall
        return AgentTaskCall.objects.filter(
            session=self.subject.model,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        ).order_by("created_at")

    @property
    def queue_count(self):
        return self.queued_calls.count()

    @property
    def show_pill(self):
        return self.queue_count > 0

    @property
    def DOM_ELEMENT_CLASS(self):
        return 'queue-card'


    def call_model_name(self, call):
        if self.subject and self.subject.aimodel:
            return self.subject.aimodel.name
        return ""

    def cancelCall(self, call_pk):
        from server.models.tasks.agent_task_call import AgentTaskCall
        AgentTaskCall.objects.filter(pk=call_pk).delete()
        self.update()

    def clearAll(self):
        self.queued_calls.delete()
        self.update()

    def combineAll(self):
        from server.models.tasks.agent_task_call import AgentTaskCall
        calls = list(self.queued_calls)
        if not calls:
            return
        combined_parts = []
        for call in calls:
            args = call.carguments_json or {}
            parts = args.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if part not in combined_parts:
                        combined_parts.append(part)
        AgentTaskCall.objects.filter(pk__in=[c.pk for c in calls]).delete()
        if combined_parts and self.subject:
            self.subject.add_user_message(combined_parts, force=True)
        self.update()

    def _on_subject_updated(self, source, **kwargs):
        super()._on_subject_updated(source, **kwargs)
        count = self.queue_count
        self.eval_javascript("""
            var pill = document.querySelector('.queue-pill-outer');
            if (pill) {
                if (""" + str(count) + """ > 0) {
                    pill.classList.add('show');
                    var cnt = pill.querySelector('.queue-pill-count');
                    if (cnt) cnt.textContent = '""" + str(count) + """ queued';
                } else {
                    pill.classList.remove('show');
                }
            }
        """, skip_results=True)

    def hideCard(self):
        self.eval_javascript("""
            var card = document.querySelector('.queue-card');
            if (card) card.classList.remove('visible');
            var outer = document.querySelector('.queue-pill-outer');
            if (outer) outer.classList.add('show');
        """, skip_results=True)
