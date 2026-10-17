

from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path

from runtime.session.session import Session


# Pipeline: update_timeline_daily finds stale day folders via git history, then
# per stale day fans out reads that converge in write_day_index (code owns
# the file — the scheduler delivers it once every result-ref resolves):
# - one baseagent prose session (same spawn mechanics as double_check_summary
#   in update_timeline.py) that reads the folder itself — frontmatter lists
#   are cheap, marketing bodies can be skipped — and returns ONLY the body
#   markdown via final_result. It writes nothing.
# - one tiny llm_query per metadata field (tags/persons/companies/groups/products)
#   whose input is ONLY that field's code-collected item list.
# write_day_index validates the body, applies the dedup pairs to the day's
# summary files in code, assembles frontmatter + body + code-built catalog
# into timeline/YYYY/MM/DD/index.md, and spawns a fire-and-forget
# double-check session on the result. Code owns metadata and the file, the
# sessions own prose judgment.
#
# Staleness: index.md carries ``sources_fingerprint`` (sha1 over the day's
# summary names + full texts) plus ``last_checked_at`` (vault HEAD at
# dispatch, provenance only). A day is stale when its index is missing,
# legacy, unfingerprinted, or the live sources differ from the recorded
# fingerprint — new/edited/removed summaries, committed or not. Committing
# the index itself never changes the fingerprint, so rebuilding is
# self-terminating by construction (the old commit-time comparison looped:
# every rebuild recorded a hash that the subsequent index commit postdated).

