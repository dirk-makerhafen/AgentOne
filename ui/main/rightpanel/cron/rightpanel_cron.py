from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView
from ui.main.rightpanel.cron.rightpanel_cron_history import RightPanelCronHistory
from ui.main.rightpanel.cron.rightpanel_cron_schedule import RightPanelCronSchedule
from ui.main.rightpanel.assistant_chat import RightPanelCronjobAssistant

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp



class RightPanelCron(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "schedule" %} active{% endif %}" data-panel="schedule" data-label="Schedule" onclick="pyview.switchTab('schedule')" title="Schedule">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "history" %} active{% endif %}" data-panel="history" data-label="History" onclick="pyview.switchTab('history')" title="History">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/><path d="M12 2v4"/><path d="M2 12h4"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "assistant" %} active{% endif %}" data-panel="assistant" data-label="Assistant" onclick="pyview.switchTab('assistant')" title="Cron Job Assistant">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </button>

        </div>
        {% if pyview.current_tab %}
            {{ pyview.current_tab.render() }}
        {% else %}
            <div style="flex:1;padding:8px">
                <div style="font-size:12px;color:var(--muted);text-align:center;margin-top:40%"></div>
            </div>
        {% endif %}
        <div class="resize-handle" id="rightpanelResize"></div>
    '''

    def __init__(self, subject: Cronjob, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None

    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["schedule", "history", "assistant"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "schedule":
            self.current_tab = RightPanelCronSchedule(self.subject, self)
        elif name == "history":
            self.current_tab = RightPanelCronHistory(self.subject, self)
        elif name == "assistant":
            self.current_tab = RightPanelCronjobAssistant(self.subject, self)
        self.update()
