
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
            <select id="settingsModel" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px" onchange="pyview.set_default_model(this.value)">
                <option value=""{% if not pyview._default_model %} selected{% endif %} data-i18n="settings_desc_model_none">— None (use agent default) —</option>
                {% for model in pyview._model_options %}
                <option value="{{ model.name }}"{% if model.name == pyview._default_model %} selected{% endif %}>{{ model.name }}</option>
                {% endfor %}
            </select>
            <div style="font-size:11px;color:var(--muted);margin-top:4px" data-i18n="settings_desc_model">Used for new conversations. Existing conversations keep their selected model. Also used when an agent's model.md declares <code>model: default</code> or no model.</div>
        </div>
        <div class="settings-field">
            <label for="settingsSendKey" data-i18n="settings_label_send_key">Send Key</label>
            <select id="settingsSendKey" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px" onchange="pyview.set_send_key(this.value)">
                <option value="ctrl+enter"{% if pyview._send_key == 'ctrl+enter' %} selected{% endif %}>Ctrl+Enter (Enter for newline)</option>
                <option value="enter"{% if pyview._send_key == 'enter' %} selected{% endif %}>Enter (Shift+Enter for newline)</option>
            </select>
        </div>
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title">Power &amp; Battery</div>
                <div class="settings-section-meta">Keeps a macOS laptop awake during local model inference and protects the battery.</div>
            </div>
        </div>
        <div class="settings-field" id="settingsPowerStatus">
            <div style="display:flex;gap:18px;flex-wrap:wrap;font-size:13px">
                <div>Battery: <b id="powerBattery">…</b></div>
                <div>Power source: <b id="powerSource">…</b></div>
                <div>Sleep prevention: <b id="powerSleep">…</b></div>
                <div>Local AI: <b id="powerPause">…</b></div>
            </div>
            <div style="font-size:11px;color:var(--muted);margin-top:4px">Refreshed every 30 seconds.</div>
        </div>
        <script>
        (function(){
            if (window.__agentonePowerPoll) { clearInterval(window.__agentonePowerPoll); window.__agentonePowerPoll = null; }
            var refreshPowerStatus = function(){
                var root = document.getElementById('settingsPowerStatus');
                if (!root) return;
                pyview.get_power_status().then(function(data){
                    var s = data || {};
                    var el = document.getElementById('powerBattery');
                    if (el) el.textContent = (s.battery_percent == null) ? '—' : s.battery_percent + '%';
                    el = document.getElementById('powerSource');
                    if (el) el.textContent = s.source || '—';
                    el = document.getElementById('powerSleep');
                    if (el) {
                        if (s.sleep_state === 'active') el.textContent = 'Active now';
                        else if (s.sleep_state === 'ready') el.textContent = 'Armed — activates during local calls';
                        else if (s.sleep_state === 'battery_low') el.textContent = 'Off — battery below ' + s.min_caffeinate_pct + '%';
                        else if (s.sleep_state === 'disabled') el.textContent = 'Disabled';
                        else el.textContent = 'Unavailable';
                    }
                    el = document.getElementById('powerPause');
                    if (el) {
                        if (s.paused) el.textContent = 'Paused — battery below ' + s.pause_local_pct + '%';
                        else el.textContent = 'OK';
                    }
                });
            };
            refreshPowerStatus();
            window.__agentonePowerPoll = setInterval(refreshPowerStatus, 30000);
        })();
        </script>
        <div class="settings-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
                <input type="checkbox" id="settingsPreventSleep" style="width:15px;height:15px;accent-color:var(--accent)"{% if pyview._prevent_sleep_when_local_ai %} checked{% endif %} onchange="pyview.set_prevent_sleep_when_local_ai(this.checked)">
                <span>Keep system awake while local AI is working</span>
            </label>
            <div style="font-size:11px;color:var(--muted);margin-top:4px">Prevents the Mac from sleeping (<code>caffeinate</code>) during local model generation so it is not interrupted mid-inference. Only active while a local model call is running.</div>
        </div>
        <div class="settings-field">
            <label for="settingsMinBatteryCaffeinate">Minimum battery for sleep prevention</label>
            <input type="number" id="settingsMinBatteryCaffeinate" min="0" max="100" step="1" value="{{ pyview._min_battery_pct_for_caffeinate }}" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px;font-size:13px" onchange="pyview.set_min_battery_pct_for_caffeinate(this.value)">
            <div style="font-size:11px;color:var(--muted);margin-top:4px">On battery power, sleep prevention only kicks in while remaining charge is at least this percent. On power supply it is always active.</div>
        </div>
        <div class="settings-field">
            <label for="settingsPauseBattery">Pause local AI below battery</label>
            <input type="number" id="settingsPauseBattery" min="0" max="100" step="1" value="{{ pyview._pause_local_ai_below_battery_pct }}" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px;font-size:13px" onchange="pyview.set_pause_local_ai_below_battery_pct(this.value)">
            <div style="font-size:11px;color:var(--muted);margin-top:4px">On battery power, when charge drops below this percent local model tasks pause and wait until you plug in or charge back above the threshold. Cloud/remote models are unaffected.</div>
        </div>
        <div class="settings-field">
            <label for="settingsGuardTimeout">Keep-awake grace period (minutes)</label>
            <input type="number" id="settingsGuardTimeout" min="0" max="120" step="1" value="{{ pyview._sleep_guard_release_delay_minutes }}" style="width:100%;padding:8px;background:var(--code-bg);color:var(--text);border:1px solid var(--border2);border-radius:6px;font-size:13px" onchange="pyview.set_sleep_guard_release_delay_minutes(this.value)">
            <div style="font-size:11px;color:var(--muted);margin-top:4px">After the last local model call finishes, keep the system awake for this many more minutes so back-to-back calls don't sleep/wake the machine in between. 0 = release immediately.</div>
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

    @property
    def _settings(self):
        return self.subject.settings

    @property
    def _model_options(self):
        from server.models.providers.ai_model import AiModel
        return AiModel.objects.filter(enabled=True).order_by("name")

    @property
    def _default_model(self) -> str:
        return self._settings.default_model

    @property
    def _send_key(self) -> str:
        return self._settings.send_key

    @property
    def _prevent_sleep_when_local_ai(self) -> bool:
        return self._settings.prevent_sleep_when_local_ai

    @property
    def _min_battery_pct_for_caffeinate(self) -> int:
        return self._settings.min_battery_pct_for_caffeinate

    @property
    def _pause_local_ai_below_battery_pct(self) -> int:
        return self._settings.pause_local_ai_below_battery_pct

    @property
    def _sleep_guard_release_delay_minutes(self) -> int:
        return self._settings.sleep_guard_release_delay_minutes

    def get_power_status(self):
        from runtime.power import power_state_summary
        return power_state_summary()

    def set_default_model(self, value: str):
        self._settings.default_model = value
        self.update()

    def set_send_key(self, value: str):
        self._settings.send_key = value
        self.update()

    def set_prevent_sleep_when_local_ai(self, value):
        self._settings.prevent_sleep_when_local_ai = bool(value)
        self.update()

    def set_min_battery_pct_for_caffeinate(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return
        if 0 <= value <= 100:
            self._settings.min_battery_pct_for_caffeinate = value
        self.update()

    def set_pause_local_ai_below_battery_pct(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return
        if 0 <= value <= 100:
            self._settings.pause_local_ai_below_battery_pct = value
        self.update()

    def set_sleep_guard_release_delay_minutes(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return
        if 0 <= value <= 120:
            self._settings.sleep_guard_release_delay_minutes = value
        self.update()
