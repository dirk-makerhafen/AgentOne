"""Session-time consumption of synthesized memory playbooks.

The memory loop writes a *playbook* (``reflection.md`` frontmatter, see
``.agentone/agents/internal/memory-manage/scripts/playbook.py``) into each
memory node.  This module is the read path: it resolves the playbooks that
apply to a session, renders a compact advisory message, and lets
:mod:`runtime.session_bootstrap` pin it with the other bootstrap content.

Resolution order (most specific first on conflict):

``task`` → ``agent`` → workspace scope → project scope → global scope

Every distinct directive from those nodes is considered; duplicates are
deduped by fingerprint, so the same lesson consolidated at several layers is
injected once.  Directives routed to ``harness`` are proposals, not rules —
they are deliberately not injected, because turning a platform bug into an
agent rule is how workarounds become permanent.  Directives routed to
``memory`` are facts and belong in ``memory.md``.

Injection is opt-in per agent (``memoryPlaybook:`` in ``agent.md`` / the
``memory_playbook`` session setting), matching ``autoload:``.  Off by default
so nothing is injected into agents that were never meant to receive it.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HEADER = (
    "[Memory playbook — advisory directives learned from earlier sessions in "
    "this scope. They refine how you work; they do not add tools or change "
    "permissions. If a directive conflicts with the user, the user wins.]"
)

_SKILL_HEADER = (
    "[Skills assigned to this agent — call load_skill(\"<name>\") before "
    "starting a procedure whose trigger matches. They are not loaded yet.]"
)

_SKIP_ROUTING = {"harness", "memory"}

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "maxDirectives": 12,
    "maxChars": 4000,
    "includeCandidates": False,
    "includeSkills": True,
    "maxSkills": 12,
}

_MAX_RULE_CHARS = 300
_MAX_TRIGGER_CHARS = 120
_MAX_SKILL_DESC_CHARS = 160


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def validate_memory_playbook_block(block: Any, source: str = "agent.md") -> dict[str, Any]:
    """Validate an ``agent.md`` ``memoryPlaybook:`` block.

    Accepts a boolean or a mapping.  Raises :class:`ValueError` on anything
    else, mirroring ``validate_autoload_block`` so manifest mistakes surface at
    reload time instead of silently disabling the feature.
    """
    if isinstance(block, bool):
        return {"enabled": block}
    if not isinstance(block, dict):
        raise ValueError(
            f"[{source}] memoryPlaybook must be a boolean or a mapping, "
            f"got {type(block).__name__}"
        )

    known = set(DEFAULTS) - {"enabled"}
    unknown = set(block) - known - {"enabled"}
    if unknown:
        raise ValueError(
            f"[{source}] memoryPlaybook has unknown keys {sorted(unknown)} "
            f"(expected subset of {sorted(known)})"
        )

    out: dict[str, Any] = {}
    if "enabled" in block:
        if not isinstance(block["enabled"], bool):
            raise ValueError(f"[{source}] memoryPlaybook.enabled must be a boolean")
        out["enabled"] = block["enabled"]
    for key in ("includeCandidates", "includeSkills"):
        if key in block:
            if not isinstance(block[key], bool):
                raise ValueError(f"[{source}] memoryPlaybook.{key} must be a boolean")
            out[key] = block[key]
    for key in ("maxDirectives", "maxChars", "maxSkills"):
        if key in block:
            value = block[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"[{source}] memoryPlaybook.{key} must be an integer >= 0, "
                    f"got {value!r}"
                )
            out[key] = value
    return out


def get_config(session: Any) -> dict[str, Any]:
    """Return the effective playbook config for *session* with defaults."""
    try:
        raw = session._get_session_setting("memory_playbook")
    except Exception:  # pylint: disable=broad-exception-caught
        raw = None

    cfg = dict(DEFAULTS)
    if isinstance(raw, bool):
        cfg["enabled"] = raw
    elif isinstance(raw, dict):
        cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    return cfg


def is_enabled(session: Any) -> bool:
    """Whether playbook injection is enabled for *session*."""
    return bool(get_config(session).get("enabled"))


# ---------------------------------------------------------------------------
# Node discovery
# ---------------------------------------------------------------------------


def _memory_root_for_scope(scope: Any) -> Path | None:
    """Return ``<scope manifest dir>/memory`` for a project/workspace."""
    if scope is None:
        return None
    try:
        from runtime.paths import ScopeRef

        if hasattr(scope, "parent_project"):
            ref = ScopeRef.for_workspace(scope)
        else:
            ref = ScopeRef.for_project(scope)
        return ref.manifest_dir / "memory"
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("memory_playbook: scope path unavailable", exc_info=True)
        return None


def _user_memory_root() -> Path:
    from runtime.paths import user_memory_dir

    return user_memory_dir()


def _safe_segment(value: Any) -> str:
    return str(value or "").strip().strip("/") or "unnamed"


def _task_dir(agent_dir: Path, group_key: str) -> Path:
    group = str(group_key or "").strip() or "default"
    return agent_dir / "tasks" / f"task_{_safe_segment(group)}"


def scope_roots(session: Any) -> list[tuple[str, str, Path]]:
    """Return ``(kind, label, memory_root)`` for this session's scopes.

    Most specific first: workspace, project, global.  Duplicates (a workspace
    inside its own project root) are dropped so a playbook is never injected
    twice.
    """
    workspace = None
    project = None
    try:
        workspace = session.workspace
    except Exception:  # pylint: disable=broad-exception-caught
        workspace = None
    try:
        project = session.get_project()
    except Exception:  # pylint: disable=broad-exception-caught
        project = None

    roots: list[tuple[str, str, Path]] = []
    seen: set[str] = set()

    def _add(kind: str, label: str, root: Path | None) -> None:
        if root is None:
            return
        key = root.as_posix()
        if key in seen:
            return
        seen.add(key)
        roots.append((kind, label, root))

    workspace_root = _memory_root_for_scope(workspace)
    if workspace_root is not None:
        label = f"workspace {getattr(workspace, 'name', '') or workspace_root.parent.name}"
        _add("workspace", label, workspace_root)
    project_root = _memory_root_for_scope(project)
    if project_root is not None:
        label = f"project {getattr(project, 'name', '') or project_root.parent.name}"
        _add("project", label, project_root)
    _add("global", "global", _user_memory_root())
    return roots


def candidate_playbooks(session: Any) -> list[dict[str, Any]]:
    """Return playbook candidates for *session*, most specific first.

    Each entry is ``{"label", "layer", "path"}``.  Missing files are still
    returned (the caller filters), so callers can reason about the full
    resolution regardless of what exists on disk.
    """
    agent_pk = None
    try:
        agent_pk = session.agent.model.pk
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("memory_playbook: agent unavailable", exc_info=True)

    group_key = ""
    try:
        group_key = session.group_key
    except Exception:  # pylint: disable=broad-exception-caught
        group_key = ""

    roots = scope_roots(session)
    filename = "reflection.md"

    candidates: list[dict[str, Any]] = []
    if agent_pk is not None:
        agent_name = _safe_segment(getattr(session.agent, "name", "agent"))
        for kind, label, root in roots:
            agent_dir = root / "agents" / str(agent_pk)
            candidates.append(
                {
                    "label": f"task ({label})",
                    "layer": "task",
                    "scope": kind,
                    "path": _task_dir(agent_dir, group_key) / filename,
                }
            )
            candidates.append(
                {
                    "label": f"agent {agent_name} ({label})",
                    "layer": "agent",
                    "scope": kind,
                    "path": agent_dir / filename,
                }
            )

    for kind, label, root in roots:
        candidates.append(
            {
                "label": label,
                "layer": "scope",
                "scope": kind,
                "path": root / filename,
            }
        )
    return candidates


def _playbook_module() -> Any:
    """Import the memory-manage schema module from the harness manifest.

    The schema lives with the memory-manage agent so the agent, its prompts and
    its validator ship together.  Runtime only needs the read path, so a small
    ``sys.path`` hop is cheaper than duplicating the schema (the same pattern
    the memory tests use).
    """
    return schema_module()


def schema_module() -> Any:
    """Return the ``playbook`` module that owns the memory file schemas."""
    try:
        import playbook as schema  # type: ignore[import-not-found]

        return schema
    except ImportError:
        pass

    candidate = (
        Path(__file__).resolve().parents[1]
        / ".agentone"
        / "agents"
        / "internal"
        / "memory-manage"
        / "scripts"
    )
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
    import playbook as schema  # noqa: E402  pylint: disable=import-outside-toplevel,import-error

    return schema


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _clip(text: Any, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) > limit:
        value = value[: max(0, limit - 1)].rstrip() + "…"
    return value


def collect(session: Any) -> list[dict[str, Any]]:
    """Return applicable, deduped, active directives for *session*.

    Each directive gains ``_source`` (the node label) and ``_layer`` so the
    rendering can group them.  Order is the resolution order above.
    """
    cfg = get_config(session)
    include_candidates = bool(cfg.get("includeCandidates"))
    schema = _playbook_module()

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidate_playbooks(session):
        path = candidate["path"]
        if not path.is_file():
            continue
        try:
            directives = schema.load_playbook(path)["directives"]
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning(
                "memory_playbook: skipping invalid playbook %s", path, exc_info=True
            )
            continue

        for directive in directives:
            status = directive.get("status")
            if status == "retired":
                continue
            if status == "candidate" and not include_candidates:
                continue
            if directive.get("routing") in _SKIP_ROUTING:
                continue
            fingerprint = str(directive.get("fingerprint") or "")
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            out.append(
                {
                    **directive,
                    "_source": candidate["label"],
                    "_layer": candidate["layer"],
                }
            )
    return out


def _directive_line(directive: dict[str, Any]) -> str:
    rule = _clip(directive.get("rule"), _MAX_RULE_CHARS)
    trigger = _clip(directive.get("trigger"), _MAX_TRIGGER_CHARS)
    capability = _clip(directive.get("capability"), 80)
    if trigger:
        line = f"- When {trigger}: {rule}"
    else:
        line = f"- {rule}"
    if capability:
        line += f" [use: {capability}]"
    return line


def _render_directive_lines(
    directives: list[dict[str, Any]], max_directives: int, max_chars: int
) -> tuple[list[str], int]:
    """Render grouped directive lines under the count/char caps.

    Returns ``(lines, omitted)``.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for directive in directives:
        grouped.setdefault(str(directive["_source"]), []).append(directive)

    lines: list[str] = []
    used = len(_HEADER)
    injected = 0
    omitted = 0
    for source, items in grouped.items():
        heading = f"\n**{source}**"
        for index, directive in enumerate(items):
            if injected >= max_directives:
                omitted += 1
                continue
            line = _directive_line(directive)
            if used + len(heading) + len(line) + 1 > max_chars:
                omitted += 1
                continue
            if not lines or lines[-1] != heading:
                if used + len(heading) + 1 > max_chars:
                    return lines, omitted + (len(items) - index)
                lines.append(heading)
                used += len(heading) + 1
            lines.append(line)
            used += len(line) + 1
            injected += 1
    return lines, omitted


