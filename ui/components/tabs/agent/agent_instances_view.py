from __future__ import annotations
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from server.models.agents.agent_instance import AgentInstance
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
from ui.components.tabs.agent.agent_task_instances_view import AgentTaskInstancesView

class AgentInstanceView(PyHtmlView):
    DOM_ELEMENT_EXTRAS = "style='border:1px solid red'"
    TEMPLATE_STR = """
        name: {{ pyview.subject.name }}  workingdir = {{ pyview.subject.workingdir }} <br>
        latest_version = {{ pyview.subject.latest_agent_instance_version }}, current_variant= {{ pyview.subject.current_agent_variant }} <br>
        task instances = { { pyv iew.agent_task_instances_view.render() } }
        <button onclick="pyview.parent.parent.open_instance_tab({{pyview.subject.pk}})"></button>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        print("hfoobarhehe1r1", type(subject), subject)
        #print("here23",  subject.related_agent_task_instances)
        #print("hfoobarheher", subject.agent_task_instances.all())
        #self.agent_task_instances_view = AgentTaskInstancesView(subject=subject.related_agent_task_instances, parent=self)

class AgentInstancesView(PyHtmlView):
    TEMPLATE_STR = """
        <h4>Instances</h4>
        {{ pyview.agent_instances_view.render() }}
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_instances_view = QuerySetView(subject=subject, parent=self, item_class=AgentInstanceView)

    def open_instance_tab(self, instance_id):
        self.parent.open_instance_tab(instance_id)

    def delete_instance(self, instance_id):
        print(f"Deleting instance {instance_id}")
        AgentInstance.objects.filter(id=instance_id).delete()
        self.subject.refresh_from_db() # Refresh the agent to update its instances
        self.update()
