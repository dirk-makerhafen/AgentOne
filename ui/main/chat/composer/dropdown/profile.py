from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter


class ProfileDropdownOption(ModelView):
    TEMPLATE_STR = '''
        <div class="profile-opt-name">
            {{ pyview.subject.name }}
            <span style="opacity:.5;font-weight:400">(default)</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--link)" stroke-width="3" style="vertical-align:-1px"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </div>
        <div class="profile-opt-meta">
            gemma4:e4X · 89 skillsX
        </div>
    '''
    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'onclick="set_profile({self.subject.pk})"'

    @property
    def DOM_ELEMENT_CLASS(self):
        return f'profile-opt {"active" if self.parent.parent.subject.agent.name == self.subject.name else ""}'


class ProfileDropdown(PyHtmlView):
    TEMPLATE_STR = '''
        <div class="profile-scope-note">Applies to this conversation from your next message.</div>
        <div class="profile-search-row">
            <input id="input_{{pyview.uid}}" class="profile-search-input" type="text" placeholder="Search agents.." spellcheck="false" autocomplete="off"  oninput="pyview.filter_agents(document.getElementById('input_{{pyview.uid}}').value)">
            <button class="profile-search-clear" title="Clear search">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>

        {{ pyview.profile_list.render() }}

        <div class="ws-divider"></div>

        <div class="profile-opt ws-manage">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Manage profiles
        </div>
        <script>
            document.getElementById('{{pyview.uid}}').style.left = document.getElementById('{{pyview.anchor_uid}}').offsetLeft + "px";
            function set_profile(pk){
                pyview.set_profile(pk);
            }
        </script>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'profile-dropdown {"open" if self.open else ""}{" rp-open-down" if self.open_downward else ""}'

    def __init__(self, subject: Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open = False
        self.open_downward = False
        self.search_string = ""
        models = AgentModel.objects.all()
        self.profile_list = QuerySetView(
            subject=models,
            parent=self,
            item_class=ProfileDropdownOption,
            filter_function=self._filter_function
        )

    def _refresh_selection(self) -> None:
        wrap = getattr(self.parent, "profile_wrap", None)
        if wrap is not None:
            wrap.update()
            return
        if hasattr(self.parent, "update"):
            self.parent.update()

    @property
    def anchor_uid(self) -> str:
        wrap = getattr(self.parent, "profile_wrap", None)
        if wrap is not None:
            return wrap.uid
        return self.uid

    def set_profile(self, pk):
        self.subject.set_agent(AgentModel.objects.get(pk=int(pk)))
        self.open = False
        self._refresh_selection()
        self.update()

    def toggle(self):
        close = getattr(self.parent, "close_dropdowns", None)
        if not self.open and close is not None:
            close()
        self.open = not self.open
        self.update()

    def close(self):
        if self.open:
            self.open = False
            self.update()

    def _filter_function(self, item:ProfileDropdownOption):
        return self.search_string not in item.subject.name or not item.subject.is_user_visible

    def filter_agents(self, searchstring):
        self.search_string = searchstring
        self.profile_list.update()
