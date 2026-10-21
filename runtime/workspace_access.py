"""Workspace-scoped filesystem access policy.

The policy is expressed as an ``access`` block configured in two places:

* **Workspace** (``project.md`` frontmatter): governs paths *inside* the
  workspace.  Patterns are workspace-relative globs.
* **Agent** (``agent.md`` frontmatter): two sub-scopes:

  * ``workspace`` — overrides/extends the workspace's inside-rules.
    Patterns are workspace-relative.
  * ``external`` — governs paths *outside* the workspace.  Patterns must
    be absolute or ``~``-anchored.

Schema (per action, ``read`` and ``write``)::

    access:
      read:
        default: allow        # allow | ask | deny
        allow:  []            # carve-outs (used when default: deny)
        ask:    []            # require approval for these paths
        deny:   []            # always denied (global floor)
      write:
        default: deny
        allow:  ["inbox/**"]
        ask:    ["scratch/**"]
        deny:   []

Evaluation precedence is ``deny > ask > allow > default``.  ``deny``
patterns are **global**: a deny in any scope blocks the path everywhere.
``write`` implies ``read`` on allowed/asked paths; ``read`` rules never
grant writes.

Sessions without a workspace are not restricted (returns ``allow``),
except for other sessions' private-storage folders (always ``deny``).

Session-private storage (``~/.agentone/sessions/<pk>/``, see
``runtime/session_folder.py``) is carved out in :func:`evaluate`: the owning
session's own folder is always ``allow`` (read and write); other sessions'
folders and the base dir itself are always ``deny``.  Only an explicit
global ``deny`` pattern overrides the own-folder allow.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.guardrails import GuardrailVerdict

ACCESS_ACTIONS = ("read", "write")
ACCESS_POSTURES = ("allow", "ask", "deny")

# Tool name → path argument names.  Group name determines the action:
# ``filesystem-write`` → write, ``filesystem-read`` → read.
# A value may also be a ``{arg: action}`` mapping for tools that mix actions
# in one signature (``browser``: ``path``/``download_path`` are written,
# ``upload_path`` is read).
PATH_ARG_NAMES: dict[str, list[str] | dict[str, str]] = {
    "browser": {"path": "write", "download_path": "write", "upload_path": "read"},
    "read": ["path"],
    "grep": ["path"],
    "glob": ["path"],
    "stat": ["path"],
    "tree": ["path"],
    "diff": ["path", "target"],
    "write": ["path"],
    "append": ["path"],
    "edit": ["path"],
    "multiedit": ["path"],
    "copy": ["source", "destination"],
    "move": ["source", "destination"],
    "mkdir": ["path"],
    "rm": ["path"],
}


@dataclass
class _ActionPolicy:
    """Per-action policy: default posture + per-path overrides."""

    default: str = "allow"
    allow: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)


@dataclass
class _WorkspaceAccessPolicy:
    """Resolved, merged access policy for a session."""

    workspace_root: Path | None
    inside_read: _ActionPolicy = field(default_factory=_ActionPolicy)
    inside_write: _ActionPolicy = field(default_factory=_ActionPolicy)
    external_read: _ActionPolicy = field(default_factory=_ActionPolicy)
    external_write: _ActionPolicy = field(default_factory=_ActionPolicy)
    # Owning session pk for the session-private storage carve-out
    # (``~/.agentone/sessions/<pk>/``).  *None* when unknown.
    session_pk: int | None = None
    # Additional roots treated as "inside" for policy purposes: the
    # session's manifest directories (project/workspace ``.agentone``),
    # including central storage locations outside the workspace path.
    manifest_roots: list[Path] = field(default_factory=list)

    @property
    def global_deny(self) -> list[str]:
        """All deny patterns across every scope (deny always wins)."""
        deny: list[str] = []
        for policy in (
            self.inside_read,
            self.inside_write,
            self.external_read,
            self.external_write,
        ):
            deny.extend(policy.deny)
        return deny

    def _inside_policy(self, action: str) -> _ActionPolicy:
        return self.inside_read if action == "read" else self.inside_write

    def _external_policy(self, action: str) -> _ActionPolicy:
        return self.external_read if action == "read" else self.external_write


def _normalize_pattern(pattern: str) -> str:
    pattern = os.path.expanduser(pattern.strip())
    while pattern.startswith("./"):
        pattern = pattern[2:]
    return pattern


def _pattern_matches(pattern: str, target_abs: str, target_rel: str | None) -> bool:
    """Match a glob against the absolute and workspace-relative target forms."""
    pattern = _normalize_pattern(pattern)
    if not pattern:
        return False
    if fnmatch.fnmatch(target_abs, pattern):
        return True
    if target_rel is not None and fnmatch.fnmatch(target_rel, pattern):
        return True
    return False


def _matches(
    patterns: list[str], candidates: list[str], target_rel: str | None
) -> bool:
    return any(_pattern_matches(p, c, target_rel) for p in patterns for c in candidates)


def _action_config(scope: dict[str, Any] | None, action: str) -> _ActionPolicy:
    """Extract an _ActionPolicy from an ``access`` scope dict (unmerged).

    ``default`` is ``None`` when not explicitly configured — the caller
    decides the effective fallback so an explicit ``allow`` can override a
    parent's ``deny``.
    """
    cfg = (scope or {}).get(action) or {}
    default = cfg.get("default")
    if default is not None and default not in ACCESS_POSTURES:
        default = None
    return _ActionPolicy(
        default=default,
        allow=[str(p) for p in (cfg.get("allow") or [])],
        ask=[str(p) for p in (cfg.get("ask") or [])],
        deny=[str(p) for p in (cfg.get("deny") or [])],
    )


def _merge_action(base: _ActionPolicy, override: _ActionPolicy) -> _ActionPolicy:
    """Merge an agent ``workspace`` override on top of the workspace base."""
    return _ActionPolicy(
        default=override.default if override.default is not None else base.default,
        allow=list(base.allow) + list(override.allow),
        ask=list(base.ask) + list(override.ask),
        deny=list(base.deny) + list(override.deny),
    )


def _agent_access(session: Any) -> dict[str, Any]:
    """Return the agent's ``access`` block, if any."""
    try:
        access = session.agent.get_agent_setting("access")
    except Exception:  # pylint: disable=broad-exception-caught
        return {}
    return access if isinstance(access, dict) else {}


