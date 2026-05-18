
from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.main.main_view import MainView

class CronCreateAgent(ModelView):
    DOM_ELEMENT =  "option"
    TEMPLATE_STR = '''{{pyview.subject.name}}'''
    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f' value="{self.subject.name}" selected=""'

class CronCreateView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title" id="taskDetailTitle">New job</div>
            <div class="main-view-actions">
                <button id="btnRunTaskDetail" class="panel-head-btn" title="Run now" data-i18n-title="cron_run_now" onclick="runCurrentCron()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></button>
                <button id="btnPauseTaskDetail" class="panel-head-btn" title="Pause" data-i18n-title="cron_pause" onclick="pauseCurrentCron()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg></button>
                <button id="btnResumeTaskDetail" class="panel-head-btn" title="Resume" data-i18n-title="cron_resume" onclick="resumeCurrentCron()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon><line x1="22" y1="4" x2="22" y2="20"></line></svg></button>
                <button id="btnEditTaskDetail" class="panel-head-btn" title="Edit" data-i18n-title="edit" onclick="editCurrentCron()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg></button>
                <button id="btnDuplicateTaskDetail" class="panel-head-btn" title="Duplicate" data-i18n-title="cron_duplicate" onclick="duplicateCurrentCron()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                <button id="btnDeleteTaskDetail" class="panel-head-btn" title="Delete" data-i18n-title="delete_title" onclick="deleteCurrentCron()" style="display: none1;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
                <button id="btnCancelTaskDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelCronForm()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                <button id="btnSaveTaskDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveCronForm()" style=""><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg></button>
            </div>
        </div>
        <div class="main-view-body" id="taskDetailBody" style="">
            <div class="main-view-content">
                <form class="detail-form" onsubmit="event.preventDefault(); saveCronForm();">
                    <div class="detail-form-row">
                        <label for="cronFormName">Name</label>
                        <input type="text" id="cronFormName" value="" placeholder="Optional" autocomplete="off">
                    </div>
                    <div class="detail-form-row">
                        <label for="cronFormSchedule">Schedule</label>
                        <input type="text" id="cronFormSchedule" value="" placeholder="0 9 * * *  —  every 1h  —  @daily" autocomplete="off" required="">
                        <div class="detail-form-hint">Cron expression or shorthand like 'every 1h'.</div>
                    </div>
                    <div class="detail-form-row">
                        <label for="cronFormPrompt">Prompt</label>
                        <textarea id="cronFormPrompt" rows="6" placeholder="Prompt" required=""></textarea>
                    </div>
                    <div class="detail-form-row">
                        <label for="cronFormDeliver">Deliver output to</label>
                        <select id="cronFormDeliver">
                            <option value="local" selected="">Local (save output only)</option>
                            <option value="discord">Discord</option>
                            <option value="telegram">Telegram</option>
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label for="cronFormProfile">Profile</label>

                        {{ pyview.agent_list.render() }}
                       
                        <div class="detail-form-hint">Uses the WebUI server default profile at run time. Existing jobs without a profile keep this legacy behavior.</div>
                    </div>
                    <div class="detail-form-row">
                        <label for="cronFormSkillSearch">Skills</label>
                        <div class="skill-picker-wrap">
                            <input type="text" id="cronFormSkillSearch" placeholder="Add skills (optional)…" autocomplete="off">
                            <div id="cronFormSkillDropdown" class="skill-picker-dropdown" style="display:none"></div>
                            <div id="cronFormSkillTags" class="skill-picker-tags"></div>
                        </div>
                    </div>
                    <div id="cronFormError" class="detail-form-error" style="display:none"></div>
                </form>
            </div>
        </div>
        <div class="main-view-empty" id="taskDetailEmpty" style="display: none;">
            <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            <div class="main-view-empty-title" data-i18n="tasks_empty_title">Select a scheduled job</div>
            <div class="main-view-empty-sub" data-i18n="tasks_empty_sub">Pick a job from the sidebar to view its details and runs, or create a new one.</div>
        </div>
    '''
    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent_list = QuerySetView(
            subject = subject.agents.root(),
            parent = self,
            item_class = CronCreateAgent,
            dom_element = "select"
        )
    