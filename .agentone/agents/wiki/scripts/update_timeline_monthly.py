from __future__ import annotations

import datetime
import sys
from pathlib import Path

from runtime.session.session import Session

sys.path.insert(0, Path(__file__).resolve().parent.as_posix())
from update_timeline_daily import (  # noqa: E402
    DAY_FIELDS,
    DEDUP_FIELD_PROMPT,
    FRONTMATTER_RE,
    _FIELD_PLURAL,
    _FIELD_SINGULAR,
    _aggregate_day_lists,
    _canonicalize_list,
    _extract_result_text,
    _git_head,
    _git_names,
    _is_explicit_none,
    _parse_frontmatter,
    _parse_pair_lines,
    _pick_body,
    _read_child_session_texts,
    _read_index_facts,
    _replace_frontmatter_item,
    _set_frontmatter_scalar,
    _spawn_baseagent,
    _validate_body,
    _vault_rel,
    _workspace_root,
    _yaml_flow_list,
    apply_dedup_to_files,
)


# Pipeline: update_timeline_monthly finds stale month folders via a content
# fingerprint, then per stale month fans out reads that converge in
# write_month_index (code owns the file — the scheduler delivers it once
# every result-ref resolves):
# - one baseagent prose session (same spawn mechanics as the daily pipeline)
#   that reads the month's DAY indices — already distilled syntheses, cheap
#   to read — and returns ONLY the body markdown as its last message. It
#   writes nothing.
# - one tiny llm_query per metadata field (tags/persons/companies/groups/products)
#   whose input is ONLY that field's code-collected item list (union of the
#   day indices' frontmatter lists).
# write_month_index validates the body, applies the dedup pairs back into the
# month's SOURCES in code (variant → canonical, ``updated:`` bumped — same
# fix-back the daily pipeline does, one level up), and assembles frontmatter
# + body + code-built ``## Tage`` catalog into timeline/YYYY/MM/index.md,
# then spawns a fire-and-forget double-check session. Code owns metadata
# and the file, the sessions own prose judgment.
#
# The fix-back covers two layers: the day ``index.md`` files AND the
# per-mail summary files inside usable days (``apply_dedup_to_files``,
# verbatim-match only — files without the variant are untouched). Both must
# be unified or the month rollup rots: a canonical spelling in the month
# index has to win everywhere. Days without a ``daily_summary`` index are
# skipped (the daily pipeline owns them; the next month pass picks them up).
#
# Termination: rewriting per-mail files changes the DAY fingerprints, so
# fixed days rebuild via the daily pipeline — which stales the month exactly
# once. The next month pass then sees already-unified lists (dedup returns
# ``none``), records the fresh fingerprint, and the system settles. The
# month fingerprint itself is computed AFTER all fixes, so the month pass
# can never retrigger itself directly.
#
# Sources are the day indices (``type: daily_summary``) — not raw mail and
# not per-mail summaries. A month is stale when its index is missing, is a
# legacy non-``monthly_summary`` file, has no ``sources_fingerprint``, or the
# live day-index set differs from the recorded fingerprint
# (added/removed/rebuilt days — the daily pipeline rebuilding a day
# automatically stales its month, which is the intended cascade).
# Per-mail files sitting directly in the month folder (legacy strays, e.g.
# ``20221001-*.md`` in ``2022/10/`` instead of ``2022/10/01/``) are NOT
# sources: they are reported as hints (move them into day folders) and only
# their names feed the fingerprint, so cleaning them up retriggers a build.
# Committing the month index never changes the fingerprint, so rebuilding
# is self-terminating by construction (same argument as the daily pipeline).


def _build_month_session_brief(month_rel: str, month_str: str, day_files: list[str]) -> str:
    """Assemble the work order for a month-summary subagent session.

    The session returns ONLY the body markdown as its last message and
    writes nothing — frontmatter, catalog, and the index file itself are
    built by code. Metadata lists and spelling variants are handled by a
    separate code pass, so the session ignores them beyond reading.
    """
    listing = "\n".join(f"- {name}" for name in day_files) if day_files else "- (no day indices yet)"
    return f"""Synthesize the timeline month {month_str} from its daily index files.

Your working dir is the vault root; all paths below are vault-relative.
The month folder is `{month_rel}` and currently holds these day indices:

{listing}

Read the day indices — they are already distilled syntheses, so read them
all (frontmatter lists are cheap, bodies carry the substance). Synthesize,
don't concatenate: key events of the month, important numbers (amounts,
donations, totals, deadlines), decisions and outcomes, short quotes when the
exact wording matters. Bullets by default. If there is nothing substantial,
say so in one line instead of inventing importance.

Return EXACTLY the body markdown below as your LAST message — no frontmatter
(it is built by code), no code fences, no explanations, write NO files, and
output NOTHING after it (a separate code pass reads your last message and
stores it as the month's summary; it cannot see anything else you write):

```markdown
# Summary for {month_str}

<Key events, important numbers, decisions, quotes for the month.>
```

The heading MUST be exactly `# Summary for {month_str}`.
"""


