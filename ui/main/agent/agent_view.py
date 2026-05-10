from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class AgentView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div id="mainProfiles" class="main-view">
            <div class="main-view-header">
                <div class="main-view-title" id="profileDetailTitle"></div>
                <div class="main-view-actions">
                <button id="btnActivateProfileDetail" class="panel-head-btn" title="Activate" data-i18n-title="profile_switch_title" onclick="activateCurrentProfile()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                <button id="btnDeleteProfileDetail" class="panel-head-btn" title="Delete" data-i18n-title="profile_delete_title" onclick="deleteCurrentProfile()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                <button id="btnCancelProfileDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelProfileForm()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button id="btnSaveProfileDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveProfileForm()" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                </div>
            </div>
            <div class="main-view-body" id="profileDetailBody">
                <div class="main-view-content">
                    <div class="detail-card">
                        <div class="detail-card-title">Agent Profile</div>
                        <div class="detail-row">
                            <div class="detail-row-label">Status</div>
                            <div class="detail-row-value"><span class="detail-badge active">ACTIVE</span> <span class="detail-badge">(default)</span> </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Gateway</div>
                            <div class="detail-row-value"><span class="detail-badge">Gateway stopped</span></div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Model</div>
                            <div class="detail-row-value"><code>gemma4:e4b</code>
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Provider</div>
                            <div class="detail-row-value">ollama-launch</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">API key</div>
                            <div class="detail-row-value">API keys configured</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Skills</div>
                            <div class="detail-row-value">89 skills</div>
                        </div>
                    </div>
                </div>
            
            </div>
            <div class="main-view-empty" id="profileDetailEmpty">
                <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <div class="main-view-empty-title" data-i18n="profiles_empty_title">Select a profile</div>
                <div class="main-view-empty-sub" data-i18n="profiles_empty_sub">Pick an agent profile from the sidebar to view and edit its settings, or create a new one.</div>
            </div>
        </div>
    '''

    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
