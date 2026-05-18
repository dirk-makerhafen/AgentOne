from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class CronView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
        <div class="main-view-title" id="taskDetailTitle">{{ pyview.subject.name }}</div>
        <div class="main-view-actions">
            <button id="btnRunTaskDetail" class="panel-head-btn" title="Run now" data-i18n-title="cron_run_now" onclick="runCurrentCron()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></button>
            <button id="btnPauseTaskDetail" class="panel-head-btn" title="Pause" data-i18n-title="cron_pause" onclick="pauseCurrentCron()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg></button>
            <button id="btnResumeTaskDetail" class="panel-head-btn" title="Resume" data-i18n-title="cron_resume" onclick="resumeCurrentCron()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon><line x1="22" y1="4" x2="22" y2="20"></line></svg></button>
            <button id="btnEditTaskDetail" class="panel-head-btn" title="Edit" data-i18n-title="edit" onclick="editCurrentCron()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg></button>
            <button id="btnDuplicateTaskDetail" class="panel-head-btn" title="Duplicate" data-i18n-title="cron_duplicate" onclick="duplicateCurrentCron()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
            <button id="btnDeleteTaskDetail" class="panel-head-btn" title="Delete" data-i18n-title="delete_title" onclick="deleteCurrentCron()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
            <button id="btnCancelTaskDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelCronForm()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
            <button id="btnSaveTaskDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveCronForm()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg></button>
        </div>
        </div>
        <div class="main-view-body" id="taskDetailBody" style="">
            <div class="main-view-content">
                
                <div class="detail-card">
                <div class="detail-card-title">Active</div>
                <div class="detail-row"><div class="detail-row-label">Status</div><div class="detail-row-value"><span class="detail-badge ok">active</span></div></div>
                <div class="detail-row"><div class="detail-row-label">Schedule</div><div class="detail-row-value"><code>0 0 * * *</code></div></div>
                <div class="detail-row"><div class="detail-row-label">Next</div><div class="detail-row-value">16.5.2026, 00:00:00</div></div>
                <div class="detail-row"><div class="detail-row-label">Last</div><div class="detail-row-value">never</div></div>
                <div class="detail-row"><div class="detail-row-label">Deliver</div><div class="detail-row-value">local</div></div>
                <div class="detail-row"><div class="detail-row-label">Profile</div><div class="detail-row-value"><span class="detail-badge active" title="Uses the WebUI server default profile at run time. Existing jobs without a profile keep this legacy behavior.">server default</span></div></div>
                <div class="detail-row"><div class="detail-row-label">Skills</div><div class="detail-row-value">—</div></div>
                
                </div>
                <div class="detail-card">
                <div class="detail-card-title">Prompt</div>
                <div class="detail-prompt">test</div>
                </div>
                <div class="detail-card " id="cronDetailRuns"><div class="detail-card-title">Last output</div><div style="color:var(--muted);font-size:12px">(no runs yet)</div></div>
            </div>
        </div>
        <div class="main-view-empty" id="taskDetailEmpty" style="display: none;">
            <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            <div class="main-view-empty-title" data-i18n="tasks_empty_title">Select a scheduled job</div>
            <div class="main-view-empty-sub" data-i18n="tasks_empty_sub">Pick a job from the sidebar to view its details and runs, or create a new one.</div>
        </div>
    '''