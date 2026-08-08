"""
Guardrail/call-level approval card.
Shown when an AgentTaskCall enters HALTED_APPROVAL state —
either via manifest requires_approval or dynamic guardrail scoring.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.tasks.agent_task_call import AgentTaskCall
from ui.app import UiApp
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from runtime.session.session import Session


class GuardrailApprovalCard(ModelView):
    #DOM_ELEMENT_CLASS = 'guardrail-approval-card'
    DOM_ELEMENT_EXTRAS = 'role="alertdialog" aria-labelledby="guardrailHeading" aria-describedby="guardrailDesc"'
    TEMPLATE_STR = '''
        <div class="guardrail-inner" style="{% if not pyview.pending_calls %}display:none{% endif %}">
            <div class="guardrail-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                <span id="guardrailHeading">Commands awaiting approval</span>
            </div>
            <div class="guardrail-desc" id="guardrailDesc">
                The following commands need your approval before they can execute:
            </div>
            {% for call in pyview.pending_calls %}
            <div class="guardrail-call">
                <div class="guardrail-call-name">{{ call.task_definition_version.task_definition.name }}</div>
                {% if call.carguments_json and call.guardrail_reason %}
                <div class="guardrail-call-reason">{{ call.guardrail_reason }}</div>
                {% endif %}
                {% if call.carguments_json %}
                <div class="guardrail-call-args">
                    {% for key, value in call.carguments_json.items() %}
                    {% if key != 'guardrail_reason' and key != '*' %}
                    <div><span class="guardrail-arg-key">{{ key }}:</span> <span class="guardrail-arg-val">{{ value }}</span></div>
                    {% endif %}
                    {% endfor %}
                </div>
                {% endif %}
                <div class="guardrail-call-feedback">
                    <input class="guardrail-feedback-input" id="guardrail_feedback_{{ call.pk }}" type="text" placeholder="Reason for denying (optional)" autocomplete="off" spellcheck="false">
                </div>
                <div class="guardrail-call-btns">
                    <button class="guardrail-btn approve" onclick="pyview.approve_call({{ call.pk }})">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                        Approve
                    </button>
                    <button class="guardrail-btn deny" onclick="pyview.deny_call({{ call.pk }}, document.getElementById('guardrail_feedback_{{ call.pk }}').value)">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        Deny
                    </button>
                </div>
            </div>
            {% endfor %}
        </div>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return 'guardrail-approval-card' + ' visible' if self.pending_calls else ""

    def __init__(self, subject: Session, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        if getattr(self.parent, 'live_session', None):
            self.add_observable(self.parent.live_session)
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
                callback_name="_on_guardrail_taskcall_updated",
                view=self,
                action="update",
            )

    @property
    def pending_calls(self) -> list[AgentTaskCall]:
        session = self.subject
        if session is None:
            return []
        return list(AgentTaskCall.objects.filter(
            session=session.model,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
        ).select_related('task_definition_version__task_definition')[:5])

    def _call_or_none(self, pk: int) -> AgentTaskCall | None:
        return AgentTaskCall.objects.filter(
            pk=pk, status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
        ).first()

    def approve_call(self, pk: int) -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        call = self._call_or_none(pk)
        if call:
            CallScheduler.approve_taskcall(call.pk)
        if not self.pending_calls:
            self.update()

    def deny_call(self, pk: int, feedback: str = "") -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        call = self._call_or_none(pk)
        if call:
            CallScheduler.deny_taskcall(call.pk, feedback=feedback)
        if not self.pending_calls:
            self.update()

    def _on_guardrail_taskcall_updated(self, pk: int, action: str, filter_context: dict) -> None:
        """Re-render when an AgentTaskCall for this session changes status."""
        self.update()
