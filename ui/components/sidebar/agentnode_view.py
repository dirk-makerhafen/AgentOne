from server.models.agents.agent import Agent
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.components.sidebar.instancelist_view import SidebarInstanceListView
from ui.components.sidebar.variantlist_view import SidebarVariantListView
from ui.components.sidebar.versionlist_view import SidebarVersionListView
from ui.main_view import UiAppView

class SidebarAgentNodeView(PyHtmlView):
    TEMPLATE_STR = """
    <li class="agent-node-item">
        <div class="tree-node-header agent-node">
            <span class="agent-node-content" onclick="pyview.select_agent()" style="width: stretch;"> 
                <i class="fa fa-users tree-node-icon"></i>
                <span class="tree-node-name">{{ pyview.subject.name }}</span>   
                <span style="font-size:0.9em">v{{ pyview.subject.latest_agent_version.version_number }}  </span>           
            </span>
            <div class="agent-actions-menu-container">
                <div class="agent-actions-menu" onmouseleave="pyview.hide_menu()">
                    <button class="btn btn-xs btn-default burgerbtn" onclick="event.stopPropagation(); pyview.show_menu()"><i class="fa fa-bars"></i></button>
                    <div id="agent-menu-{{pyview.subject.id}}" class="agent-menu-dropdown" style="display: none;">
                        <a href="#" onclick="event.stopPropagation(); pyview.edit_agent()">Edit Agent</a>
                        <a href="#" onclick="event.stopPropagation(); pyview.delete_agent()">Delete Agent</a>
                    </div>
                </div>
            </div>
        </div>
        <div class="tree-node-details small">
            Instances: {{ pyview.subject.related_agent_instances.count() }}
            subagents: {{ pyview.subject.latest_agent_version.sub_agent_versions.count() }}
            ImportedBy: {{ pyview.subject.latest_agent_version.imported_by_agent_versions.count() }}
        </div>
    </li>
    """
    '''
     <div class="tree-node-children" style="{{ 'display: block;' if pyview.is_expanded else 'display: none;' }}">
            <ul class="tree-view-list">
                {% if pyview.subject.agent_versions %}
                    {{pyview.versions_list.render()}}
                {% endif %}
                {% if pyview.subject.agent_instances %}
                    {{pyview.instances_list.render()}}
                {% endif %}
            </ul>
        </div>
    '''
    def __init__(self, subject: Agent, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app = parent.app
        self.app:UiAppView

        self._subject = subject
        self.is_expanded = False
        self.expanded_categories = {'versions': True, 'instances': True}
        self.instances_list = SidebarInstanceListView(subject, self)
        self.versions_list  = SidebarVersionListView(subject, self)

    def select_agent(self):
        self.app.open_agent_tab(self.subject)
        self.update()

    def toggle_node(self):
            self.is_expanded = not self.is_expanded
            self.update()

    def toggle_category(self, cat): 
        self.expanded_categories[cat] = not self.expanded_categories[cat]
        self.update()

    def show_menu(self):
        self.eval_javascript(script='document.getElementById("agent-menu-" + args.id).style.display = "block";', id=self.subject.id)

    def hide_menu(self):
        self.eval_javascript(script='document.getElementById("agent-menu-" + args.id).style.display = "none";', id=self.subject.id)

    def edit_agent(self):
        print(f"Edit Agent: {self.subject.name} ({self.subject.id})")
        self.app.open_agent_tab(self.subject)
        self.hide_menu()

    def delete_agent(self):
        print(f"Delete Agent: {self.subject.name} ({self.subject.id})")
        # Add actual deletion logic here later
        self.hide_menu()