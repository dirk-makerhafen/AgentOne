"""Reusable embedded assistant chat for entity right panels.

Every entity type has a pair of internal assistant agents:

* singular ``<entity>_assistant`` — embedded in the *single-item* view,
* plural ``<entity>s_assistant`` — embedded in the *dashboard/collection*
  view.

:class:`AssistantChatMixin` embeds a compact chat (messages + queue/approval/
question cards + composer) for the assistant's sessions in a scope, with a
session selector and a "+ New Chat" button. Subclasses set
``ASSISTANT_AGENT_NAME``/``ASSISTANT_TITLE`` and provide the scope via
:meth:`AssistantChatMixin.assistant_workspace` / :meth:`assistant_project`.

Sessions are bound to the scope so the assistant's own tools resolve the right
project (``SessionModel.parent_project``) or workspace
(``SessionVersionModel.workspace``); global assistants leave both unset. The
compact chat widget itself is the one shared with the workspace Manager tab.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.main.rightpanel.workspace.rightpanel_workspace_manager import (
    ManagerChat as AssistantChat,
)

if TYPE_CHECKING:
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel


#: Body shared by every assistant panel: an optional session selector and
#: the chat (or a "+ New Chat" empty state).
ASSISTANT_CHAT_BODY_TEMPLATE = '''
        {% if pyview.assistant_sessions %}
        <div class="manager-session-row">
            <select onchange="pyview.selectAssistantChat(this.value)" title="Assistant chat">
                {% for s in pyview.assistant_sessions %}
                <option value="{{ s.pk }}"{% if s.pk == pyview.selected_pk %} selected{% endif %}>{{ s.name }}</option>
                {% endfor %}
            </select>
        </div>
        {% endif %}
        <div class="manager-chat-wrap">
            {% if pyview.chat %}
            {{ pyview.chat.render() }}
            {% else %}
            <div class="manager-empty">
                <div>No assistant chat yet.</div>
                <button class="ws-ov-primary" onclick="pyview.newAssistantChat()">＋ New Chat</button>
            </div>
            {% endif %}
        </div>
    '''

_REFRESH_SVG = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
    '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>'
)


def unique_session_name(base: str) -> str:
    """Return *base* made unique among SessionModel names (best effort)."""
    from server.models.sessions.session import SessionModel

    name, i = base, 1
    try:
        while SessionModel.objects.filter(name=name).exists():
            i += 1
            name = f"{base}-{i}"
    except Exception:
        pass
    return name


def _find_sidebar(view):
    """Walk up the view tree looking for the sidebar (holds the project filter)."""
    v = view
    while v is not None:
        sidebar = getattr(v, "sidebar", None)
        if sidebar is not None:
            return sidebar
        v = getattr(v, "parent", None)
    return None


def selected_project(view):
    """The sidebar's currently selected project, or ``None`` for 'All projects'."""
    from server.models.project import Project

    sidebar = _find_sidebar(view)
    pid = getattr(sidebar, "selected_project_id", None) if sidebar is not None else None
    if pid is None:
        return None
    try:
        return Project.objects.filter(pk=pid).first()
    except Exception:
        return None


class AssistantChatMixin:
    """Session select/create shared by every embedded assistant chat.

    Concrete views set ``ASSISTANT_AGENT_NAME``/``ASSISTANT_TITLE``, provide
    the scope, and call :meth:`_reselect` from ``__init__``.
    """

    ASSISTANT_AGENT_NAME = ""
    ASSISTANT_TITLE = "Assistant"

    _selected_pk: int | None = None
    chat = None

    # ------------------------------------------------------------------
    # Scope — override in subclasses
    # ------------------------------------------------------------------

    def assistant_workspace(self):
        """Workspace the assistant's sessions are bound to (or ``None``)."""
        return None

    def assistant_project(self):
        """Project the assistant's sessions are bound to (or ``None``)."""
        return None

    def assistant_item_label(self) -> str:
        """Item name used to title sessions created from an item view."""
        return ""

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    @property
    def assistant_title(self) -> str:
        return self.ASSISTANT_TITLE

    @property
    def assistant_sessions(self) -> list:
        return self.list_assistant_sessions()

    @property
    def selected_pk(self) -> int | None:
        return self._selected_pk

    def list_assistant_sessions(self) -> list:
        """Assistant sessions in this scope, newest first (no raise)."""
        from server.models.sessions.session import SessionModel

        if not self.ASSISTANT_AGENT_NAME:
            return []
        try:
            qs = SessionModel.objects.filter(
                latest_session_version__agent__name=self.ASSISTANT_AGENT_NAME,
                latest_session_version__workspace=self.assistant_workspace(),
                parent_project=self.assistant_project(),
            )
            return list(qs.order_by("-created_at"))
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _reselect(self) -> None:
        """Point at the newest session (keeping the selection when valid)."""
        sessions = self.list_assistant_sessions()
        pks = {s.pk for s in sessions}
        if self._selected_pk not in pks:
            self._selected_pk = sessions[0].pk if sessions else None
        self._rebuild_chat()

    def _rebuild_chat(self) -> None:
        if self.chat is not None:
            try:
                self.chat.delete(remove_from_dom=False)
            except Exception:
                pass
            self.chat = None
        if self._selected_pk is None:
            return
        for s in self.list_assistant_sessions():
            if s.pk == self._selected_pk:
                self.chat = AssistantChat(s, self)
                return
        self._selected_pk = None

    def selectAssistantChat(self, pk) -> None:
        try:
            pk = int(pk)
        except (TypeError, ValueError):
            return
        if pk in {s.pk for s in self.list_assistant_sessions()}:
            self._selected_pk = pk
            self._rebuild_chat()
            self.update()

    def newAssistantChat(self) -> None:
        """Create a fresh assistant session bound to this panel's scope."""
        from server.models.agents.agent import AgentModel

        if not self.ASSISTANT_AGENT_NAME:
            return
        agent = AgentModel.objects.filter(name=self.ASSISTANT_AGENT_NAME).first()
        if agent is None or agent.latest_agent_version is None:
            return
        name = unique_session_name(self._assistant_session_base_name())
        workspace = self.assistant_workspace()
        project = self.assistant_project()
        try:
            session_version = agent.latest_agent_version.get_or_create_session(
                name=name, display_name=name, description="", workspace=workspace,
            )
        except Exception:
            return
        session = session_version.session
        project_pk = getattr(project, "pk", None)
        if project_pk is not None and session.parent_project_id != project_pk:
            try:
                session.parent_project = project
                session.save(update_fields=["parent_project_id"])
            except Exception:
                pass
        self._selected_pk = session.pk
        self._rebuild_chat()
        self.update()

    def refresh(self) -> None:
        self._reselect()
        self.update()

    def _assistant_session_base_name(self) -> str:
        label = self.assistant_item_label()
        agent = self.ASSISTANT_AGENT_NAME or "assistant"
        return f"{label}-{agent}" if label else agent


