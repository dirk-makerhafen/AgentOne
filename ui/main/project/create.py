from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.project.project_view import ProjectView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class _FormError(Exception):
    """Raised with a user-facing message when the project form is invalid."""


class ProjectCreateView(PyHtmlView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">New project</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancel()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.save()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">
                <form class="detail-form" onsubmit="event.preventDefault(); pyview.save();">

                    <div class="detail-form-row">
                        <label for="pcName">Name</label>
                        <input type="text" id="pcName" value="{{ pyview._form_data.name }}" placeholder="my-project" required="" autocomplete="off" onchange="pyview.setField('name', this.value)">
                    </div>

                    <div class="detail-form-row">
                        <label for="pcDescription">Description</label>
                        <textarea id="pcDescription" rows="6" placeholder="Optional project description" onchange="pyview.setField('description', this.value)">{{ pyview._form_data.description }}</textarea>
                    </div>

                    <div class="detail-form-row">
                        <label for="pcWorkspace">Primary workspace</label>
                        <select id="pcWorkspace" onchange="pyview.setWorkspaceRef(this.value)">
                            <option value=""{% if not pyview._form_data.workspace_ref %} selected{% endif %}>None — store manifests centrally</option>
                            {% for o in pyview.workspace_options %}
                            <option value="{{ o.value }}"{% if pyview._form_data.workspace_ref == o.value %} selected{% endif %}>{{ o.label }}</option>
                            {% endfor %}
                            <option value="new"{% if pyview._form_data.workspace_ref == "new" %} selected{% endif %}>Create new from path…</option>
                        </select>
                        <div class="detail-form-hint">Attach an existing workspace or create a new one from a folder path — it becomes the project's main workspace.</div>
                    </div>

                    {% if pyview._form_data.workspace_ref == "new" %}
                    <div class="detail-form-row">
                        <label for="pcWorkspacePath">New workspace folder</label>
                        <input type="text" id="pcWorkspacePath" value="{{ pyview._form_data.workspace_new_path }}" placeholder="/absolute/path" autocomplete="off" onchange="pyview.setField('workspace_new_path', this.value)">
                    </div>
                    {% endif %}

                    <div class="detail-form-row">
                        <label for="pcManifestInWorkspace">Manifest location</label>
                        <input type="checkbox" id="pcManifestInWorkspace"{% if not pyview.has_workspace %} disabled{% endif %}{% if pyview._form_data.manifest_in_workspace and pyview.has_workspace %} checked{% endif %} onchange="pyview.setManifestInWorkspace(this.checked)">
                        <span>Save manifests inside the primary workspace (<code>&lt;workspace&gt;/.agentone</code>)</span>
                        <div class="detail-form-hint">
                            {% if pyview.has_workspace %}Unchecked stores manifests centrally.{% else %}No primary workspace given — manifests are stored centrally.{% endif %}
                            Central location: <code>{{ pyview.central_manifest_dir }}</code>
                        </div>
                    </div>

                    <div id="pcError" class="detail-form-error" style="display:{% if pyview._form_error %}block{% else %}none{% endif %}">
                        {{ pyview._form_error }}
                    </div>

                </form>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form_data: dict[str, Any] = {
            "name": "",
            "description": "",
            "workspace_ref": "",
            "workspace_new_path": "",
            "manifest_in_workspace": False,
        }
        self._form_error: str = ""

    @property
    def workspace_options(self) -> list[dict]:
        from ui.main.project.workspace_binding import workspace_options

        return workspace_options(project=None)

    @property
    def has_workspace(self) -> bool:
        return bool(self._form_data.get("workspace_ref"))

    @property
    def central_manifest_dir(self) -> str:
        """Friendly central manifest path shown as the default."""
        name = (self._form_data.get("name") or "").strip() or "<projectname>"
        try:
            from runtime.paths import central_project_dir

            p = central_project_dir(name).as_posix()
            home = Path.home().as_posix()
            if p.startswith(home):
                return "~" + p[len(home):]
            return p
        except Exception:
            return f"~/.agentone/projects/{name}"

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self.update()

    def setWorkspaceRef(self, value: str) -> None:
        self._form_data["workspace_ref"] = value
        if value != "new":
            self._form_data["workspace_new_path"] = ""
        self.update()

    def setManifestInWorkspace(self, value: bool) -> None:
        self._form_data["manifest_in_workspace"] = bool(value)
        self.update()

    def save(self) -> None:
        try:
            proj = self._apply()
        except _FormError as e:
            self._form_error = str(e)
            self.update()
            return

        self._form_error = ""
        parent = self._find_main_view()
        if parent:
            parent.create_and_open_tab(ProjectView, proj)
        self.close_tab()

    def _apply(self):
        """Create/update the project, workspace and manifest tree.

        Raises :class:`_FormError` with a user-facing message on failure.
        """
        from runtime.paths import central_project_dir, ensure_private_dir
        from server.models.project import Project
        from ui.main.project.workspace_binding import resolve_primary_workspace

        fd = self._form_data
        name = fd.get("name", "").strip()
        if not name:
            raise _FormError("Name is required.")
        description = fd.get("description", "").strip()
        manifest_in_workspace = bool(fd.get("manifest_in_workspace"))

        proj = self._get_or_create_project(name, description)

        updates: dict[str, Any] = {}
        if description:
            updates["description"] = description

        # Optional primary workspace — reuses an existing workspace when the
        # chosen path already has one, otherwise creates the folder + row.
        ws, ws_error = resolve_primary_workspace(
            fd.get("workspace_ref"), fd.get("workspace_new_path"), proj, name,
        )
        if ws_error:
            raise _FormError(ws_error)
        if ws is not None:
            updates["main_workspace"] = ws
            if manifest_in_workspace:
                manifest = Path(ws.path) / ".agentone"
                updates["storage"] = "inline_project"
            else:
                manifest = central_project_dir(name)
                updates["storage"] = "central"
        else:
            manifest = central_project_dir(name)
            updates["storage"] = "central"

        try:
            ensure_private_dir(manifest)
        except OSError as e:
            raise _FormError(f"Cannot create manifest directory {manifest}: {e}") from e
        updates["agentone_dir"] = manifest.as_posix()

        try:
            Project.objects.filter(pk=proj.pk).update(**updates)
            proj.refresh_from_db()
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise _FormError(f"Failed to save project: {e}") from e

        try:
            from registry.loader.load_project_folder import load_scope_dir

            load_scope_dir(manifest, proj)
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise _FormError(f"Project created but sync failed: {e}") from e

        return proj

    @staticmethod
    def _get_or_create_project(name: str, description: str):
        from server.models.project import Project

        try:
            proj, _ = Project.objects.get_or_create(
                name=name, defaults={"description": description},
            )
            return proj
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise _FormError(f"Failed to create project: {e}") from e

    def cancel(self) -> None:
        self.close_tab()

    def _find_main_view(self):
        from ui.main.main_view import MainView
        p = self.parent
        while p and not isinstance(p, MainView):
            p = p.parent
        return p

    def close_tab(self) -> None:
        parent = self._find_main_view()
        if parent:
            parent.close_tab(self)
