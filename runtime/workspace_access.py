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

Sessions without a workspace are not restricted (returns ``allow``).
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
PATH_ARG_NAMES: dict[str, list[str]] = {
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
class ActionPolicy:
    """Per-action policy: default posture + per-path overrides."""

    default: str = "allow"
    allow: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)


@dataclass
class WorkspaceAccessPolicy:
    """Resolved, merged access policy for a session."""

    workspace_root: Path | None
    inside_read: ActionPolicy = field(default_factory=ActionPolicy)
    inside_write: ActionPolicy = field(default_factory=ActionPolicy)
    external_read: ActionPolicy = field(default_factory=ActionPolicy)
    external_write: ActionPolicy = field(default_factory=ActionPolicy)

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

    def _inside_policy(self, action: str) -> ActionPolicy:
        return self.inside_read if action == "read" else self.inside_write

    def _external_policy(self, action: str) -> ActionPolicy:
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


def _action_config(scope: dict[str, Any] | None, action: str) -> ActionPolicy:
    """Extract an ActionPolicy from an ``access`` scope dict (unmerged).

    ``default`` is ``None`` when not explicitly configured — the caller
    decides the effective fallback so an explicit ``allow`` can override a
    parent's ``deny``.
    """
    cfg = (scope or {}).get(action) or {}
    default = cfg.get("default")
    if default is not None and default not in ACCESS_POSTURES:
        default = None
    return ActionPolicy(
        default=default,
        allow=[str(p) for p in (cfg.get("allow") or [])],
        ask=[str(p) for p in (cfg.get("ask") or [])],
        deny=[str(p) for p in (cfg.get("deny") or [])],
    )


def _merge_action(base: ActionPolicy, override: ActionPolicy) -> ActionPolicy:
    """Merge an agent ``workspace`` override on top of the workspace base."""
    return ActionPolicy(
        default=override.default if override.default is not None else base.default,
        allow=list(base.allow) + list(override.allow),
        ask=list(base.ask) + list(override.ask),
        deny=list(base.deny) + list(override.deny),
    )


def _agent_access(session: Any) -> dict[str, Any]:
    """Return the agent's ``access`` block from extra_settings, if any."""
    try:
        extra = session.agent.get_agent_setting("extra_settings")
    except Exception:  # pylint: disable=broad-exception-caught
        return {}
    if not isinstance(extra, dict):
        return {}
    access = extra.get("access")
    return access if isinstance(access, dict) else {}


def resolve_policy(session: Any) -> WorkspaceAccessPolicy:
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

    return WorkspaceAccessPolicy(
        workspace_root=root,
        inside_read=_merge_action(base_read, override_read),
        inside_write=_merge_action(base_write, override_write),
        external_read=ext_read,
        external_write=ext_write,
    )


def _inside_workspace(policy: WorkspaceAccessPolicy, target: Path) -> bool:
    if policy.workspace_root is None:
        return False
    try:
        target.relative_to(policy.workspace_root)
        return True
    except ValueError:
        return False


# pylint: disable=too-many-return-statements
def evaluate(policy: WorkspaceAccessPolicy, target: str, action: str) -> GuardrailVerdict:
    """Evaluate *target* against *policy* for *action* (``read`` or ``write``).

    Returns an ``allow`` / ``ask`` / ``deny`` verdict.  ``ask`` means the
    operation should require human approval; ``deny`` means it must be
    blocked outright.
    """
    if action not in ACCESS_ACTIONS:
        action = "read"

    if policy.workspace_root is None:
        return GuardrailVerdict(action="allow", score=0, level="safe", reason="")

    raw = Path(target).expanduser()
    if not raw.is_absolute():
        raw = policy.workspace_root / raw
    target_resolved = raw.resolve()
    target_abs = target_resolved.as_posix()
    target_abs_raw = raw.as_posix()  # pre-symlink-resolution form (e.g. /tmp on macOS)
    try:
        target_rel = target_resolved.relative_to(policy.workspace_root).as_posix()
    except ValueError:
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

    inside = _inside_workspace(policy, target_resolved)
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
    arg_names = PATH_ARG_NAMES.get(task_name, [])
    paths: list[tuple[str, str]] = []
    for name in arg_names:
        value = args.get(name)
        if isinstance(value, str) and value.strip():
            paths.append((value, action))
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
