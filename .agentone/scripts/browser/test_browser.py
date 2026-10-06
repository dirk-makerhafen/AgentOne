import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from browser import browser, _normalize_url  # noqa: E402

from runtime.browser import paths  # noqa: E402


class _Model:
    def __init__(self, pk, name="root", parent=None):
        self.pk = pk
        self.name = name
        self.parent_session = parent


class _Session:
    def __init__(self, pk=7, name="root", parent=None):
        self.model = _Model(pk, name, parent)


class BrowserToolTests(unittest.TestCase):
    """Tests for the multiplexed browser tool (client is stubbed)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get(paths.BROWSER_DIR_ENV)
        os.environ[paths.BROWSER_DIR_ENV] = self._tmp.name
        self.addCleanup(self._restore)
        self.calls = []

    def _restore(self):
        if self._prev is None:
            os.environ.pop(paths.BROWSER_DIR_ENV, None)
        else:
            os.environ[paths.BROWSER_DIR_ENV] = self._prev
        self._tmp.cleanup()

    def _fake_call(self, result=None, exc=None):
        def call(action, scope, params=None, timeout=None):
            self.calls.append((action, scope, params))
            if exc is not None:
                raise exc
            return dict(result or {})

        return mock.patch("runtime.browser.client.call", side_effect=call)

    def test_missing_action(self):
        success, result = browser(_Session(), action="")
        self.assertFalse(success)
        self.assertIn("action is required", result["message"])
        self.assertIn("snapshot", result["available_actions"])

    def test_unknown_action(self):
        success, result = browser(_Session(), action="teleport")
        self.assertFalse(success)
        self.assertIn("unknown action", result["message"])

    def test_scope_is_server_derived(self):
        """The tool sends its own session scope, never an LLM-supplied one."""
        child = _Session(pk=9, parent=_Model(7))
        with self._fake_call({"page_id": "p1"}):
            browser(child, action="snapshot")
        _, scope, _ = self.calls[-1]
        self.assertEqual(scope["root_pk"], 7)
        self.assertEqual(scope["session_pk"], 9)
        self.assertFalse(scope["is_root"])

    def test_named_profile_argument(self):
        with self._fake_call({}):
            browser(_Session(), action="open", url="example.com", profile="github")
        _, scope, _ = self.calls[-1]
        self.assertEqual(scope["profile_key"], "named-github")

    def test_url_is_upgraded_to_https(self):
        with self._fake_call({}):
            browser(_Session(), action="navigate", url="example.com/x")
        _, _, params = self.calls[-1]
        self.assertEqual(params["url"], "https://example.com/x")

    def test_workspace_root_is_always_sent(self):
        with self._fake_call({}):
            browser(_Session(), action="snapshot")
        _, _, params = self.calls[-1]
        self.assertEqual(params["write_root"], os.getcwd())
        self.assertEqual(params["read_root"], os.getcwd())

    def test_empty_params_are_dropped(self):
        with self._fake_call({}):
            browser(_Session(), action="snapshot")
        _, _, params = self.calls[-1]
        self.assertNotIn("url", params)
        self.assertNotIn("ref", params)
        self.assertNotIn("ms", params)

    def test_snapshot_marks_page_content_untrusted(self):
        with self._fake_call({"snapshot": "Page: x", "refs": 3}):
            success, result = browser(_Session(), action="snapshot")
        self.assertTrue(success)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["refs"], 3)
        self.assertIn("untrusted", result["notice"])

    def test_read_marks_page_content_untrusted(self):
        with self._fake_call({"text": "hello"}):
            _, result = browser(_Session(), action="read")
        self.assertIn("untrusted", result["notice"])

    def test_read_only_action_has_no_notice(self):
        with self._fake_call({"tabs": []}):
            _, result = browser(_Session(), action="tabs")
        self.assertNotIn("notice", result)

    def test_client_error_is_reported_not_raised(self):
        with self._fake_call(exc=RuntimeError("daemon down")):
            success, result = browser(_Session(), action="open", url="x.test")
        self.assertFalse(success)
        self.assertIn("daemon down", result["message"])
        self.assertEqual(result["action"], "open")

    def test_ok_flag_is_stripped_from_payload(self):
        with self._fake_call({"ok": True, "page_id": "p9"}):
            _, result = browser(_Session(), action="open", url="x.test")
        self.assertNotIn("ok", result)
        self.assertEqual(result["page_id"], "p9")

    def test_type_forwards_text_and_submit(self):
        with self._fake_call({"typed": 5}):
            browser(_Session(), action="type", ref="e3", text="hello", submit=True)
        _, _, params = self.calls[-1]
        self.assertEqual(params["text"], "hello")
        self.assertEqual(params["ref"], "e3")
        self.assertTrue(params["submit"])

    def test_upload_forwards_both_paths(self):
        with self._fake_call({"uploaded": "a.bin"}):
            browser(_Session(), action="upload", ref="e1", upload_path="docs/a.bin")
        _, _, params = self.calls[-1]
        self.assertEqual(params["upload_path"], "docs/a.bin")

    def test_scope_failure_is_reported(self):
        success, result = browser(_Session(pk="bad"), action="snapshot")
        self.assertFalse(success)
        self.assertIn("could not resolve browser scope", result["message"])


class UrlNormalizationTests(unittest.TestCase):
    def test_scheme_upgrade(self):
        self.assertEqual(_normalize_url("example.com"), "https://example.com")
        self.assertEqual(_normalize_url("http://x.test"), "http://x.test")

    def test_special_schemes_preserved(self):
        self.assertEqual(_normalize_url("about:blank"), "about:blank")
        self.assertEqual(_normalize_url("file:///tmp/x.html"), "file:///tmp/x.html")


if __name__ == '__main__':
    unittest.main()