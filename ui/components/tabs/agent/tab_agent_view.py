from server.models.agents.agent import Agent
from server.models.agents.agent_instance import AgentInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.components.tabs.agent.agent_instances_view import AgentInstancesView
from ui.components.tabs.agent.agent_versions_view import AgentVersionsView

class TabAgentView(PyHtmlView):
    DOM_ELEMENT_CLASS = 'tab-content active agent-edit-tab'
    DOM_ELEMENT_EXTRAS = 'style="padding:20px;"'
    TEMPLATE_STR = """
        <div class="agent-edit-container">
            <h3>Edit Agent: <span contenteditable="true" onblur="pyview.update_agent_name(this.innerText)">{{ pyview.subject.name }}</span></h3>
            <div class="form-group" style="margin-top: 15px;">
                <label>Description:</label>
                <textarea class="form-control" rows="3" onblur="pyview.update_agent_description(this.value)">{{ pyview.subject.description }}</textarea>
            </div>
            {{ pyview.versions_table_view.render() }}
            {{ pyview.instances_table_view.render() }}
            <div class="agent-edit-footer" style="margin-top:20px; border-top: 1px solid #eee; padding-top: 15px;">
                <button class="btn btn-success" onclick="pyview.save()">Save</button>
                <button class="btn btn-default" onclick="pyview.cancel()">Cancel</button>
            </div>
        </div>
    """
    def __init__(self, subject: Agent, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.active_instance = None
        self.agent = subject
        self.instances_table_view = AgentInstancesView(subject.agent_instances, self)
        self.versions_table_view  = AgentVersionsView(subject.agent_versions, self)

    def update_agent_name(self, name):
        if self.subject.name != name:
            self.subject.name = name
            self.subject.save()
            # Also update the tab label if the name changes
            self.parent.open_agent_tab(self.subject)

    def update_agent_description(self, description):
        if self.subject.description != description:
            self.subject.description = description
            self.subject.save()

    def open_instance_tab(self, instance_id):
        # This method is called from AgentInstancesTableView
        self.active_instance = AgentInstance.objects.get(id=instance_id)
        print(self.active_instance)
        self.parent.open_instance_tab(self.active_instance)

    def open_version_tab(self, version_id):
        # This method is called from AgentVersionsTableView
        # For now, just print. In a real scenario, this might open a new tab for the version
        print(f"Opening version tab for version {version_id}")

    def save(self):
        # The name and description are saved onblur. This save button can be for other potential edits.
        # For now, just re-render to ensure everything is up to date.
        self.update()

    def cancel(self):
        # Discard unsaved changes by re-fetching from DB and updating
        self.subject.refresh_from_db()
        self.update()
