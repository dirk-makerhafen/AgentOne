from __future__ import annotations
import os
from typing import TYPE_CHECKING
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.rightpanel.workspace.rightpanel_workspace import RightPanelWorkspace
from ui.main.workspace.access_editor import AccessEditor

if TYPE_CHECKING:
    from ui.main.main_view import MainView


def norm_workspace_path(path: str) -> str:
    """Normalize a workspace path for prefix comparison (symlinks resolved)."""
    try:
        return os.path.realpath(path or "").rstrip(os.sep)
    except Exception:
        return os.path.normpath(path or "").rstrip(os.sep)


def workspace_parent_map(workspaces: list) -> dict[int, int | None]:
    """Map each workspace pk to its parent pk (longest path-prefix wins).

    Items need ``pk`` and ``path`` attributes.  Workspaces with no
    containing workspace map to None.
    """
    normed = {ws.pk: norm_workspace_path(ws.path) for ws in workspaces}
    parent_of: dict[int, int | None] = {}
    for ws in workspaces:
        best: int | None = None
        best_len = -1
        mine = normed[ws.pk]
        for other in workspaces:
            if other.pk == ws.pk:
                continue
            theirs = normed[other.pk]
            if not theirs or theirs == os.sep:
                continue
            if mine != theirs and mine.startswith(theirs + os.sep) and len(theirs) > best_len:
                best, best_len = other.pk, len(theirs)
        parent_of[ws.pk] = best
    return parent_of


def current_session_workspace_pk(main_view) -> int | None:
    """Workspace pk bound to the current chat session, if any.

    Scans the open tabs for a session subject (the selected tab first)
    so the ACTIVE badge survives while the overview or a detail tab is
    selected.  Never raises — returns None when nothing matches.
    """
    try:
        selected = main_view.selected_tab_view
        rest = [v for v in getattr(main_view, "open_tabs", {}).values() if v is not selected]
        tabs = ([selected] if selected is not None else []) + rest
    except Exception:
        return None
    for tab in tabs:
        subj = getattr(tab, "subject", None)
        if subj is None:
            continue
        try:
            from server.models import SessionModel

            if isinstance(subj, SessionModel):
                sv = getattr(subj, "latest_session_version", None)
                ws_id = getattr(sv, "workspace_id", None)
                if ws_id:
                    return ws_id
        except Exception:
            continue
    return None


def workspace_card_data(ws) -> dict:
    """Card info dict for a workspace (sessions/agents counts, no raise)."""
    try:
        from server.models.sessions.session_version import SessionVersionModel

        versions = SessionVersionModel.objects.filter(workspace=ws)
        sessions = versions.count()
        agents = versions.values_list("agent__name", flat=True).distinct().count()
    except Exception:
        sessions, agents = 0, 0
    return {
        "pk": ws.pk,
        "name": ws.name or ws.path,
        "path": ws.path,
        "description": ws.description or "",
        "session_count": sessions,
        "agent_count": agents,
    }


def related_chat_data(session) -> dict:
    """Row info dict for a session bound to a workspace (no raise)."""
    try:
        from server.models.enums.session_enums import SessionType

        type_label = dict(SessionType.choices).get(
            session.session_type, session.session_type or ""
        )
    except Exception:
        type_label = ""
    return {
        "pk": session.pk,
        "name": session.name or f"Session {session.pk}",
        "type_label": type_label,
        "is_active": bool(getattr(session, "is_active", False)),
        "turn_count": getattr(session, "turn_count", 0) or 0,
    }


# NOTE: ``; pyview.`` (with the semicolon/space prefix) matters — the
# pyHtmlGui template rewrite only picks up ``pyview.method(`` after one of
# ``> (= "' ;`` whitespace etc.  Never call it directly after ``)`` or ``{``.
WS_FILTER_SCRIPT = '''
        <script>
            function wsOvFilter() {
                var q = document.getElementById("wsOvSearch").value.toLowerCase();
                var cards = document.querySelectorAll("#wsOvGrid .ws-ov-card");
                var visible = 0;
                for (var i = 0; i < cards.length; i++) {
                    var match = cards[i].dataset.name.toLowerCase().indexOf(q) !== -1;
                    cards[i].style.display = match ? "" : "none";
                    if (match) visible++;
                }
                document.getElementById("wsOvEmpty").style.display = visible ? "none" : "block";
            }
        </script>
'''

