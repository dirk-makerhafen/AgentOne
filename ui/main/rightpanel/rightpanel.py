from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.rightpanel.settings import RightPanelSettings
from ui.main.rightpanel.workspace import RightPanelWorkspace


if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView

class RightPanel(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel1"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab active" data-panel="workspce" data-label="Workspace" onclick="pyview.switchPanel('workspace')" title="Workspace" data-i18n-title="tab_workspace">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <div class="rail-button-text" style="display:none">Workspace</div>
            </button>
            <button class="nav-tab active" data-panel="settings" data-label="Settings" onclick="pyview.switchPanel('settings')" title="Settings" data-i18n-title="tab_settings">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                <div class="rail-button-text" style="display:none">Settings</div>
            </button>
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>

        {{pyview.current_view.render()}}
    '''
    def __init__(self, subject:UiApp, parent: UiAppView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.workspace_view = RightPanelWorkspace(subject, self)
        self.settings_view = RightPanelSettings(subject, self)
        self.current_view = self.workspace_view

    def switchPanel(self, name):
        if name == "workspace" and self.current_view != self.workspace_view:
            self.current_view = self.workspace_view
        if name == "settings" and self.current_view != self.settings_view:
            self.current_view = self.settings_view
        self.update()