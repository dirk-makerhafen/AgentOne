from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.main.chat.banner.health import HealthBanner
from ui.main.chat.banner.reconnect import ReconnectBanner
from ui.main.chat.banner.update import UpdateBanner
from ui.main.chat.composer.box import ComposerBox
from ui.main.chat.cards.approval import ApprovalCard
from ui.main.chat.cards.clarify import ClarifyCard
from ui.main.chat.cards.guardrail_approval import GuardrailApprovalCard
from ui.main.chat.cards.question import QuestionCard
from ui.main.chat.cards.queue import QueueCard
from ui.main.chat.cards.rate_limit import RateLimitCard
from ui.main.chat.messages.messages import Messages
from ui.main.chat.toc import ChatTocView
from ui.main.chat.panel.terminal import TerminalPanel
from ui.main.rightpanel.session.rightpanel_session import RightPanelSession

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class Chat(ModelView):
    RIGHTPANEL_VIEW = RightPanelSession
    DOM_ELEMENT_CLASS = 'main-view'
    #  {{ pyview.chat_toc.render() }} we add this later.
    TEMPLATE_STR = '''
       

        {{ pyview.messages.render() }}
        
        {{ pyview.update_banner.render() }}
        
        {{ pyview.reconnect_banner.render() }}

        {{ pyview.health_banner.render() }}

        <div class="composer-wrap" id="composerWrap">
            
            <div class="composer-flyout">
                {{ pyview.queue_card.render() }}

                {{ pyview.approval_card.render() }}

                {{ pyview.guardrail_card.render() }}

                {{ pyview.question_card.render() }}

                {{ pyview.rate_limit_card.render() }}
                
                {{ pyview.clarify_card.render() }}

                {{ pyview.terminal_panel.render() }}

                <div id="handoffHintContainer" class="handoff-hint-container" style="display:none1;"></div>

            </div>

            <div class="queue-pill-outer {% if pyview.queue_card.show_pill %}show{% endif %}">
                <button id="queuePill" class="queue-pill" onclick="document.querySelector('.queue-card').classList.add('visible');this.closest('.queue-pill-outer').classList.remove('show')" aria-label="Show queued messages" type="button" title="Show queued messages">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="3" y="5" width="6" height="6" rx="1"></rect><path d="m3 17 2 2 4-4"></path><path d="M13 6h8"></path><path d="M13 12h8"></path><path d="M13 18h8"></path></svg>
                    <span class="queue-pill-count">{{ pyview.queue_card.queue_count }} queued</span>
                    <span class="queue-pill-chevron">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="18 15 12 9 6 15"></polyline></svg>
                    </span>
                </button>
            </div>

            {{ pyview.composer_box.render() }}

        </div>
       
    '''
    def __init__(self, subject: SessionModel, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(subject)
        self.messages = Messages(self.session, self)

        self.chat_toc = ChatTocView(self.session, self, messages_view=self.messages)

        self.update_banner = UpdateBanner(self.session, self)
        self.reconnect_banner = ReconnectBanner(self.session, self)
        self.health_banner = HealthBanner(self.session, self)

        self.queue_card = QueueCard(self.session, self)
        self.approval_card = ApprovalCard(self.session, self)
        self.guardrail_card = GuardrailApprovalCard(self.session, self)
        self.question_card = QuestionCard(self.session, self)
        self.rate_limit_card = RateLimitCard(self.session, self)
        self.clarify_card = ClarifyCard(self.session, self)
        self.terminal_panel = TerminalPanel(self.session, self)

        self.composer_box = ComposerBox(self.session, self)

