"""Tests for the browser daemon transport and path safety.

Covers the two things that must hold without Playwright installed: the local
HTTP API rejects unauthenticated callers, and daemon-side file writes/read are
confined to the workspace root the tool passed in.
"""
import json
import os
import secrets
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from django.test import SimpleTestCase

from runtime.browser import paths
from runtime.browser.config import get_browser_config
from runtime.browser.daemon import BrowserError, Daemon, _Handler
from runtime.browser.policy import check_navigation


class _StubDaemon:
    """Minimal stand-in for the driver-owning Daemon."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.seen = []

    def _submit(self, fn, timeout=None):
        return fn()

    def handle(self, action, scope, params):
        self.seen.append((action, scope, params))
        if self.fail:
            raise BrowserError("boom")
        return {"page_id": "p1", "url": "https://example.com/"}


class _Transport:
    def __init__(self, daemon_obj, token):
        handler = type("BoundHandler", (_Handler,), {"daemon_obj": daemon_obj, "token": token})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _send(self, request):
        try:
            with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - loopback
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def _request(self, path, token=None, data=None, method=None):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method=method or ("POST" if data is not None else "GET"),
        )
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        return self._send(request)

    def get(self, path, token=None):
        return self._request(path, token=token)

    def post(self, path, payload, token=None):
        return self._request(path, token=token, data=json.dumps(payload).encode())

    def raw_post(self, path, body, token=None):
        return self._request(path, token=token, data=body)


class TransportAuthTests(SimpleTestCase):
    def setUp(self):
        self.token = secrets.token_urlsafe(16)
        self.stub = _StubDaemon()
        self.transport = _Transport(self.stub, self.token)
        self.addCleanup(self.transport.stop)

    def test_health_requires_token(self):
        status, body = self.transport.get("/health")
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])

    def test_health_with_wrong_token(self):
        status, _ = self.transport.get("/health", token="nope")
        self.assertEqual(status, 401)

    def test_health_with_token(self):
        status, body = self.transport.get("/health", token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "agentone-browser")

    def test_unknown_path(self):
        status, _ = self.transport.get("/nope", token=self.token)
        self.assertEqual(status, 404)

    def test_action_requires_token(self):
        status, _ = self.transport.post("/action", {"action": "status"})
        self.assertEqual(status, 401)
        self.assertEqual(self.stub.seen, [])

    def test_action_dispatches_scope_and_params(self):
        payload = {"action": "snapshot", "scope": {"profile_key": "s1"}, "params": {"page_id": "p1"}}
        status, body = self.transport.post("/action", payload, token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(self.stub.seen[-1][0], "snapshot")
        self.assertEqual(self.stub.seen[-1][1]["profile_key"], "s1")

    def test_daemon_error_becomes_ok_false(self):
        transport = _Transport(_StubDaemon(fail=True), self.token)
        self.addCleanup(transport.stop)
        status, body = transport.post("/action", {"action": "click"}, token=self.token)
        self.assertEqual(status, 200)
        self.assertFalse(body["ok"])
        self.assertIn("boom", body["error"])

    def test_invalid_json(self):
        status, body = self.transport.raw_post("/action", b"{not json", token=self.token)
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_token_is_not_accepted_as_query_param(self):
        # A query-string token must not authenticate (it would leak into logs).
        status, body = self.transport.get(f"/health?token={self.token}")
        self.assertNotEqual(status, 200)
        self.assertFalse(body.get("ok"))


class DaemonPathSafetyTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get(paths.BROWSER_DIR_ENV)
        os.environ[paths.BROWSER_DIR_ENV] = self._tmp.name
        self.addCleanup(self._restore)
        self.root = os.path.realpath(self._tmp.name)
        self.daemon = Daemon(get_browser_config())

    def _restore(self):
        if self._prev is None:
            os.environ.pop(paths.BROWSER_DIR_ENV, None)
        else:
            os.environ[paths.BROWSER_DIR_ENV] = self._prev
        self._tmp.cleanup()

    def test_relative_path_resolves_under_root(self):
        params = {"path": "shots/a.png", "write_root": self.root}
        resolved = self.daemon._safe_write_path(params)
        self.assertTrue(resolved.startswith(self.root))
        self.assertTrue(resolved.endswith("shots/a.png"))

    def test_parent_traversal_is_blocked(self):
        params = {"path": "../../etc/passwd", "write_root": self.root}
        with self.assertRaises(BrowserError):
            self.daemon._safe_write_path(params)

    def test_absolute_path_outside_root_is_blocked(self):
        params = {"path": "/tmp/evil.png", "write_root": self.root}
        with self.assertRaises(BrowserError):
            self.daemon._safe_write_path(params)

    def test_absolute_path_inside_root_is_allowed(self):
        target = os.path.join(self.root, "inside.png")
        params = {"path": target, "write_root": self.root}
        self.assertEqual(self.daemon._safe_write_path(params), os.path.realpath(target))

    def test_missing_required_path(self):
        with self.assertRaises(BrowserError):
            self.daemon._safe_write_path({}, key="download_path", required=True)
        self.assertIsNone(self.daemon._safe_write_path({}, key="download_path", required=False))

    def test_read_path_must_exist(self):
        with self.assertRaises(BrowserError):
            self.daemon._safe_read_path({"upload_path": "nope.bin", "read_root": self.root})
        present = os.path.join(self.root, "there.bin")
        with open(present, "wb") as handle:
            handle.write(b"x")
        self.assertEqual(
            self.daemon._safe_read_path({"upload_path": "there.bin", "read_root": self.root}),
            os.path.realpath(present),
        )

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(BrowserError):
            self.daemon.handle("launch_missiles", {}, {})


class ActionCatalogueTests(SimpleTestCase):
    def test_read_actions_do_not_need_approval(self):
        from runtime.browser.actions import READ_ONLY_ACTIONS, requires_approval

        for action in READ_ONLY_ACTIONS:
            self.assertFalse(requires_approval(action), action)

    def test_mutating_actions_need_approval(self):
        from runtime.browser.actions import MUTATING_ACTIONS, requires_approval

        for action in MUTATING_ACTIONS:
            self.assertTrue(requires_approval(action), action)

    def test_evaluate_requires_approval(self):
        from runtime.browser.actions import requires_approval

        self.assertTrue(requires_approval("evaluate"))

    def test_every_action_is_categorised_exactly_once(self):
        from runtime.browser.actions import ALL_ACTIONS, MUTATING_ACTIONS, READ_ONLY_ACTIONS

        self.assertFalse(READ_ONLY_ACTIONS & MUTATING_ACTIONS)
        self.assertEqual(ALL_ACTIONS, READ_ONLY_ACTIONS | MUTATING_ACTIONS)


class ConfigTests(SimpleTestCase):
    def setUp(self):
        self._prev = os.environ.get("AGENTONE_CONFIG_FILE")
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AGENTONE_CONFIG_FILE"] = os.path.join(self._tmp.name, "config.yaml")
        self.addCleanup(self._restore)

    def _restore(self):
        if self._prev is None:
            os.environ.pop("AGENTONE_CONFIG_FILE", None)
        else:
            os.environ["AGENTONE_CONFIG_FILE"] = self._prev
        self._tmp.cleanup()

    def _write(self, body: str):
        with open(os.environ["AGENTONE_CONFIG_FILE"], "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_defaults_when_file_missing(self):
        cfg = get_browser_config()
        self.assertEqual(cfg["mode"], "headful")
        self.assertEqual(cfg["max_processes"], 6)

    def test_user_values_merge(self):
        self._write("browser:\n  max_processes: 2\n  mode: headless\n")
        cfg = get_browser_config()
        self.assertEqual(cfg["max_processes"], 2)
        self.assertEqual(cfg["mode"], "headless")
        self.assertEqual(cfg["idle_seconds"], 3600)  # default kept

    def test_invalid_values_fall_back(self):
        self._write("browser:\n  max_processes: 'lots'\n  mode: sideways\n  idle_seconds: -5\n")
        cfg = get_browser_config()
        self.assertEqual(cfg["max_processes"], 6)
        self.assertEqual(cfg["mode"], "headful")
        self.assertEqual(cfg["idle_seconds"], 3600)

    def test_unknown_keys_ignored(self):
        self._write("browser:\n  wat: true\n")
        self.assertNotIn("wat", get_browser_config())

    def test_malformed_yaml_falls_back(self):
        self._write("browser: [oops\n")
        self.assertEqual(get_browser_config()["mode"], "headful")


class ProfileKeyTests(SimpleTestCase):
    def test_traversal_keys_are_rejected(self):
        for bad in ("../escape", "s1/../s2", "named-../../x", "", "s", "named-"):
            with self.assertRaises(ValueError, msg=bad):
                paths.profile_dir(bad)

    def test_valid_keys(self):
        self.assertEqual(paths.profile_dir("s42").name, "s42")
        self.assertEqual(paths.profile_dir("named-github").name, "named-github")
        self.assertEqual(paths.profile_dir("clean-" + "a" * 32).name, "clean-" + "a" * 32)

    def test_token_is_created_once_and_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = os.environ.get(paths.BROWSER_DIR_ENV)
            os.environ[paths.BROWSER_DIR_ENV] = tmp
            try:
                token = paths.read_token()
                self.assertTrue(token)
                self.assertEqual(paths.read_token(), token)
                mode = oct(paths.token_path().stat().st_mode & 0o777)
                self.assertEqual(mode, "0o600")
            finally:
                if prev is None:
                    os.environ.pop(paths.BROWSER_DIR_ENV, None)
                else:
                    os.environ[paths.BROWSER_DIR_ENV] = prev


class ProbeStatusTests(SimpleTestCase):
    """``probe_status`` must never spawn the daemon (``server browser status``)."""

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

    def test_returns_none_when_no_state_file(self):
        from runtime.browser import client  # pylint: disable=import-outside-toplevel
        self.assertIsNone(client.probe_status())
        self.assertFalse(paths.state_path().exists(), "probe must not start a daemon")

    def test_returns_none_when_pid_is_dead(self):
        from runtime.browser import client  # pylint: disable=import-outside-toplevel
        paths.ensure_private_dir(paths.browser_base())
        paths.state_path().write_text(json.dumps({"pid": 2 ** 22, "port": 1}), encoding="utf-8")
        self.assertIsNone(client.probe_status())

    def test_returns_none_when_state_is_corrupt(self):
        from runtime.browser import client  # pylint: disable=import-outside-toplevel
        paths.ensure_private_dir(paths.browser_base())
        paths.state_path().write_text("not json", encoding="utf-8")
        self.assertIsNone(client.probe_status())

    def test_returns_status_from_a_live_daemon(self):
        from runtime.browser import client  # pylint: disable=import-outside-toplevel
        stub = _StubDaemon()
        transport = _Transport(stub, paths.read_token())
        self.addCleanup(transport.stop)
        paths.ensure_private_dir(paths.browser_base())
        paths.state_path().write_text(
            json.dumps({"pid": os.getpid(), "port": transport.port}), encoding="utf-8"
        )
        info = client.probe_status()
        self.assertIsNotNone(info)
        self.assertEqual(stub.seen[-1][0], "status")

class NavigationPolicyTests(SimpleTestCase):
    """Scheme allowlist + domain lists.  ``file:`` must never be navigable."""

    def test_web_schemes_are_allowed(self):
        for url in ("http://example.com/", "https://example.com/a?b=1", "about:blank"):
            ok, reason = check_navigation(url, {})
            self.assertTrue(ok, f"{url}: {reason}")

    def test_file_urls_are_blocked(self):
        # The browser runs as the user: a file: page would render local files
        # and hand them back via snapshot/read, bypassing workspace guardrails.
        for url in (
            "file:///etc/passwd",
            "file:///Users/dirk/.ssh/id_rsa",
            "FILE:///etc/passwd",
        ):
            ok, reason = check_navigation(url, {})
            self.assertFalse(ok, url)
            self.assertIn("scheme", reason)

    def test_data_urls_are_blocked(self):
        ok, reason = check_navigation("data:text/html,<b>hi</b>", {})
        self.assertFalse(ok)
        self.assertIn("scheme", reason)

    def test_javascript_urls_are_blocked(self):
        ok, _ = check_navigation("javascript:alert(1)", {})
        self.assertFalse(ok)

    def test_allow_all_is_the_default(self):
        ok, _ = check_navigation("https://anything.example/", {"allow_domains": []})
        self.assertTrue(ok)

    def test_allow_list_is_enforced(self):
        cfg = {"allow_domains": ["example.com"]}
        self.assertTrue(check_navigation("https://example.com/", cfg)[0])
        self.assertTrue(check_navigation("https://api.example.com/", cfg)[0])
        self.assertFalse(check_navigation("https://evil.test/", cfg)[0])

    def test_deny_list_is_a_floor(self):
        cfg = {"deny_domains": ["blocked.test"]}
        self.assertTrue(check_navigation("https://allowed.test/", cfg)[0])
        self.assertFalse(check_navigation("https://blocked.test/", cfg)[0])
        self.assertFalse(check_navigation("https://sub.blocked.test/", cfg)[0])

    def test_about_blank_bypasses_domain_lists(self):
        cfg = {"allow_domains": ["example.com"]}
        self.assertTrue(check_navigation("about:blank", cfg)[0])
