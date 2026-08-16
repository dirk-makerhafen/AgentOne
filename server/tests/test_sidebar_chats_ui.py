from __future__ import annotations
import re
from unittest.mock import MagicMock

import jinja2
from django.test import TestCase

from server.models import (
    AgentModel,
    AgentVersionModel,
    SessionModel,
    SessionVersionModel,
)
from ui.app import UiApp
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.sidebar.panels.chats import SidebarPanelChat, SidebarPanelChats


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


class FakeRootView:
    def __init__(self, instance: FakeInstance):
        self._instance = instance
        self.main_panel = MagicMock()
        self.main_panel.selected_tab_view = None


class FakeSidebar:
    def __init__(self, instance: FakeInstance, root_view: FakeRootView):
        self._instance = instance
        self.root_view = root_view

    def _add_child(self, child):
        pass


class SidebarChatsTreeTest(TestCase):
    def setUp(self):
        self.agent = AgentModel.objects.create(name="test_agent")
        self.agent_version = AgentVersionModel.objects.create(
            agent=self.agent, version_number=1,
        )
        self.ui_app = UiApp()

    def tearDown(self):
        UiApp._instance = None

    def _session(self, name, parent=None, is_active=True) -> SessionModel:
        sm = SessionModel.objects.create(
            name=name, parent_session=parent, is_active=is_active,
        )
        sv = SessionVersionModel.objects.create(
            session=sm,
            agent=self.agent,
            pinned_agent_version=self.agent_version,
            version_number=1,
        )
        SessionModel.objects.filter(pk=sm.pk).update(latest_session_version=sv)
        sm.latest_session_version = sv
        return sm

    def _root_panel(self) -> SidebarPanelChat:
        instance = FakeInstance()
        root_view = FakeRootView(instance)
        panel = SidebarPanelChats(
            subject=self.ui_app, parent=FakeSidebar(instance, root_view),
        )
        panel.agent_list.set_visible(True)
        root_panel = panel.agent_list._wrapped_data[0]
        self.assertIsInstance(root_panel, SidebarPanelChat)
        return root_panel

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_children_render_as_own_panels_with_menu(self):
        """Sub-sessions are rendered as their own SidebarPanelChat rows that
        carry the full action menu (pin / move / archive / delete)."""
        root = self._session("root")
        child = self._session("child", parent=root)
        grand = self._session("grandchild", parent=child)

        root_panel = self._root_panel()
        html = root_panel.render()

        # Root + child + grandchild all render as full session rows.
        for name in ("root", "child", "grandchild"):
            self.assertIn(name + "\n", html)

        # Every panel now has its own action menu trigger (previously the
        # inline tree rows had none).
        self.assertEqual(len(html.split("session-actions-trigger")) - 1, 3)

        # Nested panels are marked as tree children with the indented container.
        self.assertEqual(
            len(re.findall(r'class="session-item session-tree-child', html)), 2,
        )
        self.assertEqual(
            len(re.findall(r'class="session-tree-children"', html)), 2,
        )

        # The view tree mirrors the data tree: each child is its own panel.
        child_panel = root_panel.child_list._wrapped_data[0]
        self.assertEqual(child_panel.subject.pk, child.pk)
        self.assertEqual(child_panel.depth, 1)
        grand_panel = child_panel.child_list._wrapped_data[0]
        self.assertEqual(grand_panel.subject.pk, grand.pk)
        self.assertEqual(grand_panel.depth, 2)
        self.assertIn("session-tree-child", grand_panel.DOM_ELEMENT_CLASS)
        # Leaf: child_list exists but wraps nothing.
        self.assertEqual(len(grand_panel.child_list._wrapped_data), 0)

    def test_collapse_hides_children(self):
        """toggle_children collapses the tree without breaking rendering."""
        root = self._session("root")
        self._session("child", parent=root)

        root_panel = self._root_panel()
        root_panel._show_children = False
        html = root_panel.render()

        self.assertIn("▸", html)  # caret points at the collapsed state
        self.assertNotIn('class="session-item session-tree-child', html)
        self.assertNotIn('class="session-tree-children"', html)

    def test_depth_cap_stops_recursion(self):
        """The tree recursion stops at MAX_TREE_DEPTH (no infinite loop)."""
        parent = None
        for level in range(15):
            parent = self._session(f"L{level}", parent=parent)

        root_panel = self._root_panel()
        html = root_panel.render()

        # Rendering terminates; rows down to depth MAX_TREE_DEPTH are shown,
        # deeper ones are cut off — matching the old inline-tree cap.
        self.assertIn("L10", html)
        self.assertNotIn("L11", html)