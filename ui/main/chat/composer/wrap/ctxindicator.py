from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter


class CtxIndicatorWrap(ModelView):
    DOM_ELEMENT_CLASS = 'ctx-indicator-wrap'
    TEMPLATE_STR = '''
        <button class="ctx-indicator" id="ctxIndicator" type="button" aria-label="Context window usage" aria-describedby="ctxTooltip">
            <span class="ctx-ring">
                <svg class="ctx-ring-svg" viewBox="0 0 24 24" aria-hidden="true"><circle class="ctx-ring-track" cx="12" cy="12" r="9.75"></circle><circle class="ctx-ring-value" id="ctxRingValue" cx="12" cy="12" r="9.75"></circle></svg>
                <span class="ctx-ring-center" id="ctxPercent">23%</span>
            </span>
        </button>
        <div class="ctx-tooltip ctx-tooltip-active1" id="ctxTooltip" role="tooltip" aria-hidden="false">
            <div class="ctx-tooltip-title">Context window</div>
            <div class="ctx-tooltip-line" id="ctxTooltipUsage">23.6M tokens used</div>
            <div class="ctx-tooltip-line" id="ctxTooltipTokens">In: 23.1M · Out: 544.0k</div>
            <div class="ctx-tooltip-line" id="ctxTooltipThreshold" style="display: none;"></div>
            <div class="ctx-tooltip-line" id="ctxTooltipCost" style="display:none"></div>
            <div class="ctx-tooltip-compress" id="ctxTooltipCompress" style="display:none">
                <button class="ctx-compress-btn" id="ctxCompressBtn" type="button" style="display: none;"></button>
            </div>
        </div>
    '''
    def __init__(self, subject:Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def toggle(self):
        self.parent.toggleReasoningDropdown()
