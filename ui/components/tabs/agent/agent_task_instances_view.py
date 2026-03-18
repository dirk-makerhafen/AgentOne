from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView


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
