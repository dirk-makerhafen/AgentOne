from __future__ import annotations
from server.models.agents.agent import AgentModel
from server.models.agents.agent_instance import InstanceModel
from ui.lib.model_view import ModelView


class ProjectWorkspaceView(ModelView):
    """
    Per-project definition tab.
ist.
    """
    DOM_ELEMENT_CLASS = "ProjectWorkspaceView tab-content project-workspace"
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


        </div>
    """
    CSS_STR = '''
.agent-edit-container {
    flex-grow: 1;
    overflow-y: auto; /* Allow the inner container with the form to scroll */
    padding: 20px;
}

'''

    def __init__(self, subject: AgentModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        #self.versions_view = AgentVersionsView(subject=subject.agent_versions.order_by('-version_number'), parent=self)
        #self.instances_view = AgentInstancesView(subject=subject.agent_instances.all(), parent=self)
        #self.subagents_view = SubAgentVersionsView(subject=subject.latest_agent_version.sub_agent_versions.all(), parent=self)

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
        instance = InstanceModel.objects.get(id=instance_id)
        # Walk up to the workspace to open the tab
        node = self.parent
        while node is not None:
            if hasattr(node, 'open_instance_tab'):
                node.open_instance_tab(instance)
                return
            node = getattr(node, 'parent', None)