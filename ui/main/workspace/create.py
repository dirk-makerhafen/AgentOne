from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView

class CreateWorkspace(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''  
        <div class="main-view-header">
            <div class="main-view-title" id="workspaceDetailTitle">New Workspace</div>
            <div class="main-view-actions">
                <button id="btnCancelWorkspaceDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelWorkspaceForm()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                <button id="btnSaveWorkspaceDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveWorkspaceForm()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg></button>
            </div>
        </div>
        <div class="main-view-body" id="workspaceDetailBody" style="">
            <div class="main-view-content">
                <form class="detail-form" onsubmit="event.preventDefault(); saveWorkspaceForm();">
                    <div class="detail-form-row">
                        <label for="workspaceFormName">Name</label>
                        <input type="text" id="workspaceFormName" value="" placeholder="Optional friendly name" autocomplete="off">
                    </div>
                    <div class="detail-form-row">
                        <label for="workspaceFormPath">Path</label>
                        <div class="workspace-form-path-wrap" style="position:relative">
                            <input type="text" id="workspaceFormPath" value="" placeholder="Add workspace path (e.g. /home/user/my-project)" autocomplete="off" required="">
                            <div id="workspaceFormPathSuggestions" class="ws-suggestions" style="display:none"></div>
                        </div>
                        <div class="detail-form-hint">Paths are validated as existing directories before saving.</div>
                    </div>
                    <div id="workspaceFormError" class="detail-form-error" style="display:none"></div>
                </form>
            </div>
        </div>        
    '''