from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observableList import ObservableList
from ui.lib.pyHtmlGui.pyhtmlgui.view.observable_list_view import ObservableListView
from ui.lib.queryset_view import QuerySetView
from ui.main.chat.chat import Chat

if TYPE_CHECKING:
    from ui.app import UiApp

LIFECYCLE_LABELS = {"single": "Single", "multi": "Multi", "background": "Bg"}


class SubagentLaunchItem(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "subagent-item"
    TEMPLATE_STR = """
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:var(--link)" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
        <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ pyview.subject.name }}</div>
            <div style="font-size:10px;color:var(--muted);margin-top:1px">{{ pyview.subject.parent_name }} · <span class="lifecycle-badge" style="background:var(--bg3);padding:0 4px;border-radius:3px">{{ pyview.lifecycle_label }}</span>{% if pyview.subject.max_turns %} · max {{ pyview.subject.max_turns }}t{% endif %}</div>
        </div>
        <button class="btn btn-sm btn-primary" onclick="pyview.open()" style="flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;background:var(--accent);color:#fff;border:none">Open</button>
    """

    @property
    def lifecycle_label(self) -> str:
        return LIFECYCLE_LABELS.get(self.subject.lifecycle, self.subject.lifecycle)

    def open(self):
        self.parent.parent.open_subagent(self.subject.name)


class ChildSessionItem(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "subagent-session-item"
    TEMPLATE_STR = """
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:var(--success)" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ pyview.subject.latest_session_version.agent.name }}</div>
            <div style="font-size:10px;color:var(--muted);margin-top:1px">from {{ pyview.parent_name }} · {{ pyview.subject.turn_count }}t · {{ pyview.created_label }}</div>
        </div>
        <button class="btn btn-sm btn-outline" onclick="pyview.close()" style="flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:4px;cursor:pointer;background:none;border:1px solid var(--border2);color:var(--text)">Close</button>
    """

    @property
    def parent_name(self) -> str:
        p = self.subject.parent_session
        if p and p.latest_session_version:
            return p.latest_session_version.agent.name
        return "?"

    @property
    def created_label(self) -> str:
        if self.subject.created_at:
            return self.subject.created_at.strftime("%b %d %H:%M")
        return ""

    def close(self):
        SessionModel.objects.filter(pk=self.subject.pk).update(is_active=False)
        self.parent._recreate()
        self.parent.parent.update()


class RightPanelSubagents(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
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
            {{ pyview.available_list.render() }}
            <div style="border-top:1px solid var(--border2);margin:8px 0"></div>
            <div class="section-label" style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;margin:4px 0 8px">Active Child Sessions</div>
            {{ pyview.active_list.render() }}
        </div>
    '''

    def __init__(self, subject: UiApp, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        items = ObservableList()
        parents = AgentVersionModel.objects.filter(
            subagent_configs__isnull=False,
        ).exclude(subagent_configs={}).order_by("agent__name").select_related("agent")
        for parent_av in parents:
            for name, cfg in parent_av.subagent_configs.items():
                create = cfg.get("create", "agent")
                if create not in ("user", "both"):
                    continue
                subagent_av = parent_av.subagent_versions.filter(agent__name=name).first()
                if not subagent_av:
                    continue
                items.append(_SubagentConfigWrapper(
                    name=name,
                    parent_name=parent_av.agent.name,
                    lifecycle=cfg.get("lifecycle", "single"),
                    max_turns=cfg.get("maxTurns", 0),
                    parent_av=parent_av,
                ))

        self.available_list = ObservableListView(
            subject=items,
            parent=self,
            item_class=SubagentLaunchItem,
            dom_element="div",
            dom_element_class="available-subagents",
        )
        self.active_list = QuerySetView(
            subject=SessionModel.objects.none(),
            parent=self,
            item_class=ChildSessionItem,
            dom_element="div",
            dom_element_class="active-child-sessions",
        )
        self._rebuild_active()

    def open_subagent(self, name: str):
        agent = AgentModel.objects.filter(name=name).first()
        if not agent:
            return
        av = agent.latest_agent_version
        if not av:
            return
        ts = timezone.now().strftime("%Y%m%d%H%M%S")
        sv = av.get_or_create_session(
            name=f"user-launch:{name}:{ts}"
        )
        self.parent.parent.main_panel.create_and_open_tab(Chat, sv.session)

    def refresh(self):
        self._rebuild_active()
        self.update()

    def _rebuild_active(self):
        current = self.current_session
        if current is not None:
            qs = SessionModel.objects.filter(
                parent_session=current,
                is_active=True,
            ).order_by("-created_at").select_related(
                "latest_session_version__agent",
                "parent_session__latest_session_version__agent",
            )
        else:
            qs = SessionModel.objects.none()
        self.active_list.query = qs
        self.active_list._recreate()

    @property
    def current_session(self) -> SessionModel | None:
        tab = self.parent.parent.main_panel.selected_tab_view
        if tab is not None and hasattr(tab, "subject"):
            subj = tab.subject
            if isinstance(subj, SessionModel):
                return subj
        return None


class _SubagentConfigWrapper:
    def __init__(self, name: str, parent_name: str, lifecycle: str, max_turns: int, parent_av: AgentVersionModel):
        self.name = name
        self.parent_name = parent_name
        self.lifecycle = lifecycle
        self.max_turns = max_turns
        self.parent_av = parent_av
