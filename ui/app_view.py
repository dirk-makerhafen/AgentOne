
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.rightpanel.rightpanel import RightPanel
from ui.overlay.appdialog import AppDialogOverlay
from ui.overlay.mobile import MobileOverlay
from ui.overlay.onboarding import OnboardingOverlay
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
    CATEGORIES = {
        "Chat": "CHAT",
        "CronView": "CRONJOB",
        "CronCreateView": "CRONJOB",
        "CollectionDetailView": "DATAFLOW",
        "CollectionCreateView": "DATAFLOW",
        "AgentView": "AGENT",
        "ProjectView": "PROJECT",
        "Workspace": "WORKSPACE",
        "CreateWorkspace": "WORKSPACE",
        "SkillView": "SKILL",
        "SettingsView": "SETTINGS",
        "DashboardView": "DASHBOARD",
    }

    TEMPLATE_STR = '''
        <header class="app-titlebar" role="banner">
            <button class="app-titlebar-hamburger" id="btnHamburger" onclick="toggleMobileSidebar()" type="button" title="Menu" aria-label="Menu">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
            <div class="app-titlebar-inner">
                <span class="app-titlebar-icon" aria-hidden="true">

                </span>
                <span class="app-titlebar-title" id="appTitlebarTitle">{{ pyview.title_text }}</span>
                <span class="app-titlebar-sub" id="appTitlebarSub" hidden></span>
            </div>
            <div class="app-titlebar-spacer" aria-hidden="true"></div>
        </header>
    '''

    @property
    def title_text(self):
        parts = ["AgentOne"]
        main_panel = getattr(self.parent, 'main_panel', None)
        tab = getattr(main_panel, 'selected_tab_view', None) if main_panel else None
        if tab is not None:
            proj = self._tab_project(tab)
            if proj:
                parts.append(proj)
            cat = self.CATEGORIES.get(tab.__class__.__name__)
            if cat:
                parts.append(cat)
            name = self._tab_name(tab)
            if name:
                parts.append(name)
        else:
            sidebar = getattr(self.parent, 'sidebar', None)
            if sidebar is not None:
                pid = getattr(sidebar, 'selected_project_id', None)
                if pid is not None:
                    from server.models.project import Project
                    project = Project.objects.filter(pk=pid).first()
                    if project is not None:
                        parts.append(project.name)
        return " · ".join(parts)

    @staticmethod
    def _tab_name(tab):
        subject = getattr(tab, 'subject', None)
        if subject is not None:
            return getattr(subject, 'name', None)
        return None

    @staticmethod
    def _tab_project(tab):
        subject = getattr(tab, 'subject', None)
        if subject is None:
            return None
        pp = getattr(subject, 'parent_project', None)
        if pp is not None:
            return getattr(pp, 'name', str(pp))
        ppid = getattr(subject, 'parent_project_id', None)
        if ppid is not None:
            from server.models.project import Project
            project = Project.objects.filter(pk=ppid).first()
            if project is not None:
                return project.name
        return None


class UiAppView(PyHtmlView):
    TEMPLATE_STR = """
        {{ pyview.titlebar.render() }}

        <div class="layout">

            {{ pyview.rail.render() }}
            
            {{ pyview.sidebar.render() }}

            {{ pyview.main_panel.render() }}
            
            {{ pyview.rightpanel.render() }}

        </div>

        {{ pyview.onboarding_overlay.render() }}

        {{ pyview.mobile_overlay.render() }}

        {{ pyview.app_dialog_overlay.render() }}

        """
    
    def __init__(self, subject:UiApp, parent, **kwargs):
        self._subject = subject
        super().__init__(subject, parent, **kwargs)

        self.titlebar = AppTitlebar(subject=subject, parent=self)

        self.rail     = RailView(subject=subject, parent=self) # Subject will be the main UiApp
        self.sidebar = SidebarView(subject=subject,parent= self) # Subject will be the main UiApp
        self.main_panel = MainView(subject, self)

        self.rightpanel = RightPanel(subject, self)

        self.onboarding_overlay = OnboardingOverlay(subject, self)
        self.mobile_overlay = MobileOverlay(subject, self)
        self.app_dialog_overlay = AppDialogOverlay(subject, self)
        
        
        