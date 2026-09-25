from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.main.settings.panels.appearance import SettingPanelAppearance
from ui.main.settings.panels.conversation import SettingPanelConversation
from ui.main.settings.panels.preferences import SettingPanelPerferences
from ui.main.settings.panels.providers import SettingPanelProviders
from ui.main.settings.panels.system import SettingPanelSystem

if TYPE_CHECKING:
    from ui.main.main_view import MainView

class SettingsView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''   
        <div class="settings-main">
            {{ pyview.selected_settings_panel.render() }}
        </div>
    '''

    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "mainSettings"
        self.selected_settings_panel_name = ""
        self.selected_settings_panel = None
        self.settings_sections = dict(
            appearance = SettingPanelAppearance(subject=self.subject, parent=self),
            conversation = SettingPanelConversation(subject=self.subject, parent=self),
            preferences = SettingPanelPerferences(subject=self.subject, parent=self),
            providers = SettingPanelProviders(subject=self.subject, parent=self),
            system = SettingPanelSystem(subject=self.subject, parent=self),
        )
        self.switchSettingsSection("conversation")
    
    def switchSettingsSection(self, settings_section_name):
        if settings_section_name not in self.settings_sections:
            print(f"No main view named {settings_section_name}")
            return 
        if settings_section_name != "providers":
            # Avoid a stale provider detail lingering in the rightbar.
            try:
                providers_panel = self.settings_sections["providers"]
                providers_panel.clear_detail()
                rightpanel = getattr(getattr(self, "parent", None), "rightpanel", None)
                if rightpanel is not None:
                    rightpanel.close()
            except Exception:
                pass
        self.selected_settings_panel_name = settings_section_name
        self.selected_settings_panel = self.settings_sections[settings_section_name]
        self.update()
