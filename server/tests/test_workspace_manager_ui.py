"""Stub-render + pure-logic tests for the Workspace Manager (no DB).

Covers the right-panel manager tab template, the embedded mini-chat
template, the agent-scoped workspace tool error paths (unbound session),
path helpers, and the panel wiring.
"""
from __future__ import annotations
import glob
from types import SimpleNamespace

import jinja2


def _find_workspace_tools():
    """Locate the workspace agent's tools script (survives agent renames)."""
    for path in sorted(glob.glob(".agentone/agents/**/workspaces.py", recursive=True)):
        try:
            if "def list_subworkspaces" in open(path, encoding="utf-8").read():
                return path
        except OSError:
            continue
    return ".agentone/agents/internal/workspace_assistant/scripts/workspaces.py"


def _find_workspace_agent_md():
    """Locate the workspace agent manifest (survives agent renames)."""
    for path in sorted(glob.glob(".agentone/agents/**/agent.md", recursive=True)):
        try:
            if "Manages a single workspace" in open(path, encoding="utf-8").read():
                return path
        except OSError:
            continue
    return ".agentone/agents/internal/workspace_assistant/agent.md"


WORKSPACE_TOOLS_PY = _find_workspace_tools()
WORKSPACE_AGENT_MD = _find_workspace_agent_md()


