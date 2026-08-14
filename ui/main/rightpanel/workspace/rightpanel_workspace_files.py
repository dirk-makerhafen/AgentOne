from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from runtime.session.session import Session

from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView



if TYPE_CHECKING:
    from ui.main.rightpanel.workspace.rightpanel_workspace import RightPanelWorkspace
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession
    from server.models.sessions.session import SessionModel



class RightPanelWorkspaceFiles(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Workspace</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.update()" title="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                </button>
            </div>
        </div>
        <div class="workspace-root-label" style="padding:4px 8px;font-size:11px;color:var(--muted)">{{ pyview.root_label }}</div>
        <div style="flex:1;overflow-y:auto">
            {% if pyview.root_view %}
            {{ pyview.root_view.render() }}
            {% else %}
            <div style="font-size:12px;color:var(--muted);padding:16px 8px;text-align:center">No workspace path set.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelWorkspace|RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._root_view: DirectoryView | None = None


    @property
    def workspace_root(self) -> Path | None:
        session:SessionModel = self.subject
        if session:
            workspace: WorkspaceModel = session.workspace
        else:
            subj = self.parent.current_subject
            workspace = subj if isinstance(subj, WorkspaceModel) else None
        if not workspace:
            return None
        working_dir = workspace.path
        if not working_dir:
            return None
        working_path = Path(working_dir)
        if working_path.is_dir() is False or working_path.exists() is False:
            return None
        return working_path.resolve()
      

    @property
    def root_label(self) -> str:
        rp = self.workspace_root
        if rp:
            return str(rp)
        return "\u2014"

    @property
    def root_view(self) -> DirectoryView | None:
        root = self.workspace_root
        if root is None:
            return None
        if self._root_view is None or Path(self._root_view._path).resolve() != Path(root).resolve():
            self._root_view = DirectoryView(subject=self.subject, parent=self, path=root, indent=8)
        return self._root_view

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)




class DirectoryView(ModelView):
    DOM_ELEMENT = "div"
    TEMPLATE_STR = '''
        {% for entry in pyview.entries %}
        <div class="file-item" style="padding:4px 8px;padding-left:{{ pyview.indent }}px;display:flex;align-items:center;gap:6px;cursor:{% if entry.is_dir %}pointer{% else %}default{% endif %}" {% if entry.is_dir %}onclick="pyview.toggle('{{ entry.name }}')"{% endif %}>
            {% if entry.is_dir %}
                {% if entry.name in pyview.expanded_names %}
                    <span style="width:10px;font-size:10px;color:var(--muted)">▾</span>
                {% else %}
                    <span style="width:10px;font-size:10px;color:var(--muted)">▸</span>
                {% endif %}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            {% else %}
                <span style="width:10px"></span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            {% endif %}
            <span class="file-name" style="flex:1;font-size:12px">{{ entry.name }}</span>
            {% if not entry.is_dir %}
            <span class="file-size" style="font-size:10px;color:var(--muted)">{{ entry.size_str }}</span>
            {% endif %}
        </div>
        {% if entry.is_dir and entry.name in pyview.expanded_names %}
            {% set child = pyview.child_view(entry.name) %}
            {% if child %}{{ child.render() }}{% endif %}
        {% endif %}
        {% else %}
        <div class="file-item file-empty" style="padding-left: {{ pyview.indent}}px;">- empty -</div>
        {% endfor %}
    '''

    def __init__(self, subject: WorkspaceModel, parent, path:Path, indent: int = 8, **kwargs):
        super().__init__(subject=subject, parent=parent, **kwargs)
        self._path = path
        self._indent = indent
        self._expanded: set[str] = set()
        self._child_views: dict[str, DirectoryView] = {}

    @property
    def indent(self) -> int:
        return self._indent

    @property
    def expanded_names(self) -> set[str]:
        return self._expanded

    @property
    def entries(self) -> list[FileEntry]:
        try:
            p = Path(self._path)
            return self._list_dir(p)
        except OSError:
            return []

    def child_view(self, name: str) -> DirectoryView | None:
        if name not in self._expanded:
            return None
        if name not in self._child_views:
            for entry in self.entries:
                if entry.name == name and entry.is_dir:
                    self._child_views[name] = DirectoryView(
                        subject=self.subject,
                        parent=self,
                        path=entry.path, indent=self._indent + 20
                    )
                    break
        return self._child_views.get(name)

    def toggle(self, name: str):
        if name in self._expanded:
            self._expanded.discard(name)
            self._child_views.pop(name, None)
        else:
            self._expanded.add(name)
        self.update()




    def _skip(self, name: str) -> bool:
        return name in ("__pycache__", ".DS_Store")


    def _list_dir(self, path: Path) -> list[FileEntry]:
        entries = []
        try:
            for child in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if self._skip(child.name):
                    continue
                entries.append(FileEntry(
                    name=child.name,
                    path=child,
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else 0,
                ))
        except (PermissionError, OSError):
            pass
        return entries




@dataclass
class FileEntry:
    name: str
    path: Path
    is_dir: bool
    size: int

    @property
    def size_str(self) -> str:
        if self.size < 1024:
            return f"{self.size}B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f}K"
        return f"{self.size / (1024 * 1024):.1f}M"
