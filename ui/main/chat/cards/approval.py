"""Approval card — shown when a session hits turn limits and needs approval."""
from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView


class ApprovalCard(ModelView):
    #DOM_ELEMENT_CLASS = 'approval-card'
    DOM_ELEMENT_EXTRAS = 'role="alertdialog" aria-labelledby="approvalHeading" aria-describedby="approvalDesc"'
    TEMPLATE_STR = '''
        <div class="approval-inner" style="{% if not pyview.subject.needs_approval() %}display:none{% endif %}">
            <div class="approval-header">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <span id="approvalHeading">Unattended turn limit reached</span>
            </div>
            <div class="approval-desc" id="approvalDesc">
                The agent has reached the maximum number of unattended turns.
                Approve to reset the counters and continue processing.
            </div>
            <div class="approval-cmd" id="approvalCmd"></div>
            <div class="approval-counter" id="approvalCounter" style="display:none1;font-size:0.75em;opacity:0.6;margin-top:4px;"></div>
            <div class="approval-btns">
                <button class="approval-btn once" onclick="pyview.approve('once')">
                    <span class="approval-btn-icon">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                    </span>
                    <span class="approval-btn-label">Allow once</span>
                    <kbd class="approval-kbd">&#x23CE;</kbd>
                </button>
                <button class="approval-btn session" onclick="pyview.approve('session')">
                    <span class="approval-btn-icon">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        </svg>
                    </span>
                    <span class="approval-btn-label">Allow session</span>
                </button>
                <button class="approval-btn deny" onclick="pyview.approve('deny')">
                    <span class="approval-btn-icon">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </span>
                    <span class="approval-btn-label">Deny</span>
                </button>
            </div>
        </div>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return 'approval-card' + ' visible' if self.subject.needs_approval() else ""
    
    def __init__(self, subject: Session, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        if getattr(self.parent, 'live_session', None):
            self.add_observable(self.parent.live_session)

    def approve(self, mode: str) -> None:
        """Handle approval button clicks.

        Resets turn counters and, for 'once' or 'session' modes,
        restarts processing from the last assistant message.
        """
        session = self.subject
        session.reset_turn_count()
        session.reset_unattended_turn_count()

        if mode == "deny":
            self.update()
            return

        last_message = session.get_messages().order_by("-pk").first()
        if last_message:
            session.get_task("process_turn").delay(message=last_message)

        self.update()