def _render(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


def _manager_pyview(**overrides):
    base = dict(sessions=[], selected_pk=None, chat=None)
    base.update(overrides)
    return SimpleNamespace(**base)


class FakeChat:
    def render(self):
        return "<div>mini-chat</div>"


class TestManagerTabTemplate:
    def test_empty_state_with_new_chat_button(self):
        from ui.main.rightpanel.workspace.rightpanel_workspace_manager import (
            RightPanelWorkspaceManager,
        )

        html = _render(
            RightPanelWorkspaceManager.TEMPLATE_STR, pyview=_manager_pyview()
        )
        assert "Workspace Manager" in html
        assert "New Chat" in html
        assert "newManagerChat()" in html
        assert "No manager chat yet." in html

    def test_session_selector_and_chat(self):
        from ui.main.rightpanel.workspace.rightpanel_workspace_manager import (
            RightPanelWorkspaceManager,
        )

        sessions = [
            SimpleNamespace(pk=11, name="privat-manager"),
            SimpleNamespace(pk=12, name="privat-manager-2"),
        ]
        html = _render(
            RightPanelWorkspaceManager.TEMPLATE_STR,
            pyview=_manager_pyview(
                sessions=sessions, selected_pk=12, chat=FakeChat()
            ),
        )
        assert "privat-manager" in html
        assert "selectManagerChat" in html
        assert "mini-chat" in html


class TestMiniChatTemplate:
    def test_renders_children(self):
        from ui.main.rightpanel.workspace.rightpanel_workspace_manager import (
            ManagerChat,
        )

        class FakePart:
            def __init__(self, label):
                self.label = label

            def render(self):
                return f"<div>{self.label}</div>"

        pyview = SimpleNamespace(
            messages=FakePart("msgs"),
            queue_card=FakePart("queue"),
            approval_card=FakePart("approval"),
            question_card=FakePart("question"),
            composer_box=FakePart("composer"),
        )
        html = _render(ManagerChat.TEMPLATE_STR, pyview=pyview)
        for label in ("msgs", "queue", "approval", "question", "composer"):
            assert label in html


class UnboundSession:
    workspace = None


class TestToolUnboundSession:
    """All tools must fail cleanly when the session has no workspace (no DB)."""

    def test_all_tools_reject_unbound(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "wm_workspaces",
            WORKSPACE_TOOLS_PY,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        results = [
            mod.list_subworkspaces(UnboundSession()),
            mod.create_subworkspace(UnboundSession(), "x", "/tmp/x"),
            mod.edit_workspace(UnboundSession(), description="d"),
            mod.rename_workspace(UnboundSession(), "new"),
            mod.list_sessions(UnboundSession()),
            mod.create_chat(UnboundSession(), "AgentOne"),
        ]
        assert len(results) == 6
        for ok, payload in results:
            assert ok is False
            assert payload["status"] == "error"
            assert "not bound" in payload["message"]

    def test_create_chat_requires_agent_name(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "wm_workspaces2",
            WORKSPACE_TOOLS_PY,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ok, payload = mod.create_chat(
            SimpleNamespace(workspace=SimpleNamespace(pk=1, name="ws", path="/tmp")), ""
        )
        assert ok is False
        assert "agent name" in payload["message"].lower()


class TestPathHelpers:
    def test_is_within(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "wm_workspaces3",
            WORKSPACE_TOOLS_PY,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod._is_within("/a/b/c", "/a/b") is True
        assert mod._is_within("/a/b", "/a/b") is False
        assert mod._is_within("/a/b2", "/a/b") is False
        assert mod._is_within("/other", "/a/b") is False


class TestPanelWiring:
    def test_switch_tab_accepts_manager(self):
        import inspect
        from ui.main.rightpanel.workspace.rightpanel_workspace import (
            RightPanelWorkspace,
        )

        src = inspect.getsource(RightPanelWorkspace.switchTab)
        assert "manager" in src
        assert "RightPanelWorkspaceManager" in src

    def test_nav_has_manager_button(self):
        from ui.main.rightpanel.workspace.rightpanel_workspace import (
            RightPanelWorkspace,
        )

        assert "switchTab('manager')" in RightPanelWorkspace.TEMPLATE_STR
        assert "Workspace Manager" in RightPanelWorkspace.TEMPLATE_STR

    def test_agent_manifest_names_workspace_tools(self):
        import frontmatter

        post = frontmatter.load(WORKSPACE_AGENT_MD)
        assert post.metadata["name"] in ("workspace_manager", "workspace_assistant")
        assert any("workspace" in t for t in post.metadata["tools"])

    def test_manager_chat_scroll_layout_css(self):
        """Messages wrapper must be a flex column so .messages{flex:1}
        constrains its height (scrolls) instead of pushing the composer
        out of view."""
        import re

        css = open("ui/static/css/main.css").read()
        m = re.search(r"\.manager-chat-messages\{([^}]*)\}", css)
        assert m, "missing .manager-chat-messages rule"
        body = m.group(1)
        assert "display:flex" in body.replace(" ", "")
        assert "flex-direction:column" in body.replace(" ", "")
        assert "min-height:0" in body.replace(" ", "")


def _overview_pyview(**overrides):
    base = dict(assistant_sessions=[], selected_pk=None, chat=None)
    base.update(overrides)
    return SimpleNamespace(**base)


class TestOverviewManagerPanel:
    """Top-level workspaces dashboard right panel (plural assistant chat)."""

    def test_overview_uses_dashboard_rightpanel(self):
        from ui.main.workspace.overview import WorkspacesOverview
        from ui.main.rightpanel.workspace.rightpanel_workspaces_overview import (
            RightPanelWorkspacesOverview,
        )

        assert WorkspacesOverview.RIGHTPANEL_VIEW is RightPanelWorkspacesOverview

    def test_panel_targets_plural_workspaces_assistant(self):
        from ui.main.rightpanel.workspace.rightpanel_workspaces_overview import (
            RightPanelWorkspacesOverview,
        )

        assert RightPanelWorkspacesOverview.ASSISTANT_AGENT_NAME == "workspaces_assistant"

    def test_session_selector_and_chat(self):
        from ui.main.rightpanel.workspace.rightpanel_workspaces_overview import (
            RightPanelWorkspacesOverview,
        )

        sessions = [
            SimpleNamespace(pk=11, name="workspaces_assistant"),
            SimpleNamespace(pk=12, name="workspaces_assistant-2"),
        ]
        html = _render(
            RightPanelWorkspacesOverview.TEMPLATE_STR,
            pyview=_overview_pyview(
                assistant_sessions=sessions, selected_pk=12, chat=FakeChat()
            ),
        )
        assert "selectAssistantChat" in html
        assert "workspaces_assistant-2" in html
        assert "mini-chat" in html

    def test_no_sessions_shows_new_chat(self):
        from ui.main.rightpanel.workspace.rightpanel_workspaces_overview import (
            RightPanelWorkspacesOverview,
        )

        html = _render(
            RightPanelWorkspacesOverview.TEMPLATE_STR, pyview=_overview_pyview()
        )
        assert "No assistant chat yet." in html
        assert "newAssistantChat()" in html

    def test_new_manager_chat_needs_workspace(self):
        """Guard returns cleanly without a bound workspace (no DB access)."""
        from ui.main.rightpanel.workspace.rightpanel_workspace_manager import (
            ManagerChatMixin,
        )

        obj = SimpleNamespace(manager_workspace=None, update=lambda: None)
        assert ManagerChatMixin.newManagerChat(obj) is None

    def test_manager_workspace_defaults_to_subject(self):
        from ui.main.rightpanel.workspace.rightpanel_workspace_manager import (
            ManagerChatMixin,
        )

        ws = SimpleNamespace(pk=1, name="alpha")
        obj = SimpleNamespace(subject=ws)
        assert ManagerChatMixin.manager_workspace.fget(obj) is ws
