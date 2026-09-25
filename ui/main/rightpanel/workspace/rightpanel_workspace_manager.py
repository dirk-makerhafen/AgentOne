"""Workspace Manager chat tab for the workspace right panel.

Embeds a compact session chat (messages + queue/approval/question cards +
composer) for a ``workspace_manager`` agent session bound to the workspace,
so the user can ask the manager to organize the workspace without leaving
the workspace page. A "+ New Chat" button on top creates a fresh manager
chat bound to the same workspace.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.main.chat.cards.approval import ApprovalCard
from ui.main.chat.cards.question import QuestionCard
from ui.main.chat.cards.queue import QueueCard
from ui.main.chat.composer.box import ComposerBox
from ui.main.chat.messages.messages import Messages

if TYPE_CHECKING:
    from ui.main.rightpanel.workspace.rightpanel_workspace import RightPanelWorkspace
    from server.models.sessions.session import SessionModel
    from server.models.workspace import WorkspaceModel

MANAGER_AGENT_NAME = "workspace_manager"


def manager_sessions(workspace) -> list:
    """Manager sessions bound to *workspace*, newest first (no raise)."""
    try:
        from server.models.sessions.session import SessionModel

        return list(
            SessionModel.objects.filter(
                latest_session_version__workspace=workspace,
                latest_session_version__agent__name=MANAGER_AGENT_NAME,
            ).order_by("-created_at")
        )
    except Exception:
        return []


def new_manager_session_name(workspace, agent_name: str = MANAGER_AGENT_NAME) -> str:
    """Unique display name for a fresh manager chat (no raise)."""
    from server.models.sessions.session import SessionModel

    base = f"{getattr(workspace, 'name', None) or 'workspace'}-{agent_name}"
    name, i = base, 1
    try:
        while SessionModel.objects.filter(name=name).exists():
            i += 1
            name = f"{base}-{i}"
    except Exception:
        pass
    return name


class ManagerChat(ModelView):
    """Compact embedded chat: messages + cards + composer for one session."""

    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "manager-chat"
    TEMPLATE_STR = '''
        <div class="manager-chat-messages">
            {{ pyview.messages.render() }}
        </div>
        <div class="composer-wrap manager-composer-wrap">
            <div class="composer-flyout">
                {{ pyview.queue_card.render() }}
                {{ pyview.approval_card.render() }}
                {{ pyview.question_card.render() }}
            </div>
            {{ pyview.composer_box.render() }}
        </div>
    '''

    def __init__(self, subject: SessionModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(subject)
        self.messages = Messages(self.session, self)
        self.queue_card = QueueCard(self.session, self)
        self.approval_card = ApprovalCard(self.session, self)
        self.question_card = QuestionCard(self.session, self)
        self.composer_box = ComposerBox(self.session, self)


class RightPanelWorkspaceManager(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Workspace Manager</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.newManagerChat()" title="New manager chat">＋</button>
                <button class="panel-icon-btn" onclick="pyview.update()" title="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                </button>
            </div>
        </div>
        {% if pyview.sessions %}
        <div class="manager-session-row">
            <select onchange="pyview.selectManagerChat(this.value)" title="Manager chat">
                {% for s in pyview.sessions %}
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
                <div>No manager chat yet.</div>
                <button class="ws-ov-primary" onclick="pyview.newManagerChat()">＋ New Chat</button>
            </div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: WorkspaceModel, parent: RightPanelWorkspace, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._selected_pk: int | None = None
        self.chat: ManagerChat | None = None
        self._reselect()

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @property
    def sessions(self) -> list:
        return manager_sessions(self.subject)

    @property
    def selected_pk(self) -> int | None:
        return self._selected_pk

    def _reselect(self) -> None:
        """Point at the newest session (keeping the selection when valid)."""
        sessions = manager_sessions(self.subject)
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
        for s in manager_sessions(self.subject):
            if s.pk == self._selected_pk:
                self.chat = ManagerChat(s, self)
                return
        self._selected_pk = None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def selectManagerChat(self, pk) -> None:
        try:
            pk = int(pk)
        except (TypeError, ValueError):
            return
        if any(s.pk == pk for s in manager_sessions(self.subject)):
            self._selected_pk = pk
            self._rebuild_chat()
            self.update()

    def newManagerChat(self) -> None:
        """Create a fresh workspace_manager chat bound to this workspace."""
        from server.models.agents.agent import AgentModel

        try:
            agent = AgentModel.objects.get(name=MANAGER_AGENT_NAME)
        except Exception:
            return
        if agent.latest_agent_version is None:
            return
        name = new_manager_session_name(self.subject)
        try:
            session_version = agent.latest_agent_version.get_or_create_session(
                name=name,
                display_name=name,
                description="",
                workspace=self.subject,
            )
        except Exception:
            return
        self._selected_pk = session_version.session.pk
        self._rebuild_chat()
        self.update()