DAY_FIELDS = ("tags", "persons", "companies", "groups", "products")
FRONTMATTER_RE = re.compile(r"\A\s*(?:\ufeff)?---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

DEDUP_FIELD_PROMPT = '''Deduplicate a list of {field} if needed, otherwise output exactly `none`. The items in the list below were created
independently by different language models, so the same {field_singular} may appear under different names
or spellings (e.g. `Luna Jeschke` vs `L. Jeschke`, `Müller` vs `Mueller`,
`PayPal` vs `paypal`, `3D-Druck` vs `3d-druck`). 
This is a simple task, and has no tricks or hidden meaning, no need to think about that for long, if you see no duplications, its good, output exactly `none`. 

The complete `{field}` list for {day_str} ({count} items):

```
{items}
```

If duplications exists, output ONLY deduplication lines, one per duplicate variant — no bullets, no code fences, no explanations. If no duplications exist, output exactly one line containing only `none` (this tells code "checked, nothing found", as opposed to an empty response, which means the query failed):

```
<canonical item>, <duplicate variant>
```

`<canonical item>` is the form to keep — prefer the most complete and most
common spelling. `<duplicate variant>` is ONE other spelling from the list
above that means the SAME {field_singular} (repeat the line per variant).
Only list variants that actually occur in the list above. Never invent items,
never merge two genuinely different {field_plural}. A lone `none` line means
no duplicates — output it (and nothing else) instead of an empty response.
Lines are parsed by code (first comma separates), so be precise.
'''

_FIELD_SINGULAR = {"tags": "tag", "persons": "person", "companies": "company", "groups": "group", "products": "product"}
_FIELD_PLURAL = {"tags": "tags", "persons": "persons", "companies": "companies", "groups": "groups", "products": "products"}


def _build_day_session_brief(day_rel: str, day_str: str, summary_files: list[str]) -> str:
    """Assemble the work order for a day-summary subagent session.

    The session returns ONLY the body markdown via final_result and writes
    nothing — frontmatter, catalog, and the index file itself are built by
    code. Metadata lists and spelling variants are handled by a separate
    code pass, so the session ignores them beyond reading.
    """
    listing = "\n".join(f"- {name}" for name in summary_files) if summary_files else "- (no summary files yet)"
    return f"""Synthesize the timeline day {day_str} from its per-mail summaries.

Your working dir is the vault root; all paths below are vault-relative.
The day folder is `{day_rel}` and currently holds:

{listing}

Read the day's summaries — frontmatter lists are cheap, read them all, and
read the bodies you need for a good synthesis. Skip marketing / `werbung`
bodies (one glance at the title usually suffices for those).

Synthesize, don't concatenate: key events of the day, important numbers
(amounts, donations, totals, deadlines), decisions and outcomes, short quotes
when the exact wording matters. Bullets by default. If there is nothing
substantial, say so in one line instead of inventing importance.

Return EXACTLY the body markdown below as your LAST message — no frontmatter
(it is built by code), no code fences, no explanations, write NO files, and
output NOTHING after it (a separate code pass reads your last message and
stores it as the day's summary; it cannot see anything else you write):

```markdown
# Summary for {day_str}

<Key events, important numbers, decisions, quotes for the day.>
```

The heading MUST be exactly `# Summary for {day_str}`.
"""


def _build_day_update_brief(day_rel: str, day_str: str, all_files: list[str], changed: set[str], removed: list[str]) -> str:
    """Assemble the work order for revising an existing day index.

    The day already has a ``daily_summary`` index: the session reads its
    current body plus ONLY the changed files (not the whole folder) and
    returns the full revised synthesis. Frontmatter, catalog, and the file
    itself stay code-built, exactly like the fresh-build brief.
    """
    lines = []
    for name in all_files:
        if name in changed:
            lines.append(f"- {name} (CHANGED since last build — re-read fully)")
        else:
            lines.append(f"- {name}")
    listing = "\n".join(lines) if lines else "- (no summary files)"
    removed_block = "\n".join(f"- {name}" for name in removed) if removed else "- (none)"
    return f"""Revise the timeline day {day_str} index from its changed files.

Your working dir is the vault root; all paths below are vault-relative.
The day folder is `{day_rel}`. An `index.md` with a previous synthesis
already exists — this is an UPDATE, not a fresh build.

Start by reading the current `{day_rel}/index.md` body and keep whatever
still holds. Then read the changed files below in full (frontmatter lists
are cheap; bodies in full unless obviously marketing / `werbung`, which
needs only a glance at the title). The unchanged files are already
reflected in the current body — do NOT re-read their bodies unless a
changed file references them. Changes may be frontmatter-only spelling
normalizations (unified tags/persons) — where the substance is unchanged,
keep the existing text as is.

Changed files:

{listing}

Removed since the last build (their content must no longer appear in the synthesis):

{removed_block}

Return EXACTLY the full revised body markdown below as your LAST message —
no frontmatter (it is built by code), no code fences, no explanations,
write NO files, and output NOTHING after it (a separate code pass reads
your last message and stores it as the day's summary; it cannot see
anything else you write):

```markdown
# Summary for {day_str}

<Key events, important numbers, decisions, quotes for the day.>
```

The heading MUST be exactly `# Summary for {day_str}`.
"""


def _build_day_check_brief(day_rel: str, day_str: str, summary_files: list[str], lint_hints: list[str]) -> str:
    """Assemble the work order for a day-index double-check session."""
    listing = "\n".join(f"- {name}" for name in summary_files) if summary_files else "- (no summary files)"
    hints_block = "\n".join(f"- {hint}" for hint in lint_hints) if lint_hints else "- (no code hints — still verify facts, numbers, and cross-references)"
    return f"""Double-check the daily index file `{day_rel}/index.md` for {day_str}.

Your working dir is the vault root; all paths below are vault-relative.
The day folder holds:

{listing}

## Expected file format (authoritative — do NOT read other index files for reference)

`{day_rel}/index.md` MUST have exactly this shape:

```markdown
---
type: daily_summary
updated: YYYY-MM-DD                # today's date
last_checked_at: <40-hex git hash> # provenance only — never hand-edit
sources_fingerprint: <40-hex sha>  # provenance only — never hand-edit
tags: [tag1, tag2]                 # flow-style YAML lists, canonical spellings
persons: [Name One, Name Two]
companies: [Company]
groups: [Club, Crew]               # clubs/associations/crews/teams — neither person nor commercial company
products: []
---

# Summary for {day_str}            # exact heading, then bullet synthesis

<key events, important numbers, decisions, quotes>

## Einträge                        # one bullet per summary file in the folder

- [[{day_rel}/<summary-file>.md|<summary-file>.md]]
```

Catalog entries are exactly `[[vault-rel-path|filename]]`, one per `*.md`
file in the folder (except `index.md` itself), label is the bare filename.
The lists cover the day's files; the body distills them with bullets.

## Hints from deterministic code checks
{hints_block}

Read `index.md` and the day's summaries. Verify against the format above:
the body faithfully synthesizes the day (events, numbers, decisions,
quotes — no invented facts); the `## Einträge` catalog is complete and
correctly linked; frontmatter is valid with `type: daily_summary`, today's
`updated`, a `last_checked_at` hash, and tags/persons/companies/groups/products
covering the day's files. Fix the index file in place wherever a hint (or
anything else you spot) is valid. Never modify anything under `raw/` or
the day's summary files — only `index.md` is yours to fix.
"""


# ---------------------------------------------------------------------------
# Pure helpers (no session needed — unit-testable)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str):
    """Split a markdown file into (frontmatter_dict_or_None, body, error_or_None)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text, "missing frontmatter (file must start with --- YAML ---)"
    fm_raw = m.group(1)
    body = text[m.end():]
    try:
        import yaml
        try:
            fm = yaml.safe_load(fm_raw)
        except Exception:
            fm = yaml.load(fm_raw, Loader=yaml.BaseLoader)
    except Exception as e:
        return None, body, f"frontmatter is not valid YAML: {e}"
    if not isinstance(fm, dict):
        return None, body, "frontmatter must be a YAML mapping"
    return fm, body, None


def _fm_list_values(fm: dict, field: str) -> list[str]:
    """String items of a frontmatter list field (order-preserving)."""
    values = fm.get(field)
    if not isinstance(values, list):
        return []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


def _collect_day_summaries(day_dir: Path) -> tuple[list[dict], list[str]]:
    """Read a day folder's per-mail summaries (skips index.md).

    Returns (summaries, hints); each summary has ``path``, ``fm``,
    ``body``, ``title``. Only ``type: summary`` files are included.
    """
    summaries: list[dict] = []
    hints: list[str] = []
    for fp in sorted(day_dir.glob("*.md")):
        if fp.name == "index.md":
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            hints.append(f"unreadable file {fp.name}: {e} — skipped")
            continue
        fm, body, error = _parse_frontmatter(text)
        if error or not isinstance(fm, dict):
            hints.append(f"{fp.name}: {error} — skipped")
            continue
        if fm.get("type") != "summary":
            hints.append(f"{fp.name}: type is {fm.get('type')!r}, not `summary` — skipped")
            continue
        summaries.append({"path": fp, "fm": fm, "body": body, "text": text, "title": fm.get("title")})
    return summaries, hints


def _aggregate_day_lists(summaries: list[dict]) -> dict[str, list[str]]:
    """Union of tags/persons/companies/groups/products over the day (ordered, deduped)."""
    aggregate: dict[str, list[str]] = {f: [] for f in DAY_FIELDS}
    for s in summaries:
        for field in DAY_FIELDS:
            for item in _fm_list_values(s["fm"], field):
                if item not in aggregate[field]:
                    aggregate[field].append(item)
    return aggregate


def _is_explicit_none(text: str | None) -> bool:
    """True when the LLM explicitly reported 'no duplicates' via the none sentinel.

    Distinguishes "checked, nothing found" from an empty/failed response.
    """
    if not isinstance(text, str):
        return False
    return text.strip().strip("`'\"").strip().lower() == "none"


def _parse_pair_lines(dedup_raw: str, field: str, items: list[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Parse ``canonical, variant`` lines for one field into validated pairs.

    A leading ``field:`` prefix per line is tolerated, and bare ``none``
    lines (the explicit no-duplicates sentinel) are silently skipped.
    Variants absent from *items* are reported and ignored — the LLM must
    never cause renames of items it did not see.
    """
    pairs: list[tuple[str, str, str]] = []
    hints: list[str] = []
    seen: dict[str, str] = {}
    for lineno, line in enumerate((dedup_raw or "").split("\n"), 1):
        line = line.strip().strip("`")
        if not line or line.startswith("#"):
            continue
        if _is_explicit_none(line):
            continue
        if re.match(rf"^{re.escape(field)}\s*:", line):
            line = line.split(":", 1)[1].strip()
        if "," not in line:
            #hints.append(f"dedup `{field}` line {lineno} malformed (want `canonical, variant`): '{line}' — ignored")
            continue
        canonical, variant = (part.strip().strip("`") for part in line.split(",", 1))
        if not canonical or not variant:
            hints.append(f"dedup `{field}` line {lineno} has an empty side: '{line}' — ignored")
            continue
        if canonical == variant:
            continue
        if variant not in items:
            hints.append(f"dedup `{field}: {canonical}, {variant}` — variant not in the day's `{field}` list, likely invented — ignored")
            continue
        if variant in seen:
            hints.append(f"dedup variant '{variant}' in `{field}` mapped twice ({seen[variant]} and {canonical}) — first wins")
            continue
        seen[variant] = canonical
        pairs.append((field, canonical, variant))
    return pairs, hints


def _canonicalize_list(items: list[str], field: str, pairs: list[tuple[str, str, str]]) -> list[str]:
    """Apply variant→canonical replacements, then dedupe preserving order."""
    mapping = {v: c for f, c, v in pairs if f == field}
    out: list[str] = []
    for item in items:
        item = mapping.get(item, item)
        if item not in out:
            out.append(item)
    return out


def _split_flow_items(inner: str) -> list[str]:
    """Split the inside of a flow list ``[a, "b, c"]`` respecting quotes."""
    items, current, quote = [], "", None
    for ch in inner:
        if quote is not None:
            current += ch
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote, current = ch, current + ch
        elif ch == ",":
            items.append(current)
            current = ""
        else:
            current += ch
    items.append(current)
    return items


def _replace_frontmatter_item(fm_raw: str, field: str, variant: str, canonical: str) -> tuple[str, bool, str]:
    """Replace one list item in raw frontmatter text (flow or block style).

    If *canonical* is already present in the same list, the variant entry
    is dropped instead. Returns (new_fm_raw, changed, detail); matching is
    exact on the unquoted, stripped item text.
    """
    lines = fm_raw.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(field)}\s*:", line):
            start = i
            break
    if start is None:
        return fm_raw, False, f"field `{field}` not found"
    first = lines[start]
    rest_of_line = first.split(":", 1)[1]

    def _norm(item: str) -> str:
        item = item.strip()
        if len(item) >= 2 and item[0] == item[-1] and item[0] in ("'", '"'):
            item = item[1:-1]
        return item.strip()

    if "[" in rest_of_line and "]" in rest_of_line:
        pre, post = first.split("[", 1)
        inner, suffix = post.rsplit("]", 1)
        items = _split_flow_items(inner)
        normed = [_norm(it) for it in items]
        if variant not in normed:
            return fm_raw, False, f"'{variant}' not in `{field}`"
        if canonical in normed:
            items = [it for it, n in zip(items, normed) if n != variant]
            detail = f"dropped '{variant}' from `{field}` (canonical '{canonical}' already present)"
        else:
            items = [f'"{canonical}"' if (it.strip().startswith('"') and _norm(it) == variant) else (canonical if n == variant else it) for it, n in zip(items, normed)]
            detail = f"replaced '{variant}' with '{canonical}' in `{field}`"
        lines[start] = f"{pre}[{', '.join(it.strip() for it in items)}]{suffix}"
        return "\n".join(lines), True, detail

    end = start + 1
    while end < len(lines) and re.match(r"^\s*-\s+", lines[end]):
        end += 1
    block = lines[start + 1:end]
    normed = [_norm(re.sub(r"^\s*-\s+", "", ln)) for ln in block]
    if variant not in normed:
        return fm_raw, False, f"'{variant}' not in `{field}`"
    if canonical in normed:
        block = [ln for ln, n in zip(block, normed) if n != variant]
        detail = f"dropped '{variant}' from `{field}` (canonical '{canonical}' already present)"
    else:
        new_block = []
        for ln, n in zip(block, normed):
            if n == variant:
                m = re.match(r"^(\s*-\s*)(.*)$", ln)
                prefix, old_item = m.group(1), m.group(2)
                quote = '"' if old_item.strip().startswith('"') else ("'" if old_item.strip().startswith("'") else "")
                new_block.append(f"{prefix}{quote}{canonical}{quote}" if quote else f"{prefix}{canonical}")
            else:
                new_block.append(ln)
        block = new_block
        detail = f"replaced '{variant}' with '{canonical}' in `{field}`"
    lines[start + 1:end] = block
    return "\n".join(lines), True, detail


