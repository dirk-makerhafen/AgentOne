from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List
from runtime.session.aimodel_picker import available_aimodels, model_groups
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
                <span class="{{ pyview.count_class }}" onclick="event.stopPropagation();pyview.toggle_providers()">{{ pyview.subject.provider_count }} providers {{ pyview.pin_label }}</span>
            {% endif %}
        </div>
        {% if pyview.providers_open %}
        <ul class="model-opt-provider-list">
            {% for p in pyview.provider_rows %}
            <li class="model-opt-provider-row{% if p.active %} active{% endif %}"
                onclick="event.stopPropagation();set_specific_provider('{{ pyview.name_escaped }}', {{ p.pk }})">
                <span class="model-opt-provider-name">{{ p.name }}</span>
                {% if p.active %}<span class="model-opt-provider-check">✓</span>{% endif %}
            </li>
            {% endfor %}
        </ul>
        {% endif %}
    '''
    _providers_open = False

    @property
    def name_escaped(self) -> str:
        return self.subject.name.replace("\\", "\\\\").replace("'", "\\'")

    @property
    def providers_open(self) -> bool:
        return self._providers_open

    @property
    def count_class(self) -> str:
        return "model-opt-count" + (" model-opt-count--hide" if self._providers_open else "")

    @property
    def pin_label(self) -> str:
        return "(hide)" if self._providers_open else "▾"

    @property
    def provider_rows(self) -> List[Dict[str, object]]:
        """One row per WORKING provider — an enabled model row whose provider
        has a configured API key (or a default key)."""
        current = self.parent.parent.subject.aimodel
        usable = {(m.api_provider_id, m.name) for m in available_aimodels()}
        rows: List[Dict[str, object]] = []
        for member in sorted(self.subject.members, key=lambda m: m.api_provider.name):
            if not member.enabled or (member.api_provider_id, member.name) not in usable:
                continue
            rows.append(
                {
                    "pk": member.api_provider_id,
                    "name": member.api_provider.name,
                    "active": bool(
                        current is not None
                        and current.name == self.subject.name
                        and current.api_provider_id == member.api_provider_id
                    ),
                }
            )
        return rows

    def toggle_providers(self) -> None:
        self._providers_open = not self._providers_open
        self.update()

    @property
    def DOM_ELEMENT_CLASS(self):
        current = self.parent.parent.subject.aimodel
        active = current is not None and current.name == self.subject.name
        return f'model-opt {"active" if active else ""}'

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'onclick="set_model_group(\'{self.name_escaped}\')"'

class ModelDropdown(ModelView):
    TEMPLATE_STR = '''
        <div class="model-scope-note">Applies to this conversation from your next message.</div>
        <div class="model-search-row">
            <input id="input_{{pyview.uid}}" class="model-search-input" type="text" placeholder="Search models…" spellcheck="false" autocomplete="off"  oninput="pyview.filter_models(document.getElementById('input_{{pyview.uid}}').value)">
            <button class="model-search-clear" title="Clear search">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
       
        {{ pyview.model_list.render() }}
        <script>
            document.getElementById('{{pyview.uid}}').style.left = document.getElementById('{{pyview.parent.model_wrap.uid}}').offsetLeft + "px";
            function set_model_group(name){
                pyview.set_model_group(name);
            }
            function set_specific_provider(name, provider_id){
                pyview.set_specific_provider(name, provider_id);
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

    def set_specific_provider(self, name, provider_id):
        self.subject.set_aimodel_by_provider(name, int(provider_id))
        self.open = False
        self.parent.model_wrap.update()
        self.update()

    def toggle(self):
        if not self.open:
            self.parent.close_dropdowns()
        self.open = not self.open
        if self.open:
            self._collapse_provider_lists()
        self.update()

    def _collapse_provider_lists(self):
        # pylint: disable=protected-access
        for child in self.model_list._wrapped_data:
            if getattr(child, "_providers_open", False):
                child._providers_open = False
                child.update()

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