from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.chat.chat import Chat

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView



'''
        
        <div class="session-action-menu open" style="left: 81px; top: 325.086px;">
<button type="button" class="ws-opt session-action-opt">
    <span class="ws-opt-action">
        <span class="ws-opt-icon">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><polygon points="8,2 9.8,6.2 14.2,6.2 10.7,9.2 12,13.8 8,11 4,13.8 5.3,9.2 1.8,6.2 6.2,6.2"></polygon></svg>
        </span>
        <span class="session-action-copy">
            <span class="ws-opt-name">Pin conversation</span>
            <span class="session-action-meta">Keep this conversation at the top</span>
        </span>
    </span>
</button>
<button type="button" class="ws-opt session-action-opt">
<span class="ws-opt-action">
<span class="ws-opt-icon">
<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M2 4.5h4l1.5 1.5H14v7H2z"></path></svg>
</span>
<span class="session-action-copy">
<span class="ws-opt-name">Move to project</span>
<span class="session-action-meta">Assign a project to this conversation</span>
</span>
</span></button>
<button type="button" class="ws-opt session-action-opt">
<span class="ws-opt-action">
<span class="ws-opt-icon">
<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="1.5" y="2" width="13" height="3" rx="1"></rect><path d="M2.5 5v8h11V5"></path><line x1="6" y1="8.5" x2="10" y2="8.5"></line></svg>
</span>
<span class="session-action-copy">
<span class="ws-opt-name">Archive conversation</span>
<span class="session-action-meta">Hide this conversation until archived is shown</span>
</span>
</span></button>
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
</span></button></div>
        
        '''



exmapke = '''
        <div class="session-text"  onclick="pyview.open_instance_detail()">
            <div class="session-title-row">
                <span class="session-branch-indicator" title="Forked from AI Agent Capabilities and Functionality Overview">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
                </span>
                <span class="session-title" title="Double-click to rename">AI Agent Capabilities and Functionality Overview (fork)</span>
                <span class="session-time">1w</span>
            </div>
            <div class="session-meta">30 msgs · gemma423:e4b</div>
        </div>
        <span class="session-attention-indicator session-state-indicator" aria-hidden="true"></span>
        <div class="session-actions">
            <button type="button" class="session-actions-trigger" title="Conversation actions" aria-haspopup="menu" aria-label="Conversation actions">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" stroke="none"><circle cx="8" cy="3" r="1.25"></circle><circle cx="8" cy="8" r="1.25"></circle><circle cx="8" cy="13" r="1.25"></circle></svg>
            </button>
        </div>
'''
class SidebarPanelChat(ModelView):
    DOM_ELEMENT_CLASS = "session-item"
    TEMPLATE_STR = '''
        <div class="session-text" onclick="pyview.open_instance_detail()">
            <div class="session-title-row">

                <span class="session-branch-indicator" title="Forked from AI Agent Capabilities and Functionality Overview">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
                </span>
                <span class="session-title" title="Double-click to rename">{{ pyview.session.name }}</span>
                <span class="session-time">1w</span>
            </div>
            <div class="session-meta">{{pyview.subject.messages.count()}} msgs · {{ pyview.session.aimodel.name }}</div>
        </div>
        <span class="session-attention-indicator session-state-indicator" aria-hidden="true"></span>
        <div class="session-actions">
            <button type="button" class="session-actions-trigger" title="Conversation actions" aria-haspopup="menu" aria-label="Conversation actions" onclick="toggleSessionMenu(event, '{{pyview.uid}}')">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" stroke="none"><circle cx="8" cy="3" r="1.25"></circle><circle cx="8" cy="8" r="1.25"></circle><circle cx="8" cy="13" r="1.25"></circle></svg>
            </button>
            <div class="session-action-menu" id="menu_{{pyview.uid}}" style="display:none1">
                <button type="button" class="ws-opt session-action-opt">
                    <span class="ws-opt-action">
                        <span class="ws-opt-icon">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><polygon points="8,2 9.8,6.2 14.2,6.2 10.7,9.2 12,13.8 8,11 4,13.8 5.3,9.2 1.8,6.2 6.2,6.2"></polygon></svg>
                        </span>
                        <span class="session-action-copy">
                            <span class="ws-opt-name">Pin conversation</span>
                            <span class="session-action-meta">Keep this conversation at the top</span>
                        </span>
                    </span>
                </button>
                <button type="button" class="ws-opt session-action-opt">
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
                <button type="button" class="ws-opt session-action-opt">
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
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.session = Session(subject)
        print(self.session.aimodel)
        self.root_view: UiAppView = parent.parent.root_view

    def open_instance_detail(self):
        self.root_view.main_panel.create_and_open_tab(Chat, self.subject)
      

class SidebarPanelChats(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <!-- Chat panel -->
        <div class="panel-head">
            <span data-i18n="tab_chat">Chat</span>
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
        <div class="session-list" id="sessionList" data-session-virtual-active-anchor="f0dba7de3f21" data-session-virtual-total="3" data-session-virtual-filter="" data-session-virtual-start="0" data-session-virtual-end="3">
            <div id="batchActionBar" class="batch-action-bar" style="display: none;"></div>
            <div class="project-bar">
                <span class="project-chip active">All</span>
                <span class="project-chip no-project" title="Show conversations not yet assigned to a project">Unassigned</span>
                <button class="project-create-btn" title="New project">+</button>
            </div>
            <div class="session-date-group">
                <div class="session-date-header">
                    <span class="session-date-caret">▾</span>
                    <span>Last week</span>
                </div>
                {{ pyview.agent_list.render() }}
            </div>
            <div class="session-select-toggle">Select</div>
        </div>
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
                }
            }
            function closeAllSessionMenus() {
                var menus = document.querySelectorAll('.session-action-menu');
                for (var i = 0; i < menus.length; i++) {
                    menus[i].style.display = 'none';
                }
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

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.agent_list = QuerySetView(
            subject=subject.sessions.root(),
            parent=self,
            item_class=SidebarPanelChat,
            dom_element_class="session-date-body"
        )

    def set_project_filter(self, project_id: int | None) -> None:
        if project_id is None:
            self.agent_list.query = self.subject.sessions.root()
        else:
            self.agent_list.query = SessionModel.objects.filter(
                related_session_versions__agent__parent_project=project_id
            ).distinct()
        self.agent_list._recreate()
        self.update()

    def new_conversation(self):
        self.subject.agents.root().first().get_runtime()
        self.subject.agents.root().first().latest_agent_version.get_or_create_session()
        