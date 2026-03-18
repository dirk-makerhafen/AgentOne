from __future__ import annotations
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.components.sidebar.agentlist_view import SidebarAgentListView


from typing import TYPE_CHECKING

from ui.components.sidebar.instancelist_view import SidebarInstanceListView

if TYPE_CHECKING:
    from ui.main_app import UiApp
    from ui.main_view import UiAppView

class SidebarContainerView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="resizable-panel sidebar_left_body flex-column" id="sidebarAgentsContainer">
        <div id="agents-list-header" class="sidebar-list-header">
            <span>Agents</span>
            <button class="btn btn-xs btn-default" onclick="pyview.add_agent()"><i class="fa fa-plus"></i></button>
        </div>
        <div class="instance-view-controls">
            <button class="btn btn-default btn-sm {{ 'active' if pyview.view_mode == 'agent' else '' }}" onclick="pyview.set_view_mode('agent')">
                <i class="fa fa-users"></i> Agents
            </button>
            <button class="btn btn-default btn-sm {{ 'active' if pyview.view_mode == 'dir' else '' }}" onclick="pyview.set_view_mode('dir')">
                <i class="fa fa-folder-open"></i> Directory
            </button>
            <button class="btn btn-default btn-sm {{ 'active' if pyview.view_mode == 'instance' else '' }}" onclick="pyview.set_view_mode('instance')">
                <i class="fa fa-code-fork"></i> Hierarchy
            </button>
        </div>
        <div id="agents-list-body">
            {% if pyview.view_mode == 'agent' %}
                {{ pyview.agent_list.render() }}
            {% elif pyview.view_mode == 'dir' %}

            {% elif pyview.view_mode == 'instance' %}
                {{ pyview.instance_list.render() }}
            {% endif %}
        </div>      
        <div class="sidebar-nav-ribbons">
            <button class="nav-ribbon" onclick="pyview.app.open_buildin_tab('systems')"><i class="fa fa-tasks"></i> Systems</button>
            <button class="nav-ribbon" onclick="pyview.app.open_buildin_tab('providers')"><i class="fa fa-cloud"></i> API Providers</button>
            <button class="nav-ribbon" onclick="pyview.app.open_buildin_tab('prompts')"><i class="fa fa-pencil-square-o"></i> Prompts</button>
            <button class="nav-ribbon" onclick="pyview.app.open_buildin_tab('tools')"><i class="fa fa-wrench"></i> Tool Registry</button>
        </div>
    </div>
    """
    
    def __init__(self, subject: UiApp, parent: UiAppView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._subject = subject
        self.app = parent
        self.app:UiAppView
        self.agent_list = SidebarAgentListView(subject, self)
        self.instance_list = SidebarInstanceListView(subject, self)
        self.view_mode = "instance"

    def set_view_mode(self, mode):
        self.view_mode = mode
        self.update()

    def add_agent(self): pass
