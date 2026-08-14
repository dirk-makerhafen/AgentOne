from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.cron.rightpanel_cron import RightPanelCron
    from ui.app import UiApp


class RightPanelCronSchedule(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Schedule</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Expression</div>
                    <div class="detail-row-value"><code>{{ pyview.subject.schedule }}</code></div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Active</div>
                    <div class="detail-row-value">
                        {% if pyview.subject.is_active %}
                            <span style="color:var(--success)">yes</span>
                        {% else %}
                            <span style="color:var(--error)">paused</span>
                        {% endif %}
                    </div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Last run</div>
                    <div class="detail-row-value">{{ pyview.last_run }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Next run</div>
                    <div class="detail-row-value">{{ pyview.next_run }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Run count</div>
                    <div class="detail-row-value">{{ pyview.subject.run_count }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Agent</div>
                    <div class="detail-row-value">{{ pyview.subject.agent.name }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Workspace</div>
                    <div class="detail-row-value">{% if pyview.subject.workspace %}{{ pyview.subject.workspace.name }}{% else %}&mdash;{% endif %}</div>
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: Cronjob, parent: RightPanelCron, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def last_run(self) -> str:
        c = self.subject
        if c and c.last_run_at:
            return c.last_run_at.strftime("%Y-%m-%d %H:%M")
        return "\u2014"

    @property
    def next_run(self) -> str:
        c = self.subject
        if c and c.next_run:
            return c.next_run.strftime("%Y-%m-%d %H:%M")
        return "\u2014"