def resolve_policy(session: Any) -> _WorkspaceAccessPolicy:
    """Build the merged access policy for *session*.

    Combines the workspace ``access`` block with the agent's ``access``
    block (``workspace`` override + ``external`` scope).  Sessions without
    a workspace get an all-allow policy (no enforcement).
    """
    workspace = getattr(session, "workspace", None)
    root: Path | None = None
    workspace_access: dict[str, Any] = {}
    if workspace is not None:
        path = getattr(workspace, "path", None)
        if path:
            root = Path(path).resolve()
        workspace_access = getattr(workspace, "access", None) or {}

    agent_access = _agent_access(session)
    agent_workspace = agent_access.get("workspace") or {}
    agent_external = agent_access.get("external") or {}

    base_read = _action_config(workspace_access, "read")
    base_write = _action_config(workspace_access, "write")
    override_read = _action_config(agent_workspace, "read")
    override_write = _action_config(agent_workspace, "write")

    ext_read = _action_config(agent_external, "read")
    ext_write = _action_config(agent_external, "write")
    ext_read.default = ext_read.default if ext_read.default is not None else "deny"
    ext_write.default = ext_write.default if ext_write.default is not None else "deny"

    base_read.default = base_read.default if base_read.default is not None else "allow"
    base_write.default = base_write.default if base_write.default is not None else "allow"

    manifest_roots: list[Path] = []
    seen_roots: set[str] = set()
    def _add_root(candidate: Any) -> None:
        if candidate is None:
            return
        try:
            p = Path(candidate).expanduser()
            try:
                p = p.resolve()
            except OSError:
                pass
            key = p.as_posix()
            if key and key not in seen_roots:
                seen_roots.add(key)
                manifest_roots.append(p)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    if workspace is not None:
        try:
            _add_root(workspace.get_agentone_dir())
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    try:
        project = session.get_project() if hasattr(session, "get_project") else None
    except Exception:  # pylint: disable=broad-exception-caught
        project = None
    if project is not None:
        try:
            _add_root(project.get_agentone_dir())
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    if not manifest_roots:
        try:
            from runtime.paths import agentone_home

            _add_root(agentone_home())
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    return _WorkspaceAccessPolicy(
        workspace_root=root,
        inside_read=_merge_action(base_read, override_read),
        inside_write=_merge_action(base_write, override_write),
        external_read=ext_read,
        external_write=ext_write,
        session_pk=_session_pk(session),
        manifest_roots=manifest_roots,
    )


