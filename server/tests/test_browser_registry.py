"""Tests for the browser binding registry (runtime/browser/registry.py).

Fake contexts stand in for Playwright: the registry only needs ``new_page()``,
``pages``, ``close()``, and a ``url`` attribute.
"""
import os
import tempfile
import time
from unittest import mock

from django.test import SimpleTestCase

from runtime.browser import paths
from runtime.browser.registry import OwnershipError, Registry


class _FakePage:
    def __init__(self, url="about:blank"):
        self.url = url
        self.closed = False

    def close(self):
        self.closed = True


class _FakeContext:
    def __init__(self):
        self.pages = []
        self.closed = False

    def new_page(self):
        page = _FakePage()
        self.pages.append(page)
        return page

    def close(self):
        self.closed = True


class RegistryTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get(paths.BROWSER_DIR_ENV)
        os.environ[paths.BROWSER_DIR_ENV] = self._tmp.name
        self.addCleanup(self._restore)
        self.launched: list[str] = []
        self.cfg = {"max_processes": 3, "idle_seconds": 900}

    def _restore(self):
        if self._prev is None:
            os.environ.pop(paths.BROWSER_DIR_ENV, None)
        else:
            os.environ[paths.BROWSER_DIR_ENV] = self._prev
        self._tmp.cleanup()

    def _registry(self):
        def launch(profile_key):
            self.launched.append(profile_key)
            return _FakeContext()
        return Registry(lambda: self.cfg, launch)

    def test_same_profile_reuses_one_process(self):
        reg = self._registry()
        a = reg.get_or_launch("s1", 1)
        b = reg.get_or_launch("s1", 1)
        self.assertIs(a, b)
        self.assertEqual(self.launched, ["s1"])

    def test_named_profile_shared_by_two_roots(self):
        reg = self._registry()
        a = reg.get_or_launch("named-github", 1)
        b = reg.get_or_launch("named-github", 2)
        self.assertIs(a, b)
        self.assertEqual(len(self.launched), 1)

    def test_child_inherits_parent_binding(self):
        reg = self._registry()
        parent = reg.get_or_launch("s7", 7)
        child = reg.get_or_launch("s7", 7)
        self.assertIs(parent, child)

    def test_root_may_resolve_any_page_in_binding(self):
        reg = self._registry()
        binding = reg.get_or_launch("s7", 7)
        page = binding.context.new_page()
        child_rec = reg.add_page(binding, owner_pk=9)
        # Root (session 7, is_root=True) sees the child's tab.
        self.assertEqual(reg.resolve(binding, child_rec.page_id, 7, True), child_rec)

    def test_child_cannot_touch_sibling_or_parent_page(self):
        reg = self._registry()
        binding = reg.get_or_launch("s7", 7)
        parent_page = binding.context.new_page()
        parent_rec = reg.add_page(binding, owner_pk=7)
        with self.assertRaises(OwnershipError):
            reg.resolve(binding, parent_rec.page_id, 9, False)

    def test_child_default_tab_is_its_own(self):
        reg = self._registry()
        binding = reg.get_or_launch("s7", 7)
        binding.context.new_page()
        parent_rec = reg.add_page(binding, owner_pk=7)
        child_page = binding.context.new_page()
        child_rec = reg.add_page(binding, owner_pk=9)
        # Newest owned page wins for the child.
        self.assertEqual(reg.resolve(binding, None, 9, False), child_rec)
        self.assertEqual(reg.resolve(binding, None, 7, True), child_rec)

    def test_child_with_no_owned_pages_is_refused(self):
        reg = self._registry()
        binding = reg.get_or_launch("s7", 7)
        binding.context.new_page()
        reg.add_page(binding, owner_pk=7)
        with self.assertRaises(OwnershipError):
            reg.resolve(binding, None, 9, False)

    def test_unknown_page_id_is_refused(self):
        reg = self._registry()
        binding = reg.get_or_launch("s1", 1)
        reg.add_page(binding, owner_pk=1)
        with self.assertRaises(OwnershipError):
            reg.resolve(binding, "pdeadbeef", 1, True)

    def test_empty_binding_is_refused(self):
        reg = self._registry()
        binding = reg.get_or_launch("s1", 1)
        with self.assertRaises(OwnershipError):
            reg.resolve(binding, None, 1, True)

    def test_max_processes_evicts_lru(self):
        self.cfg["max_processes"] = 2
        reg = self._registry()
        first = reg.get_or_launch("s1", 1)
        reg.get_or_launch("s2", 2)
        first.last_used = time.monotonic() - 100
        reg.get_or_launch("s3", 3)
        self.assertTrue(first.context.closed)
        self.assertIsNone(reg.get("s1"))

    def test_reap_idle_closes_stale_bindings(self):
        reg = self._registry()
        stale = reg.get_or_launch("s1", 1)
        reg.get_or_launch("s2", 2)
        stale.last_used = time.monotonic() - 10_000
        self.assertEqual(reg.reap_idle(), 1)
        self.assertIsNone(reg.get("s1"))

    def test_idle_accounting_survives_wall_clock_jump(self):
        """System sleep / NTP steps jump wall-clock time forward.

        Idle accounting must use the monotonic clock, so such a jump is not
        mistaken for user idleness and a just-used browser is not reaped.
        """
        self.cfg["idle_seconds"] = 3600
        reg = self._registry()
        with mock.patch("time.monotonic", return_value=1_000.0):
            reg.get_or_launch("s1", 1)
        # Ten seconds of monotonic time pass, but the wall clock jumps an hour
        # (sleep + wake). Reaping consults only the monotonic clock.
        with mock.patch("time.monotonic", return_value=1_010.0):
            with mock.patch("time.time", return_value=1_000.0 + 3_600 + 60):
                self.assertEqual(reg.reap_idle(), 0)
                self.assertIsNotNone(reg.get("s1"))

    def test_ephemeral_profile_is_deleted_on_close(self):
        reg = self._registry()
        binding = reg.get_or_launch("s1", 1, ephemeral=True)
        paths.ensure_private_dir(paths.profile_dir("s1"))
        reg._close_binding(binding)  # pylint: disable=protected-access
        self.assertFalse(paths.profile_dir("s1").exists())

    def test_named_profile_survives_close(self):
        reg = self._registry()
        binding = reg.get_or_launch("named-github", 1)
        paths.ensure_private_dir(paths.profile_dir("named-github"))
        reg._close_binding(binding)  # pylint: disable=protected-access
        self.assertTrue(paths.profile_dir("named-github").exists())

    def test_close_all(self):
        reg = self._registry()
        reg.get_or_launch("s1", 1)
        reg.get_or_launch("s2", 2)
        reg.close_all()
        self.assertEqual(reg.status()["bindings"], [])

    def test_page_ids_are_unique(self):
        reg = self._registry()
        ids = {reg.new_page_id() for _ in range(200)}
        self.assertEqual(len(ids), 200)