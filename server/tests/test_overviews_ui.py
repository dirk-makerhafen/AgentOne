"""Stub-render tests for the overview pages (no DB).

Covers ChatsOverview (new-chat form), AgentsOverview, ProjectsOverview and
CronOverview templates plus the pure row/card helpers and the sidebar
panel_activated wiring.
"""
from __future__ import annotations
from datetime import datetime
from types import SimpleNamespace

import jinja2


def _render(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


def _chat_pyview(**overrides):
    base = dict(
        preset_workspace=None,
        form={"name": "", "agent_id": "1", "workspace_id": "", "description": ""},
        form_error="",
        agent_options=[SimpleNamespace(pk=1, name="Helper")],
        workspace_options=[SimpleNamespace(pk=2, name="WS")],
        recent_chats=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestChatsOverviewTemplate:
    def test_form_fields_present(self):
        from ui.main.chat.overview import ChatsOverview

        html = _render(ChatsOverview.TEMPLATE_STR, pyview=_chat_pyview())
        assert "newChatName" in html
        assert "newChatAgent" in html
        assert "newChatWorkspace" in html
        assert "newChatDescription" in html
        assert "Start chat" in html
        assert "Helper" in html and "WS" in html
        assert "Recent chats" in html

    def test_form_error_shown(self):
        from ui.main.chat.overview import ChatsOverview

        html = _render(
            ChatsOverview.TEMPLATE_STR,
            pyview=_chat_pyview(form_error="Select an agent first."),
        )
        assert "Select an agent first." in html

    def test_recent_chats_render_with_workspace_color(self):
        from ui.main.chat.overview import ChatsOverview

        chats = [
            {
                "pk": 5, "name": "Chat 5", "agent_name": "Helper",
                "workspace_color": "#ef4444", "workspace_name": "WS",
                "turn_count": 3,
            },
        ]
        html = _render(ChatsOverview.TEMPLATE_STR, pyview=_chat_pyview(recent_chats=chats))
        assert "Chat 5" in html and "#ef4444" in html
        assert "openChat(5)" in html

    def test_preset_workspace_crumb(self):
        from ui.main.chat.overview import ChatsOverview

        ws = SimpleNamespace(name="MySpace")
        html = _render(ChatsOverview.TEMPLATE_STR, pyview=_chat_pyview(preset_workspace=ws))
        assert "MySpace" in html


class TestAgentsOverviewTemplate:
    def test_cards_render(self):
        from ui.main.agent.overview import AgentsOverview

        agents = [
            {
                "pk": 1, "name": "Helper", "description": "Helps",
                "model_name": "gpt-x", "skill_count": 2, "tool_count": 3,
                "task_count": 1, "command_count": 0, "session_count": 4,
            },
        ]
        html = _render(AgentsOverview.TEMPLATE_STR, pyview=SimpleNamespace(agents=agents))
        assert "Helper" in html and "gpt-x" in html
        assert "openAgent(1)" in html and "openCreate()" in html

    def test_empty_state(self):
        from ui.main.agent.overview import AgentsOverview

        html = _render(AgentsOverview.TEMPLATE_STR, pyview=SimpleNamespace(agents=[]))
        assert "No agents found" in html


class TestProjectsOverviewTemplate:
    def test_cards_render(self):
        from ui.main.project.overview import ProjectsOverview

        projects = [
            {
                "pk": 7, "name": "Site", "description": "Web",
                "path": "/tmp/site", "agent_count": 1,
                "session_count": 2, "cron_count": 0,
            },
        ]
        html = _render(ProjectsOverview.TEMPLATE_STR, pyview=SimpleNamespace(projects=projects))
        assert "Site" in html and "/tmp/site" in html
        assert "openProject(7)" in html

    def test_empty_state(self):
        from ui.main.project.overview import ProjectsOverview

        html = _render(ProjectsOverview.TEMPLATE_STR, pyview=SimpleNamespace(projects=[]))
        assert "No projects found" in html


class TestCronOverviewTemplate:
    def test_table_renders(self):
        from ui.main.cron.overview import CronOverview

        jobs = [
            {
                "pk": 3, "name": "Morning", "schedule": "0 9 * * *",
                "agent_name": "Helper", "status": "active",
                "last_run_at": "2026-09-01 09:00", "next_run_at": "2026-09-02 09:00",
                "total_runs": 10,
            },
        ]
        html = _render(CronOverview.TEMPLATE_STR, pyview=SimpleNamespace(jobs=jobs))
        assert "Morning" in html and "0 9 * * *" in html
        assert "openJob(3)" in html and "active" in html

    def test_empty_state(self):
        from ui.main.cron.overview import CronOverview

        html = _render(CronOverview.TEMPLATE_STR, pyview=SimpleNamespace(jobs=[]))
        assert "No scheduled jobs found" in html


class TestRowHelpers:
    def test_cron_row_data(self):
        from ui.main.cron.overview import cron_row_data

        agent = SimpleNamespace(name="Helper")
        job = SimpleNamespace(
            pk=3, name="Morning", schedule="@daily", agent=agent,
            is_archived=False, is_active=True,
            last_run_at=datetime(2026, 9, 1, 9, 0), next_run_at=None,
            total_runs=5,
        )
        row = cron_row_data(job)
        assert row["status"] == "active"
        assert row["agent_name"] == "Helper"
        assert row["last_run_at"] == "2026-09-01 09:00"
        assert row["next_run_at"] == "—"

    def test_cron_row_archived(self):
        from ui.main.cron.overview import cron_row_data

        job = SimpleNamespace(
            pk=4, name="Old", schedule="x", agent=None,
            is_archived=True, is_active=False,
            last_run_at=None, next_run_at=None, total_runs=0,
        )
        assert cron_row_data(job)["status"] == "archived"

    def test_project_card_data_never_raises(self):
        from ui.main.project.overview import project_card_data

        project = SimpleNamespace(pk=1, name="P", description="d", path="/x")
        card = project_card_data(project)
        assert card["name"] == "P" and card["path"] == "/x"

    def test_agent_card_data_never_raises(self):
        from ui.main.agent.overview import agent_card_data

        agent = SimpleNamespace(pk=1, name="A")
        card = agent_card_data(agent)
        assert card["name"] == "A"


class TestPanelWiring:
    def test_panels_have_panel_activated(self):
        from ui.sidebar.panels.agents import SidebarPanelAgents
        from ui.sidebar.panels.projects import SidebarPanelProjects
        from ui.sidebar.panels.cron import SidebarPanelCronjobs
        from ui.sidebar.panels.chats import SidebarPanelChats

        for cls in (SidebarPanelAgents, SidebarPanelProjects, SidebarPanelCronjobs, SidebarPanelChats):
            assert callable(getattr(cls, "panel_activated", None)), cls.__name__

    def test_sidebar_new_conversation_opens_overview(self):
        import inspect
        from ui.sidebar.panels.chats import SidebarPanelChats

        src = inspect.getsource(SidebarPanelChats.new_conversation)
        assert "ChatsOverview" in src
        assert "get_or_create_session" not in src

    def test_workspace_new_chat_opens_overview(self):
        import inspect
        from ui.main.workspace.workspace import Workspace

        src = inspect.getsource(Workspace.newChat)
        assert "ChatsOverview" in src
        assert "get_or_create_session" not in src