def _set_frontmatter_scalar(fm_raw: str, field: str, value: str) -> str:
    """Set a top-level scalar field, preserving position when present."""
    lines = fm_raw.split("\n")
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(field)}\s*:", line):
            lines[i] = f"{field}: {value}"
            return "\n".join(lines)
    return fm_raw


def apply_dedup_to_files(day_dir: Path, pairs: list[tuple[str, str, str]], today_str: str) -> tuple[dict[str, list[str]], list[str]]:
    """Rewrite variant items to canonical form in the day's summaries.

    Only touches ``*.md`` (excluding ``index.md``) whose frontmatter list
    contains the variant verbatim; bumps ``updated:`` on touched files.
    Returns ({filename: [changes]}, hints).
    """
    fixed: dict[str, list[str]] = {}
    hints: list[str] = []
    for fp in sorted(day_dir.glob("*.md")):
        if fp.name == "index.md":
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            hints.append(f"{fp.name}: unreadable ({e}) — dedup skipped")
            continue
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        fm_raw = m.group(1)
        changes: list[str] = []
        for field, canonical, variant in pairs:
            fm_raw, changed, detail = _replace_frontmatter_item(fm_raw, field, variant, canonical)
            if changed:
                changes.append(detail)
        if changes:
            fm_raw = _set_frontmatter_scalar(fm_raw, "updated", today_str)
            fp.write_text(text[:m.start(1)] + fm_raw + text[m.end(1):], encoding="utf-8")
            fixed[fp.name] = changes
    return fixed, hints


