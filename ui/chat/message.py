from __future__ import annotations
from server.models.conversation_message import ConversationMessage
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


class MessagePartView(ModelView):
    DOM_ELEMENT_CLASS = "MessagePartView message-part"

    TEMPLATE_STR = """
        {% if pyview.subject.content and pyview.subject.content.content_type == 'image' %}
            <img src="{{ pyview.subject.content.content }}" class="msg-image" alt="image">
        {% elif pyview.subject.content and pyview.subject.content.content %}
            <p class="msg-text">{{ pyview.subject.content.content }}</p>
        {% endif %}
    """

    CSS_STR = """
.message-part { display: block; }

.msg-text {
    margin: 0;
    padding: 0;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.55;
}
.msg-image {
    max-width: 100%;
    max-height: 300px;
    border-radius: var(--r-sm);
    border: 1px solid var(--border);
    margin-top: 4px;
    display: block;
}
/* highlight when referenced by a query part */
.message-part.source-highlighted {
    border-left: 3px solid var(--accent);
    padding-left: 6px;
}
    """


class MessageView(ModelView):
    """
    Renders a single ConversationMessage.
    Simple mode: content + collapsible tool-call summary.
    Developer mode: same, but tool calls link to full TaskCallView trees.
    """
    DOM_ELEMENT_CLASS = "MessageView conversation-log-item log-type-conversation"

    TEMPLATE_STR = """
        <div class="message-header">
            <span class="msg-role msg-role-{{ pyview.subject.role }}">{{ pyview.subject.role }}</span>
            <span class="message-time">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            <span class="message-actions">
                <i class="fa fa-thumb-tack pin-icon {{ 'pinned' if pyview.subject.pin_to_context else '' }}"
                   title="{{ 'Unpin' if pyview.subject.pin_to_context else 'Pin to context' }}"
                   onclick="pyview.toggle_pin()"></i>
                <i class="fa fa-eye-slash hide-icon {{ 'hide_from_context' if pyview.subject.hide_from_context else '' }}"
                   title="{{ 'Show in context' if pyview.subject.hide_from_context else 'Hide from context' }}"
                   onclick="pyview.toggle_hide()"></i>
            </span>
        </div>

        <div class="message-content">
            {{ pyview.part_views.render() }}
        </div>

        {% if pyview.subject.tool_calls.exists() %}
            <div class="msg-tool-summary">
                <button class="log-btn" onclick="pyview.toggle_details()">
                    <i class="fa fa-wrench"></i>
                    {{ pyview.subject.tool_calls.count() }} tool call{{ 's' if pyview.subject.tool_calls.count() != 1 else '' }}
                    {{ '▲' if not pyview.is_details_hidden else '▼' }}
                </button>
            </div>
        {% endif %}

        {% if not pyview.is_details_hidden %}
            <div class="msg-tool-detail">
                {% for tc in pyview.subject.tool_calls.all() %}
                    <div class="tool-call-ref">
                        <i class="fa fa-wrench fa-fw"></i>
                        <span class="tool-call-name">{{ tc.agent_task_definition.name }}</span>
                        <span class="badge badge--{{ tc.status_detail|lower|replace('_','-') }}">
                            {{ tc.status_detail }}
                        </span>
                    </div>
                {% endfor %}
                {% if pyview.subject.response %}
                    <div class="tool-call-ref text-muted small">
                        {{ pyview.subject.response.prompt_tokens }}&nbsp;↑&nbsp;/&nbsp;{{ pyview.subject.response.completion_tokens }}&nbsp;↓ tokens
                    </div>
                {% endif %}
            </div>
        {% endif %}
    """

    CSS_STR = """
        /* Role pill */
        .msg-role {
            font-size: 0.75em;
            font-weight: 600;
            padding: 1px 8px;
            border-radius: 8px;
            text-transform: capitalize;
            background: var(--badge-neutral-bg);
            color: var(--badge-neutral-fg);
        }
        .msg-role-user      { background: var(--badge-active-bg);   color: var(--badge-active-fg); }
        .msg-role-assistant { background: var(--badge-success-bg);  color: var(--badge-success-fg); }
        .msg-role-system    { background: var(--badge-warning-bg);  color: var(--badge-warning-fg); }

        /* Tool call expand row */
        .msg-tool-summary {
            padding: 3px 10px 4px;
            border-top: 1px solid var(--border-light);
        }
        .msg-tool-detail {
            padding: 4px 10px 6px;
            border-top: 1px solid var(--border-light);
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .tool-call-ref {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85em;
        }
        .tool-call-name { flex-grow: 1; }
    """

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    def __init__(self, subject: ConversationMessage, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_details_hidden = True
        self.part_views = QuerySetView(
            subject=subject.parts.all(),
            parent=self,
            item_class=MessagePartView,
        )

    def toggle_details(self):
        self.is_details_hidden = not self.is_details_hidden
        self.update()

    def toggle_pin(self):
        self.subject.pin_to_context = not self.subject.pin_to_context
        if self.subject.pin_to_context:
            self.subject.hide_from_context = False
        self.subject.save()
        self.update()

    def toggle_hide(self):
        self.subject.hide_from_context = not self.subject.hide_from_context
        if self.subject.hide_from_context:
            self.subject.pin_to_context = False
        self.subject.save()
        self.update()