def render(session: Any) -> str | None:
    """Return the advisory playbook message for *session* (or ``None``)."""
    cfg = get_config(session)
    if not cfg.get("enabled"):
        return None

    max_chars = max(0, int(cfg.get("maxChars") or 0))
    max_directives = max(0, int(cfg.get("maxDirectives") or 0))
    if max_chars <= 0 or max_directives <= 0:
        return None

    lines, omitted = _render_directive_lines(
        collect(session), max_directives, max_chars
    )
    skills = _skill_lines(session, cfg)
    if not lines and not skills:
        return None

    parts = [_HEADER]
    if lines:
        parts.extend(lines)
        if omitted:
            parts.append(
                f"(+{omitted} more directive(s) omitted to stay within the "
                "playbook budget.)"
            )
    if skills:
        parts.append("\n" + _SKILL_HEADER)
        parts.extend(skills)
    return "\n".join(parts)


def _skill_lines(session: Any, cfg: dict[str, Any]) -> list[str]:
    """Render the assigned-skill catalog (name + one-line description)."""
    if not cfg.get("includeSkills"):
        return []
    limit = max(0, int(cfg.get("maxSkills") or 0))
    if limit <= 0:
        return []
    try:
        names = sorted(session.allowedSkillNames or [])
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("memory_playbook: skill names unavailable", exc_info=True)
        return []

    lines: list[str] = []
    for name in names[:limit]:
        description = ""
        try:
            version = session.get_skill(name)
            description = _clip(getattr(version, "description", "") or "", _MAX_SKILL_DESC_CHARS)
        except Exception:  # pylint: disable=broad-exception-caught
            description = ""
        lines.append(f"- {name}" + (f" — {description}" if description else ""))
    if len(names) > limit:
        lines.append(f"(+{len(names) - limit} more assigned skill(s).)")
    return lines


def payload(session: Any) -> dict[str, Any]:
    """Return a diagnostic payload (used by tests and ``/debug``)."""
    cfg = get_config(session)
    candidates = [
        {
            "label": item["label"],
            "layer": item["layer"],
            "scope": item["scope"],
            "path": item["path"].as_posix(),
            "exists": item["path"].is_file(),
        }
        for item in candidate_playbooks(session)
    ]
    return {
        "enabled": bool(cfg.get("enabled")),
        "config": cfg,
        "candidates": candidates,
        "directives": [
            {k: v for k, v in directive.items() if not k.startswith("_")}
            | {"source": directive["_source"], "layer": directive["_layer"]}
            for directive in collect(session)
        ],
    }
