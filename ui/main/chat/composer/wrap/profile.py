from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.agents.session import Session
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter



class ProfileWrap(ModelView):
    DOM_ELEMENT_CLASS = 'composer-profile-wrap'
    TEMPLATE_STR = '''
        <button class="composer-profile-chip profile-chip" id="profileChip" type="button" onclick="pyview.toggle()" title="Switch profile">
            <span class="composer-profile-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </span>
            <span class="composer-profile-label" id="profileChipLabel">
               {{ pyview.subject.agent.name }}
            </span>
            <span class="composer-profile-chevron" aria-hidden="true">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
        </button>
    '''
    
    def __init__(self, subject:Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def toggle(self):
        self.parent.toggleProfileDropdown()
