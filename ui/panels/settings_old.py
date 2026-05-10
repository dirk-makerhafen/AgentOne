from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


class SettingsPanelView(PyHtmlView):
    """
    Instance settings panel.

    Subject is AgentInstance. Several fields referenced here
    (limit_max_conversation_messages, limit_max_memory_items, etc.)
    are planned additions to AgentInstance — they render as None/empty
    until those model fields exist.

    The History Limiting Rules section is a stub pending HistoryLimit
    model implementation.
    """
    DOM_ELEMENT_CLASS = "SettingsPanelView"

    TEMPLATE_STR = """
        <div class="settings-container">

            <h5>Instance limits</h5>

            {{ pyview._limit_row('convo', 'Conversation history limit',
                pyview.subject.limit_max_conversation_messages,
                pyview.subject.default_limit_max_conversation_messages|default('—'))|safe }}

            {{ pyview._limit_row('mem', 'Memory items per track/layer',
                pyview.subject.limit_max_memory_items,
                pyview.subject.default_limit_max_memory_items|default('—')) |safe}}

            {{ pyview._limit_row('steps', 'Max automatic steps',
                pyview.subject.limit_max_automated_steps,
                pyview.subject.default_limit_max_automated_steps|default('—')) |safe}}

            <h5>Rate limiting</h5>

            {{ pyview._limit_row('requests', 'Max requests / minute',
                pyview.subject.max_requests_per_minute, 'None') |safe}}

            {{ pyview._limit_row('tokens', 'Max tokens / minute',
                pyview.subject.max_token_per_minute, 'None') |safe}}

            <h5>History limiting rules
                <i class="fa fa-info-circle"
                   title="Override default tool history limits."></i>
            </h5>
            <p class="text-muted small">History limiting rules coming soon.</p>

        </div>
    """
    CSS_STR = '''
/* --- Sidebar Settings Tab --- */
.sidebar-settings-container {
    padding: 10px;
    font-size: 0.9em;
}

.setting-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e9ecef;
}

.setting-item label {
    font-weight: bold;
    color: #495057;
    margin-right: 10px;
}

.editable-setting {
    display: flex;
    align-items: center;
    gap: 5px;
}

.editable-setting .editable-limit {
    font-weight: 600;
    color: #0056b3;
    cursor: pointer;
}

.editable-setting i {
    cursor: pointer;
    color: #6c757d;
}

.editable-setting .current-step-count {
    font-style: italic;
    color: #6c757d;
    margin-left: 5px;
}

.history-limit-actions {
    padding-right: 5px;
}
.history-limit-actions:hover{
    color: #dc3545;
}
/* --- History Limiting Rules Grid --- */
.history-limits-grid {
    display: grid;
    grid-template-columns: auto min-content 10fr 10fr 10fr 10fr;
    gap: 4px 2px;
    align-items: center;
    font-size: 0.9em;
}

.history-limits-header {
    font-weight: bold;
    font-size: 0.8em;
    color: #bbb;
    text-align: center;
}

.history-limit-rule-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: monospace;
    font-size: 0.9em;
    cursor: help;
}

.history-limit-input {
    width: 100%;
    color: black;
    border: 1px solid #555;
    border-radius: 3px;
    text-align: center;
    padding: 1px;
    -moz-appearance: textfield; /* Firefox */
}

.history-limit-input::-webkit-outer-spin-button,
.history-limit-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
}

/* Style for default history limit fields */
.history-limits-grid .is-default-limit {
    background-color: #f0f0f0; /* Light gray background */
    border: 1px solid #ccc;   /* Dashed border */
}

/* --- History Limiting Rules Grouping --- */
.tool-history-rules-group {
    margin-bottom: 20px;
    border: 1px solid #e9ecef;
    border-radius: 4px;
    padding: 10px;
    background-color: #fff;
}

.tool-history-rules-group h6 {
    margin-top: 0;
    margin-bottom: 10px;
    color: #343a40;
    font-size: 1em;
    padding-bottom: 5px;
    border-bottom: 1px solid #f0f0f0;
}

/* --- Flexbox Layout for Scrolling --- */
.sidebar-settings-container {
    height: 100%; /* Fill the parent flex container */
    overflow-y: auto; /* Enable scrolling on the container itself */
    padding-bottom: 20px; /* Add some padding at the bottom */
}
'''

    # Reusable limit-row macro — called from template via pyview._limit_row(...)
    def _limit_row(self, key, label, value, placeholder):
        is_editing = getattr(self, f'_editing_{key}', False)
        input_id = f"limit-{key}-input_{self.subject.id}"
        display = value if value is not None else placeholder
        reset_btn = (
            f'<i class="fa fa-undo reset-limit-btn" title="Reset" '
            f'onclick="pyview.reset_limit(\'{key}\')"></i>'
            if value is not None else ''
        )
        style = "inline-block" if is_editing else "none"
        return f"""
            <div class="setting-item">
                <label>{label}:</label>
                <div class="editable-setting">
                    <span class="editable-limit" onclick="pyview.edit_limit('{key}')">{display}</span>
                    <i class="fa fa-pencil-square-o edit-limit-btn" onclick="pyview.edit_limit('{key}')"></i>
                    {reset_btn}
                    <input type="number" id="{input_id}"
                           value="{value or ''}" placeholder="{placeholder}"
                           style="display:{style}; width:60px;"
                           onkeydown="pyview.handle_keydown(event, '{key}')"
                           onblur="pyview.save_limit('{key}')"/>
                </div>
            </div>
        """

    # Limit fields — map key → AgentInstance attribute name
    _LIMIT_FIELDS = {
        'convo':    'limit_max_conversation_messages',
        'mem':      'limit_max_memory_items',
        'steps':    'limit_max_automated_steps',
        'requests': 'max_requests_per_minute',
        'tokens':   'max_token_per_minute',
    }

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        # Editing state per limit key
        for key in self._LIMIT_FIELDS:
            setattr(self, f'_editing_{key}', False)

    def edit_limit(self, key: str):
        setattr(self, f'_editing_{key}', True)
        self.update()

    def handle_keydown(self, event, key: str):
        if event.key == 'Enter':
            self.save_limit(key)
        elif event.key == 'Escape':
            setattr(self, f'_editing_{key}', False)
            self.update()

    def save_limit(self, key: str):
        field = self._LIMIT_FIELDS.get(key)
        if not field:
            return
        input_id = f"limit-{key}-input_{self.subject.id}"
        raw = self.eval_javascript(
            script=f"return document.getElementById('{input_id}').value;"
        )
        try:
            value = int(raw) if raw else None
        except ValueError:
            value = None
        setattr(self.subject, field, value)
        self.subject.save()
        setattr(self, f'_editing_{key}', False)
        self.update()

    def reset_limit(self, key: str):
        field = self._LIMIT_FIELDS.get(key)
        if not field:
            return
        setattr(self.subject, field, None)
        self.subject.save()
        self.update()