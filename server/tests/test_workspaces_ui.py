"""Tests for the workspace sidebar tree, overview grid and detail page."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock

import jinja2
from django.test import TestCase

from ui.sidebar.panels.workspaces import build_workspace_tree


def _ws(pk, name, path):
    return SimpleNamespace(pk=pk, name=name, path=path)


class TestBuildWorkspaceTree:
    def test_roots_and_nesting(self):
        items = [
            _ws(1, "Projects", "/data/projects"),
            _ws(2, "Harness", "/data/projects/harness"),
            _ws(3, "Exp", "/data/projects/harness/exp"),
            _ws(4, "Other", "/data/other"),
        ]
        rows = build_workspace_tree(items)
        assert [(r["pk"], r["depth"]) for r in rows] == [(4, 0), (1, 0), (2, 1), (3, 2)]
        assert rows[2]["display_path"] == "harness"
        assert rows[3]["display_path"] == "exp"
        assert rows[0]["display_path"] == "/data/other"
        assert rows[1]["has_children"] is True
        assert rows[3]["has_children"] is False

    def test_similar_prefix_is_not_a_parent(self):
        rows = build_workspace_tree([_ws(1, "a", "/data/a"), _ws(2, "a2", "/data/a2")])
        assert all(r["depth"] == 0 for r in rows)

    def test_longest_prefix_wins(self):
        rows = build_workspace_tree(
            [_ws(1, "a", "/x"), _ws(2, "b", "/x/y"), _ws(3, "c", "/x/y/z")]
        )
        assert [r["depth"] for r in rows] == [0, 1, 2]

    def test_siblings_sorted_by_name(self):
        rows = build_workspace_tree(
            [_ws(1, "zeta", "/z"), _ws(2, "alpha", "/a"), _ws(3, "mid", "/m")]
        )
        assert [r["name"] for r in rows] == ["alpha", "mid", "zeta"]

    def test_root_slash_never_parents(self):
        rows = build_workspace_tree([_ws(1, "root", "/"), _ws(2, "a", "/a")])
        assert all(r["depth"] == 0 for r in rows)

    def test_empty_name_falls_back_to_path(self):
        rows = build_workspace_tree([_ws(1, "", "/data/nameless")])
        assert rows[0]["name"] == "/data/nameless"

    def test_parent_map_shared_helper(self):
        from ui.main.workspace.workspace import workspace_parent_map

        items = [_ws(1, "a", "/x"), _ws(2, "b", "/x/y"), _ws(3, "c", "/z")]
        assert workspace_parent_map(items) == {1: None, 2: 1, 3: None}


class FakeInstance:
    """Minimal PyHtmlGuiInstance stand-in: real jinja templates, no sockets."""

    def __init__(self):
        self.instance_key = "test"
        self.observed_views = {}
        self._function_references = MagicMock()
        self._template_cache = {}
        self._env = jinja2.Environment(autoescape=jinja2.select_autoescape())
        self._env.globals["_create_py_function_reference"] = lambda f: str(f)
        self.add_css_string = MagicMock()
        self.call_javascript = MagicMock()

    def get_template(self, view, force_reload=False):
        from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance

        key = view.__class__.__name__
        if key not in self._template_cache:
            self._template_cache[key] = self._env.from_string(
                PyHtmlGuiInstance._prepare_template(view.TEMPLATE_STR),
            )
        return self._template_cache[key]

    def _add_polling_child(self, child):
        pass

    def _remove_polling_child(self, child):
        pass


def _render_template(template_str, **context):
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


class TestWorkspaceTemplates:
    """Render the raw templates with stub data (no DB, runs anywhere)."""

    def test_sidebar_tree_template(self):
        from ui.sidebar.panels.workspaces import SidebarPanelWorkspaces

        rows = build_workspace_tree(
            [_ws(1, "Projects", "/p"), _ws(2, "Sub", "/p/sub")]
        )
        pyview = SimpleNamespace(
            tree_rows=rows, collapsed={1}, current_workspace_pk=2,
            active_workspace_pk=1,
        )
        html = _render_template(SidebarPanelWorkspaces.TEMPLATE_STR, pyview=pyview)
        assert "Projects" in html and "Sub" in html
        assert "padding-left:8px" in html and "padding-left:26px" in html
        assert "ACTIVE" in html
        assert "ws-tree-chevron" not in html
        # Parent (collapsed) gets the files-icon toggle, leaf a plain folder.
        assert html.count("ws-tree-folder--toggle") == 1
        assert 'title="Expand"' in html

    def test_overview_template_grid_and_list(self):
        from ui.main.workspace.overview import WorkspacesOverview

        cards = [
            {"pk": 1, "name": "A", "path": "/a", "description": "d",
             "session_count": 2, "agent_count": 1},
        ]
        for mode in ("grid", "list"):
            pyview = SimpleNamespace(
                workspaces=cards, view_mode=mode, active_workspace_pk=1,
            )
            html = _render_template(WorkspacesOverview.TEMPLATE_STR, pyview=pyview)
            assert "ws-ov-card" in html and "/a" in html
            assert "2 session(s)" in html
            if mode == "list":
                assert "ws-ov-list" in html

    def test_detail_template(self):
        from ui.main.workspace.workspace import Workspace

        subject = SimpleNamespace(name="Demo", path="/demo", pk=1)
        child = {
            "pk": 2, "name": "Kid", "path": "/demo/kid",
            "description": "kid desc", "session_count": 1, "agent_count": 1,
        }
        pyview = SimpleNamespace(
            subject=subject, view_mode="grid", ancestors=[],
            children_cards=[child], child_count=1, active_workspace_pk=1,
            related_chats=[], chat_count=0, chat_page=0, chat_page_count=1,
        )
        html = _render_template(Workspace.TEMPLATE_STR, pyview=pyview)
        assert "Demo" in html and "/demo" in html
        assert "Kid" in html and "kid desc" in html
        assert "1 session(s)" in html
        assert "ws-card-menu" in html and "wsRename" in html
        assert "ws-detail-about" not in html
        assert "checkpointListContainer" not in html
        # Current-workspace card on top, then chats, then the section headline.
        assert "ws-current-card" in html
        assert "Sub workspaces" in html
        assert html.index("ws-current-card") < html.index("ws-chat-head")
        assert html.index("ws-chat-head") < html.index("Sub workspaces")
        assert html.index("ws-sub-head") < html.index("wsOvGrid")
        # Child cards: name next to the icon, no per-card menu button
        # (only the current-workspace card keeps one).
        assert html.count("ws-card-menu-btn") == 1
        assert html.index("ws-ov-card-top") < html.index("<h3>Kid</h3>")
        assert html.index("<h3>Kid</h3>") < html.index("ws-ov-card-info")

    def test_detail_template_empty_state(self):
        from ui.main.workspace.workspace import Workspace

        subject = SimpleNamespace(name="Leaf", path="/leaf", pk=9)
        pyview = SimpleNamespace(
            subject=subject, view_mode="grid", ancestors=[],
            children_cards=[], child_count=0, active_workspace_pk=None,
            editing=False, related_chats=[], chat_count=0,
            chat_page=0, chat_page_count=1,
        )
        html = _render_template(Workspace.TEMPLATE_STR, pyview=pyview)
        assert "Sub workspaces" in html
        assert "No sub workspaces found" in html
        assert "Chats" in html
        assert "No chats found" in html

    def test_detail_template_chats(self):
        from ui.main.workspace.workspace import Workspace

        subject = SimpleNamespace(name="Demo", path="/demo", pk=1)
        chats = [
            {"pk": 11, "name": "Main chat", "type_label": "Session",
             "is_active": True, "turn_count": 5},
            {"pk": 12, "name": "Helper", "type_label": "Subsession",
             "is_active": False, "turn_count": 0},
        ]
        pyview = SimpleNamespace(
            subject=subject, view_mode="grid", ancestors=[],
            children_cards=[], child_count=0, active_workspace_pk=None,
            editing=False, related_chats=chats, chat_count=2,
            chat_page=0, chat_page_count=1,
        )
        html = _render_template(Workspace.TEMPLATE_STR, pyview=pyview)
        assert "Chats" in html
        assert "Main chat" in html and "Helper" in html
        assert "Subsession" in html and "5 turn(s)" in html
        assert "pyview.openChat(11)" in html
        # Inactive chat gets the idle dot; active one does not.
        assert "ws-ov-dot--idle" in html
        # Empty state stays in the DOM but hidden when chats exist.
        assert html.count("No chats found") == 1
        assert 'class="ws-ov-empty" style="display:none"' in html

    def test_detail_template_chat_pager(self):
        from ui.main.workspace.workspace import Workspace

        subject = SimpleNamespace(name="Demo", path="/demo", pk=1)
        base = dict(
            subject=subject, view_mode="grid", ancestors=[],
            children_cards=[], child_count=0, active_workspace_pk=None,
            editing=False, related_chats=[], chat_count=25,
        )
        # Single page: no pager at all.
        html = _render_template(
            Workspace.TEMPLATE_STR,
            pyview=SimpleNamespace(**{**base, "chat_page": 0,
                                      "chat_page_count": 1}),
        )
        assert "ws-chat-pager" not in html
        # Multi-page: label plus prev/next wiring, prev disabled on page 1.
        html = _render_template(
            Workspace.TEMPLATE_STR,
            pyview=SimpleNamespace(**{**base, "chat_page": 0,
                                      "chat_page_count": 3}),
        )
        assert "ws-chat-pager" in html
        assert "1 / 3" in html
        assert "pyview.setChatPage(1)" in html
        assert "pyview.setChatPage(-1)" in html
        assert html.count("disabled") == 1
        # Last page: next disabled instead.
        html = _render_template(
            Workspace.TEMPLATE_STR,
            pyview=SimpleNamespace(**{**base, "chat_page": 2,
                                      "chat_page_count": 3}),
        )
        assert "3 / 3" in html
        assert html.count("disabled") == 1
        assert "pyview.setChatPage(3)" in html

    def test_detail_template_edit_mode(self):
        from ui.main.workspace.workspace import Workspace

        subject = SimpleNamespace(name="Demo", path="/demo",
                                  description="d", pk=1)
        access_stub = SimpleNamespace(render=lambda: "<div>access</div>")
        pyview = SimpleNamespace(
            subject=subject, view_mode="grid", ancestors=[],
            children_cards=[], child_count=0, active_workspace_pk=None,
            editing=True,
            edit_data={"name": "Demo", "path": "/demo", "description": "d"},
            edit_error="", access_editor=access_stub,
            related_chats=[], chat_count=0, chat_page=0, chat_page_count=1,
        )
        html = _render_template(Workspace.TEMPLATE_STR, pyview=pyview)
        assert "ws-current-input" in html
        assert "access" in html

    def test_create_template(self):
        from ui.main.workspace.create import CreateWorkspace

        access_stub = SimpleNamespace(render=lambda: "<div>access</div>")
        pyview = SimpleNamespace(
            form={"name": "", "path": "", "description": ""},
            form_error="", access_editor=access_stub,
        )
        html = _render_template(CreateWorkspace.TEMPLATE_STR, pyview=pyview)
        assert "workspaceFormDescription" in html
        assert "access" in html
        assert "pyview.saveWorkspaceForm()" in html

    def test_access_editor_template(self):
        from ui.main.workspace.access_editor import AccessEditor

        editor = SimpleNamespace(
            sections=("read", "write"), keys=("allow", "ask", "deny"),
            defaults=("allow", "ask", "deny"),
            data={"read": {"default": "ask", "allow": [], "ask": [],
                           "deny": []},
                  "write": {"default": "deny", "allow": [], "ask": [],
                            "deny": []}},
            list_text=lambda s, k: "",
        )
        html = _render_template(AccessEditor.TEMPLATE_STR, pyview=editor)
        assert html.count("ws-access-section") == 2
        assert "pyview.setAccessList(" in html


class TestAccessEditor:
    def _editor(self, access=None):
        from ui.main.workspace.access_editor import AccessEditor

        class FakeSubject:
            pass

        class FakeParent:
            def __init__(self):
                self._instance = FakeInstance()

            def _add_child(self, child):
                pass

        return AccessEditor(
            subject=FakeSubject(), parent=FakeParent(), access=access,
        )

    def test_normalize_fills_shape(self):
        editor = self._editor(access={"read": {"default": "allow"}})
        data = editor.access_data
        assert data["read"]["default"] == "allow"
        assert data["read"]["allow"] == []
        # Unset sections fall back to the runtime inside-default (allow),
        # so saving an untouched workspace never narrows its policy.
        assert data["write"]["default"] == "allow"

    def test_invalid_default_falls_back(self):
        editor = self._editor(access={"write": {"default": "bogus"}})
        assert editor.access_data["write"]["default"] == "allow"

    def test_unconfigured_workspace_stays_open(self):
        # Regression: saving a workspace whose access was never configured
        # must not narrow it to ask/ask (which halted every read behind an
        # approval popup the auto-reviewer never sees).
        for access in (None, {}, {"read": {}, "write": {}}):
            editor = self._editor(access=access)
            data = editor.access_data
            assert data["read"]["default"] == "allow", access
            assert data["write"]["default"] == "allow", access

    def test_set_access_and_lists(self):
        editor = self._editor()
        editor.setAccess("read", "default", "deny")
        editor.setAccessList("read", "allow", "src/**\n\ndocs/**\n")
        assert editor.access_data["read"]["default"] == "deny"
        assert editor.access_data["read"]["allow"] == ["src/**", "docs/**"]
        assert editor.list_text("read", "allow") == "src/**\ndocs/**"

    def test_rejects_bad_section_and_default(self):
        editor = self._editor()
        editor.setAccess("bogus", "default", "allow")
        editor.setAccess("read", "default", "bogus")
        assert editor.access_data["read"]["default"] == "allow"


class FakeRootView:
    def __init__(self, instance: FakeInstance):
        self._instance = instance
        self.main_panel = MagicMock()
        self.main_panel.selected_tab_view = None
        self.main_panel.open_tabs = {}


class FakeSidebar:
    def __init__(self, instance: FakeInstance, root_view: FakeRootView):
        self._instance = instance
        self.root_view = root_view

    def _add_child(self, child):
        pass


class TestSidebarTreePanel(TestCase):
    """DB-backed panel behaviour (runs in the real env)."""

    def setUp(self):
        from server.models.workspace import WorkspaceModel

        self.WorkspaceModel = WorkspaceModel
        self.root = WorkspaceModel.objects.create(name="Projects", path="/t/projects")
        self.child = WorkspaceModel.objects.create(
            name="Harness", path="/t/projects/harness"
        )
        self.other = WorkspaceModel.objects.create(name="Other", path="/t/other")

    def _panel(self):
        from ui.app import UiApp
        from ui.sidebar.panels.workspaces import SidebarPanelWorkspaces

        instance = FakeInstance()
        root_view = FakeRootView(instance)
        panel = SidebarPanelWorkspaces(
            subject=UiApp(), parent=FakeSidebar(instance, root_view),
        )
        UiApp._instance = None
        return panel

    def test_tree_rows_nest_by_path(self):
        panel = self._panel()
        rows = panel.tree_rows
        by_pk = {r["pk"]: r for r in rows}
        assert by_pk[self.root.pk]["depth"] == 0
        assert by_pk[self.child.pk]["depth"] == 1
        assert by_pk[self.other.pk]["depth"] == 0
        assert by_pk[self.root.pk]["has_children"] is True

    def test_subtrees_collapsed_by_default(self):
        panel = self._panel()
        pks = [r["pk"] for r in panel.tree_rows]
        assert self.root.pk in pks and self.other.pk in pks
        assert self.child.pk not in pks

    def test_toggle_expands_and_collapses(self):
        panel = self._panel()
        assert len(panel.tree_rows) == 2
        panel.toggle_collapse(self.root.pk)
        assert len(panel.tree_rows) == 3
        panel.toggle_collapse(self.root.pk)
        pks = [r["pk"] for r in panel.tree_rows]
        assert self.root.pk in pks and self.child.pk not in pks

    def test_open_workspace_opens_detail_tab(self):
        from ui.main.workspace.workspace import Workspace

        panel = self._panel()
        panel.root_view.main_panel.create_and_open_tab = MagicMock()
        panel.open_workspace(self.child.pk)
        args, _ = panel.root_view.main_panel.create_and_open_tab.call_args
        assert args[0] is Workspace and args[1].pk == self.child.pk


class TestOverviewActions(TestCase):
    def setUp(self):
        from server.models.workspace import WorkspaceModel

        self.ws = WorkspaceModel.objects.create(name="Demo", path="/t/demo")

    def _overview(self):
        from ui.app import UiApp
        from ui.main.workspace.overview import WorkspacesOverview

        main = MagicMock()
        main.selected_tab_view = None
        main.open_tabs = {}
        main.create_and_open_tab = MagicMock()
        main.parent = None
        view = WorkspacesOverview(subject=UiApp(), parent=main)
        UiApp._instance = None
        return view, main

    def test_cards_list_all_workspaces(self):
        view, _ = self._overview()
        assert [c["pk"] for c in view.workspaces] == [self.ws.pk]

    def test_set_view_toggles_mode(self):
        view, _ = self._overview()
        assert view.view_mode == "grid"
        view.update = MagicMock()
        view.setView("list")
        assert view.view_mode == "list"
        view.setView("bogus")
        assert view.view_mode == "list"

    def test_open_workspace_dispatches_detail_tab(self):
        from ui.main.workspace.workspace import Workspace

        view, main = self._overview()
        view.openWorkspace(self.ws.pk)
        args, _ = main.create_and_open_tab.call_args
        assert args[0] is Workspace and args[1].pk == self.ws.pk


class TestWorkspaceDetailActions(TestCase):
    def setUp(self):
        import tempfile

        from server.models.workspace import WorkspaceModel

        self.tmp = tempfile.mkdtemp()
        self.ws = WorkspaceModel.objects.create(name="Demo", path=self.tmp)

    def _detail(self):
        from ui.main.workspace.workspace import Workspace

        main = MagicMock()
        main.selected_tab_view = None
        main.open_tabs = {}
        main.parent = None
        view = Workspace(subject=self.ws, parent=main)
        view.update = MagicMock()
        return view, main

    def test_save_rejects_empty_name(self):
        view, _ = self._detail()
        view.update = MagicMock()
        view.renameWorkspace(self.ws.pk, "  ")
        self.ws.refresh_from_db()
        assert self.ws.name == "Demo"

    def test_rename_persists(self):
        view, _ = self._detail()
        view.update = MagicMock()
        view.renameWorkspace(self.ws.pk, "Renamed")
        self.ws.refresh_from_db()
        assert self.ws.name == "Renamed"

    def test_delete_removes_child_and_refreshes(self):
        from server.models.workspace import WorkspaceModel

        view, _ = self._detail()
        view.update = MagicMock()
        kid = WorkspaceModel.objects.create(name="Kid", path="/t/demo/kid")
        view.deleteWorkspace(kid.pk)
        assert not WorkspaceModel.objects.filter(pk=kid.pk).exists()
        assert WorkspaceModel.objects.filter(pk=self.ws.pk).exists()

    def test_delete_current_workspace_closes_tab(self):
        from server.models.workspace import WorkspaceModel

        view, main = self._detail()
        view.deleteWorkspace(self.ws.pk)
        assert not WorkspaceModel.objects.filter(pk=self.ws.pk).exists()
        main.close_tab.assert_called_once_with(view)

    def test_save_edit_persists_all_fields(self):
        view, _ = self._detail()
        view.update = MagicMock()
        view.startEdit()
        view.setEditField("name", "Edited")
        view.setEditField("description", "edited desc")
        view.access_editor.setAccess("write", "default", "deny")
        view.access_editor.setAccessList("read", "allow", "src/**\n")
        view.saveEdit()
        assert view.editing is False
        self.ws.refresh_from_db()
        assert self.ws.name == "Edited"
        assert self.ws.description == "edited desc"
        assert self.ws.access["write"]["default"] == "deny"
        assert self.ws.access["read"]["allow"] == ["src/**"]

    def test_save_edit_rejects_bad_path(self):
        view, _ = self._detail()
        view.update = MagicMock()
        view.startEdit()
        view.setEditField("path", "/does/not/exist")
        view.saveEdit()
        assert view.editing is True and "directory" in view.edit_error

    def _bind_session(self, name, session_type, ws=None):
        from server.models.agent import AgentModel, AgentVersionModel
        from server.models.sessions.session import SessionModel
        from server.models.sessions.session_version import SessionVersionModel
        from server.models.settings import SettingsModel

        agent = AgentModel.objects.create(name=f"ag-{name}")
        av = AgentVersionModel.objects.create(
            agent=agent, agent_settings=SettingsModel.objects.create(),
        )
        session = SessionModel.objects.create(
            name=name, session_type=session_type,
        )
        sv = SessionVersionModel.objects.create(
            session=session, agent=agent, pinned_agent_version=av,
            workspace=ws,
        )
        SessionModel.objects.filter(pk=session.pk).update(
            latest_session_version=sv,
        )
        return session

    def test_related_chats_filters_by_type_and_workspace(self):
        from server.models.enums.session_enums import SessionType
        from server.models.workspace import WorkspaceModel

        other = WorkspaceModel.objects.create(name="Other", path="/t/other")
        keep = self._bind_session("Main", SessionType.SESSION, ws=self.ws)
        sub = self._bind_session("Helper", SessionType.SUBSESSION, ws=self.ws)
        self._bind_session("Delegated", SessionType.SUBTASK_DELEGATE, ws=self.ws)
        self._bind_session("Elsewhere", SessionType.SESSION, ws=other)
        self._bind_session("Unbound", SessionType.SESSION)
        view, _ = self._detail()
        assert [c["pk"] for c in view.related_chats] == [sub.pk, keep.pk]
        assert view.chat_count == 2
        assert {c["type_label"] for c in view.related_chats} == {
            "Session", "Subsession",
        }

    def test_open_chat_opens_session_tab(self):
        from server.models.enums.session_enums import SessionType
        from ui.main.chat.chat import Chat

        session = self._bind_session("Main", SessionType.SESSION, ws=self.ws)
        view, main = self._detail()
        view.openChat(session.pk)
        main.create_and_open_tab.assert_called_once_with(Chat, session)

    def test_open_chat_ignores_unknown_pk(self):
        view, main = self._detail()
        view.openChat(999999)
        main.create_and_open_tab.assert_not_called()

    def test_related_chats_paginates(self):
        from server.models.enums.session_enums import SessionType
        from ui.main.workspace.workspace import Workspace

        for i in range(12):
            self._bind_session(f"Paged {i:02d}", SessionType.SESSION,
                               ws=self.ws)
        view, _ = self._detail()
        assert view.chat_count == 12
        assert view.chat_page_count == 2
        assert len(view.related_chats) == Workspace.CHAT_PAGE_SIZE == 10
        view.setChatPage(1)
        assert view.chat_page == 1
        assert len(view.related_chats) == 2
        # Out-of-range pages clamp instead of going empty.
        view.setChatPage(99)
        assert view.chat_page == 1
        assert len(view.related_chats) == 2
        view.setChatPage(-5)
        assert view.chat_page == 0
        assert len(view.related_chats) == 10


class TestCreateWorkspace(TestCase):
    def _create_view(self):
        from ui.app import UiApp
        from ui.main.workspace.create import CreateWorkspace

        main = MagicMock()
        main.parent = None
        main.subject = MagicMock()
        view = CreateWorkspace(subject=UiApp(), parent=main)
        view.update = MagicMock()
        UiApp._instance = None
        return view, main

    def test_save_rejects_missing_path(self):
        view, _ = self._create_view()
        view.setWsField("path", "/does/not/exist")
        view.saveWorkspaceForm()
        assert "directory" in view.form_error

    def test_save_creates_workspace_with_description_and_access(self):
        import tempfile

        from server.models.workspace import WorkspaceModel
        from ui.main.workspace.workspace import Workspace

        tmp = tempfile.mkdtemp()
        view, main = self._create_view()
        view.setWsField("name", "New One")
        view.setWsField("path", tmp)
        view.setWsField("description", "shiny")
        view.access_editor.setAccess("read", "default", "allow")
        view.saveWorkspaceForm()
        ws = WorkspaceModel.objects.get(path=tmp)
        assert (ws.name, ws.description) == ("New One", "shiny")
        assert ws.access["read"]["default"] == "allow"
        args, _ = main.create_and_open_tab.call_args
        assert args[0] is Workspace and args[1].pk == ws.pk
        main.close_tab.assert_called_once_with(view)


class TestWorkspaceHierarchy(TestCase):
    def setUp(self):
        from server.models.workspace import WorkspaceModel

        self.root = WorkspaceModel.objects.create(name="R", path="/h/r")
        self.mid = WorkspaceModel.objects.create(name="M", path="/h/r/m")
        self.leaf = WorkspaceModel.objects.create(name="L", path="/h/r/m/l")
        self.lone = WorkspaceModel.objects.create(name="Q", path="/h/q")

    def _detail(self, ws):
        from ui.main.workspace.workspace import Workspace

        main = MagicMock()
        main.selected_tab_view = None
        main.open_tabs = {}
        main.parent = None
        main.subject = MagicMock()
        view = Workspace(subject=ws, parent=main)
        view.update = MagicMock()
        return view, main

    def test_ancestors_root_first(self):
        view, _ = self._detail(self.leaf)
        assert [w.pk for w in view.ancestors] == [self.root.pk, self.mid.pk]

    def test_root_has_no_ancestors(self):
        view, _ = self._detail(self.root)
        assert view.ancestors == []

    def test_children_cards_direct_only(self):
        view, _ = self._detail(self.root)
        assert [c["pk"] for c in view.children_cards] == [self.mid.pk]
        assert view.child_count == 1

    def test_leaf_has_no_children(self):
        view, _ = self._detail(self.leaf)
        assert view.children_cards == [] and view.child_count == 0

    def test_set_view_and_open_child(self):
        from ui.main.workspace.workspace import Workspace

        view, main = self._detail(self.root)
        view.setView("list")
        assert view.view_mode == "list"
        view.openWorkspace(self.mid.pk)
        args, _ = main.create_and_open_tab.call_args
        assert args[0] is Workspace and args[1].pk == self.mid.pk
