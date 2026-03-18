from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView


class AgentTaskDefinitionView(PyHtmlView):
    TEMPLATE_STR = """
    <div style='display:grid; grid-template-columns: repeat(13, auto);'>
        <div class="grid-cell">{{ pyview.subject.name }}</div>
        <div class="grid-cell">{{ pyview.subject.task_type }}</div>
        <div class="grid-cell">{{ pyview.subject.description }}</div>
        <div class="grid-cell">{{ pyview.subject.function_schema }}</div>
        <div class="grid-cell">{{ pyview.subject.requires_approval }}</div>
        <div class="grid-cell">{{ pyview.subject.max_retries }}</div>
        <div class="grid-cell">{{ pyview.subject.retry_delay }}</div>
        <div class="grid-cell">{{ pyview.subject.max_concurrency }}</div>
        <div class="grid-cell">{ { pyview.subject.max_autonomous_steps } }</div>
        <div class="grid-cell">{{ pyview.subject.trigger }}</div>
        <div class="grid-cell">{{ pyview.subject.agent_task_instances.count() }}</div>
        <div class="grid-cell">{{ pyview.subject.agent_versions.count() }}</div>
    </div>
    """

class AgentTaskDefinitionsView(QuerySetView):
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            <tr>
                <td>
                    {{item.subject.name}}
                </td>
                <td>
                    {{ item.render()}}
                </td> 
            </tr>
        {% endfor %}
    '''
    def __init__(self, subject, parent, **kwargs):
        self.s = subject
        super().__init__(subject, parent, **kwargs)