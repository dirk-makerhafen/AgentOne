from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.agents.agent import AgentModel
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelChat(ModelView):
    DOM_ELEMENT_CLASS = "session-item"    
    TEMPLATE_STR = '''
        <div class="session-text">
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
    
    def __init__(self, subject: AgentModel, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view
    
    def open_agent_details(self):
        self.root_view.main_panel.create_and_open_tab(AgentView, self.subject)
      



class SidebarPanelChats(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <!-- Chat panel -->
        <div class="panel-head">
            <span data-i18n="tab_chat">Chat</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" id="btnNewChat" title="New conversation (Cmd+K)" data-i18n-title="new_conversation" aria-label="New conversation">
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
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.agent_list = QuerySetView(
            subject=subject.instances.root(),
            parent=self,
            item_class=SidebarPanelChat,
            dom_element_class="session-date-body"
        )
