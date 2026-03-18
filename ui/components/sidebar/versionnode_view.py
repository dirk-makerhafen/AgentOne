from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.components.sidebar.variantlist_view import SidebarVariantListView

class SidebarVersionNodeView(PyHtmlView):
    TEMPLATE_STR = """
    <li class="version-node-item">
        <div class="tree-node-header version-node">
            {% if pyview.subject.agent_instances or pyview.subject.agent_variants %}
                <i class="fa fa-caret-right tree-node-toggle" onclick="event.stopPropagation(); pyview.toggle_node()"></i>
            {% else %}
                <span class="tree-node-spacer"></span>
            {% endif %}
            <span class="version-node-content" onclick="pyview.select_version()"> 
                <i class="fa fa-code tree-node-icon"></i>
                <span class="tree-node-name">v{{ pyview.subject.version }}</span>
            </span>
            <div class="agent-actions-menu-container">
                <div class="agent-actions-menu" onmouseleave="pyview.hide_menu()">
                    <button class="btn btn-xs btn-default burgerbtn" onclick="event.stopPropagation(); pyview.show_menu()"><i class="fa fa-bars"></i></button>
                    <div id="version-menu-{{pyview.subject.id}}" class="agent-menu-dropdown" style="display: none;">
                        <a href="#" onclick="event.stopPropagation(); pyview.edit_version()">Edit Version</a>
                        <a href="#" onclick="event.stopPropagation(); pyview.delete_version()">Delete Version</a>
                    </div>
                </div>
            </div>
        </div>
        <div class="tree-node-children" style="{{ 'display: block;' if pyview.is_expanded else 'display: none;' }}">
            <ul class="tree-view-list">
                {% if pyview.subject.agent_instances %}
                    { {p yview.instances_list.render() } }
                {% endif %}
                {% if pyview.subject.agent_profiles %}
                    {{pyview.profiles_list.render()}}
                {% endif %}
            </ul>
        </div>
    </li>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app = parent.app
        self._subject = subject
        self.is_expanded = False
        self.expanded_categories = {'variants': True, 'instances': True}
        #self.instances_list = SidebarInstanceListView(subject, self)
        self.profiles_list  = SidebarVariantListView(subject, self)

    def select_version(self):
        self.app.open_agent_tab(self.subject.agent) 
        self.update()

    def toggle_node(self):
        self.is_expanded = not self.is_expanded
        self.update()

    def toggle_category(self, event, cat):
        event.stopPropagation()
        self.expanded_categories[cat] = not self.expanded_categories[cat]
        self.update()

    def show_menu(self):
        self.eval_javascript(script='document.getElementById("version-menu-" + args.id).style.display = "block";', id=self.subject.id)

    def hide_menu(self):
        self.eval_javascript(script='document.getElementById("version-menu-" + args.id).style.display = "none";', id=self.subject.id)

    def edit_version(self):
        print(f"Edit Version: {self.subject.version} ({self.subject.id})")
        # Add actual edit logic here later
        self.hide_menu()

    def delete_version(self):
        print(f"Delete Version: {self.subject.version} ({self.subject.id})")
        # Add actual deletion logic here later
        self.hide_menu()