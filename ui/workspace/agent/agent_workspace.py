from __future__ import annotations
from server.models.agents.agent import Agent
from server.models.agents.agent_instance import AgentInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.workspace.agent.overview import AgentVersionsView, AgentInstancesView
from ui.workspace.agent.tasks import AgentTaskDefinitionsView, AgentTaskDefinitionView
from ui.lib.model_view import ModelView


class AgentWorkspaceView(ModelView):
    """
    Per-agent definition tab.
    Shows agent metadata (name, description) and two sub-views:
    the version history and the instance list.
    """
    DOM_ELEMENT_CLASS = "AgentWorkspaceView tab-content agent-workspace"
    DOM_ELEMENT_EXTRAS = 'style="padding: 20px;"'

    TEMPLATE_STR = """
        <div class="agent-edit-container">
            <h3>
                <span contenteditable="true"
                      onblur="pyview.save_name(this.innerText)">
                    {{ pyview.subject.name }}
                </span>
            </h3>

            <div class="form-group" style="margin-top: 12px;">
                <label>Description:</label>
                <textarea class="form-control"
                          rows="3"
                          onblur="pyview.save_description(this.value)">{{ pyview.subject.description or '' }}</textarea>
            </div>

            <div style="margin-top: 20px;">
                {{ pyview.versions_view.render() }}
            </div>

            <div style="margin-top: 20px;">
                {{ pyview.instances_view.render() }}
            </div>
        </div>
    """
    CSS_STR = '''
.agent-edit-container {
    flex-grow: 1;
    overflow-y: auto; /* Allow the inner container with the form to scroll */
    padding: 20px;
}

'''

    def __init__(self, subject: Agent, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.versions_view = AgentVersionsView(
            subject=subject.agent_versions.order_by('-version_number'),
            parent=self,
        )
        self.instances_view = AgentInstancesView(
            subject=subject.agent_instances.all(),
            parent=self,
        )

    def save_name(self, name: str):
        name = name.strip()
        if name and self.subject.name != name:
            # AgentInstance is immutable — Agent name changes need careful handling
            # TODO: implement once mutation strategy is decided
            print(f"[AgentWorkspaceView] name change to {name!r} — not yet persisted")
        self.update()

    def save_description(self, description: str):
        if self.subject.description != description:
            # TODO: persist once Agent mutation is supported
            print(f"[AgentWorkspaceView] description change — not yet persisted")
        self.update()

    def open_instance_tab(self, instance_id: int):
        instance = AgentInstance.objects.get(id=instance_id)
        # Walk up to the workspace to open the tab
        node = self.parent
        while node is not None:
            if hasattr(node, 'open_instance_tab'):
                node.open_instance_tab(instance)
                return
            node = getattr(node, 'parent', None)