from __future__ import annotations
from typing import TYPE_CHECKING, Any
from runtime.session.session import Session
from server.models.enums.task_enums import TaskSchedulerStrategy
from server.models.enums.session_enums import SessionType
from server.models.sessions.session import SessionModel
from server.models.settings import (
    ResponseTemperature,
    AgentToolCallSyntax,
    ReasoningEffort,
    SubagentResultDelivery,
)
from ui.lib.model_view import ModelView
from ui.main.chat.composer.dropdown.model import ModelDropdown
from ui.main.chat.composer.dropdown.profile import ProfileDropdown
from ui.main.chat.composer.dropdown.workspace import WorkspaceDropdown

if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession
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
    "auto_compact_limit",
    "compact_size_limit",
    "priority",
}

BOOLEAN_FIELDS = {
    "inherit_system_prompt",
}


class RightPanelSessionSettings(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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
                    <div class="detail-row-value">
                        <input type="text" value="{{ pyview.session.name }}" onchange="pyview.setSessionName(this.value)" class="setting-input" style="width:100%;font-size:12px">
                    </div>
                </div>

                <div class="detail-row">
                    <div class="detail-row-label">Type</div>
                    <div class="detail-row-value">{{ pyview.session_type_label }}</div>
                </div>

                <div class="detail-row">
                    <div class="detail-row-label">Workspace</div>
                    <div class="detail-row-value" style="flex:1;min-width:0;display:flex;flex-direction:column;gap:2px">
                        <button type="button" class="rp-dropdown-trigger" onclick="pyview.toggle_workspace_dropdown()">
                            <span class="rp-dropdown-trigger-label">{{ pyview.workspace_name }}</span>
                            <span class="rp-dropdown-trigger-chev">▾</span>
                        </button>
                        <div class="rp-dropdown-anchor">
                            {{ pyview.workspace_dropdown.render() }}
                        </div>
                    </div>
                </div> 

                <div class="detail-row">
                    <div class="detail-row-label">Agent</div>
                    <div class="detail-row-value" style="flex:1;min-width:0;display:flex;flex-direction:column;gap:2px">
                        <button type="button" class="rp-dropdown-trigger" onclick="pyview.toggle_profile_dropdown()">
                            <span class="rp-dropdown-trigger-label">{{ pyview.session.agent.name }}</span>
                            <span class="rp-dropdown-trigger-chev">▾</span>
                        </button>
                        <div class="rp-dropdown-anchor">
                            {{ pyview.profile_dropdown.render() }}
                        </div>
                    </div>
                </div>

                <div class="detail-row">
                    <div class="detail-row-label">AI Model</div>
                    <div class="detail-row-value" style="flex:1;min-width:0;display:flex;flex-direction:column;gap:2px">
                        <div style="display:flex;align-items:center;gap:6px">
                            <button type="button" class="rp-dropdown-trigger" onclick="pyview.toggle_model_dropdown()">
                                <span class="rp-dropdown-trigger-label">{{ pyview.setting_display_value('aimodel') or '—' }}</span>
                                <span class="rp-dropdown-trigger-chev">▾</span>
                            </button>
                            {% if pyview.is_overridden('aimodel') %}
                                <span class="setting-reset-btn" onclick="pyview.resetSetting('aimodel')" title="Reset to agent default">⟳</span>
                            {% else %}
                                <span class="setting-default-dot" title="Agent default">⬤</span>
                            {% endif %}
                        </div>
                        <div class="rp-dropdown-anchor">
                            {{ pyview.model_dropdown.render() }}
                        </div>
                    </div>
                </div>

                <div class="detail-row">
                    <div class="detail-row-label">Description</div>
                    <div class="detail-row-value">{{ pyview.session.description }}</div>
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
                            {% elif name in pyview.bool_fields %}
                                <select onchange="pyview.setSetting('{{name}}', this.value)" class="setting-input" style="max-width:80%;font-size:12px">
                                    <option value="">&mdash; Agent default &mdash;</option>
                                    <option value="true"{% if pyview.setting_display_value(name) == 'true' %} selected{% endif %}>true</option>
                                    <option value="false"{% if pyview.setting_display_value(name) == 'false' %} selected{% endif %}>false</option>
                                </select>
                            {% elif name in pyview.int_fields %}
                                <input type="number" value="{{ pyview.setting_display_value(name) }}" onchange="pyview.setSetting('{{name}}', this.value)" class="setting-input" style="width:80%;font-size:12px" min="0">
                            {% elif name == 'access' %}
                                <pre class="setting-json" style="width:100%;font-size:11px;max-height:120px;overflow:auto;margin:0">{{ pyview.setting_display_value(name) }}</pre>
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
            </div>

        </div>
    '''

    SETTINGS_FIELDS = [
        ("precision", "Precision"),
        ("reasoning_effort", "Reasoning Effort"),
        ("scheduler_strategy", "Scheduler Strategy"),
        ("tool_call_syntax", "Tool Call Syntax"),
        ("subagentResultDelivery", "Subagent Result Delivery"),
        ("max_retries", "Max Retries"),
        ("max_turns", "Max Turns"),
        ("max_unattended_turns", "Max Unattended Turns"),
        ("max_history_messages", "Max History Messages"),
        ("auto_compact_limit", "Auto Compact Limit"),
        ("compact_size_limit", "Compact Size Limit"),
        ("priority", "Priority"),
        ("inherit_system_prompt", "Inherit System Prompt"),
        ("access", "Filesystem Access"),
    ]

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(session_model=subject)
        self.profile_dropdown = ProfileDropdown(self.session, self)
        self.workspace_dropdown = WorkspaceDropdown(self.session, self)
        self.model_dropdown = ModelDropdown(self.session, self)
        # Embedded in a settings card: open the panels downward, aligned under
        # their trigger rows (composer keeps the default upward opening).
        for dropdown in (
            self.profile_dropdown,
            self.workspace_dropdown,
            self.model_dropdown,
        ):
            dropdown.open_downward = True

    # ------------------------------------------------------------------
    # Dropdown toggles (from the trigger buttons)
    # ------------------------------------------------------------------
    def toggle_profile_dropdown(self) -> None:
        self.profile_dropdown.toggle()

    def toggle_workspace_dropdown(self) -> None:
        self.workspace_dropdown.toggle()

    def toggle_model_dropdown(self) -> None:
        self.model_dropdown.toggle()

    def close_dropdowns(self) -> None:
        self.profile_dropdown.close()
        self.workspace_dropdown.close()
        self.model_dropdown.close()


    # ------------------------------------------------------------------
    # Session access
    # ------------------------------------------------------------------
    @property
    def settings_fields(self):
        return self.SETTINGS_FIELDS

    @property
    def workspace_name(self) -> str:
        if self.session is None:
            return ""
        ws = self.session.workspace
        if ws:
            return str(ws)
        return "\u2014"

    @property
    def session_type_label(self) -> str:
        s = self.subject
        if self.session is None:
            return "\u2014"
        return dict(SessionType.choices).get(self.session.session_type, self.session.session_type)

    # ------------------------------------------------------------------
    # Setting helpers
    # ------------------------------------------------------------------

    def _resolved_value(self, name: str) -> Any:
        """Return the raw resolved setting value (session override → agent default)."""
        if self.session is None:
            return None
        return getattr(self.session, name, None)

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
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, (dict, list)):
            import json

            return json.dumps(val, indent=2)
        if hasattr(val, "name"):
            return val.name
        return str(val)

    def is_overridden(self, name: str) -> bool:
        if self.session is None:
            return False
        ss = self.session.get_version_model().session_settings
        return bool(ss and getattr(ss, name) is not None)

    @property
    def choice_fields(self):
        return set(CHOICE_FIELDS.keys())

    @property
    def int_fields(self):
        return INT_FIELDS

    @property
    def bool_fields(self):
        return BOOLEAN_FIELDS

    def setting_options(self, name: str) -> list[str]:
        """Return valid option strings for a choice-based setting."""
        choices_cls = CHOICE_FIELDS.get(name)
        if choices_cls:
            return [str(v.value) for v in choices_cls]
        return []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def setSetting(self, name: str, raw_value: str) -> None:
        """Set a setting on the session (creates a new session version)."""
        if self.session is None:
            return

        if raw_value == "":
            value = None
        elif name in INT_FIELDS:
            try:
                value = int(raw_value)
            except (ValueError, TypeError):
                return
        elif name in BOOLEAN_FIELDS:
            value = raw_value == "true"
        elif name == "access":
            import json

            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError:
                return
        else:
            value = raw_value

        self.session._set_session_setting(name, value)
        self.update()

    def resetSetting(self, name: str) -> None:
        """Reset a setting override, restoring the agent default."""
        if self.session is None:
            return
        if not self.is_overridden(name):
            return
        self.session._set_session_setting(name, None)
        self.update()

    def setSessionName(self, value: str) -> None:
        """Update the session name."""
        from server.models.sessions.session import SessionModel
        from runtime.events import publish_model_event
        if self.session is None:
            return
        name = value.strip()
        if not name:
            return
        SessionModel.objects.filter(pk=self.session.model.pk).update(name=name)
        session_model = SessionModel.objects.get(pk=self.session.model.pk)
        publish_model_event(session_model, "update")
        self.update()
