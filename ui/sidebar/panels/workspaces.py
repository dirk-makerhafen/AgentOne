from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelWorkspace(ModelView):
    DOM_ELEMENT_CLASS = "ws-row"    
    #<div class="ws-row" data-path="/Users/Dirk/AgentOne" draggable="true">
    TEMPLATE_STR = '''
        <span class="ws-drag-handle" title="Drag to reorder"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><circle cx="9" cy="5" r="1"></circle><circle cx="9" cy="12" r="1"></circle><circle cx="9" cy="19" r="1"></circle><circle cx="15" cy="5" r="1"></circle><circle cx="15" cy="12" r="1"></circle><circle cx="15" cy="19" r="1"></circle></svg></span>
        <div class="ws-row-info">
            <div class="ws-row-name">
                {{ pyview.subject.name }}
                <span class="detail-badge active" style="margin-left:6px;font-size:9px;padding:1px 6px">
                    ACTIVE
                </span>
            </div>
            <div class="ws-row-path">/Users/Dirk/AgentOne</div>
        </div>
    '''
    # </div>

class SidebarPanelWorkspaces(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Workspaces panel -->
        <div class="panel-head">
            <span data-i18n="tab_workspaces">Workspaces</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="openWorkspaceCreate()" title="Add space" data-i18n-title="workspace_add_title" aria-label="Add space"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
            </div>
        </div>
        <div class="panel-head-sub" data-i18n="workspace_desc">Add and switch workspaces for your sessions.</div>
        <div style="flex:1;overflow-y:auto;padding:8px" id="workspacesPanel">
            {{ pyview.workspace_list.render() }}
        </div>
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "panelWorkspaces"
        self.root_view: UiAppView = parent.root_view

        self.workspace_list = QuerySetView(
            subject=subject.agents.root(),
            parent=self,
            item_class=SidebarPanelWorkspace,
        )
