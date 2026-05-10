
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.sidebar.rail import RailView
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ui.sidebar.sidebar import SidebarView
from ui.app import UiApp
from ui.main.main_view import MainView

@login_required
def ui(request):
    return render(request, 'pyhtmlgui_page.html', {})


class AppTitlebar(PyHtmlView):
    TEMPLATE_STR = '''
        <header class="app-titlebar" role="banner">
            <button class="app-titlebar-hamburger" id="btnHamburger" onclick="toggleMobileSidebar()" type="button" title="Menu" aria-label="Menu">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
            <div class="app-titlebar-inner">
                <span class="app-titlebar-icon" aria-hidden="true">
                
                </span>
                <span class="app-titlebar-title" id="appTitlebarTitle">AgentOne</span>
                <span class="app-titlebar-sub" id="appTitlebarSub" hidden></span>
            </div>
            <div class="app-titlebar-spacer" aria-hidden="true"></div>
        </header>
    '''


class UiAppView(PyHtmlView):
    TEMPLATE_STR = """
        {{ pyview.titlebar.render() }}

        <div class="layout">
            {{ pyview.rail.render() }}
            {{ pyview.sidebar.render() }}
            {{ pyview.main_panel.render() }}
            
            TODO RIGHTPANEL
        </div>

        ONBOARDING
        MOBILE

        <div class="toast" id="toast"></div>
        <script src="static/i18n.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/icons.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/ui.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/workspace.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/terminal.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/sessions.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/commands.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/messages.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/panels.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/onboarding.js?v=__WEBUI_VERSION__" defer></script>
        <script src="static/boot.js?v=__WEBUI_VERSION__" defer></script>
        """
    
    def __init__(self, subject:UiApp, parent, **kwargs):
        self._subject = subject
        super().__init__(subject, parent, **kwargs)
        self.main_panel = MainView(subject, self)
        self.titlebar = AppTitlebar(subject=subject, parent=self)
        self.rail     = RailView(subject=subject, parent=self) # Subject will be the main UiApp
        self.sidebar = SidebarView(subject=subject,parent= self) # Subject will be the main UiApp

'''
    def open_buildin_tab(self, tab_name):
        self.workspace_view.open_buildin_tab(tab_name)

    def open_instance_tab(self, instance):
        self.workspace_view.open_instance_tab(instance)

    def open_agent_tab(self, agent: AgentModel):
        self.workspace_view.open_agent_tab(agent)

    def new_chat(self, agent: AgentModel):
        agent.latest_agent_version.get_or_create_instance()

    def open_project_tab(self, project: Project):
        self.workspace_view.open_project_tab(project)
        
'''