from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.rightpanel.project.rightpanel_project import RightPanelProject

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class ProjectView(ModelView):
    RIGHTPANEL_VIEW = RightPanelProject

    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''  
        <div class="main-view-header">
            <div class="main-view-title" id="workspaceDetailTitle">{{ pyview.subject.name }}</div>
            <div class="main-view-actions">
                <button id="btnActivateWorkspaceDetail" class="panel-head-btn" title="Use this space" data-i18n-title="workspace_use_title" onclick="activateCurrentWorkspace()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                <button id="btnEditWorkspaceDetail" class="panel-head-btn" title="Rename" data-i18n-title="edit" onclick="editCurrentWorkspace()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
                <button id="btnDeleteWorkspaceDetail" class="panel-head-btn" title="Remove" data-i18n-title="remove" onclick="deleteCurrentWorkspace()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                <button id="btnCancelWorkspaceDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelWorkspaceForm()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button id="btnSaveWorkspaceDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveWorkspaceForm()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
            </div>
        </div>
        <div class="main-view-body" id="workspaceDetailBody">
            <div class="main-view-content">
                <div class="detail-card">
                    <div class="detail-card-title">Project</div>
                    <div class="detail-row"><div class="detail-row-label">Name</div><div class="detail-row-value">{{pyview.subject.name}}</div></div>
                    <div class="detail-row"><div class="detail-row-label">Path</div><div class="detail-row-value"><code>{{pyview.subject.path}}</code></div></div>
                    <div class="detail-row"><div class="detail-row-label">Description</div><div class="detail-row-value">{{pyview.subject.description}}</div></div>
                    <div class="detail-row"><div class="detail-row-label">Created</div><div class="detail-row-value">{{pyview.subject.created_at}}</div></div>
                    <div class="detail-row"><div class="detail-row-label">Status</div><div class="detail-row-value"><span class="detail-badge">Inactive</span></div></div>
                </div>
                <div class="detail-card" style="margin-top:12px">
                    <div class="detail-card-title">Checkpoints</div>
                    <div id="checkpointListContainer"><div style="color:var(--muted);font-size:12px;padding:8px 0">No checkpoints found for this workspace.</div></div>
                </div>
            </div>
        </div>
        <div class="main-view-empty" id="workspaceDetailEmpty" style="display:None">
            <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <div class="main-view-empty-title" data-i18n="workspaces_empty_title">Select a space</div>
            <div class="main-view-empty-sub" data-i18n="workspaces_empty_sub">Pick a space from the sidebar to view its files and settings, or add a new one.</div>
        </div>
    '''

    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

