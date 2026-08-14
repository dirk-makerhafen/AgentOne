from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.agents.agent_version import AgentVersionModel
from server.models.enums.session_enums import SessionType
from server.models.sessions.session import SessionModel
from runtime.session.session import Session
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView



if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession


@dataclass
class AvailableSubagent:
    name: str
    parent_name: str
    max_turns: int
    agent_version: AgentVersionModel | None


class ChildSessionItem(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "subagent-session-item"
    TEMPLATE_STR = """
        <div class="subagent-session-body" onclick="pyview.open_chat()" title="Open conversation">
            {% if pyview.mark_active %}<span class="session-state-indicator is-streaming" style="visibility:visible;flex-shrink:0;width:8px;height:8px"></span>{% endif %}
            {% if pyview.mark_needs_approval %}<span class="session-state-indicator needs-approval" style="visibility:visible;flex-shrink:0;width:8px;height:8px"></span>{% endif %}
            {% if not pyview.mark_active and not pyview.mark_needs_approval %}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:var(--success)" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            {% endif %}
            <div style="flex:1;min-width:0">
                <div style="font-size:13px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ pyview.subject.name }}</div>
                <div style="font-size:10px;color:var(--muted);margin-top:1px">{{ pyview.subject.messages.count() }} msgs{% if pyview.model_name %} · {{ pyview.model_name }}{% endif %}</div>
            </div>
        </div>
        <button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); pyview.close()" style="flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;background:none;border:1px solid var(--border2);color:var(--text)">Close</button>
    """

    @property
    def model_name(self) -> str:
        try:
            sv = self.subject.latest_session_version
            if sv and sv.session_settings and sv.session_settings.aimodel:
                return sv.session_settings.aimodel.name
        except Exception:
            pass
        return ""

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

    def open_chat(self):
        from ui.main.chat.chat import Chat
        self.parent.parent.main_panel.create_and_open_tab(Chat, self.subject)

    def close(self):
        SessionModel.objects.filter(pk=self.subject.pk).update(is_active=False)
        self.parent._rebuild_active()
        self.parent.parent.update()


class RightPanelSessionSubagents(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Sub-agents</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.refresh()" title="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                </button>
            </div>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="section-label" style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin:4px 0 8px">Available Subagents</div>
            {% if pyview.available_subagents %}
            {% for sa in pyview.available_subagents %}
            <div class="subagent-item" style="display:flex;align-items:center;gap:8px;padding:6px 0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:var(--link)" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
                <div style="flex:1;min-width:0">
                    <div style="font-size:13px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ sa.name }}</div>
                    <div style="font-size:10px;color:var(--muted);margin-top:1px">{{ sa.parent_name }}{% if sa.max_turns %} · max {{ sa.max_turns }}t{% endif %}</div>
                </div>
                <button class="btn btn-sm btn-primary" onclick="pyview.open('{{ sa.name }}')" style="flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;background:var(--accent);color:#fff;border:none">Open</button>
            </div>
            {% endfor %}
            {% else %}
            <div style="font-size:12px;color:var(--muted);padding:8px 0">None</div>
            {% endif %}
            <div style="border-top:1px solid var(--border2);margin:8px 0"></div>
            <div class="section-label" style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin:4px 0 8px">Active Child Sessions</div>
            {{ pyview.active_list.render() }}
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.active_list = QuerySetView(
            subject=SessionModel.objects.none(),
            parent=self,
            item_class=ChildSessionItem,
            dom_element="div",
            dom_element_class="active-child-sessions",
        )
        self._rebuild_active()

    @property
    def available_subagents(self) -> list[AvailableSubagent]:
        s = self.subject
        if s is None:
            return []
        result = []
        for name in s.allowedSubagentNames:
            av = s.get_subagent(name)
            cfg = s.subagent_config(name)
            result.append(AvailableSubagent(
                name=name,
                parent_name=s.agent.name,
                max_turns=cfg.get("maxTurns", 0),
                agent_version=av,
            ))
        return result

    def open(self, name: str):
        s = self.subject
        if s is None:
            return
        av = s.get_subagent(name)
        if av is None:
            return
        ts = timezone.now().strftime("%Y%m%d%H%M%S")
        sv = av.get_or_create_session(name=f"user-launch:{name}:{ts}", description="User created subagent", parent_session_version=self.session.get_version_model(), session_type=SessionType.SUBSESSION)
        from ui.main.chat.chat import Chat
        self.parent.main_panel.create_and_open_tab(Chat, sv.session)

    def refresh(self):
        self._rebuild_active()
        self.update()

    def _rebuild_active(self):
        s = self.subject
        if s is not None:
            qs = SessionModel.objects.filter(
                parent_session=s.model,
                is_active=True,
            ).order_by("-created_at").select_related(
                "latest_session_version__agent",
                "latest_session_version__session_settings__aimodel",
                "parent_session__latest_session_version__agent",
            )
        else:
            qs = SessionModel.objects.none()
        self.active_list.query = qs
        self.active_list._recreate()
