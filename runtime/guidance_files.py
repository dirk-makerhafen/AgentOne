"""AGENTS.md autoload + nested-file index/hint (spec: ``docs/agents-md.md`` §4).

Two paths, both read-only:

* **Path A (autoload):** per-agent ``autoload:`` patterns resolve against the
  session workspace once per session and are pinned as the first USER
  message(s). Re-resolved only on compaction / reset / workspace-switch
  (stale-until-compact).
* **Path B (index + hint):** nested guidance files are indexed (paths only)
  into a second USER message; touching a subtree appends a one-line hint to
  that tool call's result. The agent pulls contents itself via ``read``.

No DB writes here (cache only); any discovery/read error is a skip, never
an exception to the caller — callers log to ``DebugLogEntry``.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (spec §4.0 / §4.5)
# ---------------------------------------------------------------------------

AUTOLOAD_DEFAULT_FILES = ["AGENTS.md"]
AUTOLOAD_DEFAULT_MAX_FILES = 10
AUTOLOAD_DEFAULT_MAX_CHARS = 32768
AUTOLOAD_DEFAULT_MAX_CHARS_PER_FILE = 8192
INDEX_ENABLED_DEFAULT = True
INDEX_LIMIT_DEFAULT = 10

# Discovery filename set for the Path B index (module constant for later
# extension; exact, case-sensitive per N1).
DISCOVERY_FILENAMES = ("AGENTS.md", "CLAUDE.md")

# Directories never descended into during discovery/index scans.
_SKIP_DIR_NAMES = {".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv"}

# Django-cache keys (per session pk).
_CACHE_AUTOLOAD = "guidance:autoload:{pk}"
_CACHE_INDEX = "guidance:index:{pk}"
_CACHE_INDEXLIST = "guidance:indexlist:{pk}"
_CACHE_HINTED = "guidance:hinted:{pk}"
# Entries in the hinted-set carry a prefix: "d:" = touched directory (hint
# evaluated there), "f:" = guidance file already named in a hint or read
# explicitly. Bare pre-upgrade entries are treated as "d:" on load.
_HINTED_DIR_PREFIX = "d:"
_HINTED_FILE_PREFIX = "f:"
_CACHE_MARKER = "guidance:marker:{pk}"
_CACHE_WORKSPACE = "guidance:workspace:{pk}"


@dataclass
class GuidanceSection:
    """One autoloaded file ready for rendering."""

    relpath: str
    content: str
    truncated: bool = False


# ---------------------------------------------------------------------------
# Manifest validation (called by ``load_agent_manifest``; raises on invalid)
# ---------------------------------------------------------------------------


def _reject_escape(pattern: str, source: str) -> None:
    if pattern.startswith("/") or pattern.startswith("~"):
        raise ValueError(
            f"[{source}] autoload.files pattern {pattern!r} must be relative "
            "to the workspace root (no leading '/', no '~')"
        )
    if ".." in [seg for seg in pattern.strip().split("/") if seg]:
        raise ValueError(
            f"[{source}] autoload.files pattern {pattern!r} may not contain '..'"
        )


def validate_autoload_block(block: Any, source: str = "agent.md") -> dict[str, Any]:
    """Validate an agent.md ``autoload:`` block, returning normalized config.

    Raises :class:`ValueError` on any invalid shape. ``None`` is not valid
    here (the loader only calls this when the key is present).
    """
    if not isinstance(block, dict):
        raise ValueError(f"[{source}] autoload must be a mapping")
    if "index" in block:
        raise ValueError(
            f"[{source}] autoload.index was split out — use the standalone "
            "loadGuidanceFileIndex key instead"
        )
    known = {"files", "maxFiles", "maxChars", "maxCharsPerFile"}
    unknown = set(block) - known
    if unknown:
        raise ValueError(
            f"[{source}] autoload has unknown keys {sorted(unknown)} "
            f"(expected subset of {sorted(known)})"
        )
    files = block.get("files", list(AUTOLOAD_DEFAULT_FILES))
    if isinstance(files, str):
        files = [files]
    if not isinstance(files, (list, tuple)) or not all(
        isinstance(p, str) and p.strip() for p in files
    ):
        raise ValueError(
            f"[{source}] autoload.files must be a list of non-empty strings"
        )
    files = [p.strip() for p in files]
    for pattern in files:
        _reject_escape(pattern, source)
    out: dict[str, Any] = {"files": files}
    for key, camel in (
        ("maxFiles", "maxFiles"),
        ("maxChars", "maxChars"),
        ("maxCharsPerFile", "maxCharsPerFile"),
    ):
        _ = camel
        if block.get(key) is None:
            continue
        value = block[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"[{source}] autoload.{key} must be an integer >= 0, "
                f"got {value!r}"
            )
        out[key] = value
    return out


def get_autoload_config(session: Any) -> dict[str, Any]:
    """Return the effective autoload config for *session* with defaults."""
    raw = None
    try:
        raw = session._get_session_setting("autoload")
    except Exception:  # pylint: disable=broad-exception-caught
        raw = None
    cfg = dict(raw) if isinstance(raw, dict) else {}
    cfg.setdefault("files", list(AUTOLOAD_DEFAULT_FILES))
    cfg.setdefault("maxFiles", AUTOLOAD_DEFAULT_MAX_FILES)
    cfg.setdefault("maxChars", AUTOLOAD_DEFAULT_MAX_CHARS)
    cfg.setdefault("maxCharsPerFile", AUTOLOAD_DEFAULT_MAX_CHARS_PER_FILE)
    return cfg


def get_guidance_file_index_enabled(session: Any) -> bool:
    """Whether the nested guidance-file index is enabled (default True).

    Standalone setting (``loadGuidanceFileIndex``) — independent of the
    ``autoload:`` block. The index still excludes autoload-resolved paths
    so the two never duplicate each other.
    """
    try:
        value = session._get_session_setting("load_guidance_file_index")
    except Exception:  # pylint: disable=broad-exception-caught
        value = None
    if value is None:
        return INDEX_ENABLED_DEFAULT
    return bool(value)


def get_guidance_file_index_limit(session: Any) -> int:
    """Return the effective index count cap (default 10, 0 = omit index)."""
    try:
        value = session._get_session_setting("guidance_file_index_limit")
    except Exception:  # pylint: disable=broad-exception-caught
        value = None
    if value is None:
        return INDEX_LIMIT_DEFAULT
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return INDEX_LIMIT_DEFAULT


# ---------------------------------------------------------------------------
# Workspace root + policy helpers
# ---------------------------------------------------------------------------


def workspace_root(session: Any) -> Path | None:
    """Resolve the session workspace to an absolute ``Path`` (or ``None``)."""
    try:
        workspace = session.workspace
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    if workspace is None:
        return None
    path = getattr(workspace, "path", None)
    if not path:
        return None
    try:
        return Path(path).resolve()
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _is_readable(policy: Any, path: Path) -> bool:
    """True unless the resolved access policy denies a ``read`` of *path*."""
    try:
        from runtime.workspace_access import evaluate

        verdict = evaluate(policy, path.as_posix(), "read")
        if verdict.action == "deny":
            return False
        if verdict.action == "ask":
            logger.info("guidance: policy asks approval for %s (included)", path)
        return True
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("guidance: policy check failed for %s", path, exc_info=True)
        return False


def _contained(root: Path, candidate: Path) -> Path | None:
    """Resolve *candidate* and return it iff it stays inside *root*."""
    try:
        resolved = candidate.resolve()
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        logger.info("guidance: skipping symlink escape %s", candidate)
        return None
    return resolved


# ---------------------------------------------------------------------------
# Pattern matching (spec §4.0 — NOT access: semantics)
# ---------------------------------------------------------------------------


def _glob_to_regex(pattern: str) -> "re.Pattern[str]":
    """Translate an autoload glob to a regex over workspace-relative posix paths.

    ``*`` / ``?`` never cross ``/``; ``**`` crosses; a bare filename (no
    ``/``, no magic) is anchored to the workspace root by the caller.
    """
    i, n = 0, len(pattern)
    out = []
    while i < n:
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                if pattern[i : i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out) + r"\Z")


def _iter_files(root: Path) -> list[Path]:
    """All regular files under *root* (no dir-symlink descent, skip junk)."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIP_DIR_NAMES and not d.startswith(".")
        )
        for name in sorted(filenames):
            candidate = Path(dirpath) / name
            if candidate.is_symlink() or candidate.is_file():
                found.append(candidate)
    return found