def _build_month_check_brief(month_rel: str, month_str: str, day_files: list[str], lint_hints: list[str]) -> str:
    """Assemble the work order for a month-index double-check session."""
    listing = "\n".join(f"- {name}" for name in day_files) if day_files else "- (no day indices)"
    hints_block = "\n".join(f"- {hint}" for hint in lint_hints) if lint_hints else "- (no code hints — still verify facts, numbers, and cross-references)"
    return f"""Double-check the monthly index file `{month_rel}/index.md` for {month_str}.

Your working dir is the vault root; all paths below are vault-relative.
The month folder holds these day indices:

{listing}

## Expected file format (authoritative — do NOT read other index files for reference)

`{month_rel}/index.md` MUST have exactly this shape:

```markdown
---
type: monthly_summary
month: {month_str}                 # YYYY-MM of this folder
updated: YYYY-MM-DD                # today's date
last_checked_at: <40-hex git hash> # provenance only — never hand-edit
sources_fingerprint: <40-hex sha>  # provenance only — never hand-edit
tags: [tag1, tag2]                 # flow-style YAML lists, canonical spellings
persons: [Name One, Name Two]
companies: [Company]
groups: [Club, Crew]               # clubs/associations/crews/teams — neither person nor commercial company
products: []
---

# Summary for {month_str}          # exact heading, then bullet synthesis

<key events, important numbers, decisions, quotes>

## Tage                            # one bullet per DD day folder

- [[{month_rel}/DD/index.md|{month_str}-DD]]
```

Catalog entries for indexed days are exactly
`[[vault-rel-path|YYYY-MM-DD]]`; day folders without a usable index render
as a plain `YYYY-MM-DD (no daily index yet)` line instead. The lists cover
the month's days; the body distills them with bullets.

## Hints from deterministic code checks
{hints_block}

Read `index.md` and the month's day indices. Verify against the format
above: the body faithfully synthesizes the month (events, numbers,
decisions, quotes — no invented facts); the `## Tage` catalog lists every
day folder present; frontmatter is valid with `type: monthly_summary`, a
`month: {month_str}` scalar, today's `updated`, a `last_checked_at` hash,
and tags/persons/companies/groups/products covering the month's days. Fix the
index file in place wherever a hint (or anything else you spot) is valid.
Never modify anything under `raw/`, the day folders, or per-mail
summaries — only `index.md` is yours to fix.
"""


def _build_month_update_brief(month_rel: str, month_str: str, tage_entries: list[str], removed_days: list[str], notes: list[str]) -> str:
    """Assemble the work order for revising an existing month index.

    The month already has a ``monthly_summary`` index: the session reads
    its current body plus ONLY the changed day indices (not the whole
    month) and returns the full revised synthesis. Frontmatter, catalog,
    and the file itself stay code-built, exactly like the fresh-build brief.
    """
    listing = "\n".join(f"- {entry}" for entry in tage_entries) if tage_entries else "- (no day folders)"
    removed_block = "\n".join(f"- {day}" for day in removed_days) if removed_days else "- (none)"
    notes_block = "\n".join(f"- {note}" for note in notes) if notes else "- (none)"
    return f"""Revise the timeline month {month_str} index from its changed days.

Your working dir is the vault root; all paths below are vault-relative.
The month folder is `{month_rel}`. An `index.md` with a previous synthesis
already exists — this is an UPDATE, not a fresh build.

Start by reading the current `{month_rel}/index.md` body and keep whatever
still holds. Then read the changed day indices below in full. The unchanged
day indices are already reflected in the current body — do NOT re-read them
unless a changed day references them. Changes may be frontmatter-only
spelling normalizations (unified tags/persons) — where the substance is
unchanged, keep the existing text as is.

Days (entries marked CHANGED need a full re-read):

{listing}

Removed since the last build (their content must no longer appear in the synthesis):

{removed_block}

Further notes:

{notes_block}

Return EXACTLY the full revised body markdown below as your LAST message —
no frontmatter (it is built by code), no code fences, no explanations,
write NO files, and output NOTHING after it (a separate code pass reads
your last message and stores it as the month's summary; it cannot see
anything else you write):

```markdown
# Summary for {month_str}

<Key events, important numbers, decisions, quotes for the month.>
```

The heading MUST be exactly `# Summary for {month_str}`.
"""


