from __future__ import annotations
from ui.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView
from ui.components.tabs.agent.agent_settings_view import AgentSettingsView
from ui.components.tabs.agent.agent_task_definitions_view import  AgentTaskDefinitionView, AgentTaskDefinitionsView

class AgentVersionView(PyHtmlView):
    DOM_ELEMENT_CLASS = "AgentVersionView"
    DOM_ELEMENT = "table"
    TEMPLATE_STR = """
        <thead>
            <tr>
                <th>Parameter</th>
                <th class="permission-checkbox-cell">Value</th>
            </tr>
        </thead>
        <tbody>
            <tr>
              <td>version_number</td>
              <td>{{ pyview.subject.version_number }}</td>
            </tr>
            <tr>
              <td>Parent Version </td>
              <td>{{ pyview.subject.parent.version_number }}</td>
            </tr>
            <tr>
              <td>source</td>
              <td>{{ pyview.subject.source }}</td>
            </tr>
            <tr>
              <td>subagents</td>
              <td>{{ pyview.subject.sub_agent_versions.all() }}</td>
            </tr>
            <tr>
              <td><b>Settings</b></td>
              <td></td>
            </tr>

            {{ pyview.agent_settings_view.render()}}
            
            <tr>
              <td><b>Task Definitions</b></td>
              <td></td>
            </tr>
            {{ pyview.task_definitions_view.render()}}

            <tr>
              <td><b>Tools</b></td>
              <td></td>
            </tr>
            {% for tool in pyview.subject.tools.all() %}
              <tr>
                <td>{{ tool.name }}</td>
                <td> {{tool}} </td>
              </tr>
            {% endfor %}
            
            <tr>
              <td><b>Variants</b></td>
              <td>{{ pyview.subject.variants}}</td>
            </tr>
            
        </tbody>
   

    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.agent_settings_view = AgentSettingsView(subject.profile, self)
        self.task_definitions_view = AgentTaskDefinitionsView(subject=subject.task_definitions, parent=self, item_class=AgentTaskDefinitionView)


class AgentVersionsView(PyHtmlView):
    DOM_ELEMENT_CLASS = "AgentVersionsView"
    TEMPLATE_STR = """
    last
  {{pyview.last_agent_version_view.render()}}
          
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.av = subject
        #self.agent_versions_view = QuerySetView(subject=subject, parent=self, item_class=AgentVersionView,dom_element_class="grid-body")
        self.s=subject.last()
        self.last_agent_version_view = AgentVersionView(subject=self.s, parent=self)

    def open_version_tab(self, version_id):
        # This will need to call back to the main app to open the version tab
        print(f"Opening version tab for version {version_id}")
        # For now, just print. In a real scenario, this would trigger a backend call to open a new tab
        # self.parent.open_version_tab(version_id)




from __future__ import annotations
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.agents.agent_instance import AgentInstance
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView
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
