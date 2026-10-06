"""Tests for browser launch identity selection.

New Camoufox identities must be drawn for the host OS so the claimed platform,
font list, and native font handling stay coherent. Already-persisted launch
options are intentionally left unchanged.
"""
import json
import os
import sys
import tempfile
import types
from unittest import mock

from django.test import SimpleTestCase

from runtime.browser import launcher, paths


class HostOsKeyTests(SimpleTestCase):
    def test_known_platforms(self):
        cases = {
            "Darwin": "macos",
            "Linux": "linux",
            "Windows": "windows",
        }
        for system, expected in cases.items():
            with self.subTest(system=system):
                with mock.patch.object(launcher.platform, "system", return_value=system):
                    self.assertEqual(launcher.host_os_key(), expected)

    def test_unknown_platform_leaves_os_unpinned(self):
        with mock.patch.object(launcher.platform, "system", return_value="Solaris"):
            self.assertIsNone(launcher.host_os_key())


class EnsureLaunchOptionsTests(SimpleTestCase):
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

    def _stub_camoufox(self, seen):
        stub = types.ModuleType("camoufox.utils")

        def fake_launch_options(**kwargs):
            seen.update(kwargs)
            return {
                "executable_path": "/tmp/camoufox-test-browser",
                "env": {},
                "headless": kwargs.get("headless", False),
            }

        stub.launch_options = fake_launch_options
        parent = types.ModuleType("camoufox")
        parent.utils = stub
        return parent, stub

    def _config(self):
        return {
            "mode": "headful",
            "humanize": 1.5,
            "enable_cache": True,
            "block_images": False,
        }

    def test_new_identity_uses_host_os(self):
        seen = {}
        parent, stub = self._stub_camoufox(seen)
        with mock.patch.dict(sys.modules, {"camoufox": parent, "camoufox.utils": stub}):
            with mock.patch.object(launcher.platform, "system", return_value="Darwin"):
                options = launcher.ensure_launch_options("s123", self._config())

        self.assertEqual(seen.get("os"), "macos")
        self.assertEqual(options["user_data_dir"], str(paths.user_data_dir("s123")))
        saved = json.loads(paths.launch_options_path("s123").read_text(encoding="utf-8"))
        self.assertEqual(saved["user_data_dir"], str(paths.user_data_dir("s123")))

    def test_unknown_host_does_not_pin_os(self):
        seen = {}
        parent, stub = self._stub_camoufox(seen)
        with mock.patch.dict(sys.modules, {"camoufox": parent, "camoufox.utils": stub}):
            with mock.patch.object(launcher.platform, "system", return_value="Solaris"):
                launcher.ensure_launch_options("s124", self._config())

        self.assertIn("os", seen)
        self.assertIsNone(seen.get("os"))

    def test_existing_identity_is_not_redrawn(self):
        seen = {}
        parent, stub = self._stub_camoufox(seen)
        options_path = paths.launch_options_path("s125")
        paths.ensure_private_dir(options_path.parent)
        options_path.write_text(
            json.dumps({"executable_path": "/tmp/old-browser"}),
            encoding="utf-8",
        )
        with mock.patch.dict(sys.modules, {"camoufox": parent, "camoufox.utils": stub}):
            with mock.patch.object(launcher.platform, "system", return_value="Darwin"):
                options = launcher.ensure_launch_options("s125", self._config())

        self.assertEqual(options["executable_path"], "/tmp/old-browser")
        self.assertEqual(seen, {})
