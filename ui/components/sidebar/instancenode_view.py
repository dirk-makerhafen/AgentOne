from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from typing import TYPE_CHECKING

from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
if TYPE_CHECKING:
    from ui.main_view import UiAppView


class SidebarInstanceVersionNodeView(PyHtmlView):
    TEMPLATE_STR = """
        <div class="tree-node-header instance-node">

            {% if pyview.subject.child_agent_instance_versions.exists() %}
                <i class="fa fa-caret-right tree-node-toggle" onclick="event.stopPropagation(); pyview.toggle_node()"></i>
            {% else %}
                <span class="tree-node-spacer"></span>
            {% endif %}
            <span class="instance-node-content" onclick="pyview.select_instance()">
                <i class="fa fa-users tree-node-icon"></i>
                <span class="tree-node-name">
                    {{pyview.subject.agent_instance.agent.name}}
                    <i style="font-size:0.7em">
                        v{{pyview.subject.agent_version.version_number}}
                    </i> 
                    {{ pyview.subject.name }}
                    <i style="font-size:0.7em">
                        #{{pyview.subject.pk}}
                    </i> 
                </span>
            </span>
            <span class="instance-status instance-status-{{ pyview.subject.status }}">{{ pyview.subject.status_display }}</span>
            
            <div class="agent-actions-menu-container">
                <div class="agent-actions-menu" onmouseleave="pyview.hide_menu()">
                    <button class="btn btn-xs btn-default burgerbtn" onclick="event.stopPropagation(); pyview.show_menu()"><i class="fa fa-bars"></i></button>
                    <div id="agent-instance-menu-{{pyview.subject.id}}" class="agent-menu-dropdown" style="display: none;">
                        <a href="#" onclick="event.stopPropagation(); pyview.delete_instance()">Delete Instance</a>
                    </div>
                </div>
            </div>
        

        </div>
        <div class="tree-node-children" style="{{ 'display: block;' if pyview.is_expanded else 'display: none;' }}">
            <ul class="tree-view-list">
               {{pyview.children.render()}}
            </ul>
        </div>
    """
    def __init__(self, subject, parent, **kwargs): # subj = instance version
        super().__init__(subject, parent, **kwargs)
        try:
            self.app = parent.app
        except:
            self.app = parent.parent.app
        
        self.app:UiAppView
        self.s = subject
        self.agent_instance_version = subject
        
        self.is_selected = False 
        self.is_expanded = False

        self._child_views = {}
        self.children = QuerySetView(subject=subject.child_agent_instance_versions, parent=self, item_class=SidebarInstanceVersionNodeView)


    def toggle_node(self):
        self.is_expanded = not self.is_expanded
        self.update()
    def select_instance(self):
        self.app.open_instance_tab(self.subject.agent_instance)
        self.update()
    def show_menu(self):
        self.eval_javascript(script='document.getElementById("agent-instance-menu-" + args.id).style.display = "block";', id=self.subject.id)

    def hide_menu(self):
        self.eval_javascript(script='document.getElementById("agent-instance-menu-" + args.id).style.display = "none";', id=self.subject.id)
    def delete_instance(self):
        print(f"Delete Instance: {self.subject.name} ({self.subject.id})")
        # Add actual deletion logic here later
        self.hide_menu()


class SidebarInstanceNodeView(PyHtmlView):
    TEMPLATE_STR = """
    <li>
        <div id="agent_instance_{{ pyview.subject.id }}" class="tree-leaf-instance {{ 'selected-instance' if pyview.is_selected else '' }}">
            
            {% if pyview.child_agent_instance_versions.exists() %}
                <i class="fa fa-caret-right tree-node-toggle" onclick="event.stopPropagation(); pyview.toggle_node()"></i>
            {% else %}
                <span class="tree-node-spacer"></span>
            {% endif %}
            <span class="instance-node-content" onclick="pyview.select_instance()">
                <i class="fa fa-users tree-node-icon"></i>
                <span class="tree-node-name">
                    {{pyview.subject.agent.name}}
                    <i style="font-size:0.7em">
                        v{{pyview.latest_agent_instance_version.agent_version.version_number}}
                    </i> 
                    {{ pyview.subject.name }}
                    <i style="font-size:0.7em">
                        #{{pyview.latest_agent_instance_version.pk}}
                    </i> 
                </span>
            </span>
            <span class="instance-status instance-status-{{ pyview.subject.status }}">{{ pyview.subject.status_display }}</span>
            
            <div class="agent-actions-menu-container">
                <div class="agent-actions-menu" onmouseleave="pyview.hide_menu()">
                    <button class="btn btn-xs btn-default burgerbtn" onclick="event.stopPropagation(); pyview.show_menu()"><i class="fa fa-bars"></i></button>
                    <div id="agent-instance-menu-{{pyview.subject.id}}" class="agent-menu-dropdown" style="display: none;">
                        <a href="#" onclick="event.stopPropagation(); pyview.delete_instance()">Delete Instance</a>
                    </div>
                </div>
            </div>
        </div>
        <div class="tree-node-children" style="{{ 'display: block;' if pyview.is_expanded else 'display: none;' }}">
            <ul class="tree-view-list">
                {{pyview.children.render()}}
            </ul>
        </div>
      
    </li>
    """
    def __init__(self, subject, parent, **kwargs): # subj = instance version
        super().__init__(subject, parent, **kwargs)
        try:
            self.app = parent.app
        except:
            self.app = parent.parent.app
        
        self.app:UiAppView
        self.s = subject
        self.agent_instance = subject
        self.latest_agent_instance_version = self.agent_instance.latest_agent_instance_version
        self.child_agent_instance_versions = self.latest_agent_instance_version.child_agent_instance_versions
        
        self.is_selected = False 
        self.is_expanded = False
        self.children = QuerySetView(subject=self.child_agent_instance_versions, parent=self, item_class=SidebarInstanceVersionNodeView)

        self._child_views = {}

    def select_instance(self):
        self.app.open_instance_tab(self.subject)
        self.update()

    def show_menu(self):
        self.eval_javascript(script='document.getElementById("agent-instance-menu-" + args.id).style.display = "block";', id=self.subject.id)

    def hide_menu(self):
        self.eval_javascript(script='document.getElementById("agent-instance-menu-" + args.id).style.display = "none";', id=self.subject.id)

    def delete_instance(self):
        print(f"Delete Instance: {self.subject.name} ({self.subject.id})")
        # Add actual deletion logic here later
        self.hide_menu()

    def toggle_node(self):
        self.is_expanded = not self.is_expanded
        self.update()

    