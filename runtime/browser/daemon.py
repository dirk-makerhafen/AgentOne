"""Long-lived browser daemon.

Threading model
---------------
* **driver thread** — owns ``sync_playwright()`` and every Playwright object.
  Playwright's sync API is thread-bound, so all browser work is submitted here
  through a queue and executed serially.
* **HTTP threads** — a stdlib ``ThreadingHTTPServer`` bound to ``127.0.0.1``
  that authenticates a per-user bearer token and forwards each request to the
  driver thread.
* **reaper thread** — closes idle bindings on the driver thread.

Run standalone via ``python3 -m runtime.browser.daemon`` or
``manage.py server browser start``; ``manage.py server run`` supervises it.
"""

from __future__ import annotations

import json
import os
import queue
import secrets
import signal
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from runtime.browser import launcher, paths, policy, registry as registry_mod
from runtime.browser.snapshot import clear_refs, read_text, resolve_ref, snapshot as build_snapshot
from runtime.browser.config import get_browser_config

#: Per-request ceiling. Playwright op timeouts should fire first; this is the
#: backstop so a wedged driver cannot hold an HTTP worker forever.
REQUEST_TIMEOUT = 180.0
#: How long a parsed config.yaml is reused before re-reading. Small enough
#: that editing the file takes effect almost immediately, large enough that a
#: chatty agent does not re-parse YAML on every action.
CONFIG_TTL = 2.0


class BrowserError(RuntimeError):
    """Any browser failure surfaced to the tool as a message."""


class _Job:  # pylint: disable=too-few-public-methods
    """One unit of work handed to the driver thread."""

    __slots__ = ("fn", "event", "result", "error")

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.fn = fn
        self.event = threading.Event()
        self.result: Any = None
        self.error: BaseException | None = None


