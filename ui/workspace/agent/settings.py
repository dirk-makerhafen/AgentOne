from __future__ import annotations
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


class AgentSettingsView(ModelView):
    """
    Renders AgentProfile fields as table rows inside AgentVersionView.
    Subject is AgentProfile.
    Emits <tr> elements — must be used inside a <tbody>.
    """
    DOM_ELEMENT_CLASS = "AgentSettingsView"

    TEMPLATE_STR = """
        <tr>
            <td>Model</td>
            <td>{{ pyview.subject.aimodel.name if pyview.subject.aimodel else '—' }}</td>
        </tr>
        <tr>
            <td>Execution mode</td>
            <td>{{ pyview.subject.execution_mode }}</td>
        </tr>
        <tr>
            <td>Tool call syntax</td>
            <td>{{ pyview.subject.tool_call_syntax }}</td>
        </tr>
        <tr>
            <td>Max history messages</td>
            <td>{{ pyview.subject.max_history_messages }}</td>
        </tr>
        <tr>
            <td>Max retries</td>
            <td>{{ pyview.subject.max_retries }}</td>
        </tr>
        <tr>
            <td>Priority</td>
            <td>{{ pyview.subject.priority }}</td>
        </tr>
        <tr>
            <td>Max task steps</td>
            <td>{{ pyview.subject.max_task_steps }}</td>
        </tr>
        <tr>
            <td>Unattended steps</td>
            <td>{{ pyview.subject.unattended_steps }}</td>
        </tr>
        <tr>
            <td>Task prompt</td>
            <td>{{ pyview.subject.task_prompt }}</td>
        </tr>
        <tr>
            <td>System prompt</td>
            <td>{{ pyview.subject.system_prompt }}</td>
        </tr>
        <tr>
            <td>Used in versions</td>
            <td>{{ pyview.subject.use_in_agent_versions.count() }}</td>
        </tr>
        {% if pyview.subject.extra_settings %}
        <tr>
            <td>Extra settings</td>
            <td><pre>{{ pyview.subject.extra_settings }}</pre></td>
        </tr>
        {% endif %}
    """