def _session_pk(session: Any) -> int | None:
    """Extract the owning session pk from a session object, if available.

    Only unambiguous pk carriers are consulted.  ``id``/``session_id`` are
    deliberately *not* used: an int that merely looks like an id would
    mis-attribute the carve-out and deny the session's own folder while
    allowing a different session's.
    """
    model = getattr(session, "model", None)
    if model is not None:
        pk = getattr(model, "pk", None)
        if isinstance(pk, int):
            return pk
    for attr in ("pk", "session_pk"):
        pk = getattr(session, attr, None)
        if isinstance(pk, int):
            return pk
    return None


def _session_dir_verdict(session_pk: int | None, target_abs: str, target_abs_raw: str) -> GuardrailVerdict | None:  # pylint: disable=too-many-return-statements
    """Session-private storage carve-out.

    Own folder -> ``allow`` (read and write); another session's folder (or
    a sessions base / intermediate agent directory for the global base) ->
    ``deny``.  Returns *None* when the target is outside any session-private
    storage tree or the owning pk is unknown.  Handles both the legacy
    (``<base>/<pk>/``) and new (``<base>/<agent>/<pk>/``) layouts, as well
    as session folders nested under workspace/project agentone dirs.
    """
    if session_pk is None:
        return None
    # Global sessions base (honours AGENTONE_SESSIONS_DIR).
    try:
        from runtime.session_folder import get_sessions_base

        base_resolved = get_sessions_base().expanduser().resolve().as_posix()
    except OSError:
        base_resolved = None
    except Exception:  # pylint: disable=broad-exception-caught
        base_resolved = None
    if base_resolved is not None:
        for candidate in (target_abs, target_abs_raw):
            if candidate == base_resolved:
                rel = ""
            elif candidate.startswith(base_resolved.rstrip("/") + "/"):
                rel = candidate[len(base_resolved.rstrip("/") + "/"):]
            else:
                continue
            if rel == "":
                return GuardrailVerdict(
                    action="deny",
                    score=100,
                    level="critical",
                    reason="Session-private storage base directory is not listable",
                    risk_factors=["session_private_storage"],
                )
            segments = rel.split("/")
            owner: str | None = None
            if segments and segments[0].isdigit():
                owner = segments[0]
            elif len(segments) >= 2 and segments[1].isdigit():
                owner = segments[1]
            else:
                # Intermediate agent directory (not listable).
                return GuardrailVerdict(
                    action="deny",
                    score=100,
                    level="critical",
                    reason="Session-private storage agent directory is not listable",
                    risk_factors=["session_private_storage"],
                )
            if owner == str(session_pk):
                return GuardrailVerdict(action="allow", score=0, level="safe", reason="")
            return GuardrailVerdict(
                action="deny",
                score=100,
                level="critical",
                reason=f"Path belongs to another session's private storage: {target_abs}",
                risk_factors=["session_private_storage"],
            )

    # Structural detection for session folders nested under any other base
    # (workspace/project agentone dirs).  Only triggers when an integer
    # session pk segment is present, so unrelated ``.../sessions/...``
    # paths are left to the normal policy.
    for candidate in (target_abs, target_abs_raw):
        parts = candidate.rstrip("/").split("/")
        idx = None
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] == "sessions":
                idx = i
                break
        if idx is None:
            continue
        rest = parts[idx + 1:]
        if not rest:
            continue
        owner = None
        if rest[0].isdigit():
            owner = rest[0]
        elif len(rest) >= 2 and rest[1].isdigit():
            owner = rest[1]
        if owner is None:
            continue
        if owner == str(session_pk):
            return GuardrailVerdict(action="allow", score=0, level="safe", reason="")
        return GuardrailVerdict(
            action="deny",
            score=100,
            level="critical",
            reason=f"Path belongs to another session's private storage: {target_abs}",
            risk_factors=["session_private_storage"],
        )
    return None

def _inside_workspace(policy: _WorkspaceAccessPolicy, target: Path) -> bool:
    if policy.workspace_root is None:
        return False
    try:
        target.relative_to(policy.workspace_root)
        return True
    except ValueError:
        return False