def _yaml_flow_list(items: list[str]) -> str:
    import yaml
    return yaml.safe_dump(items, default_flow_style=True, allow_unicode=True).strip()


def _build_daily_index(day_str: str, aggregate: dict[str, list[str]], body: str, catalog: list[str], today_str: str, head_hash: str | None, fingerprint: str) -> str:
    """Assemble the day's ``index.md``: code-built frontmatter + session body + code-built catalog."""
    fm_lines = ["---", "type: daily_summary", f"updated: {today_str}"]
    if head_hash is not None:
        fm_lines.append(f"last_checked_at: {head_hash}")
    fm_lines.append(f"sources_fingerprint: {fingerprint}")
    for field in DAY_FIELDS:
        fm_lines.append(f"{field}: {_yaml_flow_list(aggregate.get(field, []))}")
    fm_lines.append("---")
    text = "\n".join(fm_lines) + "\n\n" + body.strip() + "\n"
    if catalog:
        text += "\n## Einträge\n\n" + "\n".join(f"- {entry}" for entry in catalog) + "\n"
    return text


def _validate_body(day_str: str, body: str) -> list[str]:
    """Hints for a session-returned daily body (frontmatter is code-built)."""
    hints: list[str] = []
    body_stripped = (body or "").strip()
    if len(body_stripped) < 50:
        hints.append("body is empty or too short (<50 chars) — synthesize key events, numbers, decisions, quotes for the day")
        return hints
    if not body_stripped.startswith(f"# Summary for {day_str}"):
        hints.append(f"body should start with exactly `# Summary for {day_str}`")
    has_bullets = any(
        line.lstrip().startswith(("- ", "* ", "+ "))
        or re.match(r"^\s*\d+[.)]\s", line)
        for line in body_stripped.split("\n")
    )
    if not has_bullets:
        hints.append("body has no bullet points — use bullets by default for easy scanning")
    return hints


def _git_names(args: list[str], root: Path) -> list[str] | None:
    """Run a git name-listing command (NUL-separated output); None on any failure."""
    try:
        proc = subprocess.run(
            ["git", "-C", root.as_posix(), *args],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.split("\0") if p]


def _day_changed_files(day_dir: Path, root: Path, stored_hash: str | None) -> tuple[list[str] | None, list[str]]:
    """Files in *day_dir* changed since its index was built.

    Union of worktree changes (``git status``: modified + untracked) and
    changes committed after the recorded ``last_checked_at`` hash — vault
    work gets committed, so either side can carry the news. Returns
    (changed_or_None, removed); ``index.md`` (our own output) is excluded
    from both, partitioning is by worktree existence. None when git cannot
    tell (not a repo, timeouts) — the caller falls back to a full-synthesis
    brief, which is always correct.
    """
    try:
        rel = day_dir.relative_to(root).as_posix()
    except Exception:
        return None, []
    names: set[str] = set()
    status = _git_names(["status", "--porcelain=v1", "-z", "--no-renames", "-uall", "--", rel], root)
    if status is None:
        return None, []
    for entry in status:
        # -z entries are exactly `XY PATH` (2 status chars + space); -uall makes
        # git list individual untracked files instead of the bare directory.
        path = entry[3:] if len(entry) > 3 and entry[2] == " " else entry
        name = Path(path.strip()).name
        if name and name != "index.md":
            names.add(name)
    if stored_hash:
        # --no-renames: a renamed summary must surface as removed(old) +
        # changed(new) — with rename detection --name-only shows only the
        # destination and the removed name would go untracked.
        diff = _git_names(["diff", "--no-renames", "--name-only", "-z", stored_hash, "--", rel], root)
        if diff is not None:
            for path in diff:
                name = Path(path).name
                if name and name != "index.md":
                    names.add(name)
    changed, removed = [], []
    for name in sorted(names):
        (removed if not (day_dir / name).exists() else changed).append(name)
    return changed, removed