def resolve_patterns(
    root: Path, patterns: list[str], policy: Any, max_files: int
) -> tuple[list[Path], int]:
    """Resolve autoload patterns in config order (spec §4.0/§4.1).

    Returns ``(paths, omitted)`` where *omitted* is the number of matches
    dropped by the ``max_files`` cap. Bare filenames match at the workspace
    root only; anything with ``/`` or glob magic matches against
    workspace-relative posix paths (``**/`` for recursion). Directories never
    match; policy-denied and escaping paths are skipped.
    """
    root = root.resolve()
    all_files = _iter_files(root)
    rel_of = {p: p.relative_to(root).as_posix() for p in all_files}
    seen: set[Path] = set()
    resolved: list[Path] = []
    total_matches = 0
    for pattern in patterns:
        matched: list[Path] = []
        if "/" not in pattern and not set("*?[") & set(pattern):
            candidate = root / pattern
            contained = _contained(root, candidate)
            if contained is not None and contained.is_file():
                matched = [contained]
        else:
            regex = _glob_to_regex(pattern)
            matched = [
                p for p in all_files if regex.match(rel_of[p]) is not None
            ]
            matched.sort(key=lambda p: (len(rel_of[p].split("/")), rel_of[p]))
        for candidate in matched:
            resolved_path = _contained(root, candidate)
            if resolved_path is None or not resolved_path.is_file():
                continue
            if resolved_path in seen:
                continue
            if not _is_readable(policy, resolved_path):
                continue
            seen.add(resolved_path)
            total_matches += 1
            if len(resolved) < max_files:
                resolved.append(resolved_path)
    omitted = total_matches - len(resolved)
    if omitted:
        logger.info(
            "guidance: maxFiles=%d cut %d autoload match(es)", max_files, omitted
        )
    return resolved, max(0, omitted)


