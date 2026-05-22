from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


class RightPanelSession(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Session</span>
            <div>
             <!-- AI TODO: nicer small buttons/badged --->
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
                        <div class="detail-row-value">
                            {{ pyview.setting_value(name) }}
                            {% if pyview.is_overridden(name) %}
                                <span class="setting-reset-btn" onclick="pyview.resetSetting('{name}')" title="Reset to agent default" style="cursor:pointer">⟳</span>
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
        ("reasoning_effort", "Reasoning Effort"),
        ("scheduler_strategy", "Scheduler Strategy"),
        ("tool_call_syntax", "Tool Call Syntax"),
        ("max_retries", "Max Retries"),
        ("max_turns", "Max Turns"),
        ("max_unattended_turns", "Max Unattended Turns"),
        ("max_history_messages", "Max History Messages"),
        ("priority", "Priority"),
    ]

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

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

    def setting_value(self, name: str) -> str:
        s = self.session
        if s is None:
            return ""
        val = getattr(s, name, None)
        if val is None:
            return "\u2014"
        return str(val)

    def is_overridden(self, name: str) -> bool:
        s = self.session
        if s is None:
            return False
        ss = s.get_version_model().session_settings
        return bool(ss and getattr(ss, name) is not None)

    def resetSetting(self, name: str):
        s = self.session
        if s is None:
            return
        if not self.is_overridden(name):
            return
        s._set_session_setting(name, None)
        self.update()
