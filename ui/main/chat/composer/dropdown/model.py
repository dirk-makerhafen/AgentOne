from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.aimodel_picker import model_groups
from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter

class ModelDropdownOption(ModelView):
    TEMPLATE_STR = '''
        <div class="model-opt-top">
            <span class="model-opt-name">{{ pyview.subject.name }}</span>
            {% if pyview.subject.provider_count > 1 %}
            <span class="model-opt-count">{{ pyview.subject.provider_count }} providers</span>
            {% endif %}
        </div>
        <span class="model-opt-providers">{{ pyview.providers_label }}</span>
    '''
    @property
    def providers_label(self) -> str:
        """Comma-separated list of providers serving this model."""
        return ", ".join(
            sorted({member.api_provider.name for member in self.subject.members})
        )

    @property
    def DOM_ELEMENT_CLASS(self):
        current = self.parent.parent.subject.aimodel
        active = current is not None and current.name == self.subject.name
        return f'model-opt {"active" if active else ""}'

    @property
    def DOM_ELEMENT_EXTRAS(self):
        name = self.subject.name.replace("\\", "\\\\").replace("'", "\\'")
        return f'onclick="set_model_group(\'{name}\')"'

class ModelDropdown(ModelView):
    TEMPLATE_STR = '''
        <div class="model-scope-note">Applies to this conversation from your next message.</div>
        <div class="model-search-row">
            <input id="input_{{pyview.uid}}" class="model-search-input" type="text" placeholder="Search models…" spellcheck="false" autocomplete="off"  oninput="pyview.filter_models(document.getElementById('input_{{pyview.uid}}').value)">
            <button class="model-search-clear" title="Clear search">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="model-group model-custom-sep">Custom model ID</div>
        <div class="model-custom-row">
            <input class="model-custom-input" type="text" placeholder="e.g. openai/gpt-5.4" spellcheck="false" autocomplete="off">
            <button class="model-custom-btn" title="Use this model">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            </button>
        </div>
        <div class="model-group">Configured</div>
        
        {{ pyview.model_list.render() }}
        <script>
            document.getElementById('{{pyview.uid}}').style.left = document.getElementById('{{pyview.parent.model_wrap.uid}}').offsetLeft + "px";
            function set_model_group(name){
                pyview.set_model_group(name);
            }
        </script>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'model-dropdown {"open" if self.open else ""}'

    def __init__(self, subject: Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open = False
        self.search_string = ""
        self.model_list = QuerySetView(
            subject=model_groups(),
            parent=self,
            item_class=ModelDropdownOption,
            filter_function=self._filter_function  
        )
    
    def set_model_group(self, name):
        self.subject.set_aimodel_by_name(name)
        self.open = False
        self.parent.model_wrap.update()
        self.update()

    def toggle(self):
        if not self.open:
            self.parent.close_dropdowns()
        self.open = not self.open
        self.update()

    def close(self):
        if self.open:
            self.open = False
            self.update()

    def _filter_function(self, item: ModelDropdownOption):
        if not self.search_string:
            return False
        if self.search_string in item.subject.name:
            return False
        return all(
            self.search_string not in member.api_provider.name
            for member in item.subject.members
        )

    def filter_models(self, searchstring):
        self.search_string = searchstring
        self.model_list.update()