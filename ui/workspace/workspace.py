from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.workspace.instance.instance_view import InstanceWorkspaceView
from ui.workspace.agent.agent_workspace import AgentWorkspaceView
from ui.workspace.system.providers import ProvidersView
from ui.workspace.system.systems import SystemsView
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp


class WorkspaceView(ModelView):
    """
    Tab bar + tab content area.
    Manages open tabs, selection, and closing.

    Tab types:
      instance_{id}   — InstanceWorkspaceView
      agent_{id}      — AgentWorkspaceView
      builtin_*       — system tabs (providers, systems, etc.)
    """
    DOM_ELEMENT_CLASS = "WorkspaceView resizable-panel flex-column"
    DOM_ELEMENT_EXTRAS = 'data-size-pc="100" style="height:100%;"'

    TEMPLATE_STR = """
        <div class="tab-bar-area">
            <div class="tab-bar" id="mainTabBar">
                {% for key in pyview.tab_order %}
                    {% set view = pyview.open_tabs[key] %}
                    <button class="tab-button {{ 'active' if view == pyview.selected_view else '' }}"
                            onclick="pyview.select_tab('{{ key }}')">
                        <span>{{ view.tab_label }}</span>
                        <i class="fa fa-times close-tab-btn"
                           onclick="event.stopPropagation(); pyview.close_tab('{{ key }}')"></i>
                    </button>
                {% endfor %}
            </div>
        </div>

        <div class="tab-content-area flex-column" style="flex:1; display:flex; overflow:auto">
            {% if pyview.selected_view %}
                {{ pyview.selected_view.render() }}
            {% else %}
                <div class="no-tab-selected" style="padding:20px; color:#999;">
                    Select an agent or instance from the sidebar to open a tab.
                </div>
            {% endif %}
        </div>
    """
    CSS_STR = '''
        /* --- Main Tab Bar --- */
        .tab-bar {
            display: flex;
            border-bottom: 1px solid #ccc; /* Separator for the content below */
            padding: 0 10px;
            padding-top: 5px;
            background-color: #f1f1f1; /* Light background for the tab bar */
        }

        .TabsView {
                width: 100%;
        }
        .tab-button {
            background-color: #e0e0e0; /* Default tab background */
            border: 1px solid #ccc;
            border-bottom: none; /* No bottom border to blend with the tab-bar's border-bottom */
            padding: 0px 15px;
            cursor: pointer;
            transition: background-color 0.3s, color 0.3s;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
            margin-right: 4px; /* Small space between tabs */
            font-size: 0.9em;
            color: #333;
            max-width: calc-size(min-content, size * 1.5);
            flex-grow: 1;
            outline: none; /* Remove focus outline */
        }

        .tab-button:hover:not(.active) {
            background-color: #d0d0d0; /* Slightly darker on hover */
        }

        .tab-button.active {
            background-color: #ffffff; /* Active tab is white */
            border-bottom: 1px solid #ffffff; /* Overlap the tab-bar's border */
            color: #000;
            font-weight: bold;
            z-index: 1; /* Ensure active tab is on top */
            margin-bottom: -1px;
        }

        /* --- Tab Content --- */
        .tab-content {

        }
        .tabpanel {
            width: 100%;
        }
        /* Hide content for inactive tabs - handled by JS, but good to have a default */
        .tab-content.hidden {
            display: none;
        }

        .tab-content.active {
            display: flex; /* Ensure active tab content is visible */
        }

        /* For the tab content areas that also act as resizable containers,
        ensure they occupy full height when active. */
        #tabContent_agentInstance.tab-content.active {
            height: 100%;
            /* Override display: block from .tab-content.active if .resizable-container expects flex */
            display: flex; 
            flex-direction: column;
        }
        /* --- Standardized Sidebar List Header --- */
        .sidebar-list-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px;
            padding-bottom: 0px;    
            font-weight: bold;
            border-bottom: 1px solid #dee2e6;
            background-color: #f8f9fa; /* Matches sidebar background */
        }


    '''
    
    def __init__(self, subject: "UiApp", parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.selected_view = None
        self.open_tabs: dict[str, PyHtmlView] = {}
        self.tab_order: list[str] = []

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def select_tab(self, key: str):
        if key in self.open_tabs:
            self.selected_view = self.open_tabs[key]
            self.update()

    def close_tab(self, key: str):
        if key not in self.open_tabs:
            return
        view = self.open_tabs.pop(key)
        self.tab_order.remove(key)
        if self.selected_view is view:
            self.selected_view = (
                self.open_tabs[self.tab_order[-1]] if self.tab_order else None
            )
        self.update()

    # ------------------------------------------------------------------
    # Open methods called from sidebar and agent workspace
    # ------------------------------------------------------------------

    def open_instance_tab(self, instance):
        key = f"instance_{instance.id}"
        if key not in self.open_tabs:
            view = InstanceWorkspaceView(instance, self)
            view.tab_label = instance.name or f"Instance #{instance.id}"
            self.open_tabs[key] = view
            self.tab_order.append(key)
        self.selected_view = self.open_tabs[key]
        self.update()

    def open_agent_tab(self, agent):
        key = f"agent_{agent.id}"
        if key not in self.open_tabs:
            view = AgentWorkspaceView(agent, self)
            view.tab_label = f"Agent: {agent.name}"
            self.open_tabs[key] = view
            self.tab_order.append(key)
        self.selected_view = self.open_tabs[key]
        self.update()

    def open_buildin_tab(self, tab_name: str):
        key = f"builtin_{tab_name}"
        if key not in self.open_tabs:
            view = self._create_builtin_tab(tab_name)
            if view is None:
                return
            self.open_tabs[key] = view
            self.tab_order.append(key)
        self.selected_view = self.open_tabs[key]
        self.update()

    def _create_builtin_tab(self, tab_name: str) -> PyHtmlView | None:
        if tab_name == 'providers':
            view = ProvidersView(self.subject, self)
            view.tab_label = "API Providers"
            return view
        if tab_name == 'systems':
            view = SystemsView(self.subject, self)
            view.tab_label = "Systems"
            return view
        # prompts and tools_registry — add when implemented
        return None