WS_CARD_MENU_SCRIPT = '''
        <script>
            function wsOvFilter() {
                var q = document.getElementById("wsOvSearch").value.toLowerCase();
                var cards = document.querySelectorAll("#wsOvGrid .ws-ov-card");
                var visible = 0;
                for (var i = 0; i < cards.length; i++) {
                    var match = cards[i].dataset.name.toLowerCase().indexOf(q) !== -1;
                    cards[i].style.display = match ? "" : "none";
                    if (match) visible++;
                }
                document.getElementById("wsOvEmpty").style.display = visible ? "none" : "block";
            }
            function wsCardMenu(event, pk) {
                event.stopPropagation();
                var m = document.getElementById("wsmenu_" + pk);
                var open = m.style.display === "block";
                wsCloseMenus();
                if (!open) m.style.display = "block";
            }
            function wsCloseMenus() {
                var ms = document.querySelectorAll(".ws-card-menu");
                for (var i = 0; i < ms.length; i++) ms[i].style.display = "none";
            }
            function wsRename(pk, btn) {
                wsCloseMenus();
                var n = prompt("Rename workspace", btn.getAttribute("data-name") || "");
                if (n && n.trim()) { ; pyview.renameWorkspace(pk, n.trim()); }
            }
            if (!window._wsMenuListenerAdded) {
                document.addEventListener("click", function() { wsCloseMenus(); });
                window._wsMenuListenerAdded = true;
            }
        </script>
'''


