"""Agents dashboard — quick overview of all agents.

Shown when the agents sidebar icon is clicked (previously the main content
stayed on whatever tab was open, since agents had no main page).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


def agent_card_data(agent) -> dict:
    """Card info dict for an agent (no raise)."""
    try:
        lav = agent.latest_agent_version
        description = getattr(lav, "description", "") or ""
    except Exception:
        description = ""
    try:
        from runtime.agents.agent import Agent

        runtime = Agent(agent)
        model_name = runtime.aimodel.name if runtime.aimodel else "No model"
        skill_count = len(runtime.allowedSkills)
        tool_count = len(runtime.allowedTools)
        task_count = len(runtime.allowedTasks)
        command_count = len(runtime.allowedCommands)
    except Exception:
        model_name = ""
        skill_count = tool_count = task_count = command_count = 0
    try:
        from server.models.sessions.session import SessionModel

        session_count = SessionModel.objects.filter(
            latest_session_version__agent=agent
        ).count()
    except Exception:
        session_count = 0
    return {
        "pk": agent.pk,
        "name": getattr(agent, "name", "") or f"Agent {agent.pk}",
        "description": description or "No description yet.",
        "model_name": model_name,
        "skill_count": skill_count,
        "tool_count": tool_count,
        "task_count": task_count,
        "command_count": command_count,
        "session_count": session_count,
    }


class AgentsOverview(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Agents</span>
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="agentsOvSearch" placeholder="Search agents..." oninput="agentsOvFilter()" autocomplete="off">
            </div>
            <button class="ws-ov-primary" onclick="pyview.openCreate()">＋ New agent</button>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">Agents</h1>
                        <div class="ws-ov-subtitle">{{ pyview.agents|length }} agent(s)</div>
                    </div>
                </div>
                <div class="ws-ov-grid" id="agentsOvGrid">
                    {% for agent in pyview.agents %}
                    <div class="ws-ov-card" data-name="{{ agent.name|lower }}" onclick="pyview.openAgent({{ agent.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                            </div>
                            <h3>{{ agent.name }}</h3>
                        </div>
                        <div class="ws-ov-card-info">
                            <div class="ws-ov-path" title="{{ agent.model_name }}">{{ agent.model_name }}</div>
                            <div class="ws-ov-desc">{{ agent.description }}</div>
                        </div>
                        <div class="ws-ov-card-bottom">
                            <div class="ws-ov-status">
                                {{ agent.skill_count }} skills · {{ agent.tool_count }} tools · {{ agent.task_count }} tasks · {{ agent.command_count }} cmd
                            </div>
                            <span>{{ agent.session_count }} session(s)</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" id="agentsOvEmpty" style="display:{% if pyview.agents %}none{% else %}block{% endif %}">
                    <div class="ws-ov-empty-icon">⌕</div>
                    <h2>No agents found</h2>
                    <div>Try another search or create a new agent.</div>
                </div>
            </div>
        </div>
        <script>
            function agentsOvFilter() {
                var q = document.getElementById("agentsOvSearch").value.toLowerCase();
                var cards = document.querySelectorAll("#agentsOvGrid .ws-ov-card");
                var visible = 0;
                for (var i = 0; i < cards.length; i++) {
                    var match = cards[i].dataset.name.toLowerCase().indexOf(q) !== -1;
                    cards[i].style.display = match ? "" : "none";
                    if (match) visible++;
                }
                document.getElementById("agentsOvEmpty").style.display = visible ? "none" : "block";
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agents(self) -> list[dict]:
        from server.models.agents.agent import AgentModel

        try:
            all_agents = list(AgentModel.objects.all().order_by("name"))
        except Exception:
            return []
        return [agent_card_data(a) for a in all_agents]

    def openAgent(self, pk: int) -> None:
        from server.models.agents.agent import AgentModel
        from ui.main.agent.agent_view import AgentView

        try:
            agent = AgentModel.objects.get(pk=int(pk))
        except (AgentModel.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(AgentView, agent)

    def openCreate(self) -> None:
        from ui.main.agent.create import AgentCreateView

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(AgentCreateView, self.subject)

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
