from __future__ import annotations
import os
from typing import TYPE_CHECKING
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.workspace.access_editor import AccessEditor

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView

class CreateWorkspace(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title" id="workspaceDetailTitle">New Workspace</div>
            <div class="main-view-actions">
                <button id="btnCancelWorkspaceDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="pyview.cancelWorkspaceForm()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                <button id="btnSaveWorkspaceDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="pyview.saveWorkspaceForm()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg></button>
            </div>
        </div>
        <div class="main-view-body" id="workspaceDetailBody" style="">
            <div class="main-view-content">
                <div class="detail-form">
                    <div class="detail-form-row">
                        <label for="workspaceFormName">Name</label>
                        <input type="text" id="workspaceFormName" value="{{ pyview.form.name }}" placeholder="Optional friendly name" autocomplete="off" onchange="pyview.setWsField('name', this.value)">
                    </div>
                    <div class="detail-form-row">
                        <label for="workspaceFormPath">Path</label>
                        <div class="workspace-form-path-wrap" style="position:relative">
                            <input type="text" id="workspaceFormPath" value="{{ pyview.form.path }}" placeholder="Add workspace path (e.g. /home/user/my-project)" autocomplete="off" required="" onchange="pyview.setWsField('path', this.value)">
                            <div id="workspaceFormPathSuggestions" class="ws-suggestions" style="display:none"></div>
                        </div>
                        <div class="detail-form-hint">Paths are validated as existing directories before saving.</div>
                    </div>
                    <div class="detail-form-row">
                        <label for="workspaceFormDescription">Description</label>
                        <textarea id="workspaceFormDescription" rows="3" placeholder="What is this workspace for?" onchange="pyview.setWsField('description', this.value)">{{ pyview.form.description }}</textarea>
                    </div>
                    <div class="detail-form-row">
                        <label>Filesystem access</label>
                        {{ pyview.access_editor.render() }}
                    </div>
                    {% if pyview.form_error %}
                    <div class="detail-form-error">{{ pyview.form_error }}</div>
                    {% endif %}
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form = {"name": "", "path": "", "description": ""}
        self._form_error = ""
        self.access_editor = AccessEditor(subject=subject, parent=self)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def form(self) -> dict:
        return self._form

    @property
    def form_error(self) -> str:
        return self._form_error

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def setWsField(self, field: str, value: str) -> None:
        if field in ("name", "path", "description"):
            self._form[field] = value

    def saveWorkspaceForm(self) -> None:
        name = (self._form.get("name") or "").strip()
        path = (self._form.get("path") or "").strip()
        if not path or not os.path.isdir(path):
            self._form_error = "Path must be an existing directory."
            self.update()
            return
        try:
            created = WorkspaceModel.objects.create(
                name=name or path,
                path=path,
                description=self._form.get("description", ""),
                access=self.access_editor.access_data,
            )
        except Exception as e:
            self._form_error = f"Error: {e}"
            self.update()
            return
        self._form_error = ""
        from ui.main.workspace.workspace import Workspace

        parent = self._find_main_view()
        if parent is not None:
            parent.create_and_open_tab(Workspace, created)
        self.close_tab()

    def cancelWorkspaceForm(self) -> None:
        self.close_tab()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def close_tab(self) -> None:
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)
