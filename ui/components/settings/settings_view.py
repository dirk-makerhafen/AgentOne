
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class SettingsView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="settings-container">
        <h5>Instance Limits</h5>
        <div class="setting-item">
            <label for="limit-convo-input_{{ pyview.subject.id }}">Conversation History Limit:</label>
            <div class="editable-setting">
                <span class="editable-limit" id="limit-convo-text_{{ pyview.subject.id }}" onclick="pyview.show_limit_edit('convo')">{{ pyview.subject.effective_limit_max_conversation_messages }}</span>
                <i class="fa fa-pencil-square-o edit-limit-btn" onclick="pyview.show_limit_edit('convo')"></i>
                {% if pyview.subject.limit_max_conversation_messages %}
                <i class="fa fa-undo reset-limit-btn" title="Reset to default" onclick="pyview.reset_instance_limit('convo')"></i>
                {% endif %}
                <input type="number" id="limit-convo-input_{{ pyview.subject.id }}" value="{{ pyview.subject.limit_max_conversation_messages }}" placeholder="{{ pyview.subject.default_limit_max_conversation_messages }}" style="display:{% if pyview.is_editing_convo %}'inline-block'{% else %}'none'{% endif %}; width: 60px;" onkeydown="pyview.handle_limit_keydown(event, 'convo')" onblur="pyview.save_limit('convo')"/>
            </div>
        </div>
        <div class="setting-item">
            <label for="limit-mem-input_{{ pyview.subject.id }}">Memory Items per Track/Layer:</label>
            <div class="editable-setting">
                <span class="editable-limit" id="limit-mem-text_{{ pyview.subject.id }}" onclick="pyview.show_limit_edit('mem')">{{ pyview.subject.effective_limit_max_memory_items }}</span>
                <i class="fa fa-pencil-square-o edit-limit-btn" onclick="pyview.show_limit_edit('mem')"></i>
                {% if pyview.subject.limit_max_memory_items %}
                <i class="fa fa-undo reset-limit-btn" title="Reset to default" onclick="pyview.reset_instance_limit('mem')"></i>
                {% endif %}
                <input type="number" id="limit-mem-input_{{ pyview.subject.id }}" value="{{ pyview.subject.limit_max_memory_items }}" placeholder="{{ pyview.subject.default_limit_max_memory_items }}" style="display:{% if pyview.is_editing_mem %}'inline-block'{% else %}'none'{% endif %}; width: 60px;" onkeydown="pyview.handle_limit_keydown(event, 'mem')" onblur="pyview.save_limit('mem')"/>
            </div>
        </div>
        <div class="setting-item">
            <label for="limit-steps-input_{{ pyview.subject.id }}">Max Automatic Steps:</label>
            <div class="editable-setting">
                <span class="editable-limit" id="limit-steps-text_{{ pyview.subject.id }}" onclick="pyview.show_limit_edit('steps')">{{ pyview.subject.effective_limit_max_automated_steps }}</span>
                <i class="fa fa-pencil-square-o edit-limit-btn" onclick="pyview.show_limit_edit('steps')"></i>
                {% if pyview.subject.limit_max_automated_steps %}
                <i class="fa fa-undo reset-limit-btn" title="Reset to default" onclick="pyview.reset_instance_limit('steps')"></i>
                {% endif %}
                <input type="number" id="limit-steps-input_{{ pyview.subject.id }}" value="{{ pyview.subject.limit_max_automated_steps }}" placeholder="{{ pyview.subject.default_limit_max_automated_steps }}" style="display:{% if pyview.is_editing_steps %}'inline-block'{% else %}'none'{% endif %}; width: 60px;" onkeydown="pyview.handle_limit_keydown(event, 'steps')" onblur="pyview.save_limit('steps')"/>
                <span class="current-step-count">(Current: {{ pyview.subject.automated_step_count }})</span>
            </div>
        </div>
        <h5>Rate Limiting</h5>
        <div class="setting-item">
            <label for="limit-requests-input_{{ pyview.subject.id }}">Max Requests / Minute:</label>
            <div class="editable-setting">
                <span class="editable-limit" id="limit-requests-text_{{ pyview.subject.id }}" onclick="pyview.show_limit_edit('requests')">{% if pyview.subject.max_requests_per_minute %}{{ pyview.subject.max_requests_per_minute }}{% else %}None{% endif %}</span>
                <i class="fa fa-pencil-square-o edit-limit-btn" onclick="pyview.show_limit_edit('requests')"></i>
                {% if pyview.subject.max_requests_per_minute %}
                <i class="fa fa-undo reset-limit-btn" title="Reset to default" onclick="pyview.reset_instance_limit('requests')"></i>
                {% endif %}
                <input type="number" id="limit-requests-input_{{ pyview.subject.id }}" value="{{ pyview.subject.max_requests_per_minute }}" placeholder="None" style="display:{% if pyview.is_editing_requests %}'inline-block'{% else %}'none'{% endif %}; width: 60px;" onkeydown="pyview.handle_limit_keydown(event, 'requests')" onblur="pyview.save_limit('requests')"/>
            </div>
        </div>
        <div class="setting-item">
            <label for="limit-tokens-input_{{ pyview.subject.id }}">Max Tokens / Minute:</label>
            <div class="editable-setting">
                <span class="editable-limit" id="limit-tokens-text_{{ pyview.subject.id }}" onclick="pyview.show_limit_edit('tokens')">{% if pyview.subject.max_token_per_minute %}{{ pyview.subject.max_token_per_minute }}{% else %}None{% endif %}</span>
                <i class="fa fa-pencil-square-o edit-limit-btn" onclick="pyview.show_limit_edit('tokens')"></i>
                {% if pyview.subject.max_token_per_minute %}
                <i class="fa fa-undo reset-limit-btn" title="Reset to default" onclick="pyview.reset_instance_limit('tokens')"></i>
                {% endif %}
                <input type="number" id="limit-tokens-input_{{ pyview.subject.id }}" value="{{ pyview.subject.max_token_per_minute }}" placeholder="None" style="display:{% if pyview.is_editing_tokens %}'inline-block'{% else %}'none'{% endif %}; width: 60px;" onkeydown="pyview.handle_limit_keydown(event, 'tokens')" onblur="pyview.save_limit('tokens')"/>
            </div>
        </div>
        <h5>History Limiting Rules <i class="fa fa-info-circle" title="Override default tool history limits. Empty fields will revert to the tool's default value."></i></h5>
        { % for toolName, toolRules in py view.subject.history_limiting_rules.items() % }
        <div class="tool-history-rules-group">
            <h6>{{ toolName }}</h6>
            <div class="history-limits-grid">
                <div class="history-limits-header">Rule</div>
                <div class="history-limits-header"></div>
                <div class="history-limits-header">Success</div>
                <div class="history-limits-header">Failed</div>
                <div class="history-limits-header">Pending</div>
                <div class="history-limits-header">Total(max)</div>
                {% for rule in toolRules %}
                <div class="history-limit-rule-name" title="{{ rule.description }}">
                    {{ rule.display_name }}
                </div>
                <div class="history-limit-actions">          
                    <i class="fa fa-undo reset-limit-btn {% if not rule.db_id %}hidden{% endif %}" title="Reset to default" onclick="pyview.reset_history_limit('{{ rule.full_rule_name }}')"></i>   
                </div>
                <div><input type="number" class="history-limit-input {% if not rule.db_id %}is-default-limit{% endif %}" value="{{ rule.success }}" placeholder="-" data-rule-full-name="{{ rule.full_rule_name }}" data-limit-type="success" onchange="pyview.handle_history_limit_change(event)"></div>
                <div><input type="number" class="history-limit-input {% if not rule.db_id %}is-default-limit{% endif %}" value="{{ rule.failed }}" placeholder="-" data-rule-full-name="{{ rule.full_rule_name }}" data-limit-type="failed" onchange="pyview.handle_history_limit_change(event)"></div>
                <div><input type="number" class="history-limit-input {% if not rule.db_id %}is-default-limit{% endif %}" value="{{ rule.pending }}" placeholder="-" data-rule-full-name="{{ rule.full_rule_name }}" data-limit-type="pending" onchange="pyview.handle_history_limit_change(event)"></div>
                <div><input type="number" class="history-limit-input {% if not rule.db_id %}is-default-limit{% endif %}" value="{{ rule.max }}" placeholder="-" data-rule-full-name="{{ rule.full_rule_name }}" data-limit-type="max" onchange="pyview.handle_history_limit_change(event)"></div>
                {% endfor %}
            </div>
        </div>
        { % endfor % }
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_editing_convo = False
        self.is_editing_mem = False
        self.is_editing_steps = False
        self.is_editing_requests = False
        self.is_editing_tokens = False

    def show_limit_edit(self, limit_type):
        setattr(self, f'is_editing_{limit_type}', True)
        self.update()

    def reset_instance_limit(self, limit_type):
        # Reset to None to inherit default
        if limit_type == 'convo':
            self.subject.limit_max_conversation_messages = None
        elif limit_type == 'mem':
            self.subject.limit_max_memory_items = None
        elif limit_type == 'steps':
            self.subject.limit_max_automated_steps = None
        elif limit_type == 'requests':
            self.subject.max_requests_per_minute = None
        elif limit_type == 'tokens':
            self.subject.max_token_per_minute = None

        self.subject.save()
        self.update()
    def handle_limit_keydown(self, event, limit_type):
        if event.key == 'Enter':
            self.save_limit(limit_type)
        elif event.key == 'Escape':
            setattr(self, f'is_editing_{limit_type}', False)
            self.update()
            
    def save_limit(self, limit_type):
        input_id = f"limit-{limit_type}-input_{self.subject.id}"
        value = self.eval_javascript(script=f"return document.getElementById('{input_id}').value;")

        # Convert value to int or None
        try:
            value = int(value) if value else None
        except ValueError:
            value = None # Handle cases where input is not a valid number

        # Update the subject (AgentInstance) based on limit_type
        if limit_type == 'convo':
            self.subject.limit_max_conversation_messages = value
        elif limit_type == 'mem':
            self.subject.limit_max_memory_items = value
        elif limit_type == 'steps':
            self.subject.limit_max_automated_steps = value
        elif limit_type == 'requests':
            self.subject.max_requests_per_minute = value
        elif limit_type == 'tokens':
            self.subject.max_token_per_minute = value

        self.subject.save()
        setattr(self, f'is_editing_{limit_type}', False)
        self.update()

    def reset_history_limit(self, full_rule_name):
        # This will require more complex logic to interact with the HistoryLimit model
        # For now, it's a placeholder.
        print(f"Resetting history limit for rule: {full_rule_name}")
        # In a real scenario, you'd delete or modify the HistoryLimit object associated with this rule.
        # self.subject.history_limiting_rules.filter(...).delete()
        self.update()
    def handle_history_limit_change(self, event):
        # This will also require more complex logic to interact with the HistoryLimit model
        # For now, it's a placeholder.
        rule_full_name = self.eval_javascript(script='return event.target.dataset.ruleFullName;')
        limit_type = self.eval_javascript(script='return event.target.dataset.limitType;')
        value = self.eval_javascript(script='return event.target.value;')
        print(f"History limit change: Rule={rule_full_name}, Type={limit_type}, Value={value}")
        # In a real scenario, you'd find or create a HistoryLimit object and update its fields.
        self.update()