class Workspace(ModelView):
    RIGHTPANEL_VIEW = RightPanelWorkspace
    DOM_ELEMENT_CLASS = "main-view"
    CHAT_PAGE_SIZE = 10
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb ws-ov-crumb--link" onclick="pyview.openOverview()">Workspaces</span>
                {% for anc in pyview.ancestors %}
                <span class="ws-ov-sep">/</span>
                <span class="ws-ov-crumb ws-ov-crumb--link" onclick="pyview.openWorkspace({{ anc.pk }})">{{ anc.name }}</span>
                {% endfor %}
                <span class="ws-ov-sep">/</span>
                <span class="ws-ov-crumb">{{ pyview.subject.name }}</span>
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="wsOvSearch" placeholder="Search workspaces..." oninput="wsOvFilter()" autocomplete="off">
            </div>
            <button class="ws-ov-primary" onclick="pyview.openCreate()">＋ New workspace</button>
        </div>

        <div class="main-view-body" id="workspaceDetailBody">
            <div class="main-view-content ws-ov-content">
                <div class="ws-current-card">
                    <div class="ws-ov-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    </div>
                    {% if pyview.editing %}
                    <div class="ws-current-info">
                        <input class="ws-current-input" value="{{ pyview.edit_data.name }}" onchange="pyview.setEditField('name', this.value)" autocomplete="off" placeholder="Name">
                        <input class="ws-current-input ws-current-input--path" value="{{ pyview.edit_data.path }}" onchange="pyview.setEditField('path', this.value)" autocomplete="off" placeholder="Path">
                        <textarea class="ws-current-input" rows="2" onchange="pyview.setEditField('description', this.value)" placeholder="What is this workspace for?">{{ pyview.edit_data.description }}</textarea>
                        {{ pyview.access_editor.render() }}
                        {% if pyview.edit_error %}
                        <div class="detail-form-error">{{ pyview.edit_error }}</div>
                        {% endif %}
                    </div>
                    <div class="ws-current-edit-actions">
                        <button class="panel-head-btn" title="Cancel" onclick="pyview.cancelEdit()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                        <button class="panel-head-btn primary" title="Save" onclick="pyview.saveEdit()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                    </div>
                    {% else %}
                    <div class="ws-current-info">
                        <div class="ws-current-name">
                            <span id="workspaceDetailTitle">{{ pyview.subject.name }}</span>
                            {% if pyview.subject.pk == pyview.active_workspace_pk %}
                            <span class="detail-badge active">ACTIVE</span>
                            {% endif %}
                        </div>
                        <div class="ws-ov-path" title="{{ pyview.subject.path }}">{{ pyview.subject.path }}</div>
                        {% if pyview.subject.description %}
                        <div class="ws-ov-desc">{{ pyview.subject.description }}</div>
                        {% endif %}
                    </div>
                    <button class="panel-head-btn ws-current-edit-btn" onclick="pyview.startEdit()" title="Edit workspace"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></button>
                    <button class="ws-card-menu-btn" onclick="event.stopPropagation();wsCardMenu(event, {{ pyview.subject.pk }})" title="Workspace actions">⋯</button>
                    <div class="ws-card-menu" id="wsmenu_{{ pyview.subject.pk }}" style="display:none">
                        <button data-name="{{ pyview.subject.name }}" onclick="event.stopPropagation();wsRename({{ pyview.subject.pk }}, this)">Rename</button>
                        <button class="danger" onclick="event.stopPropagation();wsCloseMenus();if(confirm('Remove workspace {{ pyview.subject.name }}?')) { ; pyview.deleteWorkspace({{ pyview.subject.pk }}); }">Remove</button>
                    </div>
                    {% endif %}
                </div>

                <div class="ws-sub-head ws-chat-head">
                    <h2 class="ws-sub-title">Chats <span class="ws-sub-count">{{ pyview.chat_count }}</span></h2>
                    <div class="ws-chat-actions">
                        <button class="ws-ov-primary" onclick="pyview.newChat()">＋ New chat</button>
                        {% if pyview.chat_page_count > 1 %}
                        <div class="ws-chat-pager">
                        <button class="ws-ov-view-btn" onclick="pyview.setChatPage({{ pyview.chat_page - 1 }})"{% if pyview.chat_page == 0 %} disabled{% endif %} title="Previous page">‹</button>
                        <span class="ws-chat-page-label">{{ pyview.chat_page + 1 }} / {{ pyview.chat_page_count }}</span>
                        <button class="ws-ov-view-btn" onclick="pyview.setChatPage({{ pyview.chat_page + 1 }})"{% if pyview.chat_page + 1 >= pyview.chat_page_count %} disabled{% endif %} title="Next page">›</button>
                        </div>
                        {% endif %}
                    </div>
                </div>

                <div class="ws-chat-list">
                    {% for c in pyview.related_chats %}
                    <div class="ws-chat-row" onclick="pyview.openChat({{ c.pk }})">
                        <span class="ws-ov-dot{% if not c.is_active %} ws-ov-dot--idle{% endif %}"></span>
                        <span class="ws-chat-name">{{ c.name }}</span>
                        <span class="ws-chat-type">{{ c.type_label }}</span>
                        <span class="ws-chat-meta">{{ c.turn_count }} turn(s)</span>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" style="display:{% if pyview.related_chats %}none{% else %}block{% endif %}">
                    <h2>No chats found</h2>
                    <div>Start a conversation in this workspace.</div>
                </div>

                <div class="ws-sub-head">
                    <h2 class="ws-sub-title">Sub workspaces <span class="ws-sub-count">{{ pyview.child_count }}</span></h2>
                    <div class="ws-ov-view-controls">
                        <button class="ws-ov-view-btn{% if pyview.view_mode == "grid" %} active{% endif %}" onclick="pyview.setView('grid')" title="Card view">▦</button>
                        <button class="ws-ov-view-btn{% if pyview.view_mode == "list" %} active{% endif %}" onclick="pyview.setView('list')" title="List view">☷</button>
                    </div>
                </div>

                <div class="ws-ov-grid{% if pyview.view_mode == "list" %} ws-ov-list{% endif %}" id="wsOvGrid">
                    {% for ws in pyview.children_cards %}
                    <div class="ws-ov-card" data-name="{{ ws.name|lower }} {{ ws.path|lower }}" onclick="pyview.openWorkspace({{ ws.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                            </div>
                            <h3>{{ ws.name }}</h3>
                        </div>
                        <div class="ws-ov-card-info">
                            <div class="ws-ov-path" title="{{ ws.path }}">{{ ws.path }}</div>
                            <div class="ws-ov-desc">{{ ws.description if ws.description else "No description yet." }}</div>
                        </div>
                        <div class="ws-ov-card-bottom">
                            <div class="ws-ov-status">
                                {% if ws.pk == pyview.active_workspace_pk %}
                                <span class="ws-ov-dot"></span> Active
                                {% else %}
                                <span class="ws-ov-dot ws-ov-dot--idle"></span> Idle
                                {% endif %}
                            </div>
                            <span>{{ ws.session_count }} session(s) · {{ ws.agent_count }} agent(s)</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" id="wsOvEmpty" style="display:{% if pyview.children_cards %}none{% else %}block{% endif %}">
                    <div class="ws-ov-empty-icon">⌕</div>
                    <h2>No sub workspaces found</h2>
                    <div>Try another search or create a new workspace.</div>
                </div>
            </div>
        </div>
    ''' + WS_CARD_MENU_SCRIPT

    def __init__(self, subject: WorkspaceModel, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._view_mode = "grid"
        self._editing = False
        self._edit_data: dict = {}
        self._edit_error = ""
        self._chat_page = 0
        self.access_editor = AccessEditor(subject=subject, parent=self)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def view_mode(self) -> str:
        return self._view_mode

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
    def ancestors(self) -> list:
        """Parent chain root-first (for the breadcrumb)."""
        try:
            workspaces = list(WorkspaceModel.objects.all())
        except Exception:
            return []
        by_pk = {ws.pk: ws for ws in workspaces}
        parent_of = workspace_parent_map(workspaces)
        chain = []
        seen = {self.subject.pk}
        pk = parent_of.get(self.subject.pk)
        while pk is not None and pk not in seen:
            seen.add(pk)
            ws = by_pk.get(pk)
            if ws is None:
                break
            chain.append(ws)
            pk = parent_of.get(pk)
        chain.reverse()
        return chain

    @property
    def children_cards(self) -> list[dict]:
        """Direct sub-workspaces as card dicts, sorted by name."""
        try:
            workspaces = list(WorkspaceModel.objects.all())
        except Exception:
            return []
        parent_of = workspace_parent_map(workspaces)
        children = [ws for ws in workspaces if parent_of.get(ws.pk) == self.subject.pk]
        children.sort(key=lambda w: (w.name or "").lower())
        return [workspace_card_data(ws) for ws in children]

    @property
    def child_count(self) -> int:
        return len(self.children_cards)

    def _all_related_chats(self) -> list[dict]:
        """All Sessions/SubSessions bound to this workspace, newest first."""
        try:
            from server.models.enums.session_enums import SessionType
            from server.models.sessions.session import SessionModel

            sessions = SessionModel.objects.filter(
                latest_session_version__workspace=self.subject,
                session_type__in=[SessionType.SESSION],
            ).order_by("-created_at")
            return [related_chat_data(s) for s in sessions]
        except Exception:
            return []

    @property
    def related_chats(self) -> list[dict]:
        """Current page of related chats (see ``CHAT_PAGE_SIZE``)."""
        chats = self._all_related_chats()
        start = self.chat_page * self.CHAT_PAGE_SIZE
        return chats[start:start + self.CHAT_PAGE_SIZE]

    @property
    def chat_count(self) -> int:
        return len(self._all_related_chats())

    @property
    def chat_page(self) -> int:
        """Current chat page, 0-indexed and clamped to the valid range."""
        pages = self.chat_page_count
        return min(max(self._chat_page, 0), pages - 1)

    @property
    def chat_page_count(self) -> int:
        total = len(self._all_related_chats())
        return max(1, -(-total // self.CHAT_PAGE_SIZE))

    @property
    def active_workspace_pk(self) -> int | None:
        try:
            return current_session_workspace_pk(self._find_main_view())
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def setView(self, mode: str) -> None:
        if mode in ("grid", "list"):
            self._view_mode = mode
            self.update()

    def setChatPage(self, page: int) -> None:
        try:
            self._chat_page = int(page)
        except (TypeError, ValueError):
            self._chat_page = 0
        self.update()

    def openWorkspace(self, pk: int) -> None:
        try:
            ws = WorkspaceModel.objects.get(pk=int(pk))
        except (WorkspaceModel.DoesNotExist, ValueError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Workspace, ws)

    def openOverview(self) -> None:
        from ui.main.workspace.overview import WorkspacesOverview

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(WorkspacesOverview, main_view.subject)

    def openCreate(self) -> None:
        from ui.main.workspace.create import CreateWorkspace

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(CreateWorkspace, main_view.subject)

    def openChat(self, pk: int) -> None:
        from ui.main.chat.chat import Chat

        try:
            from server.models.sessions.session import SessionModel

            session = SessionModel.objects.get(pk=int(pk))
        except (SessionModel.DoesNotExist, ValueError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Chat, session)

    def newChat(self) -> None:
        """Create a fresh chat session bound to this workspace and open it."""
        from ui.main.chat.chat import Chat

        try:
            from server.models.agents.agent import AgentModel
            from server.models.sessions.session import SessionModel

            agent = AgentModel.objects.filter(
                parent_skill=None, parent_agent=None, parent_project=None
            ).first()
            if agent is None or agent.latest_agent_version is None:
                return
            base = f"{self.subject.name or 'workspace'}-{agent.name}"
            name, i = base, 1
            while SessionModel.objects.filter(name=name).exists():
                i += 1
                name = f"{base}-{i}"
            session_version = agent.latest_agent_version.get_or_create_session(
                name=name,
                display_name=name,
                workspace=self.subject,
            )
            session = session_version.session
        except Exception:
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Chat, session)
        self._chat_page = 0
        self.update()

    def renameWorkspace(self, pk: int, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        try:
            ws = WorkspaceModel.objects.get(pk=int(pk))
        except (WorkspaceModel.DoesNotExist, ValueError):
            return
        ws.name = name
        ws.save(update_fields=["name", "updated_at"])
        self.update()

    def startEdit(self) -> None:
        self._editing = True
        self._edit_error = ""
        self._edit_data = {
            "name": self.subject.name,
            "description": self.subject.description or "",
            "path": self.subject.path,
        }
        self.update()

    def cancelEdit(self) -> None:
        self._editing = False
        self._edit_error = ""
        self.update()

    def setEditField(self, field: str, value: str) -> None:
        if field in ("name", "description", "path"):
            self._edit_data[field] = value

    def saveEdit(self) -> None:
        name = (self._edit_data.get("name") or "").strip()
        path = (self._edit_data.get("path") or "").strip()
        if not name:
            self._edit_error = "Name must not be empty."
            self.update()
            return
        if not path or not os.path.isdir(path):
            self._edit_error = "Path must be an existing directory."
            self.update()
            return
        self.subject.name = name
        self.subject.description = self._edit_data.get("description", "")
        self.subject.path = path
        self.subject.access = self.access_editor.access_data
        self.subject.save()
        self._editing = False
        self._edit_error = ""
        self.update()

    def deleteWorkspace(self, pk: int) -> None:
        try:
            ws = WorkspaceModel.objects.get(pk=int(pk))
        except (WorkspaceModel.DoesNotExist, ValueError):
            return
        ws.delete()
        if int(pk) == self.subject.pk:
            main_view = self._find_main_view()
            if main_view is not None and hasattr(main_view, "close_tab"):
                main_view.close_tab(self)
        else:
            self.update()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