# ---------------------------------------------------------------------------
# Pure helpers (no session needed — unit-testable)
# ---------------------------------------------------------------------------

def _collect_month_days(month_dir: Path) -> tuple[list[dict], list[str], list[str], list[str]]:
    """Read a month folder's day indices (``DD/index.md``, ``type: daily_summary``).

    Returns (days, day_dirnames, strays, hints); each day has ``day_str``,
    ``dirname``, ``index_path``, ``fm``, ``body``, ``text``. ``day_dirnames``
    covers every ``DD`` subfolder (indexed or not), ``strays`` names
    ``*.md`` files sitting directly in the month folder (legacy misplaced
    summaries — not sources, only reported).
    """
    days: list[dict] = []
    hints: list[str] = []
    try:
        year, mon = int(month_dir.parent.name), int(month_dir.name)
    except Exception:
        return days, [], [], [f"{month_dir.name}: not a YYYY/MM folder — skipped"]
    day_dirnames: list[str] = []
    for sub in sorted(month_dir.iterdir()):
        if sub.is_dir():
            if len(sub.name) == 2 and sub.name.isdigit():
                try:
                    datetime.date(year, mon, int(sub.name))
                except Exception:
                    hints.append(f"unexpected folder {sub.name}/ — not a calendar day, ignored")
                    continue
                day_dirnames.append(sub.name)
            else:
                hints.append(f"unexpected folder {sub.name}/ directly in month folder — ignored")
    for dirname in day_dirnames:
        day_str = f"{year:04d}-{mon:02d}-{int(dirname):02d}"
        index = month_dir / dirname / "index.md"
        if not index.exists():
            hints.append(f"day {day_str}: no index.md — run update_timeline_daily first")
            continue
        try:
            text = index.read_text(encoding="utf-8")
        except Exception as e:
            hints.append(f"day {day_str}: index.md unreadable ({e}) — skipped")
            continue
        fm, body, error = _parse_frontmatter(text)
        if error or not isinstance(fm, dict):
            hints.append(f"day {day_str}: index.md {error} — skipped")
            continue
        if fm.get("type") != "daily_summary":
            hints.append(f"day {day_str}: index.md type is {fm.get('type')!r}, not `daily_summary` — run update_timeline_daily first")
            continue
        days.append({"day_str": day_str, "dirname": dirname, "index_path": index,
                     "fm": fm, "body": body, "text": text})
    strays: list[str] = []
    for fp in sorted(month_dir.glob("*.md")):
        if fp.name == "index.md":
            continue
        strays.append(fp.name)
    if strays:
        shown = ", ".join(strays[:5]) + (" …" if len(strays) > 5 else "")
        hints.append(f"{len(strays)} per-mail file(s) directly in month folder ({shown}) — not covered by the monthly summary, move them into timeline/YYYY/MM/DD/ day folders")
    return days, day_dirnames, strays, hints


def _tage_entries(_session, month_dir: Path, days: list[dict], day_dirnames: list[str], mark: set[str] = frozenset()) -> tuple[list[str], list[str]]:
    """Code-built ``## Tage`` catalog entries plus missing-day list.

    Usable days link their index; other day folders render as plain
    ``YYYY-MM-DD (no daily index yet)``. Days in *mark* get a
    ``(CHANGED …)`` suffix for update briefs.
    """
    indexed = {d["day_str"]: d for d in days}
    catalog, missing = [], []
    for dirname in day_dirnames:
        day_str = f"{month_dir.parent.name}-{month_dir.name}-{int(dirname):02d}"
        if day_str in indexed:
            entry = f"[[{_vault_rel(_session, indexed[day_str]['index_path'])}|{day_str}]]"
            if day_str in mark:
                entry += " (CHANGED since last build — re-read fully)"
            catalog.append(entry)
        else:
            catalog.append(f"{day_str} (no daily index yet)")
            missing.append(day_str)
    return catalog, missing


