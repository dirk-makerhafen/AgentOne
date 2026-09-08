from __future__ import annotations
from datetime import timedelta
from typing import TYPE_CHECKING
from django.db.models import Prefetch, Q
from django.utils import timezone
from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.enums.session_enums import SessionType
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.chat.chat import Chat

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


RECENT_SUBSESSION_WINDOW = timedelta(minutes=30)
MAX_INACTIVE_SUBSESSIONS = 5
MAX_TREE_DEPTH = 10


class ChildSessionList:
    """Weakref-compatible stand-in for a child-session list used as a
    QuerySetView subject.

    ``ModelView`` weakly references its subject, which a plain ``list`` cannot
    be.  Wrapping the list keeps ``QuerySetView._iter_subjects`` happy (it
    calls ``.all()`` on non-list subjects) while staying weakref-able.
    """

    def __init__(self, sessions: list[SessionModel]):
        self._sessions = sessions

    def all(self) -> list[SessionModel]:
        return self._sessions


def _cap_inactive_children(
    children: list[SessionModel],
    max_inactive: int = MAX_INACTIVE_SUBSESSIONS,
) -> list[SessionModel]:
    """Show every active child plus the most-recently-active inactive ones,
    bounded to *max_inactive* inactive rows."""
    active = [c for c in children if c.is_active]
    inactive = [c for c in children if not c.is_active]
    inactive.sort(key=lambda c: c.last_active_at or c.created_at, reverse=True)
    inactive = inactive[:max_inactive]
    return sorted(active + inactive, key=lambda c: c.created_at, reverse=True)


def visible_child_sessions(
    session: SessionModel,
    window: timedelta = RECENT_SUBSESSION_WINDOW,
    max_inactive: int = MAX_INACTIVE_SUBSESSIONS,
    include_archived: bool = False,
) -> list[SessionModel]:
    """Children of *session* to show in the sidebar: active ones plus inactive
    ones that were active within *window*, capped at *max_inactive* inactive.

    Archived children are only shown when ``include_archived`` is ``True``
    (i.e. the user has toggled the sidebar to show archived conversations).
    """
    cutoff = timezone.now() - window
    qs = SessionModel.objects.filter(parent_session=session, session_type__in=[SessionType.SESSION, SessionType.SUBSESSION, SessionType.SUBTASK_COMPACT])
    if not include_archived:
        qs = qs.filter(is_archived=False)
    children = list(
        qs.filter(
            Q(is_active=True) | Q(last_active_at__gte=cutoff),
        ).select_related("latest_session_version__agent")
    )
    return _cap_inactive_children(children, max_inactive=max_inactive)


