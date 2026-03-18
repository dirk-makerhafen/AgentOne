from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
import json

class AgentSettingsView(PyHtmlView):
    TEMPLATE_STR = """
    <tr>
        <td>workingdir</td>
        <td>{{ pyview.subject.workingdir }}</td>
    </tr>
    <tr>
        <td>version_number</td>
        <td>{{ pyview.subject.version_number }}</td>
    </tr>
    <tr>
        <td>execution_mode</td>
        <td>{{ pyview.subject.execution_mode }}</td>
    </tr>
    <tr>
        <td>max_history_messages</td>
        <td>{{ pyview.subject.max_history_messages }}</td>
    </tr>
    <tr>
        <td>max_retries</td>
        <td>{{ pyview.subject.max_retries }}</td>
    </tr>
    <tr>
        <td>max_task_steps</td>
        <td>{{ pyview.subject.max_task_steps }}</td>
    </tr>
    <tr>
        <td>unattended_steps</td>
        <td>{{ pyview.subject.unattended_steps }}</td>
    </tr>
    <tr>
        <td>use_in_agent_versions</td>
        <td>{{ pyview.subject.use_in_agent_versions.count() }}</td>
    </tr>
    <tr>
        <td>input_schema</td>
        <td>{{ pyview.subject.input_schema }}</td>
    </tr>
    <tr>
        <td>output_schema</td>
        <td>{{ pyview.subject.output_schema }}</td>
    </tr>
    <tr>
        <td>task_prompt</td>
        <td>{{ pyview.subject.task_prompt }}</td>
    </tr>
    <tr>
        <td>system_prompt</td>
        <td>{{ pyview.subject.system_prompt }}</td>
    </tr>

    """

    def _to_pretty_json(self, value):
        try:
            return json.dumps(value, indent=2)
        except:
            return str(value)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register the custom filter for jinja
