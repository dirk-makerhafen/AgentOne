from __future__ import annotations
from ui.pyHtmlGui.pyhtmlgui.pyhtmlguiInstance import PyHtmlGuiInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
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
            {{ pyview.agent_task_definitions_view.render()}}

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
        self.agent_task_definitions_view = AgentTaskDefinitionsView(subject=subject.task_definitions, parent=self, item_class=AgentTaskDefinitionView)


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



