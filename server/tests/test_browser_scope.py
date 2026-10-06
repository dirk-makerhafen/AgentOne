"""Tests for the browser scope resolution (runtime/browser/scope.py).

Uses SimpleTestCase (no DB) — resolution walks plain attributes on the
session model, so lightweight stand-ins are enough.
"""
import os
import tempfile

from django.test import SimpleTestCase

from runtime.browser import paths
from runtime.browser.scope import resolve_scope


class _Parent:
    def __init__(self, pk, name="p", parent=None):
        self.pk = pk
        self.name = name
        self.parent_session = parent


class _Model:
    def __init__(self, pk, name="root", parent=None):
        self.pk = pk
        self.name = name
        self.parent_session = parent


class _Session:
    def __init__(self, model):
        self.model = model


class BrowserScopeTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get(paths.BROWSER_DIR_ENV)
        os.environ[paths.BROWSER_DIR_ENV] = self._tmp.name
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev is None:
            os.environ.pop(paths.BROWSER_DIR_ENV, None)
        else:
            os.environ[paths.BROWSER_DIR_ENV] = self._prev
        self._tmp.cleanup()

    def test_root_session_scopes_to_its_own_pk(self):
        scope = resolve_scope(_Session(_Model(7)))
        self.assertEqual(scope.root_pk, 7)
        self.assertEqual(scope.session_pk, 7)
        self.assertTrue(scope.is_root)
        self.assertEqual(scope.profile_key, "s7")
        self.assertFalse(scope.ephemeral)

    def test_child_inherits_root_scope_but_is_not_root(self):
        root = _Model(7, name="chat")
        child = _Session(_Model(9, name="worker", parent=root))
        scope = resolve_scope(child)
        self.assertEqual(scope.root_pk, 7)
        self.assertEqual(scope.session_pk, 9)
        self.assertFalse(scope.is_root)
        # Same browser as the root, so logins carry over.
        self.assertEqual(scope.profile_key, "s7")

    def test_grandchild_lineage(self):
        root = _Model(1)
        mid = _Model(2, parent=root)
        leaf = _Session(_Model(3, parent=mid))
        self.assertEqual(resolve_scope(leaf).root_pk, 1)

    def test_parent_cycle_does_not_hang(self):
        a = _Parent(1)
        b = _Parent(2, parent=a)
        a.parent_session = b
        scope = resolve_scope(_Session(_Model(2, parent=b)))
        self.assertIn(scope.root_pk, (1, 2))

    def test_named_profile_is_shared_across_sessions(self):
        a = resolve_scope(_Session(_Model(1)), profile="github")
        b = resolve_scope(_Session(_Model(2)), profile="GitHub!")
        self.assertEqual(a.profile_key, b.profile_key)
        self.assertEqual(a.profile_key, "named-github")

    def test_clean_profile_is_ephemeral_and_unique(self):
        one = resolve_scope(_Session(_Model(1)), clean=True)
        two = resolve_scope(_Session(_Model(1)), clean=True)
        self.assertTrue(one.ephemeral)
        self.assertNotEqual(one.profile_key, two.profile_key)
        self.assertTrue(one.profile_key.startswith("clean-"))

    def test_scope_named_config_uses_session_name(self):
        cfg = {"scope": "named", "ephemeral_by_default": False}
        scope = resolve_scope(_Session(_Model(4, name="Research Chat")), browser_config=cfg)
        self.assertEqual(scope.profile_key, "named-research-chat")

    def test_scope_named_config_uses_root_name_not_child_name(self):
        """A child subagent must share the root chat's durable login profile."""
        cfg = {"scope": "named", "ephemeral_by_default": False}
        root = _Model(4, name="Research Chat")
        child = _Session(_Model(9, name="worker subagent", parent=root))
        scope = resolve_scope(child, browser_config=cfg)
        self.assertEqual(scope.profile_key, "named-research-chat")
        self.assertEqual(scope.root_pk, 4)

    def test_scope_named_config_uses_root_name_for_grandchild(self):
        cfg = {"scope": "named", "ephemeral_by_default": False}
        root = _Model(4, name="Research Chat")
        mid = _Model(9, name="mid", parent=root)
        grandchild = _Session(_Model(11, name="deep", parent=mid))
        self.assertEqual(
            resolve_scope(grandchild, browser_config=cfg).profile_key,
            "named-research-chat",
        )

    def test_scope_named_falls_back_to_root_pk_when_root_unnamed(self):
        cfg = {"scope": "named", "ephemeral_by_default": False}
        root = _Model(4, name="")
        child = _Session(_Model(9, name="worker", parent=root))
        self.assertEqual(resolve_scope(child, browser_config=cfg).profile_key, "named-s4")

    def test_scope_named_parent_cycle_does_not_hang(self):
        """A parent_session cycle must terminate, not spin forever."""
        cfg = {"scope": "named", "ephemeral_by_default": False}
        root = _Model(4, name="root")
        child = _Model(9, name="child", parent=root)
        root.parent_session = child  # cycle
        key = resolve_scope(_Session(child), browser_config=cfg).profile_key
        self.assertIn(key, ("named-root", "named-child"))

    def test_ephemeral_by_default(self):
        cfg = {"scope": "session", "ephemeral_by_default": True}
        scope = resolve_scope(_Session(_Model(4)), browser_config=cfg)
        self.assertTrue(scope.ephemeral)

    def test_missing_pk_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_scope(_Session(_Model(pk="seven")))