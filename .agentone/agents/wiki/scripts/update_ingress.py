"""Generic ingress queue maintenance for wiki folders.

Any folder can declare an ``ingress.md`` file:

```yaml
---
type: ingress
sources: ["timeline/**/*.md", "entities/**/*.md"]  # vault-relative globs (required)
exclude: ["timeline/**/index.md"]                   # vault-relative globs (optional)
include_tags: [workshop, buchung]                   # queue only files carrying one of these tags (optional)
exclude_tags: [werbung]                             # frontmatter tags to drop (optional)
last_checked_at: <git HEAD the queue was computed against>
updated: YYYY-MM-DD
---
<queue: `- [ ]` pending / `- [x]` done lines, one vault-relative path each;
gone files carry ` (deleted)`; metadata rides in trailing comments>
```

Queue line format (code-owned; consumers only read, never edit):

```text
- [ ] timeline/2022/12/23/....md <!-- queued 2026-10-11 @ 3e9b405d -->
- [x] timeline/2022/12/22/....md <!-- queued 2026-10-09 @ b64b6a76 | done 2026-10-11 -->
```

Legacy bare-path lines are accepted as pending and normalized on write.
`history_days:` (default 90, `0` keeps forever) drops done lines older than
that — the file stays bounded without agent discipline.

Tag selection (both optional, case-insensitive, applied at selection time —
fresh files only, never evicting queued lines; gone files always stay queued
as `(deleted)` for the consumer to judge):

- ``include_tags:`` — when present, only files carrying at least one of these
  frontmatter tags are queued.
- ``exclude_tags:`` — files carrying any of these tags are dropped (checked first).

``update_ingress(session, ingress="<folder>/ingress.md")`` refreshes the
queue: the changed files between the stored ``last_checked_at`` hash and the
current HEAD (``git diff``, committed state only), filtered to the
``sources`` globs minus ``exclude`` globs and the tag selection above. Matches not already queued are appended; existing lines
are unfinished work and are kept as-is; lines the consumer deleted are
finished — they stay gone, because the base hash slides forward past them
(a file changed AGAIN later reappears through a newer window, which is
genuine news). First run (or dead git) falls back to a full glob expansion
— everything matching is new. The ingress file is the only state: no
sidecars, no memory files. Pure code, no LLM sessions.
"""

from __future__ import annotations

import datetime
import fcntl
import fnmatch
import subprocess
import sys
from pathlib import Path, PurePosixPath

from runtime.session.session import Session

sys.path.insert(0, Path(__file__).resolve().parent.as_posix())
from update_timeline_daily import (  # noqa: E402
    _fm_list_values,
    _git_head,
    _parse_frontmatter,
    _workspace_root,
)

DELETED_SUFFIX = " (deleted)"
NO_GIT_BASE = "unknown (no git — full scan)"
UNBORN_BASE = "unborn (no commits yet — full scan)"
CHECK_PENDING = "- [ ] "
CHECK_DONE = "- [x] "
DEFAULT_HISTORY_DAYS = 90

import re as _re


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _re.fullmatch(r"[0-9a-f]{40}", value) is not None


# ---------------------------------------------------------------------------
# Pure helpers (testable without a session)
# ---------------------------------------------------------------------------

def _parse_queue_line(line: str) -> tuple[str | None, bool, bool, dict]:
    """(rel, done, deleted, meta) from a queue body line.

    Accepts `- [ ]`/`- [x]` lines with trailing `<!-- ... -->` metadata
    (`queued DATE [@ HEAD]`, `| done DATE`, `| active TIMESTAMP`) and legacy
    bare-path lines (pending, no metadata). Blank lines → (None, ...).
    """
    s = line.strip()
    if not s:
        return None, False, False, {}
    done = False
    if s.startswith(CHECK_DONE):
        done = True
        s = s[len(CHECK_DONE):]
    elif s.startswith(CHECK_PENDING):
        s = s[len(CHECK_PENDING):]
    comment = ""
    m = _re.search(r"<!--(.*?)-->\s*$", s)
    if m:
        comment = m.group(1)
        s = s[:m.start()].strip()
    deleted = False
    if s.endswith(DELETED_SUFFIX):
        deleted = True
        s = s[:-len(DELETED_SUFFIX)].strip()
    meta: dict = {}
    for part in comment.split("|"):
        part = part.strip()
        mm = _re.match(r"queued\s+(\S+)(?:\s+@\s+(\S+))?", part)
        if mm:
            meta["queued"] = mm.group(1)
            meta["head"] = mm.group(2) or ""
            continue
        mm = _re.match(r"done\s+(\S+)", part)
        if mm:
            meta["done"] = mm.group(1)
            continue
        mm = _re.match(r"active\s+(\S+)", part)
        if mm:
            try:
                meta["active"] = int(mm.group(1))
            except (TypeError, ValueError):
                pass
    return (s or None), done, deleted, meta


