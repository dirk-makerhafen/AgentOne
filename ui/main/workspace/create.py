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
                        <label for="workspaceFormProject">Project</label>
                        <select id="workspaceFormProject" onchange="pyview.setWsField('parent_project_id', this.value)">
                            <option value="">(no project)</option>
                            {% for p in pyview.project_options %}
                            <option value="{{ p.pk }}"{% if pyview.form.parent_project_id == p.pk %} selected{% endif %}>{{ p.name }}</option>
                            {% endfor %}
                        </select>
                        <div class="detail-form-hint">Optional owner project (DB-canonical; no project.md involved).</div>
                    </div>
                    <div class="detail-form-row">
                        <label for="workspaceFormStorage">Manifests</label>
                        <select id="workspaceFormStorage" onchange="pyview.setWsField('storage', this.value)">
                            {% for o in pyview.storage_options %}
                                <option value="{{ o.value }}"{% if pyview.form.storage == o.value %} selected{% endif %}>{{ o.label }}</option>
                            {% endfor %}
                        </select>
                        <div class="detail-form-hint">Where this workspace's <code>.agentone</code> manifests live.</div>
                    </div>
                    <div class="detail-form-row">
                        <label for="workspaceFormGitignore">Git</label>
                        <input type="checkbox" id="workspaceFormGitignore" {% if pyview.form.manifest_gitignore %}checked{% endif %} onchange="pyview.setWsField('manifest_gitignore', this.checked ? '1' : '')">
                        <span>Add <code>.agentone/</code> to <code>.gitignore</code> (inline storage only)</span>
                    </div>
                    <div class="detail-form-row">
                        <label for="workspaceFormColor">Color</label>
                        <div class="ws-form-color-row">
                            <input type="color" id="workspaceFormColor" value="{{ pyview.form.color }}" onchange="pyview.setWsField('color', this.value)">
                            <span class="ws-current-color-value">{{ pyview.form.color }}</span>
                        </div>
                        <div class="detail-form-hint">Randomly assigned — pick any color to identify this workspace.</div>
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
        from server.models.workspace import random_workspace_color

        self._form = {
            "name": "", "path": "", "description": "",
            "color": random_workspace_color(),
            "parent_project_id": "", "storage": "central",
            "manifest_gitignore": True,
        }
        self._form_error = ""
        self.access_editor = AccessEditor(subject=subject, parent=self)
        # Opened from a project page: pre-own the new workspace to that project.
        try:
            from server.models.project import Project

            if isinstance(subject, Project):
                self._form["parent_project_id"] = str(subject.pk)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def form(self) -> dict:
        return self._form

    @property
    def form_error(self) -> str:
        return self._form_error

    @property
    def storage_options(self) -> list[dict]:
        from ui.main.workspace.manifest_location import storage_options

        return storage_options()

    @property
    def project_options(self):  # list[dict[str, str]]
        from server.models.project import Project

        try:
            return [{"pk": str(p.pk), "name": p.name}
                    for p in Project.objects.all().order_by("name")]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def setWsField(self, field: str, value: str) -> None:
        if field in ("name", "path", "description", "color", "parent_project_id", "storage"):
            self._form[field] = value
        elif field == "manifest_gitignore":
            self._form[field] = bool(value and value != "0")

    def saveWorkspaceForm(self) -> None:
        from server.models.workspace import random_workspace_color, validate_workspace_color

        name = (self._form.get("name") or "").strip()
        path = (self._form.get("path") or "").strip()
        color = (self._form.get("color") or "").strip() or random_workspace_color()
        if not path or not os.path.isdir(path):
            self._form_error = "Path must be an existing directory."
            self.update()
            return
        try:
            validate_workspace_color(color)
        except Exception:
            self._form_error = "Color must be a #rrggbb hex string."
            self.update()
            return
        try:
            from server.models.project import Project

            parent_project = None
            ppid = (self._form.get("parent_project_id") or "").strip()
            if ppid:
                try:
                    parent_project = Project.objects.filter(pk=int(ppid)).first()
                except (ValueError, TypeError):
                    parent_project = None
            from ui.main.workspace.manifest_location import STORAGES

            storage = (self._form.get("storage") or "central").strip() or "central"
            if storage not in STORAGES:
                storage = "central"
            created = WorkspaceModel.objects.create(
                name=name or path,
                path=path,
                description=self._form.get("description", ""),
                color=color,
                access=self.access_editor.access_data,
                parent_project=parent_project,
                storage=storage,
            )
            from ui.main.workspace.manifest_location import ensure_manifest_dir

            manifest_dir = ensure_manifest_dir(
                created, storage, path,
                gitignore=bool(self._form.get("manifest_gitignore")),
            )
            if manifest_dir:
                WorkspaceModel.objects.filter(pk=created.pk).update(agentone_dir=manifest_dir)
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
