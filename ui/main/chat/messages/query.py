from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.messages.message import MessageView
from server.models.queries.query import Query


class QueryView(ModelView):
    DOM_ELEMENT_CLASS = "msg-row query-row"
    TEMPLATE_STR = '''
        <div class="query-card {% if pyview.subject.status == "ACTIVE" %}query-active{% endif %} {% if pyview.is_open %}open{% endif %}">
            <div class="query-card-header" onclick="pyview.toggle()">
                <span class="query-card-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                </span>
                <span class="query-card-agent">Query: {{ pyview.subject.session_version.agent.name }}</span>
                <span class="query-card-summary"><span class="query-tokens">{{ pyview.subject.tokens or 0 }} tokens</span></span>
                <span class="query-card-status {{ pyview.subject.status|lower }}">{{ pyview.subject.status }}</span>
                <span class="query-card-toggle">
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

    def toggle(self):
        self.is_open = not self.is_open
        if self.is_open:
            aimodel = self.subject.session_version.get_runtime().aimodel
            self.requires_reasoning_echo = aimodel and aimodel.requires_reasoning_echo
            self.messages = list(self.subject.related_query_messages.order_by("pk").all())
        self.update()