def chain_for_directory(root: Path, target_dir: Path) -> list[Path]:
    """Ancestor guidance chain ``root/AGENTS.md … target_dir/AGENTS.md``.

    Only the ``AGENTS.md`` filename participates in the trigger chain (the
    index may additionally list ``CLAUDE.md`` for discovery). Present files
    only, shallow-first.
    """
    root = root.resolve()
    try:
        rel = target_dir.resolve().relative_to(root)
    except ValueError:
        return []
    chain: list[Path] = []
    for depth in range(len(rel.parts) + 1):
        candidate = root.joinpath(*rel.parts[:depth], "AGENTS.md")
        if candidate.is_file() and not candidate.is_symlink():
            chain.append(candidate)
        elif candidate.is_symlink():
            contained = _contained(root, candidate)
            if contained is not None and contained.is_file():
                chain.append(contained)
    return chain


# ---------------------------------------------------------------------------
# Loading + index
# ---------------------------------------------------------------------------


def load_sections(
    root: Path,
    paths: list[Path],
    max_chars: int,
    max_chars_per_file: int,
) -> list[GuidanceSection]:
    """Read *paths* under char budgets (spec §4.5).

    Per-file cap first, then fill the total cap in order (the overflowing
    file is cut to the remainder). ``max_chars=0`` disables contents.
    Failures skip the file; they never raise.
    """
    if max_chars <= 0:
        return []
    sections: list[GuidanceSection] = []
    remaining = max_chars
    for path in paths:
        if remaining <= 0:
            break
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("guidance: skipping unreadable %s", path, exc_info=True)
            continue
        total = len(text)
        if total > max_chars_per_file:
            text = text[:max_chars_per_file]
            text += (
                f"\n\n[truncated: showing first {max_chars_per_file} "
                f"of {total} chars]"
            )
        truncated = False
        if len(text) > remaining:
            keep = remaining
            text = text[:keep]
            text += "\n\n[truncated: file cut to fit the session autoload budget]"
            truncated = True
        elif total > max_chars_per_file:
            truncated = True
        remaining -= len(text)
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        sections.append(GuidanceSection(relpath=rel, content=text, truncated=truncated))
    return sections


def build_index(
    root: Path, policy: Any, exclude: set[str], limit: int
) -> tuple[list[str], int]:
    """Workspace guidance-file index minus autoloaded paths (spec §4.1/§4.3).

    Returns ``(relpaths, omitted)`` sorted shallow-first/lexicographically.
    Policy-denied files are omitted silently (never advertised).
    """
    root = root.resolve()
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIP_DIR_NAMES and not d.startswith(".")
        )
        for name in sorted(filenames):
            if name not in DISCOVERY_FILENAMES:
                continue
            candidate = Path(dirpath) / name
            contained = _contained(root, candidate)
            if contained is None or not contained.is_file():
                continue
            rel = contained.relative_to(root).as_posix()
            if rel in exclude:
                continue
            if not _is_readable(policy, contained):
                continue
            found.append(rel)
    found.sort(key=lambda r: (len(r.split("/")), r))
    if limit <= 0:
        return [], len(found)
    return found[:limit], max(0, len(found) - limit)


