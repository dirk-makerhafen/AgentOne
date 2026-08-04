from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter

class ModelWrap(ModelView):
    DOM_ELEMENT_CLASS = 'composer-model-wrap'
    TEMPLATE_STR = '''
        <button class="composer-model-chip" id="composerModelChip" type="button" onclick="pyview.toggle()" title="Conversation model">
            <span class="composer-model-icon" aria-hidden="true">    
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/> </svg>
            </span>
            <span class="composer-model-label" id="composerModelLabel">
                {% if pyview.subject.aimodel %}{{ pyview.subject.aimodel.name }}{% else %}Default{% endif %}
            </span>
            <span class="composer-model-chevron" aria-hidden="true">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/> </svg>
            </span>
        </button>
        <select id="modelSelect" class="composer-model-select" title="Conversation model" aria-hidden="true" tabindex="-1">
            <optgroup label="Other">
                <option value="meta-llama/llama-4-scout">Llama 4 Scout</option>
            </optgroup>
        </select>
    
    '''
    
    def __init__(self, subject: Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
      
    def toggle(self):
        self.parent.toggleModelDropdown()
    
