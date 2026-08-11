from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from django.conf import settings

from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.project.project_view import ProjectView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


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
                        <label for="pcPath">Path</label>
                        <input type="text" id="pcPath" value="{{ pyview._form_data.path }}" placeholder="/absolute/path/to/project" required="" autocomplete="off" onchange="pyview.setField('path', this.value)">
                        <div class="detail-form-hint">Absolute filesystem path for the project directory.</div>
                    </div>

                    <div class="detail-form-row">
                        <label for="pcDescription">Description</label>
                        <textarea id="pcDescription" rows="6" placeholder="Optional project description" onchange="pyview.setField('description', this.value)">{{ pyview._form_data.description }}</textarea>
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
        self._form_data: dict[str, str] = {
            "name": "",
            "path": "",
            "description": "",
        }
        self._form_error: str = ""

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self.update()

    def save(self) -> None:
        fd = self._form_data
        name = fd.get("name", "").strip()
        if not name:
            self._form_error = "Name is required."
            self.update()
            return

        project_path = fd.get("path", "").strip()
        if not project_path:
            self._form_error = "Path is required."
            self.update()
            return

        root = Path(project_path)
        agentone_dir = root / ".agentone"
        project_md_path = agentone_dir / "project.md"

        if not root.is_dir():
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self._form_error = f"Cannot create directory {project_path}: {e}"
                self.update()
                return

        try:
            agentone_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._form_error = f"Cannot create .agentone directory: {e}"
            self.update()
            return

        frontmatter: dict[str, Any] = {"name": name}
        frontmatter["workspaces"] = [
            dict(name=f"{name} project root", path=project_path, description="project root directory"),
        ]

        lines = ["---", yaml.dump(frontmatter, default_flow_style=False).strip(), "---"]
        description = fd.get("description", "").strip()
        if description:
            lines.append("")
            lines.append(description)

        try:
            project_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            self._form_error = f"Failed to write project.md: {e}"
            self.update()
            return

        projects_yaml = Path(settings.BASE_DIR) / ".agentone" / "projects.yaml"
        try:
            if projects_yaml.exists():
                existing = yaml.safe_load(projects_yaml.read_text(encoding="utf-8")) or []
            else:
                existing = []
        except Exception as e:
            self._form_error = f"Failed to read projects.yaml: {e}"
            self.update()
            return

        if project_path not in existing:
            existing.append(project_path)

        try:
            projects_yaml.write_text(
                yaml.dump(existing, default_flow_style=False),
                encoding="utf-8",
            )
        except OSError as e:
            self._form_error = f"Failed to write projects.yaml: {e}"
            self.update()
            return

        try:
            from django.core.management import call_command
            call_command("reload_all", project_path)
        except Exception as e:
            self._form_error = f"Project created but sync failed: {e}"
            self.update()
            return

        self._form_error = ""
        parent = self._find_main_view()
        if parent:
            from server.models.project import Project
            proj = Project.objects.filter(path=project_path).first()
            if proj:
                parent.create_and_open_tab(ProjectView, proj)
        self.close_tab()

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
