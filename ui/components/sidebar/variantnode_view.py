from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.components.sidebar.instancelist_view import SidebarInstanceListView
from ui.components.sidebar.instancenode_view import SidebarInstanceNodeView

class SidebarVariantNodeView(PyHtmlView):
    TEMPLATE_STR = """
    <li class="variant-node-item">
        <div class="tree-node-header variant-node">
            {% if pyview.subject.agent_instances %}
                <i class="fa fa-caret-right tree-node-toggle" onclick="event.stopPropagation(); pyview.toggle_node()"></i>
            {% else %}
                <span class="tree-node-spacer"></span>
            {% endif %}
            <span class="variant-node-content" onclick="pyview.select_variant()"> 
                <i class="fa fa-code-fork tree-node-icon"></i>
                <span class="tree-node-name">{{ pyview.subject.name }}</span>
            </span>
            <div class="agent-actions-menu-container">
                <div class="agent-actions-menu" onmouseleave="pyview.hide_menu()">
                    <button class="btn btn-xs btn-default burgerbtn" onclick="event.stopPropagation(); pyview.show_menu()"><i class="fa fa-bars"></i></button>
                    <div id="variant-menu-{{pyview.subject.id}}" class="agent-menu-dropdown" style="display: none;">
                        <a href="#" onclick="event.stopPropagation(); pyview.edit_variant()">Edit Variant</a>
                        <a href="#" onclick="event.stopPropagation(); pyview.delete_variant()">Delete Variant</a>
                    </div>
                </div>
            </div>
        </div>
        <div class="tree-node-children" style="{{ 'display: block;' if pyview.is_expanded else 'display: none;' }}">
            <ul class="tree-view-list">
                {% if pyview.subject.agent_instances %}
                    { {p yview.instances_list.render( )} }
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
        self.expanded_categories = {'instances': True}
        #self.instances_list = SidebarInstanceListView(subject, self)

    def select_variant(self):
        self.app.open_agent_tab(self.subject.agent_version.agent) 
        self.update()

    def toggle_node(self):
        self.is_expanded = not self.is_expanded
        self.update()

    def toggle_category(self, event, cat):
        event.stopPropagation()
        self.expanded_categories[cat] = not self.expanded_categories[cat]
        self.update()

    def show_menu(self):
        self.eval_javascript(script='document.getElementById("variant-menu-" + args.id).style.display = "block";', id=self.subject.id)

    def hide_menu(self):
        self.eval_javascript(script='document.getElementById("variant-menu-" + args.id).style.display = "none";', id=self.subject.id)

    def edit_variant(self):
        print(f"Edit Variant: {self.subject.name} ({self.subject.id})")
        # Add actual edit logic here later
        self.hide_menu()

    def delete_variant(self):
        print(f"Delete Variant: {self.subject.name} ({self.subject.id})")
        # Add actual deletion logic here later
        self.hide_menu()