def _month_changed_days(month_dir: Path, root: Path, stored_hash: str | None) -> tuple[list[str] | None, list[str], list[str]]:
    """Day-level changes in *month_dir* since its month index was built.

    Same git machinery as the daily pipeline (worktree ``status`` union
    committed-since-``last_checked_at``), mapped back onto days: a changed
    ``DD/index.md`` marks the day changed, a vanished day folder marks it
    removed. Per-mail changes beneath an UNCHANGED index, newly unindexed
    days, and month-folder hygiene (strays) surface as note lines — they
    need no re-read, but the synthesis and the check session should know.
    Returns (changed_or_None, removed, notes); None when git cannot tell,
    and the caller falls back to a full-synthesis brief.
    """
    try:
        year, mon = int(month_dir.parent.name), int(month_dir.name)
        rel = month_dir.relative_to(root).as_posix()
    except Exception:
        return None, [], []

    def _day_str(dirname: str) -> str | None:
        if len(dirname) != 2 or not dirname.isdigit():
            return None
        try:
            datetime.date(year, mon, int(dirname))
        except Exception:
            return None
        return f"{year:04d}-{mon:02d}-{int(dirname):02d}"

    names: set[str] = set()

    def _add(paths: list[str]) -> None:
        for path in paths:
            sub = path[len(rel) + 1:] if path.startswith(rel + "/") else path
            if sub and sub != "index.md":
                names.add(sub)

    status = _git_names(["status", "--porcelain=v1", "-z", "--no-renames", "-uall", "--", rel], root)
    if status is None:
        return None, [], []
    for entry in status:
        # -z entries are exactly `XY PATH` (2 status chars + space).
        path = entry[3:] if len(entry) > 3 and entry[2] == " " else entry
        _add([path])
    if stored_hash:
        # --no-renames: renames must surface as removed+added, or the
        # vanished name goes untracked (--name-only shows rename dest only).
        diff = _git_names(["diff", "--no-renames", "--name-only", "-z", stored_hash, "--", rel], root)
        if diff is not None:
            _add(diff)
    changed, removed, notes = [], [], []
    touched_days: set[str] = set()
    for sub in sorted(names):
        parts = sub.split("/")
        day = _day_str(parts[0]) if parts else None
        if day is None:
            notes.append(f"month-folder hygiene changed ({sub}) — catalog/frontmatter only, keep the body unless you spot an issue")
            continue
        touched_days.add(day)
        if len(parts) == 2 and parts[1] == "index.md":
            if (month_dir / parts[0] / "index.md").exists():
                changed.append(day)
            elif (month_dir / parts[0]).is_dir():
                notes.append(f"day {day} lost its index since the last build — dropped from the synthesis until update_timeline_daily rebuilds it")
            else:
                removed.append(day)
        elif not (month_dir / parts[0]).is_dir():
            removed.append(day)
        # per-mail changes beneath a day folder are handled below (pending
        # verdict depends on whether the day's index changed too)
    usable = {d["day_str"] for d in _collect_month_days(month_dir)[0]}
    changed = sorted({d for d in changed if d in usable})
    removed = sorted(set(removed))
    for day in sorted(touched_days - set(changed) - set(removed)):
        if day in usable:
            notes.append(f"day {day} has per-mail changes not yet reflected in its index — synthesize from the index as-is (daily rebuild pending)")
    return changed, removed, notes


def _month_sources_fingerprint(days: list[dict], strays: list[str]) -> str:
    """Content fingerprint of a month's sources (day key + full index text).

    Keyed by ``day_str``, not filename — every day index is named
    ``index.md``, so filenames alone would collide. Stray filenames feed the
    hash too, so cleaning them up retriggers a build. The month index commit
    itself never changes this — only real source changes do — so a matching
    fingerprint means "up to date" and can never loop.
    """
    import hashlib
    h = hashlib.sha1()
    for d in sorted(days, key=lambda d: d["day_str"]):
        h.update(d["day_str"].encode("utf-8") + b"\0")
        h.update(d["text"].encode("utf-8") + b"\0")
    for name in sorted(strays):
        h.update(b"stray\0" + name.encode("utf-8") + b"\0")
    return h.hexdigest()


def _decide_month_stale(*, index_exists: bool, fm_type, stored_fp: str | None, current_fp: str) -> tuple[bool, str]:
    """Pure staleness decision: rebuild when the month sources differ from the recorded fingerprint."""
    if not index_exists:
        return True, "no index.md"
    if fm_type != "monthly_summary":
        return True, f"legacy index.md (type {fm_type!r}) — regenerating"
    if not stored_fp:
        return True, "index.md has no sources_fingerprint — regenerating"
    if stored_fp != current_fp:
        return True, "month sources changed since last build"
    return False, "up to date"


