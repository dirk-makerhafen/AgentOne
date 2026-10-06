"""Browser binding registry.

One *binding* owns one browser process and the pages inside it, keyed by
profile.  One profile normally maps to one root session, so a session's
cookies/logins are private to it; an opt-in named profile is shared, in which
case two sessions attach to the same process but keep separate page ownership.

All browser work is serialized on the daemon's single driver thread (Playwright
sync objects are thread-bound), so the maps below are only *read* by the HTTP
handler; a re-entrant lock keeps the health/status views consistent.

Idle accounting uses :func:`time.monotonic`, never wall-clock time: the clock
jumping forward across system sleep (or an NTP step) must not read as user
idleness and reap a browser the user just stepped away from.
"""

from __future__ import annotations

import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from runtime.browser import paths


class OwnershipError(PermissionError):
    """The caller may not touch that page."""


@dataclass
class PageRecord:
    """A single tab and who owns it."""

    page_id: str
    owner_pk: int
    created_at: float
    url: str = ""

    def to_dict(self) -> dict:
        return {"page_id": self.page_id, "owner_pk": self.owner_pk, "url": self.url}


@dataclass
class Binding:
    """A live browser process plus its pages."""

    profile_key: str
    root_pk: int
    context: Any
    ephemeral: bool = False
    created_at: float = field(default_factory=time.monotonic)
    last_used: float = field(default_factory=time.monotonic)
    pages: dict[str, PageRecord] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_used = time.monotonic()

    def page_list(self) -> list[dict]:
        return [rec.to_dict() for rec in self.pages.values()]


class Registry:
    """Thread-safe map of live bindings + ownership enforcement."""

    def __init__(self, cfg_provider, launch_fn) -> None:
        # A callable, not a dict: the daemon re-reads config.yaml periodically,
        # so an operator editing max_processes/idle_seconds takes effect
        # without restarting the daemon.
        self._cfg_provider = cfg_provider
        self._launch_fn = launch_fn
        self._bindings: dict[str, Binding] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------

    def get(self, profile_key: str) -> Binding | None:
        with self._lock:
            binding = self._bindings.get(profile_key)
            if binding is not None:
                binding.touch()
            return binding

    def get_or_launch(self, profile_key: str, root_pk: int, *, ephemeral: bool = False) -> Binding:
        with self._lock:
            binding = self._bindings.get(profile_key)
            if binding is not None:
                binding.touch()
                return binding
            # Launch outside the lock would race; launching is fast enough to
            # hold it and it keeps duplicate processes impossible.
            self._enforce_budget()
            context = self._launch_fn(profile_key)
            binding = Binding(profile_key=profile_key, root_pk=root_pk, context=context, ephemeral=ephemeral)
            self._bindings[profile_key] = binding
            return binding

    def _enforce_budget(self) -> None:
        max_procs = int(self._cfg_provider().get("max_processes") or 6)
        while len(self._bindings) >= max_procs:
            oldest = min(self._bindings.values(), key=lambda b: b.last_used)
            self._close_binding(oldest)

    def idle_deadline(self) -> float:
        idle = int(self._cfg_provider().get("idle_seconds") or 3600)
        return time.monotonic() - idle

    def reap_idle(self) -> int:
        """Close bindings past the idle deadline. Returns count closed."""
        deadline = self.idle_deadline()
        with self._lock:
            stale = [b for b in self._bindings.values() if b.last_used < deadline]
            for binding in stale:
                self._close_binding(binding)
            return len(stale)

    def _close_binding(self, binding: Binding) -> None:
        self._bindings.pop(binding.profile_key, None)
        try:
            binding.context.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        # A clean profile lives only for that call — remove its footprint.
        if binding.ephemeral:
            shutil.rmtree(paths.profile_dir(binding.profile_key), ignore_errors=True)

    def close_all(self) -> None:
        with self._lock:
            for binding in list(self._bindings.values()):
                self._close_binding(binding)

    def status(self) -> dict:
        with self._lock:
            return {
                "bindings": [
                    {
                        "profile_key": b.profile_key,
                        "root_pk": b.root_pk,
                        "pages": b.page_list(),
                        "age": round(time.monotonic() - b.created_at, 1),
                        "idle": round(time.monotonic() - b.last_used, 1),
                        "ephemeral": b.ephemeral,
                    }
                    for b in self._bindings.values()
                ]
            }

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def new_page_id(self) -> str:
        return "p" + secrets.token_hex(6)

    def add_page(self, binding: Binding, owner_pk: int) -> PageRecord:
        """Register a newly opened tab owned by *owner_pk*."""
        rec = PageRecord(page_id=self.new_page_id(), owner_pk=owner_pk, created_at=time.monotonic())
        binding.pages[rec.page_id] = rec
        binding.touch()
        return rec

    def resolve(self, binding: Binding, page_id: str | None, session_pk: int, is_root: bool) -> PageRecord:
        """Resolve a page id within *binding*, enforcing ownership.

        A root session may act on any tab in its binding; a child session may
        only act on tabs it owns.  Omitting *page_id* uses the most recently
        created tab the caller is allowed to touch.
        """
        with self._lock:
            if not binding.pages:
                raise OwnershipError("no open pages in this browser — open one first")
            if page_id:
                rec = binding.pages.get(page_id)
                if rec is None:
                    raise OwnershipError(f"unknown page: {page_id}")
                if not is_root and rec.owner_pk != session_pk:
                    raise OwnershipError(
                        f"page {page_id} belongs to another session in this browser"
                    )
                binding.touch()
                return rec
            owned = [r for r in binding.pages.values() if is_root or r.owner_pk == session_pk]
            if not owned:
                raise OwnershipError("no pages owned by this session — open one first")
            rec = max(owned, key=lambda r: r.created_at)
            binding.touch()
            return rec

    def close_page(self, binding: Binding, rec: PageRecord) -> None:
        """Forget *rec* (the caller has already closed the underlying page)."""
        with self._lock:
            for pid, rec_item in list(binding.pages.items()):
                if rec_item is rec:
                    binding.pages.pop(pid, None)
                    return
