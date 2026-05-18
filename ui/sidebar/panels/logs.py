from __future__ import annotations

from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelLogs(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Logs panel -->
        <div class="panel-view" id="panelLogs">
            <div class="panel-head">
                <span data-i18n="tab_logs">Logs</span>
                <div class="panel-head-actions">
                <button class="panel-head-btn" id="logsRefreshBtn" onclick="loadLogs(true)" title="Refresh" aria-label="Refresh"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>
                </div>
            </div>
            <div class="logs-control-panel">
                <label class="logs-control-label" for="logsFile" data-i18n="logs_file">File</label>
                <select id="logsFile" onchange="loadLogs(true)">
                    <option value="agent">agent</option>
                    <option value="errors">errors</option>
                    <option value="gateway">gateway</option>
                </select>
                <label class="logs-control-label" for="logsTail" data-i18n="logs_tail">Tail</label>
                <select id="logsTail" onchange="loadLogs(true)">
                    <option value="100">100</option>
                    <option value="200" selected>200</option>
                    <option value="500">500</option>
                    <option value="1000">1000</option>
                </select>
                <label class="logs-check-row"><input id="logsAutoRefresh" type="checkbox" checked onchange="_syncLogsAutoRefresh()"><span data-i18n="logs_auto_refresh">Auto-refresh (5s)</span></label>
                <label class="logs-check-row"><input id="logsWrap" type="checkbox" onchange="_syncLogsWrap()"><span data-i18n="logs_wrap">Wrap lines</span></label>
                <button type="button" class="logs-copy" id="logsCopyAll" onclick="copyLogsAll()" data-i18n="logs_copy_all">Copy all</button>
            </div>
        </div>
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
