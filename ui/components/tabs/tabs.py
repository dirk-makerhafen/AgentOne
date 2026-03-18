from __future__ import annotations
            
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
# Import all top-level tab views
from ui.components.tabs.agent.tab_agent_view import TabAgentView
from ui.components.tabs.instance.tab_instance_view import TabInstanceView
from ui.components.tabs.providers.tab_providers_view import TabProvidersView
from ui.components.tabs.systems.tab_systems_view import TabSystemsView
from ui.components.tabs.tab_prompts_view import TabPromptsView
from ui.components.tabs.tab_tools_view import TabToolsView
from ui.main_app import UiApp


class TabsView(PyHtmlView):
    DOM_ELEMENT_CLASS = "resizable-panel flex-column"
    DOM_ELEMENT_EXTRAS = 'data-size-pc=100 style="height: 100%;"'
    TEMPLATE_STR = """
        <div class="tab-controls-area">
            <div class="tab-bar" id="mainTabBar">
                {% for key in pyview.tab_order %}
                    {% set view = pyview.open_tabs[key] %}
                    <button class="tab-button {{ 'active' if view == pyview.selected_view else '' }}" 
                            onclick="pyview.select_tab('{{ key }}')">
                        <span> {{ view.tab_label }} </span>
                        <i class="fa fa-times close-tab-btn" onclick="event.stopPropagation(); pyview.close_tab('{{ key }}')"></i>
                    </button>
                {% endfor %}
            </div>
        </div>
        <div class="tab-content flex-column" style="flex: 1; display: flex;">
            {% if not pyview.selected_view %}
                <div id="no-instance-selected-content" class="tab-content active" style="padding: 20px;">
                    <p>Select an agent or instance from the left sidebar to open its dedicated tab.</p>
                </div>
            {% else %}
                {{ pyview.selected_view.render() }}
            {% endif %}
        </div>
    """

    def __init__(self, subject: UiApp, parent, **kwargs): 
        super().__init__(subject, parent, **kwargs)
        self.selected_view = None
        self.open_tabs = {}
        self.tab_order = []

    def select_tab(self, key):
        if key in self.open_tabs:
            self.selected_view = self.open_tabs[key]
            self.update()

    def close_tab(self, key):
        if key in self.open_tabs:
            view = self.open_tabs.pop(key)
            self.tab_order.remove(key)
            if self.selected_view == view:
                if self.tab_order:
                    self.selected_view = self.open_tabs[self.tab_order[-1]]
                else:
                    self.selected_view = None
            self.update()

    def open_buildin_tab(self, tab_name):
        key = f"builtin_{tab_name}"
        if key not in self.open_tabs:
            view = None
            if tab_name == 'prompts':
                view = TabPromptsView(self.subject, self)
                view.tab_label = "Prompts"
            elif tab_name == 'providers':
                view = TabProvidersView(self.subject, self)
                view.tab_label = "API Providers"
            elif tab_name == 'systems':
                view = TabSystemsView(self.subject, self)
                view.tab_label = "Systems"
            elif tab_name == 'tools':
                view = TabToolsView(self.subject, self)
                view.tab_label = "Tool Registry"
            
            if view:
                self.open_tabs[key] = view
                self.tab_order.append(key)
        
        if key in self.open_tabs:
            self.selected_view = self.open_tabs[key]
            self.update()

    def open_agent_tab(self, agent):
        key = f"agent_{agent.id}"
        if key not in self.open_tabs:
            view = TabAgentView(agent, self)
            view.tab_label = f"Agent: {agent.name}"
            self.open_tabs[key] = view
            self.tab_order.append(key)
        self.selected_view = self.open_tabs[key]
        self.update()

    def open_instance_tab(self, instance):
        key = f"instance_{instance.id}"
        print("key:", key)
        if key not in self.open_tabs:
            view = TabInstanceView(instance, self)
            view.tab_label = instance.name
            self.open_tabs[key] = view
            self.tab_order.append(key)
        self.selected_view = self.open_tabs[key]
        self.update()
