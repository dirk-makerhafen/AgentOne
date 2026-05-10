from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class MainInsightsView(ModelView):
    TEMPLATE_STR = '''
        <div id="mainInsights" class="main-view">
            <div class="main-view-header">
                <div class="main-view-title" data-i18n="insights_title">Usage Analytics</div>
            </div>
            <div class="main-view-content" id="insightsContent" style="padding:16px;overflow-y:auto">
                <div class="insights-card wiki-status-card" id="llmWikiStatusCard">
                    <div style="color:var(--muted);font-size:12px" data-i18n="loading">Loading...</div>
                </div>
            </div>
        </div>
    '''
    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)