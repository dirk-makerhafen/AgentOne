"""New-chat page and chat overview.

Opened from the sidebar "new conversation" button and the workspace
"New chat" button *before* a session exists, so the user picks the agent,
workspace, name and description first.  Below the form a recent-chats list
gives the page its overview character.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView
    from server.models.workspace import WorkspaceModel

RECENT_CHAT_LIMIT = 10


def _is_workspace_subject(subject) -> bool:
    from server.models.workspace import WorkspaceModel

    return isinstance(subject, WorkspaceModel)


class ChatsOverview(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Chats</span>
                {% if pyview.preset_workspace %}
                <span class="ws-ov-sep">/</span>
                <span class="ws-ov-crumb">{{ pyview.preset_workspace.name }}</span>
                {% endif %}
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="chatsOvSearch" placeholder="Search recent chats..." oninput="chatsOvFilter()" autocomplete="off">
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">New chat</h1>
                        <div class="ws-ov-subtitle">Pick an agent and a workspace, then start talking.</div>
                    </div>
                </div>
                <div class="detail-card">
                    <div class="detail-form-row">
                        <label for="newChatName">Name</label>
                        <input type="text" id="newChatName" value="{{ pyview.form.name }}" placeholder="Auto-generated when left blank" autocomplete="off" onchange="pyview.setFormField('name', this.value)">
                    </div>
                    <div class="detail-form-row">
                        <label for="newChatAgent">Agent</label>
                        <select id="newChatAgent" onchange="pyview.setFormField('agent_id', this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_options %}
                            <option value="{{ agent.pk }}"{% if pyview.form.agent_id == agent.pk|string %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label for="newChatWorkspace">Workspace</label>
                        <select id="newChatWorkspace" onchange="pyview.setFormField('workspace_id', this.value)">
                            <option value="">-- No workspace --</option>
                            {% for ws in pyview.workspace_options %}
                            <option value="{{ ws.pk }}"{% if pyview.form.workspace_id == ws.pk|string %} selected{% endif %}>{{ ws.name }}</option>
                            {% endfor %}
                        </select>
                        <div class="detail-form-hint">The workspace controls filesystem access for this chat.</div>
                    </div>
                    <div class="detail-form-row">
                        <label for="newChatDescription">Description</label>
                        <textarea id="newChatDescription" rows="2" placeholder="What is this chat about? (optional)" onchange="pyview.setFormField('description', this.value)">{{ pyview.form.description }}</textarea>
                    </div>
                    {% if pyview.form_error %}
                    <div class="detail-form-error">{{ pyview.form_error }}</div>
                    {% endif %}
                    <div>
                        <button class="ws-ov-primary" onclick="pyview.createChat()">＋ Start chat</button>
                    </div>
                </div>

                <div class="ws-sub-head ws-chat-head">
                    <h2 class="ws-sub-title">Recent chats <span class="ws-sub-count">{{ pyview.recent_chats|length }}</span></h2>
                </div>
                <div class="ws-chat-list" id="chatsOvList">
                    {% for c in pyview.recent_chats %}
                    <div class="ws-chat-row" data-name="{{ c.name|lower }}" onclick="pyview.openChat({{ c.pk }})">
                        {% if c.workspace_color %}<span class="ws-color-dot" style="background:{{ c.workspace_color }}" title="{{ c.workspace_name }}"></span>{% endif %}
                        <span class="ws-chat-name">{{ c.name }}</span>
                        <span class="ws-chat-type">{{ c.agent_name }}</span>
                        <span class="ws-chat-meta">{{ c.turn_count }} turn(s)</span>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" style="display:{% if pyview.recent_chats %}none{% else %}block{% endif %}">
                    <h2>No chats yet</h2>
                    <div>Fill in the form above to start your first conversation.</div>
                </div>
            </div>
        </div>
        <script>
            function chatsOvFilter() {
                var q = document.getElementById("chatsOvSearch").value.toLowerCase();
                var rows = document.querySelectorAll("#chatsOvList .ws-chat-row");
                for (var i = 0; i < rows.length; i++) {
                    var match = (rows[i].dataset.name || "").indexOf(q) !== -1;
                    rows[i].style.display = match ? "" : "none";
                }
            }
        </script>
    '''

    def __init__(self, subject: UiApp | WorkspaceModel, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form = {"name": "", "agent_id": "", "workspace_id": "", "description": ""}
        self._form_error = ""
        preset = self.preset_workspace
        if preset is not None:
            self._form["workspace_id"] = str(preset.pk)
        # Default to the first user-visible root agent (mirrors the old instant-create).
        try:
            from server.models.agents.agent import AgentModel

            first = next(
                (
                    a
                    for a in AgentModel.objects.filter(
                        parent_skill=None, parent_agent=None, parent_project=None
                    ).order_by("name")
                    if a.is_user_visible
                ),
                None,
            )
            if first is not None:
                self._form["agent_id"] = str(first.pk)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    @property
    def preset_workspace(self):
        """Workspace the form was opened for, if any (subject polymorphism)."""
        return self.subject if _is_workspace_subject(self.subject) else None

    @property
    def form(self) -> dict:
        return self._form

    @property
    def form_error(self) -> str:
        return self._form_error

    @property
    def agent_options(self) -> list:
        from server.models.agents.agent import AgentModel

        try:
            return [a for a in AgentModel.objects.all().order_by("name") if a.is_user_visible]
        except Exception:
            return []

    @property
    def workspace_options(self) -> list:
        from server.models.workspace import WorkspaceModel

        try:
            return list(WorkspaceModel.objects.all().order_by("name"))
        except Exception:
            return []

    def _recent_chat_qs(self):
        from server.models.enums.session_enums import SessionType
        from server.models.sessions.session import SessionModel

        qs = SessionModel.objects.filter(
            parent_session__isnull=True,
            session_type=SessionType.SESSION,
            is_archived=False,
        )
        preset = self.preset_workspace
        if preset is not None:
            qs = qs.filter(latest_session_version__workspace=preset)
        return qs.select_related(
            "latest_session_version__agent",
            "latest_session_version__workspace",
        ).order_by("-created_at")

    @property
    def recent_chats(self) -> list[dict]:
        try:
            sessions = list(self._recent_chat_qs()[:RECENT_CHAT_LIMIT])
        except Exception:
            return []
        rows = []
        for s in sessions:
            try:
                sv = s.latest_session_version
                agent_name = getattr(getattr(sv, "agent", None), "name", "") or ""
                ws = getattr(sv, "workspace", None)
                ws_color = getattr(ws, "color", "") or ""
                ws_name = getattr(ws, "name", "") or ""
            except Exception:
                agent_name, ws_color, ws_name = "", "", ""
            rows.append({
                "pk": s.pk,
                "name": s.name or f"Session {s.pk}",
                "agent_name": agent_name,
                "workspace_color": ws_color,
                "workspace_name": ws_name,
                "turn_count": getattr(s, "turn_count", 0) or 0,
            })
        return rows

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def setFormField(self, field: str, value: str) -> None:
        if field in ("name", "agent_id", "workspace_id", "description"):
            self._form[field] = value

    def createChat(self) -> None:
        """Validate the form, create the session, and open it as a Chat tab."""
        from ui.main.chat.chat import Chat

        from server.models.agents.agent import AgentModel
        from server.models.sessions.session import SessionModel
        from server.models.workspace import WorkspaceModel

        try:
            agent = AgentModel.objects.get(pk=int(self._form.get("agent_id") or 0))
        except (AgentModel.DoesNotExist, ValueError, TypeError):
            self._form_error = "Select an agent first."
            self.update()
            return
        workspace = None
        if self._form.get("workspace_id"):
            try:
                workspace = WorkspaceModel.objects.get(pk=int(self._form["workspace_id"]))
            except (WorkspaceModel.DoesNotExist, ValueError, TypeError):
                self._form_error = "Selected workspace no longer exists."
                self.update()
                return
        if agent.latest_agent_version is None:
            self._form_error = f"Agent '{agent.name}' has no version yet."
            self.update()
            return
        if not agent.is_user_visible:
            self._form_error = f"Agent '{agent.name}' is not available for chats."
            self.update()
            return
        name = (self._form.get("name") or "").strip()
        if not name:
            if workspace is not None:
                base = f"{workspace.name or 'workspace'}-{agent.name}"
            else:
                base = f"{agent.name}-chat"
            name, i = base, 1
            while SessionModel.objects.filter(name=name).exists():
                i += 1
                name = f"{base}-{i}"
        elif SessionModel.objects.filter(name=name).exists():
            self._form_error = f"A chat named '{name}' already exists."
            self.update()
            return
        try:
            session_version = agent.latest_agent_version.get_or_create_session(
                name=name,
                display_name=name,
                description=(self._form.get("description") or "").strip(),
                workspace=workspace,
            )
        except Exception as e:
            self._form_error = f"Could not create chat: {e}"
            self.update()
            return
        self._form_error = ""
        self._form["name"] = ""
        self._form["description"] = ""
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Chat, session_version.session)
        self.update()

    def openChat(self, pk: int) -> None:
        from ui.main.chat.chat import Chat

        from server.models.sessions.session import SessionModel

        try:
            session = SessionModel.objects.get(pk=int(pk))
        except (SessionModel.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Chat, session)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
