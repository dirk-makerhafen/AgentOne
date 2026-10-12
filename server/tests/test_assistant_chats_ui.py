"""Stub-render + wiring tests for the entity assistant chats (no DB).

Every entity has a singular ``<entity>_assistant`` embedded in its single-item
right panel and a plural ``<entity>s_assistant`` embedded in the dashboard.
These tests cover the agent mapping, scope hooks, panel wiring, and the shared
template without touching the database.
"""
from __future__ import annotations
import inspect
from types import SimpleNamespace

import jinja2


def _render(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


def _pyview(**overrides):
    base = dict(assistant_title="Assistant", assistant_sessions=[], selected_pk=None, chat=None)
    base.update(overrides)
    return SimpleNamespace(**base)


class FakeChat:
    def render(self):
        return "<div>mini-chat</div>"


ITEM_PANELS = {
    "agent_assistant": "RightPanelAgentAssistant",
    "cronjob_assistant": "RightPanelCronjobAssistant",
    "skill_assistant": "RightPanelSkillAssistant",
    "project_assistant": "RightPanelProjectAssistant",
}

DASHBOARD_PANELS = {
    "agents_assistant": "RightPanelAgentsOverview",
    "cronjobs_assistant": "RightPanelCronjobsOverview",
    "projects_assistant": "RightPanelProjectsOverview",
    "workitems_assistant": "RightPanelWorkItemsAssistant",
    "workspaces_assistant": "RightPanelWorkspacesOverview",
}


def _panel(name):
    import ui.main.rightpanel.assistant_chat as mod

    return getattr(mod, name)


class TestAgentMapping:
    def test_item_panels_use_singular_agent(self):
        for agent_name, class_name in ITEM_PANELS.items():
            assert _panel(class_name).ASSISTANT_AGENT_NAME == agent_name

    def test_dashboard_panels_use_plural_agent(self):
        for agent_name, class_name in DASHBOARD_PANELS.items():
            assert _panel(class_name).ASSISTANT_AGENT_NAME == agent_name

    def test_every_panel_has_a_title(self):
        for class_name in list(ITEM_PANELS.values()) + list(DASHBOARD_PANELS.values()):
            assert _panel(class_name).ASSISTANT_TITLE


class TestScopeHooks:
    def test_item_panels_bind_parent_project(self):
        for class_name in ("RightPanelAgentAssistant", "RightPanelCronjobAssistant", "RightPanelSkillAssistant"):
            cls = _panel(class_name)
            subject = SimpleNamespace(parent_project="PROJ", name="thing")
            obj = SimpleNamespace(subject=subject)
            assert cls.assistant_project(obj) == "PROJ"
            assert cls.assistant_item_label(obj) == "thing"

    def test_project_panel_binds_itself(self):
        cls = _panel("RightPanelProjectAssistant")
        subject = SimpleNamespace(name="proj")
        obj = SimpleNamespace(subject=subject)
        assert cls.assistant_project(obj) is subject
        assert cls.assistant_item_label(obj) == "proj"

    def test_scoped_dashboards_override_assistant_project(self):
        for class_name in ("RightPanelAgentsOverview", "RightPanelCronjobsOverview", "RightPanelWorkItemsAssistant"):
            assert "assistant_project" in _panel(class_name).__dict__

    def test_global_dashboards_leave_scope_unset(self):
        for class_name in ("RightPanelProjectsOverview", "RightPanelWorkspacesOverview"):
            cls = _panel(class_name)
            assert "assistant_project" not in cls.__dict__
            assert "assistant_workspace" not in cls.__dict__


class TestTemplate:
    def test_empty_state_offers_new_chat(self):
        cls = _panel("RightPanelAgentAssistant")
        html = _render(cls.TEMPLATE_STR, pyview=_pyview(assistant_title=cls.ASSISTANT_TITLE))
        assert "Agent Assistant" in html
        assert "No assistant chat yet." in html
        assert "newAssistantChat()" in html

    def test_session_selector_and_chat(self):
        cls = _panel("RightPanelAgentsOverview")
        sessions = [
            SimpleNamespace(pk=1, name="agents_assistant"),
            SimpleNamespace(pk=2, name="agents_assistant-2"),
        ]
        html = _render(
            cls.TEMPLATE_STR,
            pyview=_pyview(assistant_sessions=sessions, selected_pk=2, chat=FakeChat()),
        )
        assert "selectAssistantChat" in html
        assert "agents_assistant-2" in html
        assert "mini-chat" in html

    def test_dashboard_panel_has_resize_handle(self):
        assert "resize-handle" in _panel("RightPanelAgentsOverview").TEMPLATE_STR
        assert "resize-handle" not in _panel("RightPanelAgentAssistant").TEMPLATE_STR


class TestDashboardWiring:
    def test_dashboard_views_declare_rightpanel_view(self):
        from ui.main.agent.overview import AgentsOverview
        from ui.main.cron.overview import CronOverview
        from ui.main.project.overview import ProjectsOverview
        from ui.main.workitems.board import WorkItemsBoard

        assert AgentsOverview.RIGHTPANEL_VIEW is _panel("RightPanelAgentsOverview")
        assert CronOverview.RIGHTPANEL_VIEW is _panel("RightPanelCronjobsOverview")
        assert ProjectsOverview.RIGHTPANEL_VIEW is _panel("RightPanelProjectsOverview")
        assert WorkItemsBoard.RIGHTPANEL_VIEW is _panel("RightPanelWorkItemsAssistant")


class TestItemPanelWiring:
    CASES = [
        ("ui.main.rightpanel.agent.rightpanel_agent", "RightPanelAgent", "RightPanelAgentAssistant"),
        ("ui.main.rightpanel.cron.rightpanel_cron", "RightPanelCron", "RightPanelCronjobAssistant"),
        ("ui.main.rightpanel.skill.rightpanel_skill", "RightPanelSkill", "RightPanelSkillAssistant"),
        ("ui.main.rightpanel.project.rightpanel_project", "RightPanelProject", "RightPanelProjectAssistant"),
    ]

    def test_switch_tab_accepts_assistant(self):
        for module_path, class_name, panel_name in self.CASES:
            mod = __import__(module_path, fromlist=[class_name])
            src = inspect.getsource(getattr(mod, class_name).switchTab)
            assert "assistant" in src, class_name
            assert panel_name in src, class_name

    def test_nav_has_assistant_button(self):
        for module_path, class_name, _panel_name in self.CASES:
            mod = __import__(module_path, fromlist=[class_name])
            template = getattr(mod, class_name).TEMPLATE_STR
            assert "switchTab('assistant')" in template