class SidebarPanelChat(ModelView):
    DOM_ELEMENT_CLASS = "session-item"
    TEMPLATE_STR = '''
        {% set children = pyview.active_children %}
        <div class="session-text" onclick="pyview.open_instance_detail()">
            <div class="session-title-row">
                {% if children %}
                <span class="session-caret" onclick="event.stopPropagation(); pyview.toggle_children()">{% if pyview._show_children %}▾{% else %}▸{% endif %}</span>
                {% endif %}
                <span class="session-title" title="Double-click to rename">
                    {% if pyview.subject.is_pinned %}<svg class="session-pin-icon" width="10" height="10" viewBox="0 0 16 16" fill="currentColor"><polygon points="8,2 9.8,6.2 14.2,6.2 10.7,9.2 12,13.8 8,11 4,13.8 5.3,9.2 1.8,6.2 6.2,6.2"/></svg>{% endif %}
                    {{ pyview.session.name }}
                </span>
                <span class="session-time">1w</span>
            </div>
            <div class="session-meta">{{pyview.subject.messages.count()}} msgs · {% if  pyview.session.aimodel %} {{ pyview.session.aimodel.name }}{% else %}No Model{% endif %}</div>
        </div>
        {% if children and pyview._show_children and pyview.child_list %}
            {{ pyview.child_list.render() }}
        {% endif %}
        <span class="session-attention-indicator session-state-indicator{% if pyview.mark_active %} is-streaming{% endif %}{% if pyview.mark_needs_approval %} needs-approval{% endif %}" aria-hidden="true"></span>
        <div class="session-actions">
            <button type="button" class="session-actions-trigger" title="Conversation actions" aria-haspopup="menu" aria-label="Conversation actions" onclick="toggleSessionMenu(event, '{{pyview.uid}}')">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" stroke="none"><circle cx="8" cy="3" r="1.25"></circle><circle cx="8" cy="8" r="1.25"></circle><circle cx="8" cy="13" r="1.25"></circle></svg>
            </button>
            <div class="session-action-menu" id="menu_{{pyview.uid}}" style="display:none">
                <div class="session-action-menu-items">
                    <button type="button" class="ws-opt session-action-opt" onclick="event.stopPropagation(); pyview.pin_session(); closeAllSessionMenus()">
                        <span class="ws-opt-action">
                            <span class="ws-opt-icon">
                                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><polygon points="8,2 9.8,6.2 14.2,6.2 10.7,9.2 12,13.8 8,11 4,13.8 5.3,9.2 1.8,6.2 6.2,6.2"></polygon></svg>
                            </span>
                            <span class="session-action-copy">
                                <span class="ws-opt-name">{% if pyview.subject.is_pinned %}Unpin{% else %}Pin{% endif %} conversation</span>
                                <span class="session-action-meta">{% if pyview.subject.is_pinned %}Remove from top{% else %}Keep this conversation at the top{% endif %}</span>
                            </span>
                        </span>
                    </button>
                    <button type="button" class="ws-opt session-action-opt" onclick="event.stopPropagation(); showProjectPicker('{{pyview.uid}}')">
                        <span class="ws-opt-action">
                            <span class="ws-opt-icon">
                                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M2 4.5h4l1.5 1.5H14v7H2z"></path></svg>
                            </span>
                            <span class="session-action-copy">
                                <span class="ws-opt-name">Move to project</span>
                                <span class="session-action-meta">Assign a project to this conversation</span>
                            </span>
                        </span>
                    </button>
                    <button type="button" class="ws-opt session-action-opt" onclick="event.stopPropagation(); pyview.archive_session(); closeAllSessionMenus()">
                        <span class="ws-opt-action">
                            <span class="ws-opt-icon">
                                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="1.5" y="2" width="13" height="3" rx="1"></rect><path d="M2.5 5v8h11V5"></path><line x1="6" y1="8.5" x2="10" y2="8.5"></line></svg>
                            </span>
                            <span class="session-action-copy">
                                <span class="ws-opt-name">Archive conversation</span>
                                <span class="session-action-meta">Hide this conversation until archived is shown</span>
                            </span>
                        </span>
                    </button>
                    <button type="button" class="ws-opt session-action-opt">
                        <span class="ws-opt-action">
                            <span class="ws-opt-icon">
                                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="4.5" y="4.5" width="8.5" height="8.5" rx="1.5"></rect><path d="M3 11.5V3h8.5"></path></svg>
                            </span>
                            <span class="session-action-copy">
                                <span class="ws-opt-name">Duplicate conversation</span>
                                <span class="session-action-meta">Create a copy with the same workspace and model</span>
                            </span>
                        </span>
                    </button>
                    <button type="button" class="ws-opt session-action-opt danger">
                        <span class="ws-opt-action">
                            <span class="ws-opt-icon">
                                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M3.5 4.5h9M6.5 4.5V3h3v1.5M4.5 4.5v8.5h7v-8.5"></path><line x1="7" y1="7" x2="7" y2="11"></line><line x1="9" y1="7" x2="9" y2="11"></line></svg>
                            </span>
                            <span class="session-action-copy">
                                <span class="ws-opt-name">Delete conversation</span>
                                <span class="session-action-meta">Permanently remove this conversation</span>
                            </span>
                        </span>
                    </button>
                </div>
                <div class="session-project-picker" style="display:none">
                    <div class="project-picker-item{% if not pyview.subject.parent_project_id %} active{% endif %}"
                         onclick="pyview.move_to_project(null); closeAllSessionMenus()">
                        No project
                    </div>
                    {% for project in pyview.all_projects %}
                    <div class="project-picker-item{% if project.pk == pyview.subject.parent_project_id %} active{% endif %}"
                         onclick="pyview.move_to_project({{project.pk}}); closeAllSessionMenus()">
                        {{ project.name }}
                    </div>
                    {% endfor %}
                    <div class="project-picker-item project-picker-create"
                         onclick="pyview.show_project_dialog()">
                        + New project
                    </div>
                </div>
            </div>
        </div>
        {% if pyview._show_project_dialog %}
        <div class="app-dialog-overlay" style="display:flex;position:fixed;inset:0;z-index:1100;">
            <div class="app-dialog">
                <div class="app-dialog-header">
                    <div class="app-dialog-title">New project</div>
                    <button class="app-dialog-close" onclick="pyview.cancel_project_dialog()" type="button" aria-label="Close dialog">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                </div>
                <div class="app-dialog-desc">Project name:</div>
                <input class="app-dialog-input" id="projName_{{pyview.uid}}" type="text" placeholder="Project name" autocomplete="off" spellcheck="false">
                <div class="app-dialog-actions">
                    <button class="app-dialog-btn" onclick="pyview.cancel_project_dialog()">Cancel</button>
                    <button class="app-dialog-btn confirm" onclick="pyview.create_project(document.getElementById('projName_{{pyview.uid}}').value)">Create</button>
                </div>
            </div>
        </div>
        {% endif %}
    '''

    def __init__(self, subject: SessionModel, parent: QuerySetView, depth: int = 0, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.depth = depth
        self.session = Session(subject)
        self.root_view: UiAppView = parent.parent.root_view
        self._show_project_dialog = False
        self._show_children = True
        if self.depth >= MAX_TREE_DEPTH:
            self.child_list = None
        else:
            self.child_list = QuerySetView(
                subject=ChildSessionList(
                    visible_child_sessions(
                        subject,
                        include_archived=self._archived_visible(),
                    )
                ),
                parent=self,
                item_class=SidebarPanelChat,
                dom_element_class="session-tree-children",
                depth=self.depth + 1,
            )

    def _archived_visible(self) -> bool:
        """Whether the user has toggled the sidebar to show archived sessions.

        Follows the same ancestor chain as :meth:`refresh_list` up to the
        top-level chat panel, which owns the ``_show_archived`` flag.
        """
        node = self.parent
        while node is not None and not isinstance(node, SidebarPanelChats):
            node = getattr(node, "parent", None)
        if node is not None:
            return getattr(node, "_show_archived", False)
        return False

    @property
    def DOM_ELEMENT_CLASS(self):
        cls = "session-item"
        if self.depth > 0:
            cls += " session-tree-child"
        if self._is_current_session():
            cls += " active"
        return cls

    def _is_current_session(self):
        return self.subject.pk == self._active_session_pk

    @property
    def _active_session_pk(self) -> int | None:
        tab = self.root_view.main_panel.selected_tab_view
        if tab is not None and hasattr(tab, "subject"):
            subj = tab.subject
            if hasattr(subj, "pk"):
                return subj.pk
        return None

    def open_instance_detail(self):
        self.root_view.main_panel.create_and_open_tab(Chat, self.subject)

    def pin_session(self):
        self.subject.is_pinned = not self.subject.is_pinned
        self.subject.save(update_fields=["is_pinned"])
        self.refresh_list()

    def archive_session(self):
        self.subject.is_archived = True
        self.subject.save(update_fields=["is_archived"])
        self.refresh_list()

    def move_to_project(self, project_id: int | None):
        self.subject.parent_project_id = project_id if project_id else None
        self.subject.save(update_fields=["parent_project_id"])
        self.refresh_list()

    def show_project_dialog(self):
        self._show_project_dialog = True
        self.update()

    def cancel_project_dialog(self):
        self._show_project_dialog = False
        self.update()

    def create_project(self, name: str):
        from server.models.project import Project
        project = Project.objects.create(name=name)
        self.subject.parent_project = project
        self.subject.save(update_fields=["parent_project_id"])
        self._show_project_dialog = False
        self.refresh_list()

    def refresh_list(self):
        """Bubble up to the top-level chats panel and force a rebuild."""
        node = self.parent
        while node is not None and not isinstance(node, SidebarPanelChats):
            node = getattr(node, "parent", None)
        if node is not None:
            node.refresh_list()

    @property
    def all_projects(self):
        from server.models.project import Project
        return Project.objects.only("pk", "name").all()

    @property
    def active_children(self) -> list:
        """:return: The child sessions shown under this row (same set the
        ``child_list`` QuerySetView wraps)."""
        return list(self.child_list.query.all()) if self.child_list is not None else []

    def toggle_children(self):
        self._show_children = not self._show_children
        self.update()

    @property
    def mark_active(self) -> bool:
        from server.models.queries.query import Query, QueryStatus
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatus
        return (
            Query.objects.filter(session_version__session=self.subject, status=QueryStatus.ACTIVE).exists()
            or AgentTaskCall.objects.filter(session=self.subject).exclude(status=TaskCallStatus.ENDED).exists()
        )

    @property
    def mark_needs_approval(self) -> bool:
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatusDetail
        return AgentTaskCall.objects.filter(
            session=self.subject,
            requires_approval=True,
            status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
        ).exists()

class SidebarPanelChats(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <!-- Chat panel -->
        <div class="panel-head">
            <span data-i18n="tab_chat">Chat</span>
            {% if pyview.subagent_count %}<span class="subagent-badge" title="{{ pyview.subagent_count }} active subagent session(s)">{{ pyview.subagent_count }} subagents</span>{% endif %}
            <div class="panel-head-actions">
                <button class="panel-head-btn" id="btnNewChat" title="New conversation (Cmd+K)" data-i18n-title="new_conversation" aria-label="New conversation" onclick="pyview.new_conversation()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        <div class="session-search sidebar-search">
            <svg class="sidebar-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            <input id="sessionSearch" placeholder="Filter conversations..." data-i18n-placeholder="filter_conversations" oninput="filterSessions()" autocomplete="off">
        </div>
        <div id="batchActionBar" class="batch-action-bar" style="display: none;"></div>
        <div class="project-bar">
            <span class="project-chip{% if not pyview._show_archived %} active{% endif %}" onclick="pyview.show_all()">All</span>
            <span class="project-chip no-project" title="Show conversations not yet assigned to a project">Unassigned</span>
            <span class="project-chip{% if pyview._show_archived %} active{% endif %}" onclick="pyview.toggle_archived()">Archived</span>
            <button class="project-create-btn" title="New project">+</button>
        </div>

        <div class="session-list" id="sessionList" data-session-virtual-active-anchor="f0dba7de3f21" data-session-virtual-total="3" data-session-virtual-filter="" data-session-virtual-start="0" data-session-virtual-end="3">
            <div class="session-date-group">
                <div class="session-date-header">
                    <span class="session-date-caret">▾</span>
                    <span>{% if pyview._show_archived %}Archived{% else %}Last week{% endif %}</span>
                </div>
                {{ pyview.agent_list.render() }}
            </div>
        </div>

        <div class="session-select-toggle">Select</div>
        <script>
            function toggleSessionMenu(event, uid) {
                event.stopPropagation();
                var menu = document.getElementById('menu_' + uid);
                var isOpen = menu.style.display === 'block';
                closeAllSessionMenus();
                if (!isOpen) {
                    var btn = event.currentTarget;
                    var rect = btn.getBoundingClientRect();
                    menu.style.left = Math.max(8, rect.left - 220 + rect.width) + 'px';
                    menu.style.top = (rect.bottom + 4) + 'px';
                    menu.style.display = 'block';
                    var items = menu.querySelector('.session-action-menu-items');
                    var picker = menu.querySelector('.session-project-picker');
                    if (items) items.style.display = '';
                    if (picker) picker.style.display = 'none';
                }
            }
            function closeAllSessionMenus() {
                var menus = document.querySelectorAll('.session-action-menu');
                for (var i = 0; i < menus.length; i++) {
                    menus[i].style.display = 'none';
                }
            }
            function showProjectPicker(uid) {
                var menu = document.getElementById('menu_' + uid);
                menu.querySelector('.session-action-menu-items').style.display = 'none';
                menu.querySelector('.session-project-picker').style.display = 'block';
            }
            if (!window._sessionMenuListenerAdded) {
                document.addEventListener('click', function(e) {
                    if (!e.target.closest('.session-action-menu') && !e.target.closest('.session-actions-trigger')) {
                        closeAllSessionMenus();
                    }
                });
                window._sessionMenuListenerAdded = true;
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self._show_archived = False
        self.agent_list = QuerySetView(
            subject=self._base_query(),
            parent=self,
            item_class=SidebarPanelChat,
            dom_element_class="session-date-body"
        )
        app = subject
      

    def _on_session_updated(self, pk: int, action: str, filter_context: dict) -> None:
        """Re-render sidebar when a session is renamed (or otherwise updated)."""
        self.refresh_list()

    def _on_session_created(self, pk: int, action: str, filter_context: dict) -> None:
        """Re-render sidebar when a new session (e.g. subagent) is created."""
        self.refresh_list()

    @property
    def subagent_count(self) -> int:
        return SessionModel.objects.filter(parent_session__isnull=False, is_active=True, session_type=SessionType.SESSION).count()

    def _base_query(self):
        qs = self.subject.sessions.root().filter(parent_session__isnull=True, session_type=SessionType.SESSION)
        qs = qs.prefetch_related(Prefetch('child_sessions', queryset=self._child_sessions_queryset()))
        if self._show_archived:
            return qs.filter(is_archived=True).order_by('-is_pinned', '-created_at')
        return qs.filter(is_archived=False).order_by('-is_pinned', '-created_at')

    def _child_sessions_queryset(self):
        children = SessionModel.objects.filter(
            Q(is_active=True) | Q(last_active_at__gte=timezone.now() - RECENT_SUBSESSION_WINDOW), session_type=SessionType.SESSION,
        ).select_related('latest_session_version__agent').order_by('-created_at')
        if not self._show_archived:
            children = children.filter(is_archived=False)
        return children

    def refresh_list(self):
        self.agent_list.query = self._base_query()
        self.agent_list._recreate()
        self.update()

    def set_project_filter(self, project_id: int | None) -> None:
        if project_id is None:
            base = self.subject.sessions.root().filter(parent_session__isnull=True, session_type=SessionType.SESSION)
        else:
            base = SessionModel.objects.filter(parent_project_id=project_id, parent_session__isnull=True, session_type=SessionType.SESSION)
        base = base.prefetch_related(Prefetch('child_sessions', queryset=self._child_sessions_queryset()))
        if self._show_archived:
            base = base.filter(is_archived=True)
        else:
            base = base.filter(is_archived=False)
        self.agent_list.query = base.order_by('-is_pinned', '-created_at')
        self.agent_list._recreate()
        self.update()

    def toggle_archived(self):
        self._show_archived = True
        self.refresh_list()

    def show_all(self):
        self._show_archived = False
        self.refresh_list()

    def new_conversation(self):
        self.subject.agents.root().first().get_runtime()
        self.subject.agents.root().first().latest_agent_version.get_or_create_session()
