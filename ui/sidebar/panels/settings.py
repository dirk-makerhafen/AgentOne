from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.settings.settings import SettingsView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelSettings(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Settings panel (menu list; actual panes render in .main) -->
        <div class="panel-head">
            <span data-i18n="tab_settings">Settings</span>
        </div>
        <div class="side-menu" id="settingsMenu">
            <button type="button" class="side-menu-item active" data-settings-section="conversation" onclick="pyview.open_settings_details('conversation')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            <span>Conversation</span>
            </button>
            <button type="button" class="side-menu-item" data-settings-section="appearance" onclick="pyview.open_settings_details('appearance')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
            <span>Appearance</span>
            </button>
            <button type="button" class="side-menu-item" data-settings-section="preferences" onclick="pyview.open_settings_details('preferences')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
            <span>Preferences</span>
            </button>
            <button type="button" class="side-menu-item" data-settings-section="providers" onclick="pyview.open_settings_details('providers')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
            <span data-i18n="providers_tab_title">Providers</span>
            </button>
            <button type="button" class="side-menu-item" data-settings-section="plugins" onclick="pyview.open_settings_details('plugins')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2l3 7h7l-5.5 4.3 2.1 7L12 16.2 5.4 20.3l2.1-7L2 9h7z"/></svg>
            <span>Plugins</span>
            </button>
            <button type="button" class="side-menu-item" data-settings-section="system" onclick="pyview.open_settings_details('system')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="8" rx="2"/><rect x="2" y="13" width="20" height="8" rx="2"/><line x1="6" y1="7" x2="6.01" y2="7"/><line x1="6" y1="17" x2="6.01" y2="17"/></svg>
            <span>System</span>
            </button>
        </div>
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "panelSettings"
        self.root_view: UiAppView = parent.root_view
        #self.open_settings_details()

    def open_settings_details(self, name="conversation"):
        settings_view = self.root_view.main_panel.create_and_open_tab(SettingsView, self.subject)
        settings_view.switchSettingsSection(name)