class Daemon:  # pylint: disable=too-many-instance-attributes
    """Owns the Playwright driver thread and the binding registry."""

    def __init__(self, cfg: dict | None = None, httpd: Any = None) -> None:
        self._cfg_snapshot = cfg
        self._cfg_at = 0.0
        self._httpd = httpd
        self._queue: "queue.Queue[_Job | None]" = queue.Queue()
        self._playwright: Any = None
        self._driver_ready = threading.Event()
        self._driver_error: BaseException | None = None
        self._driver_alive = False
        self._driver_thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self.registry = registry_mod.Registry(lambda: self.cfg, self._launch)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @property
    def cfg(self) -> dict:
        """Current config, re-read at most every :data:`CONFIG_TTL` seconds.

        Operators tune ``~/.agentone/config.yaml`` while the server runs, so
        the daemon must not freeze a snapshot at startup.
        """
        now = time.time()
        if self._cfg_snapshot is None or (now - self._cfg_at) >= CONFIG_TTL:
            self._cfg_snapshot = get_browser_config()
            self._cfg_at = now
        return self._cfg_snapshot

    # ------------------------------------------------------------------
    # Driver thread
    # ------------------------------------------------------------------

    def _launch(self, profile_key: str) -> Any:
        """Launch a persistent Camoufox context on the driver thread."""
        return launcher.launch(self._playwright, profile_key, self.cfg)

    def _driver_loop(self) -> None:
        # Imported here so the module loads (and the health endpoint answers)
        # even when Playwright is not installed.
        # pylint: disable=import-outside-toplevel
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on install
            self._driver_error = exc
            self._driver_ready.set()
            return
        try:
            self._playwright = sync_playwright().start()
        except BaseException as exc:  # pylint: disable=broad-exception-caught
            self._driver_error = exc
            self._driver_ready.set()
            return
        self._driver_ready.set()
        self._driver_alive = True
        while not self._stopping.is_set():
            job = self._queue.get()
            if job is None:
                break
            try:
                job.result = job.fn()
            except BaseException as exc:  # pylint: disable=broad-exception-caught
                job.error = exc
            finally:
                job.event.set()
        self._driver_alive = False

    def start_driver(self) -> None:
        self._driver_thread = threading.Thread(target=self._driver_loop, name="browser-driver", daemon=True)
        self._driver_thread.start()
        if not self._driver_ready.wait(30):
            raise BrowserError("browser driver thread failed to start")
        if self._driver_error is not None:
            raise BrowserError(
                f"Playwright/Camoufox unavailable: {self._driver_error}. "
                "Install with 'pip install camoufox'."
            ) from self._driver_error

    def _submit(self, fn: Callable[[], Any], timeout: float = REQUEST_TIMEOUT) -> Any:
        """Run *fn* on the driver thread and return its result."""
        if self._driver_error is not None:
            raise BrowserError(f"browser driver unavailable: {self._driver_error}")
        job = _Job(fn)
        self._queue.put(job)
        if not job.event.wait(timeout):
            raise BrowserError(f"browser action timed out after {int(timeout)}s")
        if job.error is not None:
            raise BrowserError(str(job.error)) from job.error
        return job.result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def nav_timeout(self) -> int:
        return int(self.cfg.get("nav_timeout") or 45) * 1000

    @property
    def action_timeout(self) -> int:
        return int(self.cfg.get("action_timeout") or 15) * 1000

    def _binding_for(self, scope: dict) -> "registry_mod.Binding":
        key = scope["profile_key"]
        binding = self.registry.get_or_launch(
            key, int(scope.get("root_pk") or 0), ephemeral=bool(scope.get("ephemeral"))
        )
        return binding

    def _page_for(self, scope: dict, params: dict, *, create: bool = False) -> tuple["registry_mod.Binding", Any, "registry_mod.PageRecord"]:
        """Resolve the target page, optionally creating one."""
        binding = self._binding_for(scope)
        session_pk = int(scope.get("session_pk") or 0)
        is_root = bool(scope.get("is_root"))
        page_id = params.get("page_id")
        if page_id:
            rec = self.registry.resolve(binding, str(page_id), session_pk, is_root)
            return binding, self._context_page(binding, rec), rec
        if not binding.pages and create:
            return self._open_page(binding, scope, session_pk)
        rec = self.registry.resolve(binding, None, session_pk, is_root)
        return binding, self._context_page(binding, rec), rec

    @staticmethod
    def _context_page(binding: "registry_mod.Binding", rec: "registry_mod.PageRecord") -> Any:
        for candidate in binding.context.pages:
            try:
                if getattr(candidate, "_agentone_page_id", None) == rec.page_id:
                    return candidate
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        # Fallback: the registry is the source of truth, so trust the last page.
        return binding.context.pages[-1]

    def _open_page(self, binding: "registry_mod.Binding", scope: dict, owner_pk: int, url: str | None = None) -> tuple["registry_mod.Binding", Any, "registry_mod.PageRecord"]:
        page = binding.context.new_page()
        rec = self.registry.add_page(binding, owner_pk)
        try:
            page._agentone_page_id = rec.page_id  # pylint: disable=protected-access
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        page.set_default_timeout(self.action_timeout)
        if url:
            self._navigate(page, url, scope, rec, binding)
        return binding, page, rec

    def _navigate(self, page: Any, url: str, scope: dict, rec: "registry_mod.PageRecord", binding: "registry_mod.Binding") -> None:
        allowed, reason = policy.check_navigation(url, self.cfg)
        policy.audit_navigation(
            url,
            {**scope, "profile_key": binding.profile_key},
            page_id=rec.page_id,
            cfg=self.cfg,
        )
        if not allowed:
            raise BrowserError(reason)
        page.goto(url, timeout=self.nav_timeout, wait_until="domcontentloaded")
        rec.url = page.url
        clear_refs(page)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def handle(self, action: str, scope: dict, params: dict) -> dict:
        """Dispatch one action on the driver thread."""
        fn = getattr(self, f"_action_{action}", None)
        if fn is None:
            raise BrowserError(f"unknown browser action: {action!r}")
        return fn(scope, params or {})

    # Every action takes the same (scope, params) pair so dispatch can be a
    # single getattr; a given action may ignore either one.
    # pylint: disable=unused-argument

    def _action_status(self, scope: dict, params: dict) -> dict:
        info = self.registry.status()
        info["max_processes"] = self.cfg.get("max_processes")
        info["idle_seconds"] = self.cfg.get("idle_seconds")
        info["browser_installed"] = launcher.browser_installed()
        return info

    def _action_open(self, scope: dict, params: dict) -> dict:
        url = str(params.get("url") or "about:blank")
        binding = self._binding_for(scope)
        session_pk = int(scope.get("session_pk") or 0)
        _, page, rec = self._open_page(binding, scope, session_pk, url)
        return {"page_id": rec.page_id, "url": page.url, "tabs": len(binding.pages)}

    def _action_navigate(self, scope: dict, params: dict) -> dict:
        url = str(params.get("url") or "")
        if not url:
            raise BrowserError("navigate requires a url")
        binding, page, rec = self._page_for(scope, params)
        self._navigate(page, url, scope, rec, binding)
        return {"page_id": rec.page_id, "url": page.url}

    def _action_tabs(self, scope: dict, params: dict) -> dict:
        binding = self._binding_for(scope)
        session_pk = int(scope.get("session_pk") or 0)
        is_root = bool(scope.get("is_root"))
        visible = [r.to_dict() for r in binding.pages.values() if is_root or r.owner_pk == session_pk]
        return {"page_id": None, "tabs": visible}

    def _action_close_tab(self, scope: dict, params: dict) -> dict:
        binding, page, rec = self._page_for(scope, params)
        try:
            page.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self.registry.close_page(binding, rec)
        return {"closed": rec.page_id, "tabs": len(binding.pages)}

    def _action_snapshot(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        data = build_snapshot(page)
        rec.url = page.url
        return {"page_id": rec.page_id, **data}

    def _action_read(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        text = read_text(page, max_chars=int(params.get("max_chars") or 20000), selector=params.get("selector"))
        return {"page_id": rec.page_id, "url": page.url, "text": text}

    def _action_click(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        ref = params.get("ref")
        if ref:
            selector = resolve_ref(ref)
            page.click(selector, timeout=self.action_timeout)
        elif params.get("selector"):
            page.click(str(params["selector"]), timeout=self.action_timeout)
        else:
            raise BrowserError("click requires a ref or selector")
        page.wait_for_load_state("domcontentloaded", timeout=self.action_timeout)
        return {"page_id": rec.page_id, "url": page.url}

    def _action_type(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        text = str(params.get("text") or "")
        target = params.get("ref") or params.get("selector")
        if not target:
            raise BrowserError("type requires a ref or selector")
        selector = resolve_ref(target) if params.get("ref") else str(target)
        page.fill(selector, text, timeout=self.action_timeout)
        if params.get("submit"):
            page.press(selector, "Enter", timeout=self.action_timeout)
            page.wait_for_load_state("domcontentloaded", timeout=self.action_timeout)
        return {"page_id": rec.page_id, "url": page.url, "typed": len(text)}

    def _action_wait(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        if params.get("ms"):
            page.wait_for_timeout(int(params["ms"]))
        elif params.get("ref"):
            page.wait_for_selector(resolve_ref(params["ref"]), timeout=self.nav_timeout)
        elif params.get("selector"):
            page.wait_for_selector(str(params["selector"]), timeout=self.nav_timeout)
        else:
            page.wait_for_load_state("load", timeout=self.nav_timeout)
        return {"page_id": rec.page_id, "url": page.url}

    def _action_back(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        page.go_back(timeout=self.nav_timeout)
        clear_refs(page)
        return {"page_id": rec.page_id, "url": page.url}

    def _action_screenshot(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        path = self._safe_write_path(params)
        page.screenshot(path=path, full_page=bool(params.get("full_page")), timeout=self.nav_timeout)
        return {"page_id": rec.page_id, "path": path}

    def _action_upload(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        target = params.get("ref") or params.get("selector")
        if not target:
            raise BrowserError("upload requires a ref or selector")
        upload_path = self._safe_read_path(params, key="upload_path")
        selector = resolve_ref(target) if params.get("ref") else str(target)
        page.set_input_files(selector, upload_path, timeout=self.action_timeout)
        return {"page_id": rec.page_id, "uploaded": upload_path}

    def _action_download(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        dest = self._safe_write_path(params, key="download_path", required=False)
        with page.expect_download(timeout=self.nav_timeout) as dl_info:
            if params.get("url"):
                allowed, reason = policy.check_navigation(str(params["url"]), self.cfg)
                policy.audit_navigation(
                    str(params["url"]), scope, page_id=rec.page_id, kind="download", cfg=self.cfg
                )
                if not allowed:
                    raise BrowserError(reason)
                page.goto(str(params["url"]), timeout=self.nav_timeout)
            elif params.get("ref"):
                page.click(resolve_ref(params["ref"]), timeout=self.action_timeout)
            else:
                raise BrowserError("download requires a url or a ref")
        download = dl_info.value
        target = dest or str(Path(download.suggested_filename))
        if dest:
            download.save_as(dest)
        return {"page_id": rec.page_id, "suggested_filename": download.suggested_filename, "path": dest, "note": None if dest else f"suggested filename: {target}"}

    def _action_evaluate(self, scope: dict, params: dict) -> dict:
        _, page, rec = self._page_for(scope, params)
        script = str(params.get("script") or "")
        if not script.strip():
            raise BrowserError("evaluate requires a script")
        result = page.evaluate(script)
        return {"page_id": rec.page_id, "result": result}

    def _action_cookies(self, scope: dict, params: dict) -> dict:
        binding = self._binding_for(scope)
        cookies = binding.context.cookies()
        # Names + domains only. Raw values are secrets and are never returned.
        return {
            "names": sorted({f"{c.get('domain','')}:{c.get('name','')}" for c in cookies}),
            "count": len(cookies),
        }

    def _action_shutdown(self, scope: dict, params: dict) -> dict:
        # Must stop the HTTP listener too: the driver thread exiting on its own
        # would leave /health answering while every /action hung until timeout,
        # and the client would keep routing to a dead daemon.
        self._stopping.set()
        self._queue.put(None)
        if self._httpd is not None:
            threading.Thread(target=self._httpd.shutdown, daemon=True).start()
        return {"stopping": True}

    # pylint: enable=unused-argument

    # ------------------------------------------------------------------
    # Path safety
    # ------------------------------------------------------------------

    def _safe_path(self, params: dict, key: str, write: bool) -> str | None:
        raw = params.get(key)
        if not raw:
            return None
        root = params.get("write_root") or params.get("read_root")
        candidate = Path(os.path.expanduser(str(raw)))
        if not candidate.is_absolute():
            candidate = Path(root or os.getcwd()) / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if root:
            try:
                root_resolved = Path(os.path.expanduser(str(root))).resolve()
            except OSError:
                root_resolved = Path(str(root))
            try:
                resolved.relative_to(root_resolved)
            except ValueError as exc:
                raise BrowserError(f"path escapes allowed root: {raw}") from exc
        if write:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        elif not resolved.exists():
            raise BrowserError(f"no such file: {resolved}")
        return str(resolved)

    def _safe_write_path(self, params: dict, key: str = "path", required: bool = True) -> str | None:
        path = self._safe_path(params, key, write=True)
        if required and not path:
            raise BrowserError(f"{key} is required")
        return path

    def _safe_read_path(self, params: dict, key: str = "upload_path") -> str:
        path = self._safe_path(params, key, write=False)
        if not path:
            raise BrowserError(f"{key} is required")
        return path

    # ------------------------------------------------------------------
    # Reaper
    # ------------------------------------------------------------------

    def _reaper_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                self._submit(self.registry.reap_idle, timeout=60)
            except BrowserError:
                pass
            self._stopping.wait(30)

    def start_reaper(self) -> None:
        threading.Thread(target=self._reaper_loop, name="browser-reaper", daemon=True).start()

    def shutdown(self) -> None:
        self._stopping.set()
        self._queue.put(None)
        if self._driver_alive:
            try:
                self._submit(self.registry.close_all, timeout=5)
            except BrowserError:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # pylint: disable=broad-exception-caught
                pass


class _Handler(BaseHTTPRequestHandler):
    """Local JSON API. Bearer-token authenticated, loopback only."""

    daemon_obj: Daemon = None  # type: ignore[assignment]
    token: str = ""

    # pylint: disable=arguments-differ,redefined-builtin
    def log_message(self, format, *args):  # name fixed by the stdlib base class
        sys.stderr.write("[browser] " + (format % args) + "\n")

    def _auth(self) -> bool:
        header = self.headers.get("Authorization", "")
        return secrets.compare_digest(header, f"Bearer {self.token}")

    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # pylint: disable=invalid-name
    def do_GET(self):  # noqa: N802 - stdlib BaseHTTPRequestHandler API
        self._get()

    def do_POST(self):  # noqa: N802 - stdlib BaseHTTPRequestHandler API
        self._post()

    def _get(self) -> None:
        if self.path != "/health":
            self._reply(404, {"ok": False, "error": "not found"})
            return
        if not self._auth():
            self._reply(401, {"ok": False, "error": "unauthorized"})
            return
        self._reply(200, {"ok": True, "service": "agentone-browser", "pid": os.getpid()})

    def _post(self) -> None:
        if self.path != "/action":
            self._reply(404, {"ok": False, "error": "not found"})
            return
        if not self._auth():
            self._reply(401, {"ok": False, "error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._reply(400, {"ok": False, "error": "invalid json"})
            return
        action = str(payload.get("action") or "")
        scope = payload.get("scope") or {}
        params = payload.get("params") or {}
        try:
            result = self.daemon_obj._submit(  # pylint: disable=protected-access
                lambda: self.daemon_obj.handle(action, scope, params)  # pylint: disable=protected-access
            )
        except BrowserError as exc:
            self._reply(200, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._reply(200, {"ok": False, "error": f"{exc}\n{traceback.format_exc(limit=3)}"})
            return
        self._reply(200, {"ok": True, **(result or {})})


def _write_state(port: int) -> None:
    paths.ensure_private_dir(paths.browser_base())
    state = {"pid": os.getpid(), "port": port, "started_at": time.time()}
    paths.state_path().write_text(json.dumps(state), encoding="utf-8")


def _clear_state() -> None:
    try:
        paths.state_path().unlink()
    except OSError:
        pass


def serve() -> None:
    """Run the daemon in the foreground until SIGINT/SIGTERM or ``shutdown``."""
    daemon_obj = Daemon()
    daemon_obj.start_driver()

    token = paths.read_token()
    handler = type("BoundHandler", (_Handler,), {"daemon_obj": daemon_obj, "token": token})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    daemon_obj._httpd = httpd  # pylint: disable=protected-access
    port = httpd.server_address[1]
    _write_state(port)
    daemon_obj.start_reaper()

    def _stop(*_args) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    sys.stderr.write(f"[browser] daemon listening on 127.0.0.1:{port} (pid {os.getpid()})\n")
    try:
        httpd.serve_forever()
    finally:
        daemon_obj.shutdown()
        _clear_state()
        httpd.server_close()
        sys.stderr.write("[browser] daemon stopped\n")


if __name__ == "__main__":
    serve()
