from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.chat.composer.footer import ComposerFooter


class WorkspaceWrap(PyHtmlView):
    DOM_ELEMENT_CLASS = 'composer-ws-wrap'
    TEMPLATE_STR = '''
        <div class="composer-workspace-group ws-chip" id="composerWorkspaceGroup" role="group" aria-label="Workspace controls">
            <button class="composer-workspace-files-btn" id="btnWorkspacePanelToggle" type="button" onclick="toggleWorkspacePanel()" title="Show workspace panel" aria-pressed="false" aria-label="Toggle workspace files panel">
                <span class="composer-workspace-icon" aria-hidden="true">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                </span>
            </button>
            <button class="composer-workspace-chip" id="composerWorkspaceChip" type="button" onclick="pyview.toggle()" title="Switch workspace">
                <span class="composer-workspace-label" id="composerWorkspaceLabel">
                    {{ pyview.subject.workspace.name }}
                </span>
                <span class="composer-workspace-chevron" aria-hidden="true">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </span>
            </button>
        </div>
    '''
    def __init__(self, subject: Session, parent: ComposerFooter, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def toggle(self):
        self.parent.toggleComposerWsDropdown()
