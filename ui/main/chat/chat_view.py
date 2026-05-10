from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class ChatView(ModelView):
    DOM_ELEMENT_CLASS = 'main-view'
    TEMPLATE_STR = '''
        <div id="mainChat" class="main-view">
            <div class="messages" id="messages">
                <button id="scrollToBottomBtn" class="scroll-to-bottom-btn" aria-label="Scroll to bottom" onclick="scrollToBottom()" style="display:none">↓</button>
                <div class="empty-state" id="emptyState">
                    <div class="empty-logo">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="80" height="80" aria-label="Hermes caduceus">
                        <defs>
                            <linearGradient id="hermes-gold" x1="0%" y1="0%" x2="0%" y2="100%">
                                <stop offset="0%" style="stop-color:#F5C542;stop-opacity:1"/>
                                <stop offset="100%" style="stop-color:#D4961C;stop-opacity:1"/>
                            </linearGradient>
                        </defs>
                        <rect x="30" y="10" width="4" height="46" rx="2" fill="url(#hermes-gold)"/>
                        <path d="M30 18 C24 14, 14 14, 10 18 C14 16, 22 16, 28 20" fill="#F5C542" opacity="0.9"/>
                        <path d="M30 22 C26 19, 18 19, 14 22 C18 20, 24 20, 28 24" fill="#D4961C" opacity="0.8"/>
                        <path d="M34 18 C40 14, 50 14, 54 18 C50 16, 42 16, 36 20" fill="#F5C542" opacity="0.9"/>
                        <path d="M34 22 C38 19, 46 19, 50 22 C46 20, 40 20, 36 24" fill="#D4961C" opacity="0.8"/>
                        <path d="M32 48 C22 44, 20 38, 26 34 C20 36, 18 42, 24 46 C18 40, 22 30, 30 28 C24 32, 22 38, 28 42" fill="none" stroke="#F5C542" stroke-width="2.5" stroke-linecap="round"/>
                        <path d="M32 48 C42 44, 44 38, 38 34 C44 36, 46 42, 40 46 C46 40, 42 30, 34 28 C40 32, 42 38, 36 42" fill="none" stroke="#D4961C" stroke-width="2.5" stroke-linecap="round"/>
                        <circle cx="32" cy="10" r="4" fill="#F5C542"/>
                        <circle cx="32" cy="10" r="2" fill="#FFF8E1" opacity="0.7"/>
                    </svg>
                    </div>
                    <h2 data-i18n="empty_title">What can I help with?</h2>
                    <p data-i18n="empty_subtitle">Ask anything, run commands, explore files, or manage your scheduled tasks.</p>
                    <div class="suggestion-grid">
                    <button class="suggestion" data-msg="What files are in this workspace?">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span data-i18n="suggest_files">What files are in this workspace?</span>
                    </button>
                    <button class="suggestion" data-msg="What's on my schedule today?">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
                            <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
                            <line x1="9" y1="12" x2="15" y2="12"/>
                            <line x1="9" y1="16" x2="12" y2="16"/>
                        </svg>
                        <span data-i18n="suggest_schedule">What's on my schedule today?</span>
                    </button>
                    <button class="suggestion" data-msg="Help me plan a small project.">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>
                            <line x1="8" y1="2" x2="8" y2="18"/>
                            <line x1="16" y1="6" x2="16" y2="22"/>
                        </svg>
                        <span data-i18n="suggest_plan">Help me plan a small project.</span>
                    </button>
                    </div>
                </div>
                <div class="messages-inner" id="msgInner"></div>
                <div id="liveCompressionCards" class="live-compression-cards"></div>
                <div id="liveToolCards" style="display:none;max-width:800px;margin:0 auto;width:100%;padding:0 24px;"></div>
            </div>
            <div class="update-banner" id="updateBanner">
                <div style="display:flex;flex-direction:column;flex:1;min-width:0">
                    <span id="updateMsg"></span>
                    <a id="updateWhatsNew" href="#" target="_blank" rel="noopener" style="font-size:11px;color:var(--accent);text-decoration:underline;display:none;margin-left:8px;white-space:nowrap">What's new?</a>
                    <div id="updateError" style="display:none;font-size:12px;color:var(--error,#e05);margin-top:4px;word-break:break-word"></div>
                </div>
                <div style="display:flex;gap:8px;flex-shrink:0;flex-wrap:wrap">
                    <button class="update-btn" onclick="dismissUpdate()">Later</button>
                    <button class="update-btn update-primary" id="btnApplyUpdate" onclick="applyUpdates()">Update Now</button>
                    <button class="update-btn" id="btnForceUpdate" style="display:none;background:var(--error,#e05);color:#fff;border-color:var(--error,#e05)" onclick="forceUpdate(this)">Force update</button>
                </div>
            </div>
            <div class="reconnect-banner" id="reconnectBanner">
                <span id="reconnectMsg">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-1px">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                    <line x1="12" y1="9" x2="12" y2="13"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    A response may have been in progress when you last left. Reload messages?
                </span>
                <div style="display:flex;gap:8px;flex-shrink:0">
                    <button class="reconnect-btn" onclick="dismissReconnect()">Dismiss</button>
                    <button class="reconnect-btn" onclick="refreshSession()">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:-1px">
                        <polyline points="23 4 23 10 17 10"/>
                        <polyline points="1 20 1 14 7 14"/>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                    </svg>
                    Reload
                    </button>
                </div>
            </div>
            <div class="agent-health-banner" id="agentHealthBanner" role="alert" aria-live="assertive" hidden>
                <div class="agent-health-copy">
                    <strong id="agentHealthTitle">Hermes agent is not responding</strong>
                    <span id="agentHealthDetails">The gateway heartbeat failed. Messages may not be delivered until it comes back.</span>
                </div>
                <button class="agent-health-dismiss" id="agentHealthDismiss" type="button" onclick="dismissAgentHealthAlert()" aria-label="Dismiss Hermes agent heartbeat alert">Dismiss</button>
            </div>
            <div class="composer-wrap" id="composerWrap">
                <div class="composer-flyout">
                    <!-- Queue flyout: slides up from behind composer, same pattern as approval-card -->
                    <div id="queueCard" class="queue-card" role="region" aria-label="Queued messages" aria-live="polite">
                    <div id="queueChips" class="queue-card-inner"></div>
                    </div>
                    <div class="approval-card" id="approvalCard" role="alertdialog" aria-labelledby="approvalHeading" aria-describedby="approvalDesc">
                    <div class="approval-inner">
                        <div class="approval-header">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/>
                                <line x1="12" y1="17" x2="12.01" y2="17"/>
                            </svg>
                            <span id="approvalHeading" data-i18n="approval_heading">Approval required</span>
                        </div>
                        <div class="approval-desc" id="approvalDesc"></div>
                        <div class="approval-cmd" id="approvalCmd"></div>
                        <div class="approval-counter" id="approvalCounter" style="display:none;font-size:0.75em;opacity:0.6;margin-top:4px;"></div>
                        <div class="approval-btns">
                            <button class="approval-btn once" id="approvalBtnOnce" onclick="respondApproval('once')" title="Allow this one command (Enter)" data-i18n-title="approval_btn_once_title">
                                <span class="approval-btn-icon">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <polyline points="20 6 9 17 4 12"/>
                                </svg>
                                </span>
                                <span class="approval-btn-label" data-i18n="approval_btn_once">Allow once</span>
                                <kbd class="approval-kbd">↵</kbd>
                            </button>
                            <button class="approval-btn session" id="approvalBtnSession" onclick="respondApproval('session')" title="Allow for this session">
                                <span class="approval-btn-icon">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                </svg>
                                </span>
                                <span class="approval-btn-label" data-i18n="approval_btn_session">Allow session</span>
                            </button>
                            <button class="approval-btn always" id="approvalBtnAlways" onclick="respondApproval('always')" title="Always allow this command pattern">
                                <span class="approval-btn-icon">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                                </svg>
                                </span>
                                <span class="approval-btn-label" data-i18n="approval_btn_always">Always allow</span>
                            </button>
                            <button class="approval-btn deny" id="approvalBtnDeny" onclick="respondApproval('deny')" title="Deny — do not run this command">
                                <span class="approval-btn-icon">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <line x1="18" y1="6" x2="6" y2="18"/>
                                    <line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                                </span>
                                <span class="approval-btn-label" data-i18n="approval_btn_deny">Deny</span>
                            </button>
                            <button class="approval-btn yolo" id="approvalSkipAll" onclick="toggleYoloFromApproval()" title="Skip all approvals this session" data-i18n-title="approval_skip_all_title">
                            <span class="approval-btn-icon" aria-hidden="true">⚡</span>
                            <span class="approval-btn-label" data-i18n="approval_skip_all">Skip all</span>
                            </button>
                        </div>
                    </div>
                    </div>
                    <div class="clarify-card" id="clarifyCard" role="dialog" aria-labelledby="clarifyHeading" aria-describedby="clarifyQuestion clarifyHint">
                    <div class="clarify-inner">
                        <div class="clarify-header">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 17h.01"/>
                                <path d="M9.09 9a3 3 0 1 1 5.82 1c0 2-3 2-3 4"/>
                                <circle cx="12" cy="12" r="10"/>
                            </svg>
                            <span id="clarifyHeading" data-i18n="clarify_heading">Clarification needed</span>
                            <span class="clarify-countdown" id="clarifyCountdown"></span>
                        </div>
                        <div class="clarify-question" id="clarifyQuestion"></div>
                        <div class="clarify-choices" id="clarifyChoices"></div>
                        <div class="clarify-response">
                            <input class="clarify-input" id="clarifyInput" type="text" data-i18n-placeholder="clarify_input_placeholder" placeholder="Type your response…">
                            <button class="clarify-submit" id="clarifySubmit" onclick="respondClarify()" data-i18n="clarify_send">Send</button>
                        </div>
                        <div class="clarify-hint" id="clarifyHint" data-i18n="clarify_hint">Pick a choice, or type your own answer below.</div>
                    </div>
                    </div>
                    <div class="composer-terminal-panel" id="composerTerminalPanel" hidden>
                    <div class="composer-terminal-inner">
                        <div class="composer-terminal-resize-handle" id="terminalResizeHandle" role="separator" aria-orientation="horizontal" aria-label="Resize terminal" tabindex="0"></div>
                        <div class="composer-terminal-header">
                            <div class="composer-terminal-title">
                                <span data-i18n="terminal_title">Terminal</span>
                                <span class="composer-terminal-dot" aria-hidden="true">·</span>
                                <span id="terminalWorkspaceLabel"></span>
                            </div>
                            <div class="composer-terminal-actions">
                                <button type="button" class="composer-terminal-action" id="btnTerminalClear" onclick="clearComposerTerminal()" data-i18n="terminal_clear">Clear</button>
                                <button type="button" class="composer-terminal-action" id="btnTerminalCopy" onclick="copyComposerTerminalOutput()" data-i18n="terminal_copy_output">Copy output</button>
                                <button type="button" class="composer-terminal-action" id="btnTerminalRestart" onclick="restartComposerTerminal()" data-i18n="terminal_restart">Restart</button>
                                <button type="button" class="composer-terminal-action" id="btnTerminalCollapse" onclick="collapseComposerTerminal()" data-i18n="terminal_collapse">Collapse</button>
                                <button type="button" class="composer-terminal-action" id="btnTerminalClose" onclick="closeComposerTerminal()" data-i18n="terminal_close">Close</button>
                            </div>
                        </div>
                        <div class="composer-terminal-viewport" id="terminalViewport" onclick="focusComposerTerminalInput()">
                            <div class="composer-terminal-surface" id="terminalSurface" aria-label="Workspace terminal"></div>
                        </div>
                    </div>
                    <div class="composer-terminal-dock" id="composerTerminalDock" hidden>
                        <div class="composer-terminal-dock-title">
                            <span class="composer-terminal-dock-dot" aria-hidden="true"></span>
                            <span data-i18n="terminal_title">Terminal</span>
                            <span class="composer-terminal-dot" aria-hidden="true">·</span>
                            <span id="terminalDockWorkspaceLabel"></span>
                        </div>
                        <div class="composer-terminal-actions">
                            <button type="button" class="composer-terminal-action" id="btnTerminalExpand" onclick="expandComposerTerminal()" data-i18n="terminal_expand">Expand</button>
                            <button type="button" class="composer-terminal-action" id="btnTerminalDockClose" onclick="closeComposerTerminal()" data-i18n="terminal_close">Close</button>
                        </div>
                    </div>
                    </div>
                    <div id="handoffHintContainer" class="handoff-hint-container" style="display:none;"></div>
                </div>
                <!-- Queue pill outer: same positioning wrapper as .queue-card (max-width + padding) -->
                <div class="queue-pill-outer">
                    <button id="queuePill" class="queue-pill" aria-label="Show queued messages" type="button"></button>
                </div>
                <div class="composer-box" id="composerBox">
                    <div class="cmd-dropdown" id="cmdDropdown"></div>
                    <div class="drop-hint" id="dropHint">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    Drop files to upload to workspace
                    </div>
                    <div class="attach-tray" id="attachTray"></div>
                    <div class="mic-status" id="micStatus" style="display:none"><span class="mic-dot"></span> Listening…</div>
                    <div class="voice-mode-bar" id="voiceModeBar" style="display:none">
                    <span class="voice-mode-indicator" id="voiceModeIndicator"></span>
                    <span class="voice-mode-label" id="voiceModeLabel"></span>
                    </div>
                    <textarea id="msg" rows="1" placeholder="Message Hermes…"></textarea>
                    <div class="composer-footer">
                    <div class="composer-left">
                        <input type="file" id="fileInput" multiple accept="image/*,text/*,application/pdf,application/json,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.md,.py,.js,.ts,.yaml,.yml,.toml,.csv,.sh,.txt,.log,.env,.xls,.xlsx,.doc,.docx,.zip,.tar,.gz,.tgz,.bz2,.xz" style="display:none">
                        <button class="icon-btn" id="btnAttach" title="Attach files">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                            </svg>
                        </button>
                        <button class="icon-btn mic-btn" id="btnMic" title="Dictate" data-i18n-title="voice_dictate" style="display:none">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="9" y="1" width="6" height="12" rx="3"/>
                                <path d="M5 10a7 7 0 0 0 14 0"/>
                                <line x1="12" y1="19" x2="12" y2="23"/>
                                <line x1="8" y1="23" x2="16" y2="23"/>
                            </svg>
                        </button>
                        <button class="icon-btn voice-mode-btn" id="btnVoiceMode" title="Voice mode" data-i18n-title="voice_mode_toggle" style="display:none">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <!-- Lucide audio-lines: signals two-way voice conversation, matches ChatGPT/Gemini convention. -->
                                <path d="M2 10v4"/>
                                <path d="M6 6v12"/>
                                <path d="M10 3v18"/>
                                <path d="M14 8v8"/>
                                <path d="M18 5v14"/>
                                <path d="M22 10v4"/>
                            </svg>
                        </button>
                        <div class="composer-divider" aria-hidden="true"></div>
                        <button class="yolo-pill" id="yoloPill" type="button" onclick="cmdYolo()" style="display:none" title="YOLO mode — click to disable" data-i18n-title="yolo_pill_title_active">
                        <span class="yolo-pill-icon" aria-hidden="true">⚡</span>
                        <span class="yolo-pill-label" data-i18n="yolo_pill_label">YOLO</span>
                        </button>
                        <div id="profileChipWrap" class="composer-profile-wrap">
                            <button class="composer-profile-chip profile-chip" id="profileChip" type="button" onclick="toggleProfileDropdown()" title="Switch profile">
                                <span class="composer-profile-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                                    <circle cx="12" cy="7" r="4"/>
                                </svg>
                                </span>
                                <span class="composer-profile-label" id="profileChipLabel">default</span>
                                <span class="composer-profile-chevron" aria-hidden="true">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="6 9 12 15 18 9"/>
                                </svg>
                                </span>
                            </button>
                        </div>
                        <div class="composer-ws-wrap">
                            <div class="composer-workspace-group ws-chip" id="composerWorkspaceGroup" role="group" aria-label="Workspace controls">
                                <button class="composer-workspace-files-btn" id="btnWorkspacePanelToggle" type="button" onclick="toggleWorkspacePanel()" title="Show workspace panel" aria-pressed="false" aria-label="Toggle workspace files panel">
                                <span class="composer-workspace-icon" aria-hidden="true">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                                    </svg>
                                </span>
                                </button>
                                <button class="composer-workspace-chip" id="composerWorkspaceChip" type="button" onclick="toggleComposerWsDropdown()" title="Switch workspace" disabled>
                                <span class="composer-workspace-label" id="composerWorkspaceLabel"></span>
                                <span class="composer-workspace-chevron" aria-hidden="true">
                                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <polyline points="6 9 12 15 18 9"/>
                                    </svg>
                                </span>
                                </button>
                            </div>
                        </div>
                        <button class="icon-btn composer-mobile-config-btn" id="composerMobileConfigBtn" type="button" onclick="toggleMobileComposerConfig()" title="Workspace, model, reasoning, and context settings" aria-label="Workspace, model, reasoning, and context settings" aria-haspopup="true" aria-expanded="false" aria-controls="composerMobileConfigPanel">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <line x1="4" y1="21" x2="4" y2="14"/>
                                <line x1="4" y1="10" x2="4" y2="3"/>
                                <line x1="12" y1="21" x2="12" y2="12"/>
                                <line x1="12" y1="8" x2="12" y2="3"/>
                                <line x1="20" y1="21" x2="20" y2="16"/>
                                <line x1="20" y1="12" x2="20" y2="3"/>
                                <line x1="1" y1="14" x2="7" y2="14"/>
                                <line x1="9" y1="8" x2="15" y2="8"/>
                                <line x1="17" y1="16" x2="23" y2="16"/>
                            </svg>
                            <span class="composer-mobile-ctx-badge" id="composerMobileCtxBadge" aria-hidden="true" style="display:none">0</span>
                        </button>
                        <div class="composer-model-wrap">
                            <button class="composer-model-chip" id="composerModelChip" type="button" onclick="toggleModelDropdown()" title="Conversation model">
                                <span class="composer-model-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <rect x="4" y="4" width="16" height="16" rx="2"/>
                                    <rect x="9" y="9" width="6" height="6"/>
                                    <path d="M15 2v2"/>
                                    <path d="M15 20v2"/>
                                    <path d="M2 15h2"/>
                                    <path d="M2 9h2"/>
                                    <path d="M20 15h2"/>
                                    <path d="M20 9h2"/>
                                    <path d="M9 2v2"/>
                                    <path d="M9 20v2"/>
                                </svg>
                                </span>
                                <span class="composer-model-label" id="composerModelLabel"></span>
                                <span class="composer-model-chevron" aria-hidden="true">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="6 9 12 15 18 9"/>
                                </svg>
                                </span>
                            </button>
                            <select id="modelSelect" class="composer-model-select" title="Conversation model" aria-hidden="true" tabindex="-1">
                                <optgroup label="OpenAI">
                                <option value="openai/gpt-5.4-mini">GPT-5.4 Mini</option>
                                <option value="openai/gpt-4o">GPT-4o</option>
                                <option value="openai/o3">o3</option>
                                <option value="openai/o4-mini">o4-mini</option>
                                </optgroup>
                                <optgroup label="Anthropic">
                                <option value="anthropic/claude-sonnet-4.6">Claude Sonnet 4.6</option>
                                <option value="anthropic/claude-sonnet-4-5">Claude Sonnet 4.5</option>
                                <option value="anthropic/claude-haiku-3-5">Claude Haiku 3.5</option>
                                </optgroup>
                                <optgroup label="Other">
                                <option value="google/gemini-3.1-pro-preview">Gemini 3.1 Pro Preview</option>
                                <option value="google/gemini-3-flash-preview">Gemini 3 Flash Preview</option>
                                <option value="deepseek/deepseek-v4-flash">DeepSeek V4 Flash</option>
                                <option value="deepseek/deepseek-v4-pro">DeepSeek V4 Pro</option>
                                <option value="deepseek/deepseek-chat-v3-0324">DeepSeek V3 (legacy)</option>
                                <option value="meta-llama/llama-4-scout">Llama 4 Scout</option>
                                </optgroup>
                            </select>
                        </div>
                        <div class="composer-reasoning-wrap" id="composerReasoningWrap" style="display:none">
                            <button class="composer-reasoning-chip" id="composerReasoningChip" type="button" onclick="toggleReasoningDropdown()" title="Reasoning effort level">
                                <span class="composer-reasoning-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/>
                                    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>
                                </svg>
                                </span>
                                <span class="composer-reasoning-label" id="composerReasoningLabel"></span>
                                <span class="composer-reasoning-chevron" aria-hidden="true">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="6 9 12 15 18 9"/>
                                </svg>
                                </span>
                            </button>
                        </div>
                        <div class="composer-toolsets-wrap" id="composerToolsetsWrap">
                            <button class="composer-toolsets-chip" id="composerToolsetsChip" type="button" onclick="toggleToolsetsDropdown()" title="Session toolsets">
                                <span class="composer-toolsets-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                                </svg>
                                </span>
                                <span class="composer-toolsets-label" id="composerToolsetsLabel">Global</span>
                                <span class="composer-toolsets-chevron" aria-hidden="true">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="6 9 12 15 18 9"/>
                                </svg>
                                </span>
                            </button>
                        </div>
                    </div>
                    <div class="composer-right">
                        <span class="composer-status" id="composerStatus" style="display:none"></span>
                        <div class="ctx-indicator-wrap" id="ctxIndicatorWrap" style="display:none">
                            <button class="ctx-indicator" id="ctxIndicator" type="button" aria-label="Context window usage" aria-describedby="ctxTooltip">
                                <span class="ctx-ring">
                                <svg class="ctx-ring-svg" viewBox="0 0 24 24" aria-hidden="true">
                                    <circle class="ctx-ring-track" cx="12" cy="12" r="9.75"></circle>
                                    <circle class="ctx-ring-value" id="ctxRingValue" cx="12" cy="12" r="9.75"></circle>
                                </svg>
                                <span class="ctx-ring-center" id="ctxPercent">0</span>
                                </span>
                            </button>
                            <div class="ctx-tooltip" id="ctxTooltip" role="tooltip" aria-hidden="true">
                                <div class="ctx-tooltip-title">Context window</div>
                                <div class="ctx-tooltip-line" id="ctxTooltipUsage"></div>
                                <div class="ctx-tooltip-line" id="ctxTooltipTokens"></div>
                                <div class="ctx-tooltip-line" id="ctxTooltipThreshold"></div>
                                <div class="ctx-tooltip-line" id="ctxTooltipCost" style="display:none"></div>
                                <div class="ctx-tooltip-compress" id="ctxTooltipCompress" style="display:none">
                                <button class="ctx-compress-btn" id="ctxCompressBtn" type="button"></button>
                                </div>
                            </div>
                        </div>
                        <span class="bg-badge" id="bgBadge" style="display:none" title="Background tasks running">0</span>
                        <button class="send-btn" id="btnSend" title="Send message" disabled>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="12" y1="19" x2="12" y2="5"/>
                                <polyline points="5 12 12 5 19 12"/>
                            </svg>
                        </button>
                    </div>
                    <div class="composer-mobile-config-panel" id="composerMobileConfigPanel" aria-label="Workspace, model, reasoning, and context settings">
                        <button class="composer-mobile-config-action" id="composerMobileWorkspaceAction" type="button" onclick="toggleComposerWsDropdown()" title="Switch workspace">
                            <span class="composer-workspace-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                                </svg>
                            </span>
                            <span class="composer-mobile-config-copy"><span class="composer-mobile-config-kicker" data-i18n="composer_mobile_workspace">Workspace</span><span class="composer-mobile-config-value" id="composerMobileWorkspaceLabel"></span></span>
                        </button>
                        <button class="composer-mobile-config-action" id="composerMobileModelAction" type="button" onclick="toggleModelDropdown()" title="Conversation model">
                            <span class="composer-model-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="4" y="4" width="16" height="16" rx="2"/>
                                <rect x="9" y="9" width="6" height="6"/>
                                <path d="M15 2v2"/>
                                <path d="M15 20v2"/>
                                <path d="M2 15h2"/>
                                <path d="M2 9h2"/>
                                <path d="M20 15h2"/>
                                <path d="M20 9h2"/>
                                <path d="M9 2v2"/>
                                <path d="M9 20v2"/>
                                </svg>
                            </span>
                            <span class="composer-mobile-config-copy"><span class="composer-mobile-config-kicker" data-i18n="composer_mobile_model">Model</span><span class="composer-mobile-config-value" id="composerMobileModelLabel"></span></span>
                        </button>
                        <button class="composer-mobile-config-action" id="composerMobileReasoningAction" type="button" onclick="toggleReasoningDropdown()" title="Reasoning effort level" style="display:none">
                            <span class="composer-reasoning-icon" aria-hidden="true">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/>
                                <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>
                                </svg>
                            </span>
                            <span class="composer-mobile-config-copy"><span class="composer-mobile-config-kicker" data-i18n="composer_mobile_reasoning">Reasoning</span><span class="composer-mobile-config-value" id="composerMobileReasoningLabel"></span></span>
                        </button>
                        <div class="composer-mobile-config-action composer-mobile-context-action" id="composerMobileContextAction" role="group" aria-label="Context window" style="display:none">
                            <span class="composer-mobile-config-copy composer-mobile-context-copy">
                            <span class="composer-mobile-config-kicker" data-i18n="composer_mobile_context">Context</span>
                            <span class="composer-mobile-config-value" id="composerMobileContextUsage"></span>
                            <span class="composer-mobile-context-detail" id="composerMobileContextTokens"></span>
                            <span class="composer-mobile-context-detail" id="composerMobileContextThreshold"></span>
                            <span class="composer-mobile-context-detail" id="composerMobileContextCost" style="display:none"></span>
                            </span>
                            <button class="ctx-compress-btn composer-mobile-context-compress" id="composerMobileCtxCompressBtn" type="button" style="display:none"></button>
                        </div>
                    </div>
                    <div class="profile-dropdown" id="profileDropdown"></div>
                    <div class="ws-dropdown ws-dropdown-footer" id="composerWsDropdown"></div>
                    <div class="composer-reasoning-dropdown" id="composerReasoningDropdown">
                        <div class="reasoning-option" data-effort="none">None</div>
                        <div class="reasoning-option" data-effort="minimal">Minimal</div>
                        <div class="reasoning-option" data-effort="low">Low</div>
                        <div class="reasoning-option" data-effort="medium">Medium</div>
                        <div class="reasoning-option" data-effort="high">High</div>
                        <div class="reasoning-option" data-effort="xhigh">Extra High</div>
                    </div>
                    <div class="composer-toolsets-dropdown" id="composerToolsetsDropdown">
                        <div class="toolsets-dropdown-desc" id="toolsetsDropdownDesc"></div>
                        <div class="toolsets-dropdown-state" id="toolsetsDropdownState"></div>
                        <div class="toolsets-dropdown-input-row">
                            <input type="text" id="toolsetsInput" class="toolsets-input" placeholder="" autocomplete="off">
                        </div>
                        <div class="toolsets-dropdown-actions">
                            <button type="button" class="toolsets-action-btn toolsets-apply-btn" id="toolsetsApplyBtn">Apply</button>
                            <button type="button" class="toolsets-action-btn toolsets-clear-btn" id="toolsetsClearBtn">Clear (global)</button>
                        </div>
                    </div>
                    <div class="model-dropdown" id="composerModelDropdown"></div>
                    </div>
                    <div class="upload-bar-wrap" id="uploadBarWrap">
                    <div class="upload-bar" id="uploadBar"></div>
                    </div>
                </div>
            </div>
        </div>
    '''
    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)