def _format_queue_line(rel: str, done: bool, deleted: bool, meta: dict,
                       today: str, head: str | None) -> str:
    """Canonical queue line (fills missing queued/done stamps, preserves rest)."""
    meta = dict(meta)
    if not done and "queued" not in meta:
        meta["queued"] = today
        meta["head"] = (head or "")[:8]
    if done and "done" not in meta:
        meta["done"] = today
        meta.pop("active", None)
    parts = []
    if "queued" in meta:
        queued = f"queued {meta['queued']}"
        if meta.get("head"):
            queued += f" @ {meta['head']}"
        parts.append(queued)
    if meta.get("active") is not None and not done:
        parts.append(f"active {meta['active']}")
    if meta.get("done"):
        parts.append(f"done {meta['done']}")
    comment = f" <!-- {' | '.join(parts)} -->" if parts else ""
    marker = CHECK_DONE if done else CHECK_PENDING
    gone = DELETED_SUFFIX if deleted and not done else ""
    return f"{marker}{rel}{gone}{comment}"


def _history_days(fm: dict) -> int:
    """Done-line retention window (`history_days:`, default 90, <=0 forever)."""
    try:
        return int(fm.get("history_days", DEFAULT_HISTORY_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_HISTORY_DAYS


def _done_expired(done_date: str, today: str, days: int) -> bool:
    """True when a done line is older than the retention window (keep on doubt)."""
    if days <= 0:
        return False
    try:
        done = datetime.date.fromisoformat(done_date)
        now = datetime.date.fromisoformat(today)
    except ValueError:
        return False
    return (now - done).days > days


def _pattern_variants(pattern: str) -> list[str]:
    """Match variants covering ``**`` zero-or-more-dir quirks across matchers."""
    variants = [pattern]
    if "**/" in pattern:
        variants.append(pattern.replace("**/", ""))
    if "**" in pattern:
        variants.append(pattern.replace("**", "*"))
    return variants


def _matches_any(rel: str, patterns: list[str]) -> bool:
    """True when vault-relative *rel* matches any glob in *patterns*."""
    posix = PurePosixPath(rel)
    for pat in patterns:
        for variant in _pattern_variants(pat):
            try:
                if posix.match(variant):
                    return True
            except Exception:
                pass
            if fnmatch.fnmatchcase(rel, variant):
                return True
    return False


def _git_names(args: list[str], root: Path, timeout: int = 30) -> list[str] | None:
    """NUL-separated git path output, or None when git cannot tell."""
    try:
        out = subprocess.run(
            ["git", "-C", root.as_posix(), "-c", "core.quotepath=false", *args],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return [p for p in out.stdout.split("\0") if p]


def _git_alive(root: Path) -> bool:
    """True when *root* sits inside a git work tree."""
    try:
        out = subprocess.run(
            ["git", "-C", root.as_posix(), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return False
    return out.returncode == 0


def _full_expansion(root: Path, sources: list[str]) -> list[str]:
    """Every vault file matching the sources globs (first run / no git)."""
    found: set[str] = set()
    for pat in sources:
        try:
            for p in root.glob(pat):
                if p.is_file():
                    found.add(p.relative_to(root).as_posix())
        except Exception:
            continue
    return sorted(found)


def _fresh_since(root: Path, base_hash: str) -> tuple[list[str] | None, list[str]]:
    """Changed/removed vault paths committed after *base_hash* (or None).

    Plain ``git diff <base> --name-only`` with ``--no-renames`` (a renamed
    file surfaces as removed + added, so the old name is never silently
    dropped). Committed state only: uncommitted worktree files are invisible
    until committed — this is what lets finished lines stay finished with
    no memory files. None when git cannot diff (history rewritten, bad
    hash) — the caller falls back to a full expansion, which is always
    correct.
    """
    diff = _git_names(
        ["diff", "--no-renames", "--name-only", "-z", base_hash, "--"], root)
    if diff is None:
        return None, []
    changed, removed = [], []
    for path in sorted(set(diff)):
        if (root / path).exists():
            changed.append(path)
        else:
            removed.append(path)
    return changed, removed


def _read_frontmatter(path: Path) -> dict:
    """Parsed frontmatter of a file ({} when unreadable or absent)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        fm, _body, _error = _parse_frontmatter(text)
    except Exception:
        return {}
    return fm if isinstance(fm, dict) else {}


def _read_tags(path: Path) -> set[str]:
    """Frontmatter `tags` of a file (empty set when unreadable)."""
    fm = _read_frontmatter(path)
    return {t.strip().lower() for t in _fm_list_values(fm, "tags") if t.strip()}


def _tag_set(fm: dict, field: str) -> set[str]:
    """Lowercased tag set for *field* (empty when absent).

    Accepts list or scalar form — `include_tags: workshop` must constrain
    exactly like `include_tags: [workshop]`; silently treating a scalar as
    "no constraint" would match everything.
    """
    values = fm.get(field)
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return set()
    return {str(v).strip().lower() for v in values if str(v).strip()}


def _yaml_scalar(value: object) -> str:
    """Minimal YAML scalar emission (quotes only when needed)."""
    if value is None:
        return ""
    text = str(value)
    if (text == "" or any(c in text for c in ":#\"'[]{}&*?|<>=!%@`,\n")
            or text != text.strip() or text.lower() in ("true", "false", "null")):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _dump_value(value: object) -> str:
    """Flow-style YAML emission for scalar / list / one-level mapping."""
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {_dump_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_scalar(v) for v in value) + "]"
    return _yaml_scalar(value)


def _dump_frontmatter(fm: dict) -> str:
    """Ordered frontmatter emission (known keys first, extras preserved)."""
    order = ["type", "sources", "exclude", "include_tags", "exclude_tags",
             "last_checked_at", "updated"]
    lines = []
    for key in order + [k for k in fm if k not in order]:
        if key not in fm:
            continue
        lines.append(f"{key}: {_dump_value(fm[key])}")
    return "---\n" + "\n".join(lines) + "\n---\n"


def refresh_ingress(root: Path, ingress_rel: str) -> tuple[bool, dict]:
    """Recompute the queue of an ingress file; pure logic, no session.

    Returns (ok, info); on success the file, its frontmatter
    (``last_checked_at``/``updated``) and sidecars are written.
    """
    ingress_file = root / ingress_rel
    if not ingress_file.is_file():
        return False, {"status": "error", "message": f"ingress file not found: {ingress_rel}"}
    try:
        text = ingress_file.read_text(encoding="utf-8")
    except Exception as e:
        return False, {"status": "error", "message": f"cannot read {ingress_rel}: {e}"}
    try:
        fm, _body, error = _parse_frontmatter(text)
    except Exception as e:
        return False, {"status": "error", "message": f"cannot parse {ingress_rel}: {e}"}
    if error or not isinstance(fm, dict):
        return False, {"status": "error", "message": f"bad frontmatter in {ingress_rel}: {error}"}
    sources = [s for s in _fm_list_values(fm, "sources") if s]
    if not sources:
        return False, {"status": "error",
                       "message": f"{ingress_rel}: `sources:` must list at least one vault-relative glob"}
    exclude = [s for s in _fm_list_values(fm, "exclude") if s]

    # Current file content = unfinished work; done lines are history.
    today = datetime.datetime.now().date().isoformat()
    pending_meta: dict[str, tuple[bool, dict]] = {}
    done_entries: list[tuple[str, bool, dict]] = []
    for raw in text.split("---", 2)[-1].splitlines():
        rel, done, deleted, meta = _parse_queue_line(raw)
        if rel is None:
            continue
        if done:
            done_entries.append((rel, deleted, meta))
        elif rel not in pending_meta:
            pending_meta[rel] = (deleted, meta)
    current = sorted(pending_meta)

    base = fm.get("last_checked_at")
    if not _is_hash(base):
        base = None
    head = _git_head(root)
    git_alive = _git_alive(root)

    # Fresh candidates: the diff window (base..HEAD, committed state only),
    # or a full expansion on first run / dead git / undiffable base.
    fresh_all: list[str] = []
    removed: list[str] = []
    full_scan = False
    base_label: str | None = head
    if not git_alive:
        full_scan = True
        base_label = NO_GIT_BASE
        fresh_all = _full_expansion(root, sources)
    elif base is None:
        # First run: everything matching is new; the current HEAD (when
        # born) becomes the diff base going forward.
        full_scan = True
        if head is None:
            base_label = UNBORN_BASE
        fresh_all = _full_expansion(root, sources)
    else:
        changed, removed_git = _fresh_since(root, base)
        if changed is None:
            full_scan = True
            fresh_all = _full_expansion(root, sources)
        else:
            fresh_all = changed
            removed = removed_git

    # The ingress file itself is working state, never a queue item.
    # On full expansions (no diff window) finished rels are excluded too —
    # without a window there is no other way to keep them finished. On the
    # diff path they stay eligible: a newer commit re-reporting a done file
    # is treated as potential news (the consumer judges substance).
    done_rels = {rel for rel, _deleted, _meta in done_entries}
    candidates = [r for r in fresh_all + removed
                  if _matches_any(r, sources) and not _matches_any(r, exclude)
                  and r != ingress_rel
                  and (not full_scan or r not in done_rels)]
    include_tags = _tag_set(fm, "include_tags")
    exclude_tags = _tag_set(fm, "exclude_tags")
    if include_tags or exclude_tags:
        kept = []
        for rel in candidates:
            if not (root / rel).is_file():
                kept.append(rel)  # gone files stay queued as `(deleted)`
                continue
            tags = _read_tags(root / rel)
            if tags & exclude_tags:
                continue
            if include_tags and not (tags & include_tags):
                continue
            kept.append(rel)
        candidates = kept

    # The queue is unfinished work plus fresh matches (deduped). Deleted
    # lines are finished: the base slides forward past them, so they stay
    # gone unless a later window re-reports the file (genuine news).
    merged = sorted(set(current) | set(candidates))
    queue_lines = []
    for rel in merged:
        if rel in pending_meta:
            stored_deleted, meta = pending_meta[rel]
            # Re-evaluate existence: a carried line whose file vanished earns the marker.
            deleted = stored_deleted or not (root / rel).exists()
        else:
            deleted, meta = (not (root / rel).exists()), {}
        queue_lines.append(_format_queue_line(rel, False, deleted, meta, today, head))
    # Done history, compacted by retention window.
    days = _history_days(fm)
    kept_done = 0
    for rel, _deleted, meta in sorted(done_entries):
        if _done_expired(meta.get("done", ""), today, days):
            continue
        kept_done += 1
        queue_lines.append(_format_queue_line(rel, True, False, meta, today, head))

    fm["last_checked_at"] = base_label if base_label else NO_GIT_BASE
    fm["updated"] = today
    try:
        # Exclusive lock: concurrent finalize tasks flip lines in this file.
        with open(ingress_file, "w", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.write(_dump_frontmatter(fm) + "\n" + "\n".join(queue_lines)
                     + ("\n" if queue_lines else ""))
    except Exception as e:
        return False, {"status": "error", "message": f"cannot write {ingress_rel}: {e}"}
    return True, {"status": "success", "ingress": ingress_rel,
                  "queued": len(merged), "fresh": len(candidates),
                  "marked_deleted": sum(1 for r in merged if not (root / r).exists()),
                  "done_kept": kept_done,
                  "full_scan": full_scan,
                  "head": base_label if base_label else NO_GIT_BASE}


def update_ingress(_session: Session, ingress: str) -> tuple[bool, dict]:
    """Refresh a folder's ingress work queue so you can process new files.

    Use this when a folder tracks incoming files with an `ingress.md`
    (e.g. calendar syncing timeline summaries). It figures out which source
    files changed since the last pass and updates the queue for you.

    Workflow:
    1. Create `<folder>/ingress.md` once, with frontmatter declaring what
       to watch:
       `sources:` (required, vault-relative globs like `timeline/**/*.md`),
       `exclude:` (optional globs), `include_tags:` (optional — queue only
       files carrying one of these frontmatter tags), `exclude_tags:`
       (optional tags to skip, e.g. `[werbung]`).
       Leave `last_checked_at:` empty; the tool fills it.
    2. Call `update_ingress` with the vault-relative path (`calendar/ingress.md`).
    3. Work the body queue with `process_ingress` (it checks lines off in
       code), or top to bottom by hand. A ` (deleted)` suffix means the
       source file is gone: check whether its entry still stands instead
       of silently keeping it. Never hand-edit queue lines or the hash.
    4. Re-run any time: unfinished lines are kept, files changed since the
       stored hash are appended (unless already queued), finished lines
       stay finished — the hash slides forward past them. A file changed
       AGAIN later correctly returns through a newer window. When only
       frontmatter is left, the pass is complete — store the returned
       `head` as `last_checked_at:`.

    The queue reflects committed state: uncommitted files appear on the
    first run's full expansion, afterwards only once committed — commit
    sources to pick them up.

    Returns (True, {status, ingress, queued, fresh,
    marked_deleted, full_scan, head}). `full_scan` means the queue was built
    from a full glob expansion (first run, or git unavailable) rather than
    a git diff — work it exactly the same way.
    """
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "message": "cannot resolve workspace root"}
    rel = ingress.strip().strip("/")
    candidate = root / rel
    if not candidate.is_file():
        return False, {"status": "error", "message": f"ingress file not found: {ingress}"}
    try:
        rel = candidate.relative_to(root).as_posix()
    except Exception:
        return False, {"status": "error", "message": f"ingress file outside workspace: {ingress}"}
    return refresh_ingress(root, rel)
