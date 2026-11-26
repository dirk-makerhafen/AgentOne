"""Effective "local only, no cloud" policy for a session and its ancestry.

The policy is additive (one-way tightening).  Any of these sources switches it
on for a session:

* the session/agent ``SettingsModel.local_only`` flag;
* a session ``route_constraints`` entry or the ``auto:local`` profile;
* the session's current workspace or its owning project;
* the same sources on every ancestor session (forks and subsessions);
* the parent project stamped directly on any session in that chain.

A ``False`` value never clears a restriction from a wider scope, so a user
cannot accidentally send a child of a local-only project to a cloud provider.
"""
from __future__ import annotations

from typing import Any

#: Route target that is itself a local-only policy (also understood by
#: :mod:`runtime.routing.intent`).
LOCAL_PROFILE = "auto:local"


def _add(sources: list[str], source: str) -> None:
    if source not in sources:
        sources.append(source)


def _settings_flag(settings: Any) -> bool:
    # Literal True only: never coerce a MagicMock/test-double attribute into a
    # security policy.
    return settings is not None and getattr(settings, "local_only", False) is True


def _settings_constraints(settings: Any) -> dict:
    value = getattr(settings, "route_constraints", None)
    return value if isinstance(value, dict) else {}


def _settings_target(settings: Any) -> str:
    return str(getattr(settings, "route_target", "") or "").strip()


def _add_version_policy(version: Any, sources: list[str], source: str) -> None:
    """Add local-only signals from one session version's immutable settings."""
    if version is None:
        return
    settings = getattr(version, "session_settings", None)
    if _settings_flag(settings):
        _add(sources, source)
    constraints = _settings_constraints(settings)
    if constraints.get("local_only"):
        _add(sources, source)
    if _settings_target(settings) == LOCAL_PROFILE:
        _add(sources, source)


def _add_scope_policy(session_model: Any, sources: list[str], *, ancestor: bool) -> None:
    """Add workspace/project policy for one session row."""
    version = getattr(session_model, "latest_session_version", None)
    if version is not None:
        workspace = getattr(version, "workspace", None)
        if workspace is not None and _settings_flag(workspace):
            _add(sources, "workspace" if not ancestor else "ancestor workspace")
        project = getattr(workspace, "parent_project", None)
        if project is not None and _settings_flag(project):
            _add(sources, "project" if not ancestor else "ancestor project")

    project = getattr(session_model, "parent_project", None)
    if project is not None and _settings_flag(project):
        _add(sources, "project" if not ancestor else "ancestor project")


def local_only_sources(session: Any) -> list[str]:  # pylint: disable=too-many-branches
    """Return short labels for every active local-only source on *session*.

    Accepts a runtime ``Session`` wrapper (or any object exposing the same
    ``model`` / ``get_version_model`` / ``_get_session_setting`` interface).
    Failures are swallowed: policy resolution must never break a call just
    because a partially initialised session is being inspected.
    """
    sources: list[str] = []

    # Session override first, then the pinned agent's setting (which is also a
    # legitimate place to declare "this agent never uses the cloud").
    try:
        if session._get_session_setting("local_only") is True:  # pylint: disable=protected-access
            _add(sources, "session")
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    for name in ("route_constraints", "route_target"):
        try:
            value = session._get_session_setting(name)  # pylint: disable=protected-access
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if name == "route_constraints" and isinstance(value, dict) and value.get("local_only"):
            _add(sources, "session route")
        if name == "route_target" and str(value or "").strip() == LOCAL_PROFILE:
            _add(sources, "session route")

    try:
        version = session.get_version_model()
    except Exception:  # pylint: disable=broad-exception-caught
        version = None
    _add_version_policy(version, sources, "session")
    try:
        _add_scope_policy(session.model, sources, ancestor=False)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    session_model = getattr(session, "model", None)
    try:
        # Imported lazily to avoid a routing ↔ models import cycle.
        from server.models.sessions import session as session_module  # pylint: disable=import-outside-toplevel
    except Exception:  # pylint: disable=broad-exception-caught
        session_module = None
    session_model_cls = getattr(session_module, "SessionModel", None)
    if session_model_cls is not None and isinstance(session_model, session_model_cls):
        seen = {session_model.pk}
        parent_id = getattr(session_model, "parent_session_id", None)
        depth = 0
        while parent_id and parent_id not in seen and depth < 64:
            depth += 1
            seen.add(parent_id)
            try:
                parent = (
                    session_model_cls.objects.filter(pk=parent_id)
                    .select_related(
                        "latest_session_version__session_settings",
                        "latest_session_version__workspace__parent_project",
                        "parent_project",
                    )
                    .first()
                )
            except Exception:  # pylint: disable=broad-exception-caught
                break
            if parent is None:
                break
            _add_version_policy(parent.latest_session_version, sources, "parent session")
            try:
                _add_scope_policy(parent, sources, ancestor=True)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            parent_id = parent.parent_session_id

    return sources


def effective_local_only(session: Any) -> bool:
    """True when *session* (and anything below it) must never use cloud models."""
    return bool(local_only_sources(session))
