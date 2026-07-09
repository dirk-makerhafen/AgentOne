
from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.settings.settings import SettingsView


class SettingPanelPerferences(ModelView):
    DOM_ELEMENT_CLASS = "settings-pane"
    TEMPLATE_STR = '''
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title" data-i18n="settings_section_preferences_title">Preferences</div>
                <div class="settings-section-meta" data-i18n="settings_section_preferences_meta">Defaults and UI behavior for AgentOne Web UI.</div>
            </div>
        </div>
        <div class="settings-field">
            <label for="settingsModel" data-i18n="settings_label_model">Default Model</label>
            <select id="settingsModel" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px"></select>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_model">Used for new conversations. Existing conversations keep their selected model.</div>
        </div>
        <div class="settings-field">
            <label for="settingsSendKey" data-i18n="settings_label_send_key">Send Key</label>
            <select id="settingsSendKey" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px">
                <option value="enter">Enter (Shift+Enter for newline)</option>
                <option value="ctrl+enter">Ctrl+Enter (Enter for newline)</option>
            </select>
        </div>
        <div class="settings-field">
            <label for="settingsLanguage" data-i18n="settings_label_language">Language</label>
            <select id="settingsLanguage" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px"></select>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsSoundEnabled" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_sound">Notification sound</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_sound">Play a sound when the assistant finishes a response.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsTtsEnabled" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_tts">Text-to-Speech for responses</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_tts">Show a speaker button on each assistant message to read it aloud using your browser's speech synthesis.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsTtsAutoRead" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_tts_auto_read">Auto-read responses aloud</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_tts_auto_read">Automatically speak each new assistant response when it finishes. Pauses when you start typing.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsVoiceModeEnabled" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_voice_mode">Hands-free voice mode button</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_voice_mode">Show the voice-mode button (audio waveform) next to the dictation mic. Lets you speak naturally — AgentOne auto-sends after a pause and reads replies aloud. Requires a browser that supports both speech recognition and TTS.</div>
        </div>
        <div class="settings-field">
            <label for="settingsTtsVoice" data-i18n="settings_label_tts_voice">Voice</label>
            <select id="settingsTtsVoice" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px">
                <option value="">Default system voice</option>
            </select>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_tts_voice">Preferred voice. Populated from your browser's available voices.</div>
        </div>
        <div class="settings-field">
            <label for="settingsTtsRate" data-i18n="settings_label_tts_rate">Speech rate</label>
            <div style="display:flex;align-items:center;gap:12px;margin-top:4px">
                <input type="range" id="settingsTtsRate" min="0.5" max="2" step="0.1" value="1" style="flex:1;accent-color:var(--accent)">
                <span id="settingsTtsRateValue" style="font-size:12px;color:var(--muted);min-width:32px;text-align:right">1.0x</span>
            </div>
        </div>
        <div class="settings-field">
            <label for="settingsTtsPitch" data-i18n="settings_label_tts_pitch">Speech pitch</label>
            <div style="display:flex;align-items:center;gap:12px;margin-top:4px">
                <input type="range" id="settingsTtsPitch" min="0" max="2" step="0.1" value="1" style="flex:1;accent-color:var(--accent)">
                <span id="settingsTtsPitchValue" style="font-size:12px;color:var(--muted);min-width:32px;text-align:right">1.0</span>
            </div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsNotificationsEnabled" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_notifications">Browser notifications</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_notifications">Show a system notification when a response completes while the tab is in the background.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsShowTokenUsage" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_token_usage">Show token usage after responses</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_token_usage">Displays input/output token count below each assistant reply. Also toggled with <code>/usage</code>.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsShowTps" style="width:15px;height:15px;accent-color:var(--accent)">
                <span>Show token speed (TPS)</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px">Displays tokens per second in assistant message headers while streaming and after a response completes. Off by default.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsSimplifiedToolCalling" style="width:15px;height:15px;accent-color:var(--accent)">
                <span>Compact tool activity</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px">Group thinking and tool calls into one collapsed activity section per assistant turn.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsApiRedact" checked style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_api_redact">Redact sensitive data in API responses</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_api_redact">Self-hosted users can disable for transparency (not recommended for shared instances).</div>
        </div>
        <div class="settings-field">
            <label for="settingsSidebarDensity" data-i18n="settings_label_sidebar_density">Sidebar density</label>
            <select id="settingsSidebarDensity" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px">
                <option value="compact" data-i18n="settings_sidebar_density_compact">Compact</option>
                <option value="detailed" data-i18n="settings_sidebar_density_detailed">Detailed</option>
            </select>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_sidebar_density">Controls how much metadata the session list shows in the left sidebar.</div>
        </div>
        <div class="settings-field">
            <label for="settingsAutoTitleRefresh" data-i18n="settings_label_auto_title_refresh">Adaptive title refresh</label>
            <select id="settingsAutoTitleRefresh" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px">
                <option value="0" data-i18n="settings_auto_title_refresh_off">Off</option>
                <option value="5" data-i18n="settings_auto_title_refresh_5">Every 5 exchanges</option>
                <option value="10" data-i18n="settings_auto_title_refresh_10">Every 10 exchanges</option>
                <option value="20" data-i18n="settings_auto_title_refresh_20">Every 20 exchanges</option>
            </select>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_auto_title_refresh">Automatically re-generates the session title based on the latest exchange, keeping it relevant as the conversation evolves. Requires an LLM title generation model to be configured.</div>
        </div>
        <div class="settings-field">
            <label for="settingsBusyInputMode" data-i18n="settings_label_busy_input_mode">Busy input mode</label>
            <select id="settingsBusyInputMode" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px">
                <option value="queue" data-i18n="settings_busy_input_mode_queue">Queue follow-up</option>
                <option value="interrupt" data-i18n="settings_busy_input_mode_interrupt">Interrupt current turn</option>
                <option value="steer" data-i18n="settings_busy_input_mode_steer">Steer (mid-turn correction)</option>
            </select>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_busy_input_mode">Controls what happens when you send a message while the agent is running. Queue waits for the current task; Interrupt cancels and starts fresh; Steer injects a mid-turn correction without interrupting (falls back to interrupt when the agent is not yet cached or the stream has ended).</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsShowCliSessions" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_external_sessions">Show non-WebUI sessions</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_external_sessions">Show conversations from CLI, Telegram, Discord, Slack, and other channels in the session list. Click to import and continue.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsSyncInsights" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_sync_insights">Sync usage to /insights</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_sync_insights">Mirrors WebUI token usage to state.db so <code>agentone /insights</code> includes browser session data. Off by default.</div>
        </div>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsCheckUpdates" style="width:15px;height:15px;accent-color:var(--accent)">
                <span data-i18n="settings_label_check_updates">Check for updates</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_check_updates">Show a banner when newer versions of the WebUI or Agent are available. Runs a background git fetch periodically.</div>
        </div>
        <div class="settings-field">
            <label for="settingsBotName" data-i18n="settings_label_bot_name">Assistant Name</label>
            <div style="font-size:11px;color:var(--muted);margin-bottom:6px" data-i18n="settings_desc_bot_name">Display name for the assistant throughout the UI. Defaults to AgentOne.</div>
            <input type="text" id="settingsBotName" placeholder="AgentOne" maxlength="64" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px;font-size:13px">
        </div>

        <button class="sm-btn" onclick="saveSettings()" style="margin-top:12px;width:100%;padding:8px;font-weight:600" data-i18n="settings_save_btn">Save Settings</button>
        <div id="settingsPreferencesAutosaveStatus" class="settings-autosave-status" aria-live="polite"></div>
    
    '''

    def __init__(self, subject, parent: SettingsView, **kwargs):
        super().__init__(subject, parent, **kwargs)