class _ItemAssistantPanel(AssistantChatMixin, ModelView):
    """Assistant chat tab embedded inside an entity's right panel."""

    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = (
        '''
        <div class="panel-header">
            <span>{{ pyview.assistant_title }}</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.newAssistantChat()" title="New assistant chat">＋</button>
                <button class="panel-icon-btn" onclick="pyview.refresh()" title="Refresh">'''
        + _REFRESH_SVG
        + '''</button>
            </div>
        </div>
    '''
        + ASSISTANT_CHAT_BODY_TEMPLATE
    )

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._selected_pk: int | None = None
        self.chat = None
        self._reselect()


class _DashboardAssistantPanel(AssistantChatMixin, ModelView):
    """Assistant chat shown in a dashboard/collection right panel."""

    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = (
        '''
        <div class="panel-header">
            <span>{{ pyview.assistant_title }}</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.newAssistantChat()" title="New assistant chat">＋</button>
                <button class="panel-icon-btn" onclick="pyview.refresh()" title="Refresh">'''
        + _REFRESH_SVG
        + '''</button>
            </div>
        </div>
    '''
        + ASSISTANT_CHAT_BODY_TEMPLATE
        + '''
        <div class="resize-handle" id="rightpanelResize"></div>
    '''
    )

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._selected_pk: int | None = None
        self.chat = None
        self._reselect()


# ----------------------------------------------------------------------
# Agents
# ----------------------------------------------------------------------

class RightPanelAgentAssistant(_ItemAssistantPanel):
    ASSISTANT_AGENT_NAME = "agent_assistant"
    ASSISTANT_TITLE = "Agent Assistant"

    def assistant_project(self):
        return getattr(self.subject, "parent_project", None)

    def assistant_item_label(self) -> str:
        return getattr(self.subject, "name", "") or ""


class RightPanelAgentsOverview(_DashboardAssistantPanel):
    ASSISTANT_AGENT_NAME = "agents_assistant"
    ASSISTANT_TITLE = "Agents Assistant"

    def assistant_project(self):
        return selected_project(self)


# ----------------------------------------------------------------------
# Cron jobs
# ----------------------------------------------------------------------

class RightPanelCronjobAssistant(_ItemAssistantPanel):
    ASSISTANT_AGENT_NAME = "cronjob_assistant"
    ASSISTANT_TITLE = "Cron Job Assistant"

    def assistant_project(self):
        return getattr(self.subject, "parent_project", None)

    def assistant_item_label(self) -> str:
        return getattr(self.subject, "name", "") or ""


class RightPanelCronjobsOverview(_DashboardAssistantPanel):
    ASSISTANT_AGENT_NAME = "cronjobs_assistant"
    ASSISTANT_TITLE = "Cron Assistant"

    def assistant_project(self):
        return selected_project(self)


# ----------------------------------------------------------------------
# Skills
# ----------------------------------------------------------------------

class RightPanelSkillAssistant(_ItemAssistantPanel):
    ASSISTANT_AGENT_NAME = "skill_assistant"
    ASSISTANT_TITLE = "Skill Assistant"

    def assistant_project(self):
        return getattr(self.subject, "parent_project", None)

    def assistant_item_label(self) -> str:
        return getattr(self.subject, "name", "") or ""


# ----------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------

class RightPanelProjectAssistant(_ItemAssistantPanel):
    ASSISTANT_AGENT_NAME = "project_assistant"
    ASSISTANT_TITLE = "Project Assistant"

    def assistant_project(self):
        return self.subject

    def assistant_item_label(self) -> str:
        return getattr(self.subject, "name", "") or ""


class RightPanelProjectsOverview(_DashboardAssistantPanel):
    ASSISTANT_AGENT_NAME = "projects_assistant"
    ASSISTANT_TITLE = "Projects Assistant"


# ----------------------------------------------------------------------
# Work items
# ----------------------------------------------------------------------

class RightPanelWorkItemsAssistant(_DashboardAssistantPanel):
    ASSISTANT_AGENT_NAME = "workitems_assistant"
    ASSISTANT_TITLE = "Work Items Assistant"

    def assistant_project(self):
        return selected_project(self)


# ----------------------------------------------------------------------
# Workspaces
# ----------------------------------------------------------------------

class RightPanelWorkspacesOverview(_DashboardAssistantPanel):
    ASSISTANT_AGENT_NAME = "workspaces_assistant"
    ASSISTANT_TITLE = "Workspaces Assistant"
