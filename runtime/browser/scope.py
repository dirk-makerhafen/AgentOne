"""Session → browser-scope resolution (server side, runs in the worker).

Scope axes
----------
``root_pk``   the topmost ancestor of the calling session.  Child/subsession
              agents inherit the root session's browser, so they share login
              state and the profile on disk.
``is_root``   True when the calling session *is* the root.  A root may inspect
              every tab in its binding; a child may only touch tabs it owns.
``profile_key``  which on-disk browser profile to bind.

Crucially, all of this is derived from the injected ``session`` object and the
config — never from LLM-supplied scope keys.  The LLM may only *choose* between
documented profiles (``profile="github"``) or ask for a clean identity; it
cannot name another session's scope.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from runtime.browser import paths


@dataclass
class BrowserScope:
    """Resolved, server-derived browser scope for one tool call."""

    root_pk: int
    session_pk: int
    is_root: bool
    profile_key: str
    ephemeral: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _model_pk(session: Any) -> int:
    model = getattr(session, "model", None)
    pk = getattr(model, "pk", None)
    if not isinstance(pk, int):
        raise ValueError("browser: session has no integer pk")
    return pk


def _root_pk(session: Any) -> int:
    """Walk ``parent_session`` to the topmost ancestor."""
    root = _model_pk(session)
    model = getattr(session, "model", None)
    seen = {root}
    parent = getattr(model, "parent_session", None)
    while parent is not None:
        pk = getattr(parent, "pk", None)
        if not isinstance(pk, int) or pk in seen:
            break
        root = pk
        seen.add(pk)
        parent = getattr(parent, "parent_session", None)
    return root


def _session_name(session: Any) -> str:
    return str(getattr(getattr(session, "model", None), "name", "") or "")


def _root_session_name(session: Any) -> str:
    """Name of the topmost ancestor session (empty when unavailable)."""
    model = getattr(session, "model", None)
    seen = {id(model)}
    root_model = model
    parent = getattr(root_model, "parent_session", None)
    while parent is not None and id(parent) not in seen:
        seen.add(id(parent))
        root_model = parent
        parent = getattr(parent, "parent_session", None)
    return str(getattr(root_model, "name", "") or "")


def resolve_scope(
    session: Any,
    *,
    profile: str | None = None,
    clean: bool = False,
    browser_config: dict | None = None,
) -> BrowserScope:
    """Resolve the browser scope for *session*.

    *profile* — opt-in named durable profile shared across sessions.
    *clean*   — request a fresh throwaway identity for this call.
    """
    # pylint: disable=import-outside-toplevel
    from runtime.browser.config import get_browser_config

    cfg = browser_config or get_browser_config()
    session_pk = _model_pk(session)
    root_pk = _root_pk(session)
    is_root = session_pk == root_pk

    if clean:
        return BrowserScope(
            root_pk=root_pk,
            session_pk=session_pk,
            is_root=is_root,
            profile_key=paths.clean_profile_key(),
            ephemeral=True,
        )

    if profile:
        return BrowserScope(
            root_pk=root_pk,
            session_pk=session_pk,
            is_root=is_root,
            profile_key=paths.named_profile_key(profile),
            ephemeral=False,
        )

    # ``scope: named`` uses the root session's name so a reopened chat — and
    # every child subagent beneath it — reuses one durable login state; the
    # default ``scope: session`` keys on the root session pk.
    if cfg.get("scope") == "named":
        key = paths.named_profile_key(_root_session_name(session) or f"s{root_pk}")
    else:
        key = paths.session_profile_key(root_pk)

    if cfg.get("ephemeral_by_default"):
        return BrowserScope(
            root_pk=root_pk,
            session_pk=session_pk,
            is_root=is_root,
            profile_key=paths.clean_profile_key(),
            ephemeral=True,
        )

    return BrowserScope(
        root_pk=root_pk,
        session_pk=session_pk,
        is_root=is_root,
        profile_key=key,
        ephemeral=False,
    )