def _build_monthly_index(month_str: str, aggregate: dict[str, list[str]], body: str, catalog: list[str], today_str: str, head_hash: str | None, fingerprint: str) -> str:
    """Assemble the month's ``index.md``: code-built frontmatter + session body + code-built catalog."""
    fm_lines = ["---", "type: monthly_summary", f"month: {month_str}", f"updated: {today_str}"]
    if head_hash is not None:
        fm_lines.append(f"last_checked_at: {head_hash}")
    fm_lines.append(f"sources_fingerprint: {fingerprint}")
    for field in DAY_FIELDS:
        fm_lines.append(f"{field}: {_yaml_flow_list(aggregate.get(field, []))}")
    fm_lines.append("---")
    text = "\n".join(fm_lines) + "\n\n" + body.strip() + "\n"
    if catalog:
        text += "\n## Tage\n\n" + "\n".join(f"- {entry}" for entry in catalog) + "\n"
    return text


def apply_month_dedup_to_day_indices(month_dir: Path, day_dirnames: list[str], pairs: list[tuple[str, str, str]], today_str: str) -> tuple[dict[str, list[str]], list[str]]:
    """Rewrite variant items to canonical form in the month's day ``index.md`` files.

    Mirrors the daily pipeline's fix-back, one level up: only ``DD/index.md``
    files with ``type: daily_summary`` are touched (legacy day catalogs are
    left for the daily pipeline), and only their frontmatter lists —
    ``updated:`` is bumped on touched files. Per-mail summary files are
    never rewritten here. Returns ({day_rel: [changes]}, hints).
    """
    fixed: dict[str, list[str]] = {}
    hints: list[str] = []
    for dirname in sorted(day_dirnames):
        fp = month_dir / dirname / "index.md"
        if not fp.exists():
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            hints.append(f"{dirname}/index.md: unreadable ({e}) — dedup skipped")
            continue
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        fm, _body, error = _parse_frontmatter(text)
        if error or not isinstance(fm, dict) or fm.get("type") != "daily_summary":
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
            fixed[f"{dirname}/index.md"] = changes
    return fixed, hints


def _apply_month_pairs(month_dir: Path, days: list[dict], day_dirnames: list[str], pairs: list[tuple[str, str, str]], today_str: str) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    """Apply validated month dedup pairs to both source layers in code.

    Day ``index.md`` frontmatter lists first, then the per-mail summary
    files inside usable days (via the daily pipeline's verbatim-match
    fix-back — files without the variant are untouched, ``updated:`` is
    bumped on touched ones). Days without a ``daily_summary`` index are
    skipped. Returns (fixed_day_indices, fixed_summaries, hints) with
    ``DD/``-prefixed keys for the per-mail layer.
    """
    fixed_files, hints = apply_month_dedup_to_day_indices(month_dir, day_dirnames, pairs, today_str)
    fixed_summaries: dict[str, list[str]] = {}
    for d in days:
        day_fixed, day_hints = apply_dedup_to_files(d["index_path"].parent, pairs, today_str)
        hints.extend(day_hints)
        for name, changes in day_fixed.items():
            fixed_summaries[f"{d['dirname']}/{name}"] = changes
    return fixed_files, fixed_summaries, hints


# ---------------------------------------------------------------------------
# Session-bound helpers
# ---------------------------------------------------------------------------

def _iter_month_dirs(root: Path):
    """Yield timeline/YYYY/MM month dirs, oldest first."""
    base = root / "timeline"
    if not base.is_dir():
        return
    for y in sorted(base.glob("[0-9]" * 4)):
        if not y.is_dir():
            continue
        for mo in sorted(y.glob("[0-9]" * 2)):
            if mo.is_dir():
                yield mo


def _spawn_month_session(_session, month_rel: str, month_str: str, brief: str):
    """Spawn the prose session for one month; returns (ok, session_pk_or_None, body_ref_or_error)."""
    from time import time

    stamp = month_str.replace("-", "")
    ok, _, session_pk, ref = _spawn_baseagent(
        _session,
        name=f"p{_session.model.pk}:monthly:{stamp}:{int(time())}",
        description=f"Monthly summary {month_rel}",
        brief=brief,
    )
    if not ok:
        return False, None, ref
    return True, session_pk, ref


def _spawn_month_check(_session, month_rel: str, month_str: str, brief: str):
    """Spawn the fire-and-forget double-check session for a written index.md."""
    from time import time

    stamp = month_str.replace("-", "")
    ok, _, session_pk, ref = _spawn_baseagent(
        _session,
        name=f"p{_session.model.pk}:monthlycheck:{stamp}:{int(time())}",
        description=f"Double-check {month_rel}/index.md",
        brief=brief,
    )
    if not ok:
        return False, {"status": "error", "month": month_rel, "message": f"double-check not spawned: {ref}"}
    return True, {"status": "dispatched", "month": month_rel, "session_pk": session_pk, "message": ref}