# ---------------------------------------------------------------------------
# Rendering (spec §4.3 — TEXT, never TEMPLATE)
# ---------------------------------------------------------------------------

_AUTOLOAD_HEADER = (
    "[Auto-loaded workspace files — advisory guidance for this session; "
    "they do not change your available tools or permissions.]"
)

_INDEX_INTRO = (
    "[Workspace guidance files: the files below may contain conventions, "
    "commands, and constraints relevant to work in their directories. Read "
    "the ones relevant to your current task before acting in their subtrees; "
    "deeper files take precedence over their parents on conflict."
)
_INDEX_INTRO_AUTOLOADED = (
    " (Workspace files already included in full above are not listed — "
    "no need to re-read them.)]"
)


def render_autoload_message(sections: list[GuidanceSection]) -> str | None:
    """Combine autoloaded sections into one USER message (None when empty)."""
    if not sections:
        return None
    parts = [_AUTOLOAD_HEADER]
    for section in sections:
        parts.append(f"\n## {section.relpath}\n{section.content}")
    return "\n".join(parts)


def render_index_message(
    relpaths: list[str], omitted: int, has_autoload: bool = True
) -> str | None:
    """Render the guidance-file index message (None when empty)."""
    if not relpaths and not omitted:
        return None
    intro = _INDEX_INTRO + (_INDEX_INTRO_AUTOLOADED if has_autoload else "]")
    lines = [intro] + [f"- {rel}" for rel in relpaths]
    if omitted:
        lines.append(
            f"(+{omitted} more — use glob **/{{AGENTS.md,CLAUDE.md}} "
            "to discover further)"
        )
    return "\n".join(lines)


def hint_line(relpath: str) -> str:
    """One-line touch hint for a guidance file (spec §4.3)."""
    return (
        f"[Note: {relpath} covers this directory — read it before "
        "continuing work here if you have not already.]"
    )


# ---------------------------------------------------------------------------
# Pin / repin (spec §4.4 — pin at session start, repin at compaction)
# ---------------------------------------------------------------------------


def _cache() -> Any:
    from django.core.cache import cache

    return cache


def clear_guidance_cache(session_pk: Any) -> None:
    """Drop all pinned AGENTS.md state for a session."""
    cache = _cache()
    for template in (
        _CACHE_AUTOLOAD,
        _CACHE_INDEX,
        _CACHE_INDEXLIST,
        _CACHE_HINTED,
        _CACHE_MARKER,
        _CACHE_WORKSPACE,
    ):
        try:
            cache.delete(template.format(pk=session_pk))
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("guidance: cache delete failed", exc_info=True)


def _latest_compaction_marker_pk(session_pk: Any) -> int | None:
    from server.models.enums.message_enums import MessagePartType
    from server.models.message import Message

    marker = (
        Message.objects.filter(session_id=session_pk, parts__type=MessagePartType.COMPACTION)
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    )
    return marker


def ensure_pinned(session: Any) -> tuple[str | None, str | None]:
    """Return pinned ``(autoload_text, index_text)`` for *session*.

    First call resolves + renders + caches; later turns reuse the bytes
    verbatim. Re-resolves when the compaction marker advanced or the
    workspace path changed (repin on compaction / workspace-switch).
    Never raises — failures yield ``(None, None)``.
    """
    try:
        return _ensure_pinned(session)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("guidance: pin failed, skipping", exc_info=True)
        return None, None


def _ensure_pinned(session: Any) -> tuple[str | None, str | None]:
    from runtime.workspace_access import resolve_policy

    root = workspace_root(session)
    if root is None:
        return None, None
    session_pk = session.model.pk
    cache = _cache()
    marker = _latest_compaction_marker_pk(session_pk)
    cached_marker = cache.get(_CACHE_MARKER.format(pk=session_pk))
    cached_workspace = cache.get(_CACHE_WORKSPACE.format(pk=session_pk))
    autoload_text = cache.get(_CACHE_AUTOLOAD.format(pk=session_pk))
    index_text = cache.get(_CACHE_INDEX.format(pk=session_pk))
    if (
        cached_marker == marker
        and cached_workspace == root.as_posix()
        and (autoload_text is not None or index_text is not None
             or cache.get(_CACHE_INDEXLIST.format(pk=session_pk)) is not None)
    ):
        return autoload_text, index_text

    cfg = get_autoload_config(session)
    policy = resolve_policy(session)
    paths, _ = resolve_patterns(root, cfg["files"], policy, cfg["maxFiles"])
    sections = load_sections(root, paths, cfg["maxChars"], cfg["maxCharsPerFile"])
    autoload_text = render_autoload_message(sections)
    # Exclude exactly what is pinned — resolved-but-capped or unloadable
    # files are NOT in context, so the index may still advertise them.
    exclude = {s.relpath for s in sections}
    index_text: str | None = None
    index_list: list[str] = []
    omitted = 0
    if get_guidance_file_index_enabled(session):
        limit = get_guidance_file_index_limit(session)
        index_list, omitted = build_index(root, policy, exclude, limit)
        index_text = render_index_message(
            index_list, omitted, has_autoload=autoload_text is not None
        )
    cache.set(_CACHE_AUTOLOAD.format(pk=session_pk), autoload_text)
    cache.set(_CACHE_INDEX.format(pk=session_pk), index_text)
    cache.set(_CACHE_INDEXLIST.format(pk=session_pk), index_list)
    cache.set(_CACHE_MARKER.format(pk=session_pk), marker)
    cache.set(_CACHE_WORKSPACE.format(pk=session_pk), root.as_posix())
    return autoload_text, index_text


