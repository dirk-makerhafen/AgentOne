from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView
if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter


class ToolsetsWrap(ModelView):
    DOM_ELEMENT_CLASS = 'composer-toolsets-wrap'
    TEMPLATE_STR = '''
        <button class="composer-toolsets-chip" id="composerToolsetsChip" type="button" onclick="pyview.toggle()" title="Session toolsets">
            <span class="composer-toolsets-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"> <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
            </span>
            <span class="composer-toolsets-label" id="composerToolsetsLabel">Global</span>
            <span class="composer-toolsets-chevron" aria-hidden="true">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"> <polyline points="6 9 12 15 18 9"/></svg>
            </span>
        </button>
    '''
    def __init__(self, subject:Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def toggle(self):
        self.parent.toggleToolsetsDropdown()