def update_timeline_monthly(_session: Session, limit: int = 2, month: str | None = None):
    """Rebuild stale month indexes (``timeline/YYYY/MM/index.md``).

    Sources are the month's day indices (``type: daily_summary``) — never
    raw mail or per-mail summaries. Staleness comes from a content
    fingerprint: a month needs work when its ``index.md`` is missing, is a
    legacy non-``monthly_summary`` file (e.g. the old ``type: index``
    catalogs), has no ``sources_fingerprint``, or the live day-index set
    differs from the recorded fingerprint (added/removed/rebuilt days —
    rebuilding a day automatically stales its month). The index commit
    itself never changes the fingerprint, so rebuilding can never retrigger
    itself. ``git`` is only used for the ``last_checked_at`` provenance hash.
    Each stale month (up to *limit*, oldest first — or just *month* as
    ``YYYY-MM``, which is always rebuilt) gets one baseagent prose session
    (body as last message, no file writes) plus one dedup query per
    non-trivial metadata field; months that already have a
    ``monthly_summary`` index get a focused update brief (only the changed
    days since the last build) instead of a full re-synthesis. All
    result-refs converge in
    ``write_month_index``, which propagates month dedup pairs into day
    indices and per-mail summaries, writes ``index.md`` in code, and spawns
    a double-check session. Months without usable day indices get no index
    (status ``pending`` — run ``update_timeline_daily`` first); truly empty
    month folders get a minimal code-written index (no session).
    Returns (True, {status, results}).
    """
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "message": "cannot resolve workspace root"}
    llm_query_tool = _session.get_tool("llm_query")
    if llm_query_tool is None:
        return False, {"status": "error", "message": "tool 'llm_query' is not available"}
    write_task = _session.get_task("write_month_index")
    if write_task is None:
        return False, {"status": "error", "message": "task 'write_month_index' is not available"}

    if month is not None:
        try:
            y, mo = month.split("-")
            if len(y) != 4 or len(mo) != 2:
                raise ValueError
            datetime.date(int(y), int(mo), 1)
        except Exception:
            return False, {"status": "error", "message": f"bad month '{month}' — want YYYY-MM"}
        month_dirs = [root / "timeline" / y / mo]
        if not month_dirs[0].is_dir():
            return False, {"status": "error", "message": f"month folder not found: timeline/{y}/{mo}"}
        explicit_month = True
    else:
        month_dirs = list(_iter_month_dirs(root))
        explicit_month = False

    # Read index facts for every candidate month; the vault HEAD is only
    # provenance for `last_checked_at` (one cheap rev-parse, optional).
    facts: dict[str, tuple[bool, object, str | None, str | None]] = {}
    for month_dir in month_dirs:
        try:
            datetime.date(int(month_dir.parent.name), int(month_dir.name), 1)
        except Exception:
            continue
        facts[_vault_rel(_session, month_dir)] = _read_index_facts(month_dir)
    head_hash = _git_head(root)

    results = []
    spawned = 0
    for month_dir in month_dirs:
        if spawned >= limit and not explicit_month:
            break
        rel = _vault_rel(_session, month_dir)
        if rel not in facts:
            continue  # not a real YYYY/MM month
        index_exists, fm_type, stored_hash, stored_fp = facts[rel]
        month_str = rel.split("timeline/")[-1].replace("/", "-")

        days, day_dirnames, strays, collect_hints = _collect_month_days(month_dir)
        current_fp = _month_sources_fingerprint(days, strays)
        if explicit_month:
            needs, reason = True, "explicitly requested"
        else:
            needs, reason = _decide_month_stale(
                index_exists=index_exists, fm_type=fm_type,
                stored_fp=stored_fp, current_fp=current_fp,
            )
        if not needs:
            if explicit_month:
                results.append({"month": rel, "status": "skipped", "message": f"up to date ({reason})"})
            continue

        if not days:
            if not day_dirnames and not strays:
                # Truly empty month folder — code-generate a minimal index, no session.
                today_str = datetime.datetime.now().date().isoformat()
                index_text = _build_monthly_index(
                    month_str, {f: [] for f in DAY_FIELDS},
                    f"# Summary for {month_str}\n\nNo entries for this month.\n",
                    [], today_str, head_hash, current_fp)
                try:
                    (month_dir / "index.md").write_text(index_text, encoding="utf-8")
                    results.append({"month": rel, "status": "success", "message": f"wrote minimal index.md ({reason}; no days, no session)"})
                except Exception as e:
                    results.append({"month": rel, "status": "error", "message": f"cannot write index.md: {e}"})
            else:
                results.append({"month": rel, "status": "pending",
                                "message": f"no usable daily_summary day indices ({len(day_dirnames)} day folders, {len(strays)} stray files) — run update_timeline_daily for {month_str} first"})
            continue

        aggregate = {f: list(_aggregate_day_lists(days).get(f, [])) for f in DAY_FIELDS}
        day_files = sorted(f"{d['dirname']}/index.md" for d in days)
        if index_exists and fm_type == "monthly_summary":
            m_changed, m_removed, m_notes = _month_changed_days(month_dir, root, stored_hash)
        else:
            m_changed, m_removed, m_notes = None, [], []
        if m_changed is not None and (m_changed or m_notes):
            # Update, not a fresh build: the session revises the existing
            # synthesis from the changed days only.
            tage, _missing = _tage_entries(_session, month_dir, days, day_dirnames, set(m_changed))
            brief = _build_month_update_brief(rel, month_str, tage, m_removed, m_notes)
            provenance = f"month update: {len(m_changed)} day(s) changed since last build"
            if m_changed:
                provenance += f" ({', '.join(m_changed[:6])}{' …' if len(m_changed) > 6 else ''})"
            collect_hints.append(provenance)
            collect_hints.extend(m_notes)
        else:
            brief = _build_month_session_brief(rel, month_str, day_files)
        ok, session_pk, body_ref = _spawn_month_session(
            _session, rel, month_str, brief)
        if not ok:
            results.append({"month": rel, "status": "error", "reason": reason, "message": f"prose session not spawned: {body_ref}"})
            continue
        # Fan out one tiny dedup query per field (list-only input, no
        # bodies). The prose ref and all dedup refs converge in
        # write_month_index, which the scheduler delivers once every ref
        # resolves — the same single-ref passing the daily pipeline relies on.
        field_refs: dict[str, object] = {}
        for field in DAY_FIELDS:
            items = aggregate.get(field, [])
            if len(set(items)) < 2:
                continue
            field_refs[field] = llm_query_tool.delay(messages=[
                {"role": "system", "content": "You are a list deduplication expect, you immediately see if a list contains duplicates or not"},
                {"role": "user", "content": DEDUP_FIELD_PROMPT.format(
                    field=field,
                    field_singular=_FIELD_SINGULAR[field],
                    field_plural=_FIELD_PLURAL[field],
                    day_str=month_str,
                    count=len(items),
                    items="\n".join(f"- {item}" for item in items),
                )},
            ])
        kwargs: dict[str, object] = {
            "month_path": rel, "month_str": month_str, "body_result": body_ref, "session_pk": session_pk,
            "aggregate": aggregate, "collect_hints": collect_hints, "head_hash": head_hash,
        }
        kwargs.update({f"{field}_result": ref for field, ref in field_refs.items()})
        write_ref = write_task.delay(**kwargs)
        results.append({"month": rel, "status": "dispatched", "session_pk": session_pk,
                        "reason": reason, "dedup_fields": sorted(field_refs), "write": write_ref})
        spawned += 1
    return True, {"status": "success", "results": results}


