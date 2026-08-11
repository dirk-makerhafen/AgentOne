from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class MainLogsView(PyHtmlView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div>
                <div class="main-view-title" data-i18n="logs_title">Logs</div>
                <div class="logs-status" id="logsStatus" data-i18n="logs_status_idle">Choose a log file to view recent lines.</div>
            </div>
            <div class="main-view-actions">
                <button type="button" class="logs-copy compact" onclick="copyLogsAll()" data-i18n="logs_copy_all">Copy all</button>
            </div>
        </div>
        <div class="main-view-body logs-main-body">
            <div class="main-view-content logs-content">
                <div class="logs-output" id="logsOutput"><div class="logs-empty" data-i18n="logs_empty">No log lines yet.</div></div>
            </div>
        </div>
    '''
    
    def __init__(self, subject, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "mainLogs"