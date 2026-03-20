from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView


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

from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView


class AgentTaskInstanceView(PyHtmlView):
    TEMPLATE_STR = """
    <b>Task Instance</b> <br>
    name = {{ pyview.subject.name }} <br>
    callbacks_instance = {{ pyview.subject.callbacks_instance }} <br>
    instance_chain = {{ pyview.subject.instance_chain }} <br>
    instance_group = {{ pyview.subject.instance_group }} <br>
    called {{ pyview.subject.agent_task_calls.count() }} times <br>
    """

class AgentTaskInstancesView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="agent-task-instances-container" style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin-top: 20px;">
        <h4>AgentTaskInstances</h4>
        {{ pyview.agent_task_instances_view.render() }}
   
    </div>
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        print("HEHRHER", subject)
        self.agent_task_instances_view = QuerySetView(subject=subject, parent=self, item_class=AgentTaskInstanceView)