def write_month_index(_session, month_path, month_str=None, body_result=None, session_pk=None, aggregate=None, collect_hints=None, head_hash=None,
                      tags_result=None, persons_result=None, companies_result=None, groups_result=None, products_result=None):
    """Merge a prose body with code-owned metadata into a month's ``index.md``.

    ``body_result`` is the prose session's message ref and ``session_pk``
    its session: the body is resolved from the ref, else from the session's
    explicit final_result args, else from its last assistant message (agents
    end turns with plain text — final_result has no recorded calls, so the
    history is the reliable source). Each ``*_result`` is one field-dedup
    LLM output (``canonical, variant`` lines, or the ``none`` sentinel). The
    scheduler delivers this task once every ref resolves. Pairs are
    re-validated against a freshly recomputed aggregate — invented variants
    are ignored — then applied back into the month's sources in code: the
    day ``index.md`` frontmatter lists plus the per-mail summary files
    inside usable days (variant → canonical, ``updated:`` bumped).
    ``index.md`` is written in one go: code-built frontmatter (canonical
    lists, ``type: monthly_summary``, ``last_checked_at``) + session body +
    code-built ``## Tage`` catalog. Afterwards a fire-and-forget
    double-check session verifies the file.

    The only failure is "nothing could be written": empty body, an
    unresolvable month folder, or day indices that vanished between dispatch
    and write. Returns (True, {status, month_path, index_path, dedup_pairs,
    fixed_files, fixed_summaries, indexed_days, missing_days, check,
    lint_results, message}) on success.
    """
    aggregate = {f: list((aggregate or {}).get(f, [])) for f in DAY_FIELDS}
    collect_hints = list(collect_hints or [])
    root = _workspace_root(_session)
    if root is None:
        return False, {"status": "error", "month_path": month_path, "message": "write_month_index: cannot resolve workspace root"}
    month_dir = (root / month_path) if not Path(month_path).is_absolute() else Path(month_path)
    if not month_dir.is_dir():
        return False, {"status": "error", "month_path": month_path, "message": f"write_month_index: month folder not found: {month_path}"}
    if month_str is None:
        try:
            datetime.date(int(month_dir.parent.name), int(month_dir.name), 1)
            month_str = f"{month_dir.parent.name}-{month_dir.name}"
        except Exception:
            return False, {"status": "error", "month_path": month_path, "message": f"write_month_index: not a YYYY/MM folder: {month_path}"}

    fr_text, hist_text = _read_child_session_texts(session_pk)
    body, body_source = _pick_body([
        ("ref", _extract_result_text(body_result)),
        ("final_result", fr_text),
        ("last_message", hist_text),
    ])
    if body is None:
        return False, {
            "status": "error",
            "month_path": month_path,
            "lint_results": [f"prose session returned no usable body ({body_source}) — nothing was written"],
            "message": "write_month_index: body empty or too short, file could not be written",
        }

    lint_results = list(collect_hints)
    lint_results.extend(_validate_body(month_str, body))

    days, day_dirnames, strays, fresh_hints = _collect_month_days(month_dir)
    lint_results.extend(fresh_hints)
    if not days:
        return False, {
            "status": "error",
            "month_path": month_path,
            "lint_results": lint_results,
            "message": "write_month_index: no usable daily_summary day indices at write time — nothing was written",
        }
    fresh = _aggregate_day_lists(days)
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
            continue
        field_pairs, field_hints = _parse_pair_lines(text, field, fresh.get(field, []))
        pairs.extend(field_pairs)
        lint_results.extend(field_hints)

    canonical = {f: _canonicalize_list(fresh.get(f, []), f, pairs) for f in DAY_FIELDS}
    today_str = datetime.datetime.now().date().isoformat()
    fixed_files, fixed_summaries, fix_hints = _apply_month_pairs(month_dir, days, day_dirnames, pairs, today_str)
    lint_results.extend(fix_hints)
    # Fingerprint AFTER the fixes, so the dedup pass's own edits are covered
    # and can never flag the month stale again. Re-collect: the fix-back
    # changed the day index texts the fingerprint hashes over. (The
    # per-mail fixes additionally stale the fixed days — the daily pipeline
    # rebuilds them, which stales the month exactly once more, and the next
    # month pass settles on already-unified lists.)
    days = _collect_month_days(month_dir)[0]
    fingerprint = _month_sources_fingerprint(days, strays)
    catalog, missing = _tage_entries(_session, month_dir, days, day_dirnames)
    indexed = {d["day_str"] for d in days}
    today_str = datetime.datetime.now().date().isoformat()
    try:
        (month_dir / "index.md").write_text(
            _build_monthly_index(month_str, canonical, body, catalog, today_str, head_hash, fingerprint), encoding="utf-8")
    except Exception as e:
        return False, {
            "status": "error",
            "month_path": month_path,
            "lint_results": lint_results,
            "message": f"write_month_index: cannot write index.md: {e}",
        }

    check_ok, check_info = _spawn_month_check(
        _session, _vault_rel(_session, month_dir), month_str,
        _build_month_check_brief(_vault_rel(_session, month_dir), month_str,
                                 sorted(f"{d['dirname']}/index.md" for d in days), lint_results))

    return True, {
        "status": "success",
        "month_path": month_path,
        "index_path": _vault_rel(_session, month_dir / "index.md"),
        "dedup_pairs": [f"{f}: {c}, {v}" for f, c, v in pairs],
        "fixed_files": fixed_files,
        "fixed_summaries": fixed_summaries,
        "indexed_days": sorted(indexed),
        "missing_days": missing,
        "check": check_info,
        "lint_results": lint_results,
        "message": f"write_month_index: wrote {month_path}/index.md ({len(indexed)} days indexed, {len(missing)} missing, {len(pairs)} dedup pairs, {len(fixed_files)} day indices + {len(fixed_summaries)} summaries fixed, double-check {'dispatched' if check_ok else 'FAILED TO SPAWN'})",
    }
