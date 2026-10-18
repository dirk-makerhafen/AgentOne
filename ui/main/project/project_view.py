from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.rightpanel.project.rightpanel_project import RightPanelProject

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class _FormError(Exception):
    """Raised with a user-facing message when the project edit form is invalid."""


class ProjectView(ModelView):
    RIGHTPANEL_VIEW = RightPanelProject

    #: How many recent chats the project page lists.
    LATEST_CHAT_LIMIT = 10

    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''  
        <div class="main-view-header">
            <div class="main-view-title" id="projectTitle">{{ pyview.subject.name }}</div>
            <div class="main-view-actions">
                {% if pyview.editing %}
                <button class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="pyview.cancelEdit()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="pyview.saveEdit()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                {% else %}
                <button id="btnEditProject" class="panel-head-btn" title="Edit project" data-i18n-title="edit" onclick="pyview.editCurrentWorkspace()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
                {% endif %}
            </div>
        </div>
        <div class="main-view-body" id="projectDetailBody">
            <div class="main-view-content">
                {% if pyview.editing %}
                <div class="detail-card">
                    <div class="detail-card-title">Edit project</div>
                    <form class="detail-form" onsubmit="event.preventDefault(); pyview.saveEdit();">
                        <div class="detail-form-row">
                            <label for="pvName">Name</label>
                            <input type="text" id="pvName" value="{{ pyview.edit_data.name }}" placeholder="my-project" required="" autocomplete="off" onchange="pyview.setEditField('name', this.value)">
                        </div>
                        <div class="detail-form-row">
                            <label for="pvDescription">Description</label>
                            <textarea id="pvDescription" rows="4" placeholder="Optional project description" onchange="pyview.setEditField('description', this.value)">{{ pyview.edit_data.description }}</textarea>
                        </div>
                        <div class="detail-form-row">
                            <label for="pvWorkspace">Primary workspace</label>
                            <select id="pvWorkspace" onchange="pyview.setWorkspaceRef(this.value)">
                                <option value=""{% if not pyview.edit_data.workspace_ref %} selected{% endif %}>None — store manifests centrally</option>
                                {% for o in pyview.workspace_options %}
                                <option value="{{ o.value }}"{% if pyview.edit_data.workspace_ref == o.value %} selected{% endif %}>{{ o.label }}</option>
                                {% endfor %}
                                <option value="new"{% if pyview.edit_data.workspace_ref == "new" %} selected{% endif %}>Create new from path…</option>
                            </select>
                            <div class="detail-form-hint">Attach an existing workspace or create a new one from a folder path — it becomes the project's main workspace.</div>
                        </div>
                        {% if pyview.edit_data.workspace_ref == "new" %}
                        <div class="detail-form-row">
                            <label for="pvWorkspacePath">New workspace folder</label>
                            <input type="text" id="pvWorkspacePath" value="{{ pyview.edit_data.workspace_new_path }}" placeholder="/absolute/path" autocomplete="off" onchange="pyview.setEditField('workspace_new_path', this.value)">
                        </div>
                        {% endif %}
                        <div class="detail-form-row">
                            <label for="pvManifestInWorkspace">Manifest location</label>
                            <input type="checkbox" id="pvManifestInWorkspace"{% if not pyview.has_workspace %} disabled{% endif %}{% if pyview.edit_data.manifest_in_workspace and pyview.has_workspace %} checked{% endif %} onchange="pyview.setEditField('manifest_in_workspace', this.checked)">
                            <span>Save manifests inside the primary workspace (<code>&lt;workspace&gt;/.agentone</code>)</span>
                            <div class="detail-form-hint">
                                {% if pyview.has_workspace %}Unchecked stores manifests centrally.{% else %}No primary workspace given — manifests are stored centrally.{% endif %}
                                Central location: <code>{{ pyview.central_manifest_dir }}</code>
                            </div>
                        </div>
                        {% if pyview.edit_error %}
                        <div class="detail-form-error">{{ pyview.edit_error }}</div>
                        {% endif %}
                    </form>
                </div>
                {% else %}
                <div class="detail-card">
                    <div class="detail-card-title">Project</div>
                    <div class="detail-row"><div class="detail-row-label">Name</div><div class="detail-row-value">{{ pyview.subject.name }}</div></div>
                    <div class="detail-row">
                        <div class="detail-row-label">Primary workspace</div>
                        <div class="detail-row-value">{% if pyview.main_workspace_path %}<code>{{ pyview.main_workspace_path }}</code>{% else %}<span style="color:var(--muted)">not set</span>{% endif %}</div>
                    </div>
                    <div class="detail-row"><div class="detail-row-label">Manifests</div><div class="detail-row-value"><code>{{ pyview.manifest_dir }}</code></div></div>
                    <div class="detail-row"><div class="detail-row-label">Description</div><div class="detail-row-value">{{ pyview.subject.description }}</div></div>
                    <div class="detail-row"><div class="detail-row-label">Created</div><div class="detail-row-value">{{ pyview.subject.created_at }}</div></div>
                    <div class="detail-row"><div class="detail-row-label">Status</div><div class="detail-row-value"><span class="detail-badge">Inactive</span></div></div>
                </div>
                {% endif %}

                <div class="ws-sub-head ws-chat-head">
                    <h2 class="ws-sub-title">Chats <span class="ws-sub-count">{{ pyview.chat_count }}</span></h2>
                </div>
                <div class="ws-chat-list">
                    {% for c in pyview.latest_chats %}
                    <div class="ws-chat-row" onclick="pyview.openChat({{ c.pk }})">
                        <span class="ws-ov-dot{% if not c.is_active %} ws-ov-dot--idle{% endif %}"></span>
                        <span class="ws-chat-name">{{ c.name }}</span>
                        <span class="ws-chat-type">{{ c.type_label }}</span>
                        <span class="ws-chat-meta">{{ c.turn_count }} turn(s)</span>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" style="display:{% if pyview.latest_chats %}none{% else %}block{% endif %}">
                    <h2>No chats found</h2>
                    <div>This project has no conversations yet.</div>
                </div>

                <div class="ws-sub-head">
                    <h2 class="ws-sub-title">Workspaces <span class="ws-sub-count">{{ pyview.workspace_count }}</span></h2>
                    <div class="ws-chat-actions">
                        <button class="ws-ov-primary" onclick="pyview.openCreateWorkspace()">＋ New workspace</button>
                    </div>
                </div>
                <div class="ws-ov-grid" id="projectWsGrid">
                    {% for ws in pyview.workspaces %}
                    <div class="ws-ov-card" data-name="{{ ws.name|lower }} {{ ws.path|lower }}" onclick="pyview.openWorkspace({{ ws.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon"{% if ws.color %} style="background:{{ ws.color }}"{% endif %}>
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                            </div>
                            <h3>{{ ws.name }}</h3>
                        </div>
                        <div class="ws-ov-card-info">
                            <div class="ws-ov-path" title="{{ ws.path }}">{{ ws.path }}</div>
                            <div class="ws-ov-desc">{{ ws.description if ws.description else "No description yet." }}</div>
                        </div>
                        <div class="ws-ov-card-bottom">
                            <div class="ws-ov-status"><span class="ws-ov-dot ws-ov-dot--idle"></span> Idle</div>
                            <span>{{ ws.session_count }} session(s) · {{ ws.agent_count }} agent(s)</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" style="display:{% if pyview.workspaces %}none{% else %}block{% endif %}">
                    <h2>No workspaces found</h2>
                    <div>Add a workspace to organize files for this project.</div>
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
        self._editing = False
        self._edit_data: dict[str, Any] = {}
        self._edit_error = ""

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def editing(self) -> bool:
        return self._editing

    @property
    def edit_data(self) -> dict:
        return self._edit_data

    @property
    def edit_error(self) -> str:
        return self._edit_error

    @property
    def main_workspace_path(self) -> str:
        ws = getattr(self.subject, "main_workspace", None)
        return getattr(ws, "path", "") or ""

    @property
    def manifest_dir(self) -> str:
        try:
            from runtime.paths import project_manifest_dir

            return project_manifest_dir(self.subject).as_posix()
        except Exception:
            return getattr(self.subject, "manifest_dir", "") or ""

    @property
    def central_manifest_dir(self) -> str:
        name = (self._edit_data.get("name") or self.subject.name or "").strip() or "<projectname>"
        try:
            from runtime.paths import central_project_dir

            p = central_project_dir(name).as_posix()
            home = Path.home().as_posix()
            return "~" + p[len(home):] if p.startswith(home) else p
        except Exception:
            return f"~/.agentone/projects/{name}"

    # ------------------------------------------------------------------
    # Chats / workspaces lists
    # ------------------------------------------------------------------

    def _project_chats(self) -> list[dict]:
        """Chats bound to this project, newest first (no raise)."""
        try:
            from server.models.sessions.session import SessionModel
            from ui.main.workspace.workspace import related_chat_data

            rows = SessionModel.objects.filter(
                parent_project=self.subject
            ).order_by("-created_at")
            return [related_chat_data(s) for s in rows]
        except Exception:  # pylint: disable=broad-exception-caught
            return []

    @property
    def latest_chats(self) -> list[dict]:
        """Latest chats for this project (capped at ``LATEST_CHAT_LIMIT``)."""
        return self._project_chats()[: self.LATEST_CHAT_LIMIT]

    @property
    def chat_count(self) -> int:
        return len(self._project_chats())

    @property
    def workspaces(self) -> list[dict]:
        """Workspaces owned by this project as card dicts."""
        try:
            from server.models.workspace import WorkspaceModel
            from ui.main.workspace.workspace import workspace_card_data

            rows = WorkspaceModel.objects.filter(
                parent_project=self.subject
            ).order_by("name")
            return [workspace_card_data(ws) for ws in rows]
        except Exception:  # pylint: disable=broad-exception-caught
            return []

    @property
    def workspace_count(self) -> int:
        return len(self.workspaces)

    # ------------------------------------------------------------------
    # Edit lifecycle
    # ------------------------------------------------------------------

    def editCurrentWorkspace(self) -> None:
        """Enter edit mode for this project (bound to the header edit button)."""
        ws = getattr(self.subject, "main_workspace", None)
        ws_path = self.main_workspace_path
        manifest_in_workspace = False
        if ws_path:
            try:
                manifest_in_workspace = (
                    Path(self.manifest_dir).as_posix().rstrip("/")
                    == (Path(ws_path) / ".agentone").as_posix().rstrip("/")
                )
            except Exception:  # pylint: disable=broad-exception-caught
                manifest_in_workspace = False
        self._edit_data = {
            "name": self.subject.name,
            "description": self.subject.description or "",
            "workspace_ref": str(ws.pk) if ws is not None else "",
            "workspace_new_path": "",
            "manifest_in_workspace": manifest_in_workspace,
        }
        self._edit_error = ""
        self._editing = True
        self.update()

    @property
    def workspace_options(self) -> list[dict]:
        from ui.main.project.workspace_binding import workspace_options

        return workspace_options(project=self.subject)

    @property
    def has_workspace(self) -> bool:
        return bool(self._edit_data.get("workspace_ref"))

    def cancelEdit(self) -> None:
        self._editing = False
        self._edit_error = ""
        self.update()

    def setEditField(self, field: str, value) -> None:
        if field == "manifest_in_workspace":
            self._edit_data[field] = bool(value)
        elif field in ("name", "description", "workspace_new_path"):
            self._edit_data[field] = value

    def setWorkspaceRef(self, value: str) -> None:
        self._edit_data["workspace_ref"] = value
        if value != "new":
            self._edit_data["workspace_new_path"] = ""
        self.update()

    def saveEdit(self) -> None:
        try:
            self._apply_edit()
        except _FormError as e:
            self._edit_error = str(e)
            self.update()
            return
        self._editing = False
        self._edit_error = ""
        self.update()

    def _apply_edit(self) -> None:
        from runtime.paths import central_project_dir, ensure_private_dir
        from server.models.project import Project
        from ui.main.project.workspace_binding import resolve_primary_workspace

        d = self._edit_data
        name = (d.get("name") or "").strip()
        if not name:
            raise _FormError("Name is required.")
        description = (d.get("description") or "").strip()
        manifest_in_workspace = bool(d.get("manifest_in_workspace"))

        proj = self.subject
        updates: dict[str, Any] = {"name": name, "description": description}

        ws, ws_error = resolve_primary_workspace(
            d.get("workspace_ref"), d.get("workspace_new_path"), proj, name,
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
            updates["main_workspace"] = None
            manifest = central_project_dir(name)
            updates["storage"] = "central"

        try:
            ensure_private_dir(manifest)
        except OSError as e:
            raise _FormError(f"Cannot create manifest directory {manifest}: {e}") from e
        updates["manifest_dir"] = manifest.as_posix()

        try:
            Project.objects.filter(pk=proj.pk).update(**updates)
            proj.refresh_from_db()
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise _FormError(f"Failed to save project: {e}") from e

        try:
            from registry.loader.load_project_folder import load_scope_dir

            load_scope_dir(manifest, proj)
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise _FormError(f"Saved but sync failed: {e}") from e

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def openChat(self, pk: int) -> None:
        from server.models.sessions.session import SessionModel
        from ui.main.chat.chat import Chat

        try:
            session = SessionModel.objects.get(pk=int(pk))
        except (SessionModel.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Chat, session)

    def openWorkspace(self, pk: int) -> None:
        from server.models.workspace import WorkspaceModel
        from ui.main.workspace.workspace import Workspace

        try:
            ws = WorkspaceModel.objects.get(pk=int(pk))
        except (WorkspaceModel.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Workspace, ws)

    def openCreateWorkspace(self) -> None:
        """Open the new-workspace form preset to this project."""
        from ui.main.workspace.create import CreateWorkspace

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(CreateWorkspace, self.subject)

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