def _git_head(root: Path) -> str | None:
    """Current vault HEAD hash (provenance for ``last_checked_at``), or None."""
    try:
        proc = subprocess.run(
            ["git", "-C", root.as_posix(), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    head = proc.stdout.strip()
    return head or None


def _sources_fingerprint(summaries: list[dict]) -> str:
    """Content fingerprint of a day's collected summaries (name + full text).

    The index commit itself never changes this — only real source changes
    (new/edited/removed summaries, including uncommitted ones) do — so a
    matching fingerprint means "up to date" and can never loop.
    """
    import hashlib
    h = hashlib.sha1()
    for s in sorted(summaries, key=lambda s: s["path"].name):
        h.update(s["path"].name.encode("utf-8") + b"\0")
        h.update(s["text"].encode("utf-8") + b"\0")
    return h.hexdigest()


def _decide_stale_fingerprint(*, index_exists: bool, fm_type, stored_fp: str | None, current_fp: str) -> tuple[bool, str]:
    """Pure staleness decision: rebuild when the sources differ from the recorded fingerprint."""
    if not index_exists:
        return True, "no index.md"
    if fm_type != "daily_summary":
        return True, f"legacy index.md (type {fm_type!r}) — regenerating"
    if not stored_fp:
        return True, "index.md has no sources_fingerprint — regenerating"
    if stored_fp != current_fp:
        return True, "day sources changed since last build"
    return False, "up to date"


# ---------------------------------------------------------------------------
# Session-bound helpers
# ---------------------------------------------------------------------------

def _workspace_root(_session) -> Path | None:
    try:
        ws = getattr(_session, "workspace", None)
        if ws is not None and getattr(ws, "path", None):
            return Path(ws.path)
    except Exception:
        pass
    try:
        version = _session.get_version_model()
        ws = getattr(version, "workspace", None)
        if ws is not None and getattr(ws, "path", None):
            return Path(ws.path)
    except Exception:
        pass
    return None


def _vault_rel(_session, absolute: Path) -> str:
    root = _workspace_root(_session)
    try:
        if root is not None:
            return absolute.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        pass
    return absolute.as_posix()


def _iter_day_dirs(root: Path):
    """Yield timeline/YYYY/MM/DD day dirs, oldest first."""
    base = root / "timeline"
    if not base.is_dir():
        return
    for y in sorted(base.glob("[0-9]" * 4)):
        if not y.is_dir():
            continue
        for mo in sorted(y.glob("[0-9]" * 2)):
            if not mo.is_dir():
                continue
            for d in sorted(mo.glob("[0-9]" * 2)):
                if d.is_dir():
                    yield d


def _read_index_facts(day_dir: Path) -> tuple[bool, object, str | None, str | None]:
    """(index_exists, fm_type_or_None, stored_hash_or_None, stored_fingerprint_or_None) for a day dir."""
    index = day_dir / "index.md"
    if not index.exists():
        return False, None, None, None
    try:
        text = index.read_text(encoding="utf-8")
    except Exception:
        return True, None, None, None
    fm, _body, _error = _parse_frontmatter(text)
    if not isinstance(fm, dict):
        return True, None, None, None
    stored = fm.get("last_checked_at")
    fingerprint = fm.get("sources_fingerprint")
    return (
        True,
        fm.get("type"),
        (stored.strip() if isinstance(stored, str) and stored.strip() else None),
        (fingerprint.strip() if isinstance(fingerprint, str) and fingerprint.strip() else None),
    )


def _spawn_baseagent(_session, name: str, description: str, brief: str, extra_parts: list | None = None):
    """Spawn a baseagent SUBTASK_DELEGATE session with *brief* and return (ok, child_session, session_pk, ref_or_error).

    Mirrors double_check_summary: baseagent is visibility: internal, so it
    is resolved directly by name, and narrowing overlays inherited from the
    parent session are reset so the child gets the full baseagent envelope.
    The returned ref is the add_user_message taskcall — resolvable by the
    scheduler exactly like an llm_query result ref. Optional *extra_parts*
    (timeline-style label/content evidence parts) are delivered after the
    brief and before the timestamp part.
    """
    from server.models.enums.message_enums import MessageContentType, MessagePartType
    from server.models.enums.session_enums import SessionType
    from server.models.settings import ReasoningEffort

    child_session = _session.spawn_subagent(
        "baseagent",
        name=name,
        description=description,
        session_type=SessionType.SUBTASK_DELEGATE,
        allow_internal=True,
        reasoning_effort=ReasoningEffort.MINIMAL,
        max_turns=20,
    )
    if child_session is None:
        return False, None, None, "agent 'baseagent' not found"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    working_dir = child_session.workspace.path if child_session.workspace else "unknown"
    parts = [
        {
            "type": MessagePartType.MESSAGE,
            "content_type": MessageContentType.TEXT,
            "content": "You are running as a subtask for another agent. "
                "When your work is complete, finish by invoking the final_result tool directly with your result as its content argument. "
                "Do not return your result as plain text only. Your task:\n",
        },
        {
            "type": MessagePartType.MESSAGE,
            "content_type": MessageContentType.TEXT,
            "content": brief,
        },
        *(extra_parts or []),
        {
            "type": MessagePartType.MESSAGE,
            "content_type": MessageContentType.TEXT,
            "content": f"It is now {now}, your working dir is '{working_dir}'.\n",
        },
    ]
    ref = child_session.add_user_message(parts)
    return True, child_session, child_session.model.pk, ref


def _spawn_day_session(_session, day_rel: str, day_str: str, brief: str):
    """Spawn the prose session for one day; returns (ok, session_pk_or_None, body_ref_or_error)."""
    from time import time

    stamp = day_str.replace("-", "")
    ok, _, session_pk, ref = _spawn_baseagent(
        _session,
        name=f"p{_session.model.pk}:daily:{stamp}:{int(time())}",
        description=f"Daily summary {day_rel}",
        brief=brief,
    )
    if not ok:
        return False, None, ref
    return True, session_pk, ref


def _spawn_day_check(_session, day_rel: str, day_str: str, brief: str):
    """Spawn the fire-and-forget double-check session for a written index.md."""
    from time import time

    stamp = day_str.replace("-", "")
    ok, _, session_pk, ref = _spawn_baseagent(
        _session,
        name=f"p{_session.model.pk}:dailycheck:{stamp}:{int(time())}",
        description=f"Double-check {day_rel}/index.md",
        brief=brief,
    )
    if not ok:
        return False, {"status": "error", "day": day_rel, "message": f"double-check not spawned: {ref}"}
    return True, {"status": "dispatched", "day": day_rel, "session_pk": session_pk, "message": ref}


def update_timeline_daily(_session: Session, limit: int = 3, day: str | None = None):
    """Rebuild stale day indexes (``timeline/YYYY/MM/DD/index.md``).

    Staleness comes from a content fingerprint: a day needs work when its
    ``index.md`` is missing, is a legacy non-``daily_summary`` file, has no
    ``sources_fingerprint``, or the day's current sources differ from the
    recorded fingerprint (new/edited/removed summaries, committed or not —
    e.g. a late scanned paper mail). The index commit itself never changes
    the fingerprint, so rebuilding can never retrigger itself. ``git`` is
    only used for the ``last_checked_at`` provenance hash (no git needed
    for the decision itself).
    Each stale day (up to *limit*, oldest first — or just *day* as
    ``YYYY-MM-DD``, which is always rebuilt) gets one baseagent prose
    session (body via final_result, no file writes) plus one dedup query
    per non-trivial metadata field; days that already have a
    ``daily_summary`` index get a focused update brief (only the
    git-changed files since the last build, via ``git status`` plus
    ``git diff`` against the recorded ``last_checked_at`` hash) instead of
    a full re-synthesis. All result-refs converge in
    ``write_day_index``, which writes ``index.md`` in code and spawns a
    double-check session. Days without summaries get a minimal code-written
    index (no session). Returns (True, {status, results}).
    """
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "message": "cannot resolve workspace root"}
    llm_query_tool = _session.get_tool("llm_query")
    if llm_query_tool is None:
        return False, {"status": "error", "message": "tool 'llm_query' is not available"}
    write_task = _session.get_task("write_day_index")
    if write_task is None:
        return False, {"status": "error", "message": "task 'write_day_index' is not available"}

    if day is not None:
        try:
            y, mo, d = day.split("-")
            datetime.date(int(y), int(mo), int(d))
        except Exception:
            return False, {"status": "error", "message": f"bad day '{day}' — want YYYY-MM-DD"}
        day_dirs = [root / "timeline" / y / mo / d]
        if not day_dirs[0].is_dir():
            return False, {"status": "error", "message": f"day folder not found: timeline/{y}/{mo}/{d}"}
        explicit_day = True
    else:
        day_dirs = list(_iter_day_dirs(root))
        explicit_day = False

    # Read index facts for every candidate day; the vault HEAD is only
    # provenance for `last_checked_at` (one cheap rev-parse, optional).
    facts: dict[str, tuple[bool, object, str | None, str | None]] = {}
    for day_dir in day_dirs:
        try:
            day_str = f"{day_dir.parent.parent.name}-{day_dir.parent.name}-{day_dir.name}"
            datetime.date(*map(int, day_str.split("-")))
        except Exception:
            continue
        facts[_vault_rel(_session, day_dir)] = _read_index_facts(day_dir)
    head_hash = _git_head(root)

    results = []
    spawned = 0
    for day_dir in day_dirs:
        if spawned >= limit and not explicit_day:
            break
        rel = _vault_rel(_session, day_dir)
        if rel not in facts:
            continue  # not a real YYYY/MM/DD date
        index_exists, fm_type, stored_hash, stored_fp = facts[rel]
        day_str = rel.split("timeline/")[-1].replace("/", "-")

        if explicit_day:
            needs, reason = True, "explicitly requested"
        else:
            current_fp = _sources_fingerprint(_collect_day_summaries(day_dir)[0])
            needs, reason = _decide_stale_fingerprint(
                index_exists=index_exists, fm_type=fm_type,
                stored_fp=stored_fp, current_fp=current_fp,
            )
        if not needs:
            if explicit_day:
                results.append({"day": rel, "status": "skipped", "message": f"up to date ({reason})"})
            continue

        summary_files = [p.name for p in sorted(day_dir.glob("*.md")) if p.name != "index.md"]
        if not summary_files:
            # Nothing to synthesize — code-generate a minimal index, no session.
            today_str = datetime.datetime.now().date().isoformat()
            lines = ["---", "type: daily_summary", f"updated: {today_str}"]
            if head_hash is not None:
                lines.append(f"last_checked_at: {head_hash}")
            lines.append(f"sources_fingerprint: {_sources_fingerprint([])}")
            for field in DAY_FIELDS:
                lines.append(f"{field}: []")
            lines.append("---")
            index_text = "\n".join(lines) + f"\n\n# Summary for {day_str}\n\nNo entries for this day.\n"
            try:
                (day_dir / "index.md").write_text(index_text, encoding="utf-8")
                results.append({"day": rel, "status": "success", "message": f"wrote minimal index.md ({reason}; no summaries, no session)"})
            except Exception as e:
                results.append({"day": rel, "status": "error", "message": f"cannot write index.md: {e}"})
            continue

        summaries, collect_hints = _collect_day_summaries(day_dir)
        aggregate = _aggregate_day_lists(summaries)
        summary_files = sorted(s["path"].name for s in summaries)
        if index_exists and fm_type == "daily_summary":
            changed_files, removed_files = _day_changed_files(day_dir, root, stored_hash)
        else:
            changed_files, removed_files = None, []
        if changed_files:
            # Update, not a fresh build: the session revises the existing
            # synthesis from the changed files only. The listing covers
            # every worktree file (so new-but-unparseable files are seen
            # too), with git-changed ones marked.
            all_files = [p.name for p in sorted(day_dir.glob("*.md")) if p.name != "index.md"]
            brief = _build_day_update_brief(rel, day_str, all_files, set(changed_files), removed_files)
            collect_hints.append(
                f"day update: {len(changed_files)} file(s) changed since last build"
                f" ({', '.join(sorted(changed_files)[:5])}{' …' if len(changed_files) > 5 else ''})"
                + (f"; removed: {', '.join(sorted(removed_files))}" if removed_files else ""))
        else:
            brief = _build_day_session_brief(rel, day_str, summary_files)
        ok, session_pk, body_ref = _spawn_day_session(
            _session, rel, day_str, brief)
        if not ok:
            results.append({"day": rel, "status": "error", "reason": reason, "message": f"prose session not spawned: {body_ref}"})
            continue
        # Fan out one tiny dedup query per field (list-only input, no
        # bodies). The prose ref and all dedup refs converge in
        # write_day_index, which the scheduler delivers once every ref
        # resolves — the same single-ref passing process_summary relies on.
        field_refs: dict[str, object] = {}
        for field in DAY_FIELDS:
            items = aggregate.get(field, [])
            if len(set(items)) < 2:
                continue
            field_refs[field] = llm_query_tool.delay(messages=[
                {"role": "system", "content": "You are a list deduplication expect, you immediately see if a list contains duplicates or not" },
                {"role": "user", "content": DEDUP_FIELD_PROMPT.format(
                    field=field,
                    field_singular=_FIELD_SINGULAR[field],
                    field_plural=_FIELD_PLURAL[field],
                    day_str=day_str,
                    count=len(items),
                    items="\n".join(f"- {item}" for item in items),
                )},
            ])
        kwargs: dict[str, object] = {
            "day_path": rel, "day_str": day_str, "body_result": body_ref, "session_pk": session_pk,
            "aggregate": aggregate, "collect_hints": collect_hints, "head_hash": head_hash,
        }
        kwargs.update({f"{field}_result": ref for field, ref in field_refs.items()})
        write_ref = write_task.delay(**kwargs)
        results.append({"day": rel, "status": "dispatched", "session_pk": session_pk,
                        "reason": reason, "dedup_fields": sorted(field_refs), "write": write_ref})
        spawned += 1
    return True, {"status": "success", "results": results}


def _resolve_message_ref(result):
    """Resolve a ``{'_type': 'Message', 'pk'}`` ref to its text parts via the DB.

    Session message-refs (add_user_message taskcalls) resolve to Message
    refs, not text — unlike llm_query refs. Returns the concatenated
    TEXT/MESSAGE part contents, or None (DB errors and non-refs included).
    """
    if not isinstance(result, dict) or result.get("_type") != "Message":
        return None
    try:
        pk = int(result.get("pk"))
    except (TypeError, ValueError):
        return None
    try:
        from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
        from server.models.message import Message

        msg = Message.objects.filter(pk=pk).first()
        if msg is None:
            return None
        texts = []
        for part in msg.parts.all():
            if part.type == MessagePartType.MESSAGE and part.content_type == MessageContentType.TEXT:
                content = getattr(part.content, "content", None)
                if isinstance(content, str) and content.strip():
                    texts.append(content.strip())
        return "\n\n".join(texts) or None
    except Exception:
        return None


def _extract_result_text(result) -> str | None:
    """Unwrap an llm_query result into raw text (string / result dict / (bool, dict) / Message ref)."""
    seen = 0
    current = result
    while seen < 5:
        seen += 1
        if current is None:
            return None
        if isinstance(current, str):
            return current if current.strip() else None
        if isinstance(current, (list, tuple)) and len(current) == 2 and isinstance(current[0], bool):
            current = current[1]
            continue
        if isinstance(current, dict):
            content = current.get("content")
            if isinstance(content, str) and content.strip():
                return content
            nested = current.get("result", current.get("data"))
            if nested is not None and nested is not current:
                current = nested
                continue
            return _resolve_message_ref(current)
        return None
    return None


def _read_child_session_texts(session_pk) -> tuple[str | None, str | None]:
    """Read a prose session's candidate bodies from the DB: (final_result args, last assistant message).

    Agents in this system end turns with plain text (final_result has zero
    recorded calls), so the message history is the reliable source; the
    explicit call args win when present. Returns (final_text_or_None,
    message_text_or_None); (None, None) on any failure.
    """
    try:
        pk = int(session_pk)
    except (TypeError, ValueError):
        return None, None
    try:
        from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
        from server.models.message import Message
        from server.models.tasks.agent_task_call import AgentTaskCall

        final_text = None
        call = AgentTaskCall.objects.filter(
            session_id=pk, task_definition__name="final_result"
        ).order_by("-created_at").first()
        if call is not None:
            content = (call.carguments_json or {}).get("content")
            if isinstance(content, str) and content.strip():
                final_text = content.strip()
        msg = Message.objects.filter(session_id=pk, role=MessageRole.ASSISTANT).order_by("-created_at").first()
        if msg is None:
            return final_text, None
        texts = []
        for part in msg.parts.all():
            if part.type == MessagePartType.MESSAGE and part.content_type == MessageContentType.TEXT:
                content = getattr(part.content, "content", None)
                if isinstance(content, str) and content.strip():
                    texts.append(content.strip())
        return final_text, ("\n\n".join(texts) or None)
    except Exception:
        return None, None


def _pick_body(candidates: list[tuple[str, str | None]], min_len: int = 50) -> tuple[str | None, str]:
    """Pick the first usable body from (source, text) candidates; always explain.

    ``final_result`` args win when usable (explicit delivery), otherwise the
    longest candidate of at least *min_len* chars. Returns (text_or_None,
    diagnostic like ``"final_result (412 chars)"`` or ``"ref: none; last_message: 12 chars (too short)"``).
    """
    usable = [(src, t.strip()) for src, t in candidates if isinstance(t, str) and t.strip()]
    diag = "; ".join(f"{src}: {len(t.strip()) if isinstance(t, str) else 0} chars" + ("" if isinstance(t, str) and len(t.strip()) >= min_len else " (unusable)") for src, t in candidates) or "no candidates"
    for src, text in usable:
        if src == "final_result" and len(text) >= min_len:
            return text, f"{diag} => {src}"
    long = [(src, text) for src, text in usable if len(text) >= min_len]
    if long:
        src, text = max(long, key=lambda item: len(item[1]))
        return text, f"{diag} => {src}"
    return None, diag


def write_day_index(_session, day_path, day_str=None, body_result=None, session_pk=None, aggregate=None, collect_hints=None, head_hash=None,
                    tags_result=None, persons_result=None, companies_result=None, groups_result=None, products_result=None):
    """Merge a prose body with code-owned metadata into a day's ``index.md``.

    ``body_result`` is the prose session's message ref and ``session_pk``
    its session: the body is resolved from the ref, else from the session's
    explicit final_result args, else from its last assistant message (agents
    end turns with plain text — final_result has no recorded calls, so the
    history is the reliable source). Each ``*_result`` is one field-dedup
    LLM output (``canonical, variant`` lines). The scheduler delivers this
    task once every ref resolves. Pairs are re-validated against a freshly
    recomputed aggregate — invented variants are ignored — then applied to
    the day's summary files in code (variant → canonical, ``updated:``
    bumped). ``index.md`` is written in one go: code-built frontmatter
    (canonical lists, ``type: daily_summary``, ``last_checked_at``) +
    session body + code-built ``## Einträge`` catalog. Afterwards a
    fire-and-forget double-check session verifies the file.

    The only failure is "nothing could be written": empty body or an
    unresolvable day folder. Returns (True, {status, day_path, index_path,
    fixed_files, check, lint_results, message}) on success.
    """
    aggregate = {f: list((aggregate or {}).get(f, [])) for f in DAY_FIELDS}
    collect_hints = list(collect_hints or [])
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "day_path": day_path, "message": "write_day_index: cannot resolve workspace root"}
    day_dir = (root / day_path) if not Path(day_path).is_absolute() else Path(day_path)
    if not day_dir.is_dir():
        return False, {"status": "error", "day_path": day_path, "message": f"write_day_index: day folder not found: {day_path}"}
    if day_str is None:
        try:
            day_str = f"{day_dir.parent.parent.name}-{day_dir.parent.name}-{day_dir.name}"
            datetime.date(*map(int, day_str.split("-")))
        except Exception:
            return False, {"status": "error", "day_path": day_path, "message": f"write_day_index: not a YYYY/MM/DD folder: {day_path}"}

    fr_text, hist_text = _read_child_session_texts(session_pk)
    body, body_source = _pick_body([
        ("ref", _extract_result_text(body_result)),
        ("final_result", fr_text),
        ("last_message", hist_text),
    ])
    if body is None:
        return False, {
            "status": "error",
            "day_path": day_path,
            "lint_results": [f"prose session returned no usable body ({body_source}) — nothing was written"],
            "message": "write_day_index: body empty or too short, file could not be written",
        }

    lint_results = list(collect_hints)
    lint_results.extend(_validate_body(day_str, body))

    fresh = _aggregate_day_lists(_collect_day_summaries(day_dir)[0])
    field_results = {"tags": tags_result, "persons": persons_result, "companies": companies_result, "groups": groups_result, "products": products_result}
    pairs: list[tuple[str, str, str]] = []
    for field in DAY_FIELDS:
        result = field_results[field]
        if result is None:
            continue
        text = _extract_result_text(result)
        if text is None:
            lint_results.append(f"dedup `{field}`: LLM result contains no usable text — field skipped")
            continue
        if _is_explicit_none(text):
            #lint_results.append(f"dedup `{field}`: explicitly no duplicates")
            continue
        field_pairs, field_hints = _parse_pair_lines(text, field, fresh.get(field, []))
        pairs.extend(field_pairs)
        lint_results.extend(field_hints)
        #if not field_pairs and text.strip():
          #lint_results.append(f"dedup `{field}`: no duplicates found")

    today_str = datetime.datetime.now().date().isoformat()
    fixed_files, fix_hints = apply_dedup_to_files(day_dir, pairs, today_str)
    lint_results.extend(fix_hints)

    canonical = {f: _canonicalize_list(fresh.get(f, []), f, pairs) for f in DAY_FIELDS}
    # Fingerprint AFTER the fixes, so the dedup pass's own edits are covered
    # and can never flag the day stale again.
    summaries = sorted(_collect_day_summaries(day_dir)[0], key=lambda s: s["path"].name)
    fingerprint = _sources_fingerprint(summaries)
    catalog = [f"[[{_vault_rel(_session, s['path'])}|{s['path'].name}]]" for s in summaries]
    try:
        (day_dir / "index.md").write_text(
            _build_daily_index(day_str, canonical, body, catalog, today_str, head_hash, fingerprint), encoding="utf-8")
    except Exception as e:
        return False, {
            "status": "error",
            "day_path": day_path,
            "lint_results": lint_results,
            "message": f"write_day_index: cannot write index.md: {e}",
        }

    check_ok, check_info = _spawn_day_check(
        _session, _vault_rel(_session, day_dir), day_str,
        _build_day_check_brief(_vault_rel(_session, day_dir), day_str,
                               [s["path"].name for s in summaries], lint_results))

    return True, {
        "status": "success",
        "day_path": day_path,
        "index_path": _vault_rel(_session, day_dir / "index.md"),
        "dedup_pairs": [f"{f}: {c}, {v}" for f, c, v in pairs],
        "fixed_files": fixed_files,
        "check": check_info,
        "lint_results": lint_results,
        "message": f"write_day_index: wrote {day_path}/index.md ({len(pairs)} dedup pairs, {len(fixed_files)} source files fixed, double-check {'dispatched' if check_ok else 'FAILED TO SPAWN'})",
    }
