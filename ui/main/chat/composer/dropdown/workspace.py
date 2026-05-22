from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter

class WorkspaceDropdownOption(ModelView):
    TEMPLATE_STR = '''
        <span class="ws-opt-name">{{ pyview.subject.name }}</span>
        <span class="ws-opt-path">{{ pyview.subject.path }}</span>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'ws-opt {"active" if self.parent.parent.subject.workspace and self.parent.parent.subject.workspace.name == self.subject.name else ""}'

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'onclick="set_workspace({self.subject.pk})"'

class WorkspaceDropdown(ModelView):
    TEMPLATE_STR = '''
        <div class="ws-search-row">
            <input id="input_{{pyview.uid}}" class="ws-search-input" type="text" placeholder="Search workspaces…" spellcheck="false" autocomplete="off" oninput="pyview.filter_workspaces(document.getElementById('input_{{pyview.uid}}').value)">
            <button class="ws-search-clear" title="Clear search">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>

        {{ pyview.workspace_list.render() }}

        <div class="ws-divider"></div>
        <div class="ws-opt ws-opt-action">
            <span class="ws-opt-icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            </span>
            <span>
                <span class="ws-opt-name">Choose workspace path</span>
                <span class="ws-opt-meta">Add a validated path and switch this conversation</span>
            </span>
        </div>

        <div class="ws-divider"></div>

        <div class="ws-opt ws-opt-action">
            <span class="ws-opt-icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            </span>
            <span>
                <span class="ws-opt-name">Manage workspaces</span>
                <span class="ws-opt-meta">Open the Spaces panel</span>
            </span>
        </div>
        <script>
            document.getElementById('{{pyview.uid}}').style.left = document.getElementById('{{pyview.parent.workspace_wrap.uid}}').offsetLeft + "px";
            function set_workspace(pk){
                pyview.set_workspace(pk);
            }
        </script>
    '''
    @property
    def DOM_ELEMENT_CLASS(self):
        return f'ws-dropdown ws-dropdown-footer {"open" if self.open else ""}'

    def __init__(self, subject: Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open = False
        self.search_string = ""
        workspaces = WorkspaceModel.objects.all()
        self.workspace_list = QuerySetView(
            subject=workspaces,
            parent=self,
            item_class=WorkspaceDropdownOption,
            filter_function=self._filter_function,
            dom_element_class = "ws-list-container",
        )
            
    def set_workspace(self, workspace_pk):
        print("set_workspace", workspace_pk)
        self.subject.set_workspace( WorkspaceModel.objects.get(pk=int(workspace_pk)))

    def toggle(self):
        if not self.open:
            self.parent.close_dropdowns()
        self.open = not self.open
        self.update()

    def close(self):
        if self.open:
            self.open = False
            self.update()

    def _filter_function(self, item:WorkspaceDropdownOption):
        return self.search_string not in item.subject.name

    def filter_workspaces(self, searchstring):
        self.search_string = searchstring
        self.workspace_list.update()
        
