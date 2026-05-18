from __future__ import annotations
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
from ui.lib.queryset_view import QuerySetView
from ui.lib.model_view import ModelView


class QueryMessagePartView(ModelView):
    """Detail view for a single QueryMessagePart — developer use only."""
    DOM_ELEMENT_CLASS = "QueryMessagePartView"

    TEMPLATE_STR = """
        <div class="qmp-row">
            <span class="detail-label">Part #{{ pyview.subject.pk }}</span>
            <span class="detail-meta">~{{ pyview.subject.tokens }} tokens</span>
            <span class="detail-meta">index {{ pyview.subject.index }}</span>
            <span class="detail-meta">{{ pyview.subject.content_type }}</span>
        </div>
        {% if pyview.subject.message_part %}
            <div class="qmp-row">
                <span class="detail-label">template:</span>
                {{ pyview.subject.message_part.content_template }}
            </div>
        {% endif %}
        <button class="log-btn" onclick="pyview.toggle_compiled()">
            {{ '▲' if not pyview.is_compiled_hidden else '▼' }} compiled
        </button>
        <div class="{{ 'hidden' if pyview.is_compiled_hidden else '' }}">
            <pre class="log-pre">{{ pyview.subject.compile(fail_on_error=False) }}</pre>
        </div>
    """

    CSS_STR = """
.qmp-row { display: flex; gap: 8px; align-items: baseline; font-size: 0.82em; padding: 2px 0; }
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_compiled_hidden = True

    def toggle_compiled(self):
        self.is_compiled_hidden = not self.is_compiled_hidden
        self.update()


class QueryMessageView(ModelView):
    DOM_ELEMENT_CLASS = "QueryMessageView"

    TEMPLATE_STR = """
        <div class="qmsg-header">
            <span class="msg-role msg-role-{{ pyview.subject.role }}">{{ pyview.subject.role }}</span>
            <span class="token-count">~{{ pyview.subject.tokens }} tokens</span>
            <button class="log-btn" onclick="pyview.toggle_parts()">
                {{ '▲' if not pyview.is_parts_hidden else '▼' }} parts
            </button>
        </div>
        <div class="{{ 'hidden' if pyview.is_parts_hidden else '' }} qmsg-parts">
            {{ pyview.parts_view.render() }}
        </div>
    """


    def __init__(self, subject: QueryMessage, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_parts_hidden = True
        self.parts_view = QuerySetView(
            subject=subject.query_message_parts.all(),
            parent=self,
            item_class=QueryMessagePartView,
        )

    def toggle_parts(self):
        self.is_parts_hidden = not self.is_parts_hidden
        self.update()


class QueryView(ModelView):
    DOM_ELEMENT_CLASS = "QueryView conversation-log-item log-type-llm"

    TEMPLATE_STR = """
        <div class="message-header">
            <span class="message-time">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            <strong>LLM Query</strong>
            <span class="token-count">{{ pyview.subject.tokens }} tokens</span>
            <button class="log-btn" onclick="pyview.toggle_messages()">
                {{ '▲' if not pyview.is_messages_hidden else '▼' }} messages
            </button>
            <button class="log-btn" onclick="pyview.toggle_raw()">
                {{ '▲' if not pyview.is_raw_hidden else '▼' }} raw
            </button>
        </div>
        <div class="{{ 'hidden' if pyview.is_messages_hidden else '' }}">
            {{ pyview.messages_view.render() }}
        </div>
        <div class="message-content {{ 'hidden' if pyview.is_raw_hidden else '' }}">
            <pre class="log-pre">{{ pyview.subject.data }}</pre>
        </div>
    """

    CSS_STR = """
        .token-count {
            font-size: 0.78em;
            color: var(--text-faint);
            white-space: nowrap;
        }
        .log-pre {
            font-family: var(--font-mono);
            font-size: 0.78em;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 8px 10px;
            border-radius: var(--r-sm);
            max-height: 240px;
            overflow-y: auto;
            margin: 0;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .detail-label { font-weight: 600; color: var(--text-muted); font-size: 0.82em; }
        .detail-meta  { font-size: 0.78em; color: var(--text-faint); }
        .message-time { font-size: 0.78em; color: var(--text-faint); white-space: nowrap; }
    """

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    def __init__(self, subject: Query, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_messages_hidden = True
        self.is_raw_hidden = True
        self.messages_view = QuerySetView(
            subject=subject.query_messages.order_by("index", "pk"),
            parent=self,
            item_class=QueryMessageView,
        )

    def toggle_messages(self):
        self.is_messages_hidden = not self.is_messages_hidden
        self.update()

    def toggle_raw(self):
        self.is_raw_hidden = not self.is_raw_hidden
        self.update()