def _cached_index_set(session_pk: Any) -> set[str] | None:
    try:
        cached = _cache().get(_CACHE_INDEXLIST.format(pk=session_pk))
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    return set(cached) if isinstance(cached, list) else None


def hint_for_call(
    session: Any, task_name: str, posture: str | None, call_args: dict[str, Any]
) -> str | None:
    """Compute a Path B touch hint for a successful tool call (spec §4.3/§4.4).

    Returns the hint line (or ``None``). Updates the hinted-set. Never raises.
    """
    try:
        return _hint_for_call(session, task_name, posture, call_args)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("guidance: hint hook failed", exc_info=True)
        return None


def _hint_for_call(
    session: Any, task_name: str, posture: str | None, call_args: dict[str, Any]
) -> str | None:
    from runtime.workspace_access import extract_path_args

    if posture not in ("read", "write"):
        return None
    pairs = extract_path_args(task_name, posture, call_args)
    if not pairs:
        return None
    root = workspace_root(session)
    if root is None:
        return None
    session_pk = session.model.pk
    indexed = _cached_index_set(session_pk)
    if indexed is None:
        ensure_pinned(session)
        indexed = _cached_index_set(session_pk) or set()
    if not indexed:
        return None
    cache = _cache()
    raw_hinted = cache.get(_CACHE_HINTED.format(pk=session_pk)) or []
    hinted_set: set[str] = set()
    if isinstance(raw_hinted, list):
        for entry in raw_hinted:
            if not isinstance(entry, str):
                continue
            if entry.startswith((_HINTED_DIR_PREFIX, _HINTED_FILE_PREFIX)):
                hinted_set.add(entry)
            else:
                hinted_set.add(f"{_HINTED_DIR_PREFIX}{entry}")
    hints: list[str] = []
    changed = False
    for raw_path, _action in pairs:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        contained = _contained(root, candidate)
        if contained is None:
            continue
        if contained.name in DISCOVERY_FILENAMES:
            # Explicit guidance read: content is already in context —
            # suppress the hint and mark file + directory hinted.
            file_rel = contained.relative_to(root).as_posix()
            parent_rel = contained.parent.relative_to(root).as_posix()
            for key in (
                f"{_HINTED_FILE_PREFIX}{file_rel}",
                f"{_HINTED_DIR_PREFIX}{parent_rel}",
            ):
                if key not in hinted_set:
                    hinted_set.add(key)
                    changed = True
            continue
        if contained.is_dir():
            touched = contained
        else:
            touched = contained.parent
        try:
            touched_rel = touched.relative_to(root).as_posix()
        except ValueError:
            continue
        if touched_rel == ".":
            touched_rel = ""
        dir_key = f"{_HINTED_DIR_PREFIX}{touched_rel}"
        if dir_key in hinted_set:
            continue
        hinted_set.add(dir_key)
        changed = True
        chain = chain_for_directory(root, touched)
        candidates = []
        for chain_path in chain:
            rel = chain_path.resolve().relative_to(root).as_posix()
            if rel in indexed and f"{_HINTED_FILE_PREFIX}{rel}" not in hinted_set:
                candidates.append(rel)
        if not candidates:
            continue
        hinted_set.add(f"{_HINTED_FILE_PREFIX}{candidates[-1]}")
        hints.append(hint_line(candidates[-1]))
    if changed:
        try:
            cache.set(_CACHE_HINTED.format(pk=session_pk), sorted(hinted_set))
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("guidance: hinted-set store failed", exc_info=True)
    return "\n".join(hints) if hints else None
