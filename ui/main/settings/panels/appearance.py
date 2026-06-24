from __future__ import annotations
from typing import TYPE_CHECKING, List
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.settings.settings import SettingsView
    from ui.app import UiApp


class SettingPanelAppearance(ModelView):
    DOM_ELEMENT_CLASS = "settings-pane"
    TEMPLATE_STR = '''
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title" data-i18n="settings_section_appearance_title">Appearance</div>
                <div class="settings-section-meta" data-i18n="settings_section_appearance_meta">Theme, accent colors, and visual style.</div>
            </div>
        </div>
        <div class="settings-field">
            <label data-i18n="settings_label_theme">Theme</label>
            <div id="themePickerGrid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:4px">
                <button type="button" data-theme-val="light" onclick="pyview.set_theme('light')" class="theme-pick-btn{{ ' active' if pyview._current_theme == 'light' else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                <div style="width:100%;height:40px;border-radius:6px;background:#fff;border:1px solid rgba(0,0,0,.12);margin-bottom:6px;display:flex;align-items:center;justify-content:center">
                    <svg width="16" height="16" fill="none" stroke="#999" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                </div>
                <span style="font-size:12px;font-weight:500;color:var(--text)">Light</span>
                </button>
                <button type="button" data-theme-val="dark" onclick="pyview.set_theme('dark')" class="theme-pick-btn{{ ' active' if pyview._current_theme == 'dark' else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                <div style="width:100%;height:40px;border-radius:6px;background:#1a1a2e;border:1px solid rgba(255,255,255,.1);margin-bottom:6px;display:flex;align-items:center;justify-content:center">
                    <svg width="16" height="16" fill="none" stroke="#666" stroke-width="2" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/></svg>
                </div>
                <span style="font-size:12px;font-weight:500;color:var(--text)">Dark</span>
                </button>
                <button type="button" data-theme-val="system" onclick="pyview.set_theme('system')" class="theme-pick-btn{{ ' active' if pyview._current_theme == 'system' else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                <div style="width:100%;height:40px;border-radius:6px;background:linear-gradient(to right,#fff,#1a1a2e);border:1px solid rgba(0,0,0,.12);margin-bottom:6px;display:flex;align-items:center;justify-content:center">
                    <svg width="16" height="16" fill="none" stroke="#888" stroke-width="2" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
                </div>
                <span style="font-size:12px;font-weight:500;color:var(--text)">System</span>
                </button>
            </div>
            <input type="hidden" id="settingsTheme" value="{{ pyview._current_theme }}">
        </div>
        <div class="settings-field">
            <label data-i18n="settings_label_skin">Skin</label>
            <div id="skinPickerGrid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:4px">
                {% for name in pyview._skin_names %}
                <button type="button" data-skin-val="{{ name }}" onclick="pyview.set_skin('{{ name }}')" class="skin-pick-btn{{ ' active' if name == pyview._current_skin else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                    <div style="width:100%;height:36px;border-radius:6px;background:{{ pyview._skin_accent(name) }};border:1px solid var(--border);margin-bottom:6px"></div>
                    <span style="font-size:11px;font-weight:500;color:var(--text)">{{ name | capitalize }}</span>
                </button>
                {% endfor %}
            </div>
            <input type="hidden" id="settingsSkin" value="{{ pyview._current_skin }}">
        </div>
        <div class="settings-field">
            <label data-i18n="settings_label_font_size">Font size</label>
            <div id="fontSizePickerGrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px">
                <button type="button" data-font-size-val="small" onclick="pyview.set_font_size('small')" class="font-size-pick-btn{{ ' active' if pyview._current_size == 'small' else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                    <div style="width:100%;height:40px;border-radius:6px;background:var(--surface);border:1px solid var(--border);margin-bottom:6px;display:flex;align-items:center;justify-content:center">
                        <span style="font-size:10px;font-weight:600;color:var(--muted)">Aa</span>
                    </div>
                    <span style="font-size:12px;font-weight:500;color:var(--text)" data-i18n="font_size_small">Small</span>
                </button>
                <button type="button" data-font-size-val="default" onclick="pyview.set_font_size('default')" class="font-size-pick-btn{{ ' active' if pyview._current_size == 'default' else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                    <div style="width:100%;height:40px;border-radius:6px;background:var(--surface);border:1px solid var(--border);margin-bottom:6px;display:flex;align-items:center;justify-content:center">
                        <span style="font-size:13px;font-weight:600;color:var(--muted)">Aa</span>
                    </div>
                    <span style="font-size:12px;font-weight:500;color:var(--text)" data-i18n="font_size_default">Default</span>
                </button>
                <button type="button" data-font-size-val="large" onclick="pyview.set_font_size('large')" class="font-size-pick-btn{{ ' active' if pyview._current_size == 'large' else '' }}" style="border:1px solid var(--border2);border-radius:10px;padding:10px 8px;text-align:center;cursor:pointer;background:none;transition:all .15s">
                    <div style="width:100%;height:40px;border-radius:6px;background:var(--surface);border:1px solid var(--border);margin-bottom:6px;display:flex;align-items:center;justify-content:center">
                        <span style="font-size:17px;font-weight:600;color:var(--muted)">Aa</span>
                    </div>
                    <span style="font-size:12px;font-weight:500;color:var(--text)" data-i18n="font_size_large">Large</span>
                </button>
            </div>
            <input type="hidden" id="settingsFontSize" value="{{ pyview._current_size }}">
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsWorkspacePanelOpen" style="width:15px;height:15px;accent-color:var(--accent)"{{ ' checked' if pyview._workspace_open else '' }} onclick="pyview.toggle_workspace_panel()">
                <span data-i18n="settings_label_workspace_panel_open">Keep workspace panel open by default</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_workspace_panel_open">When enabled, the workspace / file browser panel opens automatically with each new session. You can still close it manually at any time.</div>
        </div>
        <div id="settingsAppearanceAutosaveStatus" class="settings-autosave-status" aria-live="polite"></div>
        <script>
            (function() {
                var root = document.documentElement;

                function applyTheme() {
                    var el = document.getElementById("settingsTheme");
                    if (!el) return;
                    var theme = el.value;
                    if (theme === "dark") {
                        root.classList.add("dark");
                    } else if (theme === "light") {
                        root.classList.remove("dark");
                    } else {
                        var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
                        root.classList.toggle("dark", prefersDark);
                    }
                }

                function applySkin() {
                    var el = document.getElementById("settingsSkin");
                    if (!el) return;
                    root.setAttribute("data-skin", el.value);
                }

                function applyFontSize() {
                    var el = document.getElementById("settingsFontSize");
                    if (!el) return;
                    root.setAttribute("data-font-size", el.value);
                }

                applyTheme();
                applySkin();
                applyFontSize();
            })();
        </script>
    '''

    _skin_names: List[str] = [
        "default", "ares", "mono", "slate",
        "poseidon", "sisyphus", "charizard", "sienna",
    ]

    _skin_accent_colors: dict = {
        "default": "#98860B",
        "ares": "#C0392B",
        "mono": "#666666",
        "slate": "#475569",
        "poseidon": "#0369A1",
        "sisyphus": "#7C3AED",
        "charizard": "#EA580C",
        "sienna": "#D97755",
    }

    @property
    def _settings(self):
        return self.subject.settings

    @property
    def _current_theme(self) -> str:
        return self._settings.theme

    @property
    def _current_skin(self) -> str:
        return self._settings.skin

    @property
    def _current_size(self) -> str:
        return self._settings.font_size

    @property
    def _workspace_open(self) -> bool:
        return self._settings.workspace_panel_open

    def _skin_accent(self, name: str) -> str:
        return self._skin_accent_colors.get(name, "#98860B")

    def __init__(self, subject: UiApp, parent: SettingsView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def set_theme(self, name: str):
        self._settings.theme = name
        self.update()

    def set_skin(self, name: str):
        self._settings.skin = name
        self.update()

    def set_font_size(self, name: str):
        self._settings.font_size = name
        self.update()

    def toggle_workspace_panel(self):
        self._settings.workspace_panel_open = not self._settings.workspace_panel_open
        self.update()
