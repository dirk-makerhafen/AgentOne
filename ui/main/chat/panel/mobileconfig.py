
from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


class MobileConfigPanel(PyHtmlView):
    DOM_ELEMENT_CLASS = 'composer-mobile-config-panel'
    DOM_ELEMENT_EXTRAS = 'aria-label="Workspace, model, reasoning, and context settings"'
    TEMPLATE_STR = '''
        <button class="composer-mobile-config-action" id="composerMobileWorkspaceAction" type="button" onclick="toggleComposerWsDropdown()" title="Switch workspace">
            <span class="composer-workspace-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </span>
            <span class="composer-mobile-config-copy"><span class="composer-mobile-config-kicker" data-i18n="composer_mobile_workspace">Workspace</span><span class="composer-mobile-config-value" id="composerMobileWorkspaceLabel"></span></span>
        </button>
        <button class="composer-mobile-config-action" id="composerMobileModelAction" type="button" onclick="toggleModelDropdown()" title="Conversation model">
            <span class="composer-model-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>
            </span>
            <span class="composer-mobile-config-copy"><span class="composer-mobile-config-kicker" data-i18n="composer_mobile_model">Model</span><span class="composer-mobile-config-value" id="composerMobileModelLabel"></span></span>
        </button>
        <button class="composer-mobile-config-action" id="composerMobileReasoningAction" type="button" onclick="toggleReasoningDropdown()" title="Reasoning effort level" style="display:none1">
            <span class="composer-reasoning-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>
            </span>
            <span class="composer-mobile-config-copy"><span class="composer-mobile-config-kicker" data-i18n="composer_mobile_reasoning">Reasoning</span><span class="composer-mobile-config-value" id="composerMobileReasoningLabel"></span></span>
        </button>
        <div class="composer-mobile-config-action composer-mobile-context-action" id="composerMobileContextAction" role="group" aria-label="Context window" style="display:none1">
            <span class="composer-mobile-config-copy composer-mobile-context-copy">
            <span class="composer-mobile-config-kicker" data-i18n="composer_mobile_context">Context</span>
            <span class="composer-mobile-config-value" id="composerMobileContextUsage"></span>
            <span class="composer-mobile-context-detail" id="composerMobileContextTokens"></span>
            <span class="composer-mobile-context-detail" id="composerMobileContextThreshold"></span>
            <span class="composer-mobile-context-detail" id="composerMobileContextCost" style="display:none1"></span>
            </span>
            <button class="ctx-compress-btn composer-mobile-context-compress" id="composerMobileCtxCompressBtn" type="button" style="display:none1"></button>
        </div>
    
    '''
