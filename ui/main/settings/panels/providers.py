from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.settings.settings import SettingsView


class SettingPanelProviders(ModelView):
    DOM_ELEMENT_CLASS = "settings-pane"
    TEMPLATE_STR = '''
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title" data-i18n="providers_section_title">Providers</div>
                <div class="settings-section-meta" data-i18n="providers_section_meta">Manage API keys for AI providers. Changes take effect immediately.</div>
            </div>
        </div>
        <div id="providersList" style="display:flex;flex-direction:column;margin-top:4px">
            <!-- Populated dynamically by loadProvidersPanel() -->
        </div>
        <div id="providersEmpty" style="display:none;text-align:center;padding:32px 0;color:var(--muted);font-size:13px" data-i18n="providers_empty">
            No configurable providers found.
        </div>
    '''

    def __init__(self, subject, parent: SettingsView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "settingsPaneProviders"