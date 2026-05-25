from __future__ import annotations
from typing import TYPE_CHECKING, Any
from runtime.session.session import Session
from server.models.enums.task_enums import TaskSchedulerStrategy
from server.models.providers.ai_model import AiModel
from server.models.settings import (
    ResponseTemperature,
    AgentToolCallSyntax,
    ReasoningEffort,
    SubagentResultDelivery,
)
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


CHOICE_FIELDS = {
    "precision": ResponseTemperature,
    "reasoning_effort": ReasoningEffort,
    "scheduler_strategy": TaskSchedulerStrategy,
    "tool_call_syntax": AgentToolCallSyntax,
    "subagentResultDelivery": SubagentResultDelivery,
}

INT_FIELDS = {
    "max_retries",
    "max_turns",
    "max_unattended_turns",
    "max_history_messages",
    "priority",
}


class RightPanelSession(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Session</span>
            <div>
                {% if pyview.session.pinned_session_version %}
                    <span class="settings-version-badge">{{ pyview.session.pinned_session_version.version_number }}</span>
                    {% if not pyview.session.is_newest_version() %}
                        <span class="settings-version-badge">Show Latest</span>
                    {% endif %}
                {% else %}
                    <span class="settings-version-badge">Latest&nbsp;&nbsp;<small>(v{{ pyview.session.get_version_model().version_number }})</small></span>
                {% endif %}
            </div>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px">

            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Name</div>
                    <div class="detail-row-value">{{ pyview.session.name }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Agent</div>
                    <div class="detail-row-value">{{ pyview.session.agent.name }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Version</div>
                    <div class="detail-row-value">{{ pyview.session.version_number }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Description</div>
                    <div class="detail-row-value">{{ pyview.session.description }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Workspace</div>
                    <div class="detail-row-value">{{ pyview.workspace_name }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Active</div>
                    <div class="detail-row-value">
                        {% if pyview.session.is_active %}
                            <span style="color:var(--success)">yes</span>
                        {% else %}
                            <span style="color:var(--danger)">no</span>
                        {% endif %}
                    </div>
                </div>
            </div>

            <div class="settings-card" style="margin-bottom:8px">
                <div class="panel-header" style="margin-left:-8px">Settings</div>
                {% for name, label in pyview.settings_fields %}
                <div class="detail-row">
                    <div class="detail-row-label">{{ label }}</div>
                    <div class="detail-row">
                        {% if name in pyview.choice_fields %}
                            <select onchange="pyview.setSetting('{{name}}', this.value)" class="setting-input" style="max-width:80%;font-size:12px">
                                <option value="">&mdash; Agent default &mdash;</option>
                                {% for opt in pyview.setting_options(name) %}
                                <option value="{{ opt }}"{% if pyview.setting_display_value(name) == opt %} selected{% endif %}>{{ opt }}</option>
                                {% endfor %}
                            </select>
                        {% elif name in pyview.int_fields %}
                            <input type="number" value="{{ pyview.setting_display_value(name) }}" onchange="pyview.setSetting('{{name}}', this.value)" class="setting-input" style="width:80%;font-size:12px" min="0">
                        {% elif name == 'aimodel' %}
                            <input type="text" value="{{ pyview.setting_display_value(name) }}" onchange="pyview.setSetting('{{name}}', this.value)" class="setting-input" style="width:80%;font-size:12px">
                        {% else %}
                            {{ pyview.setting_value(name) }}
                        {% endif %}
                        {% if pyview.is_overridden(name) %}
                            <span class="setting-reset-btn" onclick="pyview.resetSetting('{{name}}')" title="Reset to agent default">⟳</span>
                        {% else %}
                            <span class="setting-default-dot" title="Agent default">⬤</span>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
                <div class="detail-row">
                    <div class="detail-row-label">Current Turn Count</div>
                    <div class="detail-row-value">{{ pyview.session.current_turn_count }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Current Unattended</div>
                    <div class="detail-row-value">{{ pyview.session.current_unattended_turn_count }}</div>
                </div>
            </div>

            <div class="settings-card" style="margin-bottom:8px">
                <div class="panel-header" style="margin-left:-8px">Prompts</div>
                <div class="detail-row">
                    <div class="detail-row-label">System Prompt</div>
                    <div class="detail-row-value" style="white-space:pre-line;max-height:120px;overflow:auto">{{ pyview.session.system_prompt }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Task Prompt</div>
                    <div class="detail-row-value" style="white-space:pre-line;max-height:120px;overflow:auto">{{ pyview.session.task_prompt }}</div>
                </div>
            </div>

        </div>
    '''

    SETTINGS_FIELDS = [
        ("aimodel", "AI Model"),
        ("precision", "Precision"),
        ("reasoning_effort", "Reasoning Effort"),
        ("scheduler_strategy", "Scheduler Strategy"),
        ("tool_call_syntax", "Tool Call Syntax"),
        ("subagentResultDelivery", "Subagent Result Delivery"),
        ("max_retries", "Max Retries"),
        ("max_turns", "Max Turns"),
        ("max_unattended_turns", "Max Unattended Turns"),
        ("max_history_messages", "Max History Messages"),
        ("priority", "Priority"),
    ]

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    # ------------------------------------------------------------------
    # Session access
    # ------------------------------------------------------------------

    @property
    def session(self) -> Session | None:
        return self.parent.current_session

    @property
    def settings_fields(self):
        return self.SETTINGS_FIELDS

    @property
    def workspace_name(self) -> str:
        s = self.session
        if s is None:
            return ""
        ws = s.workspace
        if ws:
            return str(ws)
        return "\u2014"

    # ------------------------------------------------------------------
    # Setting helpers
    # ------------------------------------------------------------------

    def _resolved_value(self, name: str) -> Any:
        """Return the raw resolved setting value (session override → agent default)."""
        s = self.session
        if s is None:
            return None
        return getattr(s, name, None)

    def setting_value(self, name: str) -> str:
        """Return the string representation of the resolved setting value."""
        val = self._resolved_value(name)
        if val is None:
            return "\u2014"
        if hasattr(val, "name"):
            return val.name
        return str(val)

    def setting_display_value(self, name: str) -> str:
        """Return the raw resolved value as a string, or empty for controls."""
        val = self._resolved_value(name)
        if val is None:
            return ""
        if hasattr(val, "name"):
            return val.name
        return str(val)

    def is_overridden(self, name: str) -> bool:
        s = self.session
        if s is None:
            return False
        ss = s.get_version_model().session_settings
        return bool(ss and getattr(ss, name) is not None)

    @property
    def choice_fields(self):
        return set(CHOICE_FIELDS.keys())

    @property
    def int_fields(self):
        return INT_FIELDS

    def setting_options(self, name: str) -> list[str]:
        """Return valid option strings for a choice-based setting."""
        choices_cls = CHOICE_FIELDS.get(name)
        if choices_cls:
            return [v.value for v in choices_cls]
        return []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def setSetting(self, name: str, raw_value: str) -> None:
        """Set a setting on the session (creates a new session version)."""
        s = self.session
        if s is None:
            return

        if raw_value == "":
            value = None
        elif name in INT_FIELDS:
            try:
                value = int(raw_value)
            except (ValueError, TypeError):
                return
        elif name == "aimodel":
            aimodel = AiModel.objects.filter(name=raw_value).first()
            if aimodel is None:
                return
            s._set_session_setting(name, aimodel)
            self.update()
            return
        else:
            value = raw_value

        s._set_session_setting(name, value)
        self.update()

    def resetSetting(self, name: str) -> None:
        """Reset a setting override, restoring the agent default."""
        s = self.session
        if s is None:
            return
        if not self.is_overridden(name):
            return
        s._set_session_setting(name, None)
        self.update()