def _inside_manifest_root(policy: _WorkspaceAccessPolicy, target: Path) -> bool:
    for root in (policy.manifest_roots or []):
        try:
            target.relative_to(root)
            return True
        except (ValueError, Exception):
            continue
    return False


# pylint: disable=too-many-return-statements,too-many-branches
def evaluate(policy: _WorkspaceAccessPolicy, target: str, action: str) -> GuardrailVerdict:
    """Evaluate *target* against *policy* for *action* (``read`` or ``write``).

    Returns an ``allow`` / ``ask`` / ``deny`` verdict.  ``ask`` means the
    operation should require human approval; ``deny`` means it must be
    blocked outright.
    """
    if action not in ACCESS_ACTIONS:
        action = "read"

    raw = Path(target).expanduser()
    if not raw.is_absolute() and policy.workspace_root is not None:
        raw = policy.workspace_root / raw
    try:
        target_resolved = raw.resolve()
    except OSError:
        target_resolved = raw
    target_abs = target_resolved.as_posix()
    target_abs_raw = raw.as_posix()  # pre-symlink-resolution form (e.g. /tmp on macOS)
    if policy.workspace_root is not None:
        try:
            target_rel = target_resolved.relative_to(policy.workspace_root).as_posix()
        except ValueError:
            target_rel = None
    else:
        target_rel = None

    # Global deny floor — deny from any scope wins everywhere.
    if _matches(policy.global_deny, [target_abs, target_abs_raw], target_rel):
        return GuardrailVerdict(
            action="deny",
            score=100,
            level="critical",
            reason=f"Path is denied by workspace access policy: {target_abs}",
            risk_factors=["workspace_access_deny"],
        )

    # Session-private storage carve-out — own folder always allowed,
    # other sessions' folders (and the base dir itself) always denied.
    # Applies even to sessions without a workspace.
    session_verdict = _session_dir_verdict(policy.session_pk, target_abs, target_abs_raw)
    if session_verdict is not None:
        return session_verdict

    if policy.workspace_root is None:
        return GuardrailVerdict(action="allow", score=0, level="safe", reason="")

    inside = _inside_workspace(policy, target_resolved)
    if not inside and _inside_manifest_root(policy, target_resolved):
        inside = True

    # pylint: disable=protected-access
    scope = policy._inside_policy(action) if inside else policy._external_policy(action)
    write_scope = policy._inside_policy("write") if inside else policy._external_policy("write")
    # pylint: enable=protected-access

    # write implies read: for reads also consider the write policy's allow/ask.
    ask_patterns = list(scope.ask)
    allow_patterns = list(scope.allow)
    if action == "read":
        ask_patterns += list(write_scope.ask)
        allow_patterns += list(write_scope.allow)

    if _matches(ask_patterns, [target_abs, target_abs_raw], target_rel):
        return GuardrailVerdict(
            action="ask",
            score=60,
            level="caution",
            reason=f"Path requires approval by workspace access policy: {target_abs}",
            risk_factors=["workspace_access_ask"],
        )

    if _matches(allow_patterns, [target_abs, target_abs_raw], target_rel):
        return GuardrailVerdict(action="allow", score=0, level="safe", reason="")

    default = scope.default
    if default == "deny":
        return GuardrailVerdict(
            action="deny",
            score=100,
            level="critical",
            reason=f"Path is outside the allowed {action} scope: {target_abs}",
            risk_factors=["workspace_access_default"],
        )
    if default == "ask":
        return GuardrailVerdict(
            action="ask",
            score=60,
            level="caution",
            reason=f"Path requires approval by workspace access policy: {target_abs}",
            risk_factors=["workspace_access_default"],
        )
    return GuardrailVerdict(action="allow", score=0, level="safe", reason="")


# Group-name fallback for tasks whose manifest does not yet declare ``access:``.
# The manifest field (``TaskDefinition.access_posture``) takes precedence; this
# map is only consulted when it is unset, so existing manifests keep working.
_FALLBACK_GROUP_POSTURE: dict[str, str] = {
    "filesystem-read": "read",
    "filesystem-write": "write",
}


