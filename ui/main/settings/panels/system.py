from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.settings.settings import SettingsView


class SettingPanelSystem(ModelView):
    DOM_ELEMENT_CLASS = "settings-pane"
    TEMPLATE_STR = '''
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title" data-i18n="settings_section_system_title">System</div>
                <div class="settings-section-meta" data-i18n="settings_section_system_meta">Session version and access controls.</div>
            </div>
            <div id="checkUpdatesBlock">
                <span class="settings-version-badge" id="settings-webui-version-badge">WebUI: —</span>
                <span class="settings-version-badge" id="settings-agent-version-badge">Agent: not detected</span>
                <button class="btn-tiny" id="btnCheckUpdatesNow" onclick="checkUpdatesNow()" title="Check for updates now" data-i18n-title="settings_check_now"><svg id="checkUpdatesSpinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spinner-xs" aria-hidden="true"><path d="M21 12a9 9 0 1 1-6.219-8.56"/><polyline points="21 3 21 9 15 9"/></svg><span id="checkUpdatesLabel" data-i18n="settings_check_now">Check now</span></button>
                <span id="checkUpdatesStatus"></span>
            </div>
        </div>

        <div class="settings-field">
            <label for="settingsPassword" data-i18n="settings_label_password">Access Password</label>
            <div style="font-size:11px;color:var(--muted);margin-bottom:6px" data-i18n="settings_desc_password">Enter a new password to set or change it. Leave blank to keep current setting.</div>
            <input type="password" id="settingsPassword" placeholder="Enter new password…" data-i18n-placeholder="password_placeholder" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px;font-size:13px">
            <div id="settingsPasswordEnvLock" data-i18n="password_env_var_locked" style="display:none;margin-top:6px;padding:8px 10px;font-size:11px;color:var(--muted);background:var(--code-bg);border:1px solid var(--border2);border-radius:6px;line-height:1.45">The HERMES_WEBUI_PASSWORD environment variable is currently set and takes precedence. Unset it and restart the server to manage the password from here.</div>
        </div>

        <button class="sm-btn" id="btnDisableAuth" onclick="disableAuth()" style="margin-top:6px;width:100%;padding:8px;font-weight:600;color:#e8a030;border-color:rgba(232,160,48,.3);display:none" data-i18n="disable_auth">Disable Auth</button>
        <button class="sm-btn" id="btnSignOut" onclick="signOut()" style="margin-top:6px;width:100%;padding:8px;font-weight:600;color:var(--accent);border-color:rgba(233,69,96,.3);display:none" data-i18n="sign_out">Sign Out</button>
        
        <div class="settings-field" style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border)">
            <label for="settingsDashboardMode">Official Hermes Dashboard</label>
            <div style="font-size:11px;color:var(--muted);margin-bottom:8px">Show a nav-rail link when the official <code>hermes dashboard</code> is reachable. Overrides are restricted to loopback URLs.</div>
            <select id="settingsDashboardMode" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px">
                <option value="auto">Auto-detect</option>
                <option value="always">Always show</option>
                <option value="never">Never show</option>
            </select>
            <input type="text" id="settingsDashboardUrl" placeholder="http://127.0.0.1:9119" style="margin-top:8px;width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px;font-size:13px">
            <button class="sm-btn" onclick="saveDashboardSettings()" style="margin-top:8px;width:100%;padding:7px;font-weight:600">Save dashboard link settings</button>
            <div id="settingsDashboardStatus" class="settings-autosave-status" aria-live="polite"></div>
        </div>

        <!-- Gateway Status Section -->
        <div class="settings-field" style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border)">
            <label>Gateway Status</label>
            <div style="font-size:11px;color:var(--muted);margin-bottom:8px">Status of the Hermes gateway (Telegram, Discord, Slack, etc.)</div>
            <div id="gatewayStatusCard"><span style="color:var(--muted);font-size:12px">Loading…</span></div>
        </div>

        <!-- MCP Servers Section -->
        <div class="settings-field" style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border)">
            <label data-i18n="mcp_servers_title">MCP Servers</label>
            <div style="font-size:11px;color:var(--muted);margin-bottom:8px" data-i18n="mcp_servers_desc">View Model Context Protocol servers configured in config.yaml.</div>
            <div id="mcpServerList"></div>
            <div class="mcp-restart-hint" data-i18n="mcp_restart_hint">Server changes are read-only here for now. Edit config.yaml and restart Hermes for changes to take effect.</div>
        </div>

        <!-- MCP Tools Section -->
        <div class="settings-field" style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border)">
            <label data-i18n="mcp_tools_title">MCP Tools</label>
            <div style="font-size:11px;color:var(--muted);margin-bottom:8px" data-i18n="mcp_tools_desc">Search known tools across active MCP servers.</div>
            <input type="search" id="mcpToolSearch" class="mcp-tool-search" data-i18n-placeholder="mcp_tools_search_placeholder" placeholder="Search tools by name, server, or description…" oninput="filterMcpTools()" autocomplete="off">
            <div id="mcpToolList"></div>
            <div class="mcp-restart-hint" data-i18n="mcp_tools_runtime_note">Tool inventory only uses already-known active MCP runtime data; the WebUI does not start or probe servers.</div>
        </div>

        <button class="sm-btn" onclick="saveSettings()" style="margin-top:12px;width:100%;padding:8px;font-weight:600" data-i18n="settings_save_btn">Save Settings</button>
   
    '''

    def __init__(self, subject, parent: SettingsView, **kwargs):
        super().__init__(subject, parent, **kwargs)