def task_access_posture(task_definition: Any) -> str | None:
    """Resolve a task's filesystem access posture ("read"/"write"/None).

    Prefers the manifest-declared ``access:`` field (stored as
    ``access_posture`` on ``TaskDefinition``); falls back to the legacy
    ``group_name`` convention when unset.  ``None`` means the tool is not a
    filesystem-guarded tool.
    """
    posture = getattr(task_definition, "access_posture", None)
    if posture in ("read", "write"):
        return posture
    group = getattr(task_definition, "group_name", "") or ""
    return _FALLBACK_GROUP_POSTURE.get(group)


def extract_path_args(
    task_name: str, posture: str | None, args: dict[str, Any]
) -> list[tuple[str, str]]:
    """Extract (path, action) pairs from a filesystem tool call.

    *task_name* is the tool name (e.g. ``write``), *posture* the resolved
    access posture (``"read"`` or ``"write"``) from
    :func:`task_access_posture`, *args* the keyword arguments.  Returns an
    empty list for tools without a filesystem posture.
    """
    if posture not in ("read", "write"):
        return []
    action = posture
    declared = PATH_ARG_NAMES.get(task_name, [])
    if isinstance(declared, dict):
        pairs = list(declared.items())
    else:
        pairs = [(name, action) for name in declared]
    paths: list[tuple[str, str]] = []
    for name, act in pairs:
        value = args.get(name)
        if isinstance(value, str) and value.strip():
            paths.append((value, act))
    return paths


# ---------------------------------------------------------------------------
# Manifest validation (called at load time; raises on invalid config)
# ---------------------------------------------------------------------------


def _is_external_scope(pattern: str) -> bool:
    """True if *pattern* is absolute or ``~``-anchored (external scope)."""
    pattern = pattern.strip()
    return pattern.startswith("/") or pattern.startswith("~")


def _has_path_escape(pattern: str) -> bool:
    return ".." in [seg for seg in pattern.strip().split("/") if seg]


def _validate_scope(
    scope: Any, scope_name: str, *, external: bool, source: str
) -> None:
    if scope is None:
        return
    if not isinstance(scope, dict):
        raise ValueError(f"[{source}] access.{scope_name} must be a mapping")
    for action in ACCESS_ACTIONS:
        cfg = scope.get(action)
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            raise ValueError(
                f"[{source}] access.{scope_name}.{action} must be a mapping"
            )
        default = cfg.get("default")
        if default is not None and default not in ACCESS_POSTURES:
            raise ValueError(
                f"[{source}] access.{scope_name}.{action}.default must be one of "
                f"{ACCESS_POSTURES}, got {default!r}"
            )
        for list_name in ("allow", "ask", "deny"):
            patterns = cfg.get(list_name) or []
            if not isinstance(patterns, (list, tuple)):
                raise ValueError(
                    f"[{source}] access.{scope_name}.{action}.{list_name} "
                    f"must be a list, got {type(patterns).__name__}"
                )
            for pattern in patterns:
                pattern = str(pattern)
                if _has_path_escape(pattern):
                    raise ValueError(
                        f"[{source}] access.{scope_name}.{action}.{list_name} "
                        f"pattern {pattern!r} may not contain '..'"
                    )
                if external and not _is_external_scope(pattern):
                    raise ValueError(
                        f"[{source}] access.{scope_name}.{action}.{list_name} "
                        f"pattern {pattern!r} must be absolute or '~'-anchored "
                        f"(external scope)"
                    )
                if not external and _is_external_scope(pattern):
                    raise ValueError(
                        f"[{source}] access.{scope_name}.{action}.{list_name} "
                        f"pattern {pattern!r} must be relative to the workspace "
                        f"root (no leading '/', no '~')"
                    )


def validate_workspace_access(access: Any, source: str = "project.md") -> None:
    """Validate a workspace ``access`` block (workspace-relative patterns)."""
    if access is None:
        return
    if not isinstance(access, dict):
        raise ValueError(f"[{source}] access must be a mapping")
    _validate_scope(access, "workspace", external=False, source=source)


def validate_agent_access(access: Any, source: str = "agent.md") -> None:
    """Validate an agent ``access`` block.

    ``workspace`` scope patterns are workspace-relative; ``external`` scope
    patterns must be absolute or ``~``-anchored.
    """
    if access is None:
        return
    if not isinstance(access, dict):
        raise ValueError(f"[{source}] access must be a mapping")
    for sub in ("workspace", "external"):
        scope = access.get(sub)
        if scope is not None:
            _validate_scope(
                scope, f"agent.{sub}", external=(sub == "external"), source=source
            )
