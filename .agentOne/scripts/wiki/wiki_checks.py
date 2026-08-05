from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


WIKILINK_RE = re.compile(r'\[\[([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]')
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)
REQUIRED_FM_FIELDS = ('type', 'date', 'updated', 'tags', 'sources')
CHECK_NAMES = ("dead_wikilinks", "link_format", "orphan_pages", "missing_index", "stale_index_entries", "frontmatter", "folder_structure", "encoding", "filenames")


def _resolve_folder(folder: str | None, session: Any | None) -> str | None:
    if folder is not None:
        p = Path(folder)
        if not p.is_absolute() and session is not None:
            folder = (Path(session.workspace.path) / p).resolve().as_posix()
        return folder

    if session is None:
        return None

    version = session.get_version_model()

    # The calling session itself is a wiki agent session → use its own workspace.
    if version.agent.name == "wiki" and version.workspace is not None:
        return version.workspace.path

    from server.models.sessions.session_version import SessionVersionModel
    wiki_paths = list(
        SessionVersionModel.objects.filter(
            parent_session_version=version,
            agent__name="wiki",
            workspace__isnull=False,
        ).values_list("workspace__path", flat=True).distinct()
    )
    if len(wiki_paths) == 1:
        return wiki_paths[0]
    return None


def _iter_md_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def _strip_code_fences(text: str) -> str:
    stripped = []
    in_fence = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped.append(line)
    return "\n".join(stripped)


def _strip_inline_code(text: str) -> str:
    return re.sub(r'`[^`]+`', '', text)


def _extract_wikilinks(text: str) -> list[str]:
    text = _strip_code_fences(text)
    text = _strip_inline_code(text)
    return [match[0].strip() for match in WIKILINK_RE.findall(text)]


def _resolve_wikilink_target(link: str, source_dir: Path, root: Path) -> Path | None:
    target = link.strip()
    if not target:
        return None
    if target.startswith("http://") or target.startswith("https://"):
        return None

    def _try_resolve(t: str) -> Path | None:
        t = t.strip()
        if not t:
            return None
        p = Path(t)
        has_ext = "." in p.name
        raw_candidates: list[Path] = []
        if p.is_absolute():
            raw_candidates.append(p)
        else:
            raw_candidates.append((source_dir / p).resolve())
            raw_candidates.append((root / p).resolve())
        for candidate in raw_candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
            if candidate.is_dir():
                idx = candidate / "index.md"
                if idx.exists():
                    return idx
        if not has_ext:
            for candidate in raw_candidates:
                with_md = candidate.with_suffix(".md")
                if with_md.exists() and with_md.is_file():
                    return with_md
        return None

    result = _try_resolve(target)
    if result is not None:
        return result

    # Try with URL-decoded name (disk has umlauts, link has percent-encoding)
    try:
        import urllib.parse
        decoded = urllib.parse.unquote(target)
        if decoded != target:
            result = _try_resolve(decoded)
            if result is not None:
                return result
    except Exception:
        pass

    for sep in ("#", "^"):
        parts = target.rsplit(sep, 1)
        if len(parts) == 2 and parts[1]:
            result = _try_resolve(parts[0])
            if result is not None:
                return result

    # Try prepending ../ for links that appear root-relative from subdirectories
    if not target.startswith("../"):
        depth = len(str(source_dir.relative_to(root)).split("/")) if source_dir != root else 0
        for ups in range(1, depth + 1):
            result = _try_resolve("../" * ups + target)
            if result is not None:
                return result

    return None


def _parse_frontmatter(content: str) -> dict | None:
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None
    fm: dict = {}
    for line in m.group(1).strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def _fix_source_to_sources(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    fm_text = m.group(1)
    new_fm_lines = []
    changed = False
    for line in fm_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("source:") or stripped == "source:":
            _, _, val = stripped.partition(":")
            val = val.strip().strip('"').strip("'")
            if val:
                new_fm_lines.append("sources:")
                new_fm_lines.append(f"  - \"{val}\"")
            else:
                new_fm_lines.append("sources: []")
            changed = True
        else:
            new_fm_lines.append(line)
    if not changed:
        return text
    new_fm = "\n".join(new_fm_lines)
    return text[:m.start(1)] + new_fm + text[m.end(1):]


def _autofix_link(fp: Path, old_link: str, new_link: str) -> bool:
    """Replace ``[[old_link]]`` / ``[[old_link|...]]`` with ``[[new_link]]`` in *fp*.

    Returns True when the file was modified.
    """
    try:
        text = fp.read_text(encoding="utf-8")
    except Exception:
        return False
    old_bracketed = f"[[{old_link}]]"
    new_bracketed = f"[[{new_link}]]"
    if old_bracketed in text:
        new_text = text.replace(old_bracketed, new_bracketed)
    else:
        old_re = re.compile(r'\[\[' + re.escape(old_link) + r'\|')
        new_text = old_re.sub(f'[[{new_link}|', text)
    if new_text == text:
        return False
    fp.write_text(new_text, encoding="utf-8")
    return True


def _fix_utf8(fp: Path) -> tuple[bool, str | None]:
    """Attempt to fix broken UTF-8 in a file.

    Returns (modified, error_message). On success with modifications,
    error_message is None. On failure, returns (False, error).
    """
    try:
        raw = fp.read_bytes()
    except Exception as e:
        return (False, f"read error: {e}")

    # First, try to decode as UTF-8 (strict) - if it works, nothing to fix
    try:
        raw.decode("utf-8")
        return (False, None)  # Already valid UTF-8
    except UnicodeDecodeError:
        pass

    # Try common fixes
    fixed = None

    # 1. Replace invalid bytes with replacement character
    try:
        fixed = raw.decode("utf-8", errors="replace")
    except Exception:
        pass

    # 2. If that didn't produce clean text, try latin-1 -> utf-8 (common mojibake)
    if fixed is None or "�" in fixed:
        try:
            # latin-1 never fails, maps bytes 0-255 directly to unicode
            as_latin1 = raw.decode("latin-1")
            # Re-encode to UTF-8
            fixed = as_latin1
        except Exception:
            pass

    # 3. Try cp1252 (Windows) -> utf-8
    if fixed is None or "�" in fixed:
        try:
            fixed = raw.decode("cp1252")
        except Exception:
            pass

    if fixed is None:
        return (False, "could not decode with any strategy")

    # Check if the fixed version is actually different and valid
    try:
        fixed.encode("utf-8")
    except Exception as e:
        return (False, f"fixed version still invalid: {e}")

    # Write back
    try:
        fp.write_text(fixed, encoding="utf-8")
        return (True, None)
    except Exception as e:
        return (False, f"write error: {e}")


_YEAR_SEGMENT_RE = re.compile(r'^[12]\d{3}$')


def _is_year_segment(seg: str) -> bool:
    return bool(_YEAR_SEGMENT_RE.match(seg)) and 2000 <= int(seg) <= 2030


_YMD_SEGMENT_RE = re.compile(r'^(19|20)\d{6}$')


def _is_ymd_segment(seg: str) -> bool:
    if not _YMD_SEGMENT_RE.match(seg):
        return False
    y = int(seg[:4])
    m = int(seg[4:6])
    d = int(seg[6:8])
    return 2000 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31


def _looks_like_ymd(seg: str) -> bool:
    """Check if segment matches YYYYMMDD pattern (without validating month/day)."""
    return bool(_YMD_SEGMENT_RE.match(seg))


def _folder_structure_issues(rel: str) -> list[str]:
    """Return structural problems found in a vault-root-relative path.

    Detects:
    - Multiple year segments: a date folder nested inside another date
      folder, e.g. ``timeline/2020/2020`` or ``timeline/2021/02/2021/02/08``
    - Invalid month/day values in date-stamped paths (e.g. month 13, day 32)
    - YYYYMMDD segment appearing after year/month (e.g. ``timeline/2020/10/20201023``)
      - Also validates month/day within the YYYYMMDD segment
    """
    segments = rel.split("/")
    issues: list[str] = []
    year_idx = [i for i, s in enumerate(segments) if _is_year_segment(s)]
    if len(year_idx) >= 2:
        years = [segments[i] for i in year_idx]
        issues.append("multiple year segments: " + " / ".join(years))
    if year_idx:
        y = year_idx[0]
        if y + 1 < len(segments):
            nxt = segments[y + 1]
            if nxt.isdigit() and len(nxt) <= 2:
                mm = int(nxt)
                if mm < 1 or mm > 12:
                    issues.append(f"invalid month '{nxt}' after year '{segments[y]}'")
            # Always check the segment after month for day or YYYYMMDD
            if y + 2 < len(segments):
                nxt2 = segments[y + 2]
                if nxt2.isdigit() and len(nxt2) <= 2:
                    dd = int(nxt2)
                    if dd < 1 or dd > 31:
                        issues.append(f"invalid day '{nxt2}' after '{segments[y]}/{nxt}'")
                elif _looks_like_ymd(nxt2):
                    issues.append(f"YYYYMMDD segment '{nxt2}' after year/month '{segments[y]}/{nxt}'")
                    # Also validate month/day within the YYYYMMDD
                    ymd_mm = int(nxt2[4:6])
                    ymd_dd = int(nxt2[6:8])
                    if ymd_mm < 1 or ymd_mm > 12:
                        issues.append(f"invalid month '{ymd_mm}' in YYYYMMDD '{nxt2}'")
                    elif ymd_dd < 1 or ymd_dd > 31:
                        issues.append(f"invalid day '{ymd_dd}' in YYYYMMDD '{nxt2}'")
    return issues


_FS_RESERVED_CHARS = frozenset('\\/:*?"<>|')


def _filename_issues(name: str) -> list[str]:
    """Return problems found in a single filename (not a full path).

    Detects broken/illegal filenames:
    - Invalid UTF-8 bytes (presented by the OS as lone surrogates)
    - Control characters (U+0000-U+001F, U+007F)
    - Reserved characters that break on Windows/many tools
      (``\\ / : * ? " < > |``)
    - Trailing dot or space (invisible/ambiguous on Windows)
    """
    issues: list[str] = []
    for ch in name:
        cp = ord(ch)
        if ch in _FS_RESERVED_CHARS:
            issues.append(f"reserved character '{ch}'")
        elif cp < 32 or cp == 127:
            issues.append(f"control character U+{cp:04X}")
        elif 0xDC80 <= cp <= 0xDCFF:
            issues.append(f"invalid UTF-8 byte ({hex(cp)})")
    if name != name.rstrip(". "):
        issues.append("trailing dot or space")
    return issues


def _valid_filename_suggestion(name: str) -> str:
    """Return a filesystem-safe version of *name*, replacing offending chars.

    Only used for suggestions — never auto-applied (renaming a file would
    break its wikilinks).
    """
    out: list[str] = []
    for ch in name:
        cp = ord(ch)
        if ch in _FS_RESERVED_CHARS:
            out.append("_")
        elif cp < 32 or cp == 127:
            out.append("_")
        elif 0xDC80 <= cp <= 0xDCFF:
            out.append("\uFFFD")
        else:
            out.append(ch)
    return "".join(out).rstrip(". ")


def wiki_check(
    _session: Any,
    folder: str | None = None,
    limit: int = 20,
    checks: str = "",
    files: str = "",
    autofix: bool = False,
) -> tuple[bool, dict]:
    """Run deterministic code checks on a wiki vault.

    Scans Markdown files for:
    - Dead wikilinks (target file doesn't exist)
    - Link-format violations (bare filenames, ``../`` relative chains,
      filesystem-absolute paths — all links should be vault-root-relative)
    - Orphan pages (no inbound wikilinks from non-archive pages)
    - Missing ``index.md`` files in subdirectories
    - Stale entries in ``index.md`` that point to non-existent files
    - Missing or invalid YAML frontmatter
    - Folder-structure problems (duplicated date segments such as
      ``2020/2020``, invalid month/day values)
    - Broken filenames (invalid UTF-8 bytes, control characters,
      reserved characters such as ``/ : * ?``, trailing dots/spaces)

    Files under ``raw/`` are excluded from all checks (immutable sources).

    Results are capped to *limit* entries per check category. Use
    ``limit=0`` to return all findings.

    Fix suggestions (``suggestion`` / ``can_autofix`` keys) are included on every
    dead wikilink whose filename matches exactly one file in the vault.
    Pass *autofix=True* to also apply them (files are modified on disk).

    Args:
        _session: The calling agent's session (bound automatically).
        folder: Optional wiki root path. When omitted and there is exactly
            one subsession with agent type ``wiki``, its workspace is used.
        limit: Max findings to return per check category. ``0`` means no limit.
            Default: 20.
        checks: Comma-separated check names to run, or ``""`` / ``"all"``
            for all checks. Valid names: ``dead_wikilinks``, ``link_format``,
            ``orphan_pages``, ``missing_index``, ``stale_index_entries``,
            ``frontmatter``, ``folder_structure``, ``encoding``,
            ``filenames``.
            Default: ``""`` (all).
        files: Comma-separated file paths or glob patterns (relative to wiki
            root) to scope the check to. Supports ``*``, ``?``, ``**``
            wildcards. When non-empty, only matching files are scanned.
            Default: ``""`` (scan all non-raw files).
        autofix: Auto-fix unambiguous dead wikilinks and source→sources.
            Default: False.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - folder: str (resolved path)
            - total_files: int (non-raw files scanned)
            - checks: list of dicts, each with:
                - check: str
                - total: int (population size)
                - wrong: int (issues found)
                - correct: int (total - wrong)
                - returned: int (items returned after cap)
                - items: list of findings (capped to *limit*)
                When *autofix* is True, dead-wikilink items include
                ``can_autofix`` and ``suggestion`` keys.
            - total_issues: int
            - total_ok: int
            - returned: int
            - omitted: int (capped-away items across all checks)
            - message: str (human-readable summary)
        On error, result contains:
            - status: "error"
            - message: str
    """
    import re
    try:
        resolved = _resolve_folder(folder, _session)
        if resolved is None:
            if _session is None:
                return (False, {"status": "error", "message": "folder is required when no session is available"})
            from server.models.sessions.session_version import SessionVersionModel
            wiki_paths = list(
                SessionVersionModel.objects.filter(
                    parent_session_version=_session.get_version_model(),
                    agent__name="wiki",
                    workspace__isnull=False,
                ).values_list("workspace__path", flat=True).distinct()
            )
            if not wiki_paths:
                return (False, {"status": "error", "message": "no wiki folder found"})
            path_list = "\n".join(f"  - {p}" for p in wiki_paths)
            return (False, {
                "status": "error",
                "message": f"more than one wiki folder found:\n{path_list}\nfolder parameter mandatory",
            })

        root = Path(resolved).resolve()
        if not root.is_dir():
            return (False, {"status": "error", "message": f"folder not found: {resolved}"})

        all_md_files = _iter_md_files(root)

        basename_index: dict[str, list[str]] = {}
        for fp in all_md_files:
            rel = fp.relative_to(root).as_posix()
            basename_index.setdefault(fp.name, []).append(rel)

        def _find_unique_target(link_text: str, source_rel: str | None = None) -> str | None:
            def _pick_candidate(name: str) -> str | None:
                candidates = basename_index.get(name, [])
                if not candidates:
                    return None
                if len(candidates) == 1:
                    return candidates[0]
                if len(candidates) > 10:
                    return None
                if source_rel is None:
                    return None
                source_dir = str(Path(source_rel).parent)
                scored = []
                for c_rel in candidates:
                    if c_rel == source_rel:
                        continue
                    c_dir = str(Path(c_rel).parent)
                    common = len(os.path.commonpath([source_dir, c_dir]).split("/"))
                    scored.append((common, c_rel))
                if not scored:
                    return None
                scored.sort(key=lambda x: -x[0])
                if scored[0][0] >= 1:
                    return scored[0][1]
                return None

            def _best_match(t: str) -> str | None:
                if not t:
                    return None
                name = Path(t).name
                if not name:
                    return None
                result = _pick_candidate(name)
                if result is not None:
                    return result
                if "." not in name:
                    result = _pick_candidate(name + ".md")
                    if result is not None:
                        return result
                return None

            result = _best_match(link_text.strip())
            if result is not None:
                return result
            for sep in ("#", "^"):
                parts = link_text.rsplit(sep, 1)
                if len(parts) == 2 and parts[1]:
                    result = _best_match(parts[0].strip())
                    if result is not None:
                        return result
            return None

        def _depth_adjust(link: str, source_dir: Path, root: Path) -> str | None:
            if not link.startswith("../"):
                return None
            for offset in (-1, 1, -2, 2):
                if offset < 0:
                    adj = re.sub(r'^\.\./', '', link, count=abs(offset))
                else:
                    adj = "../" * offset + link
                candidate = (source_dir / adj).resolve()
                if candidate.exists() and candidate.is_file():
                    try:
                        return candidate.relative_to(root).as_posix()
                    except ValueError:
                        return adj
            return None

        md_files = [fp for fp in all_md_files if not fp.relative_to(root).as_posix().startswith("raw/")]

        if files:
            patterns = [f.strip() for f in files.split(",")]
            md_files = [
                fp for fp in md_files
                if any(fp.relative_to(root).as_posix() == p or fp.relative_to(root).match(p) for p in patterns)
            ]

        findings: list[dict] = []

        inlinks: dict[str, set[str]] = {}
        outlinks: dict[str, set[str]] = {}
        for fp in md_files:
            rel = fp.relative_to(root).as_posix()
            inlinks.setdefault(rel, set())
            outlinks.setdefault(rel, set())

        total_wikilinks = 0
        for fp in md_files:
            rel = fp.relative_to(root).as_posix()
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            for link in _extract_wikilinks(text):
                total_wikilinks += 1
                target_path = _resolve_wikilink_target(link, fp.parent, root)
                if target_path:
                    try:
                        target_rel = target_path.relative_to(root).as_posix()
                    except ValueError:
                        continue
                    outlinks[rel].add(target_rel)
                    if target_rel in inlinks:
                        inlinks[target_rel].add(rel)

        effective_limit = None if limit == 0 else limit

        def _run_check(name: str) -> bool:
            return not checks or checks == "all" or name in [c.strip() for c in checks.split(",")]

        def _cap(items: list, limit: int | None) -> list:
            return items[:limit] if limit else items

        omitted_total = 0
                        
        if _run_check("dead_wikilinks"):
            dead: list[dict] = []
            for fp in md_files:
                rel = fp.relative_to(root).as_posix()
                try:
                    text = fp.read_text(encoding="utf-8")
                except Exception:
                    continue
                for link in _extract_wikilinks(text):
                    if link.startswith("http://") or link.startswith("https://"):
                        total_wikilinks -= 1
                        continue
                    if link.endswith("/.."):
                        total_wikilinks -= 1
                        continue
                    if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}/', link):
                        total_wikilinks -= 1
                        continue
                    target_path = _resolve_wikilink_target(link, fp.parent, root)
                    if target_path is None:
                        item: dict[str, Any] = {
                            "file": rel,
                            "link": link,
                        }
                        adj = _depth_adjust(link, fp.parent, root)
                        if adj is not None:
                            item["can_autofix"] = True
                            item["suggestion"] = adj
                        else:
                            unique = _find_unique_target(link, source_rel=rel)
                            if unique is not None:
                                item["can_autofix"] = True
                                item["suggestion"] = unique
                        dead.append(item)
            if autofix:
                autofix_count_dead = 0
                for item in dead:
                    if "suggestion" not in item:
                        continue
                    fp = root / item["file"]
                    item["autofixed"] = _autofix_link(fp, item["link"], item["suggestion"])
                    if item["autofixed"]:
                        autofix_count_dead += 1
            capped = _cap(dead, effective_limit)
            omitted_total += len(dead) - len(capped)
            findings.append({
                "check": "dead_wikilinks",
                "total": total_wikilinks,
                "wrong": len(dead),
                "correct": total_wikilinks - len(dead),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("link_format"):
            # Enforce the vault convention: every wikilink must be a
            # vault-root-relative path (e.g. ``[[timeline/2021/02/08/Note]]``).
            # Bare filenames ("shortest path"), ``../`` relative chains and
            # filesystem-absolute ``/`` links are flagged, with a suggestion
            # rewritten to the vault-root-relative form.
            format_total = 0
            fmt_issues: list[dict] = []
            for fp in md_files:
                rel = fp.relative_to(root).as_posix()
                try:
                    text = fp.read_text(encoding="utf-8")
                except Exception:
                    continue
                for link in _extract_wikilinks(text):
                    if link.startswith("http://") or link.startswith("https://"):
                        continue
                    if link.endswith("/.."):
                        continue
                    format_total += 1
                    bare_part = link
                    for sep in ("#", "^"):
                        bare_part = bare_part.split(sep, 1)[0]
                    is_bare = "/" not in bare_part
                    is_relative = (
                        link.startswith("../")
                        or link.startswith("./")
                        or "/../" in link
                        or "/./" in link
                    )
                    is_fs_abs = link.startswith("/")
                    if not (is_bare or is_relative or is_fs_abs):
                        continue
                    if is_relative:
                        issue = "relative path - use a vault-root-relative path"
                    elif is_fs_abs:
                        issue = "filesystem-absolute path - use a vault-root-relative path"
                    else:
                        issue = "bare filename - use a vault-root-relative path"
                    item: dict[str, Any] = {"file": rel, "link": link, "issue": issue}
                    suffix = ""
                    resolved = _resolve_wikilink_target(link, fp.parent, root)
                    if resolved is None:
                        for sep in ("#", "^"):
                            parts = link.rsplit(sep, 1)
                            if len(parts) == 2 and parts[1]:
                                base, suffix = parts[0], sep + parts[1]
                                resolved = _resolve_wikilink_target(base, fp.parent, root)
                                break
                    if resolved is not None:
                        try:
                            item["suggestion"] = resolved.relative_to(root).as_posix() + suffix
                            item["can_autofix"] = True
                        except ValueError:
                            pass
                    else:
                        unique = _find_unique_target(link, source_rel=rel)
                        if unique is not None:
                            item["suggestion"] = unique + suffix
                            item["can_autofix"] = True
                    fmt_issues.append(item)
            if autofix:
                for item in fmt_issues:
                    if not item.get("can_autofix"):
                        continue
                    fp = root / item["file"]
                    item["autofixed"] = _autofix_link(fp, item["link"], item["suggestion"])
            capped = _cap(fmt_issues, effective_limit)
            omitted_total += len(fmt_issues) - len(capped)
            findings.append({
                "check": "link_format",
                "total": format_total,
                "wrong": len(fmt_issues),
                "correct": format_total - len(fmt_issues),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("orphan_pages"):
            eligible = sorted(
                k for k in inlinks
                if k != "index.md" and not k.startswith("archive/")
            )
            orphans = sorted(k for k in eligible if not inlinks[k])
            capped = _cap(orphans, effective_limit)
            omitted_total += len(orphans) - len(capped)
            findings.append({
                "check": "orphan_pages",
                "total": len(eligible),
                "wrong": len(orphans),
                "correct": len(eligible) - len(orphans),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("missing_index"):
            dirs_with_md: set[Path] = set()
            for fp in md_files:
                dirs_with_md.add(fp.parent)
            dirs_to_check = sorted(d for d in dirs_with_md if d != root)
            missing_index: list[str] = []
            for d in dirs_to_check:
                idx = d / "index.md"
                if not idx.exists():
                    missing_index.append(str(d.relative_to(root).as_posix()) + "/")
            capped = _cap(missing_index, effective_limit)
            omitted_total += len(missing_index) - len(capped)
            findings.append({
                "check": "missing_index",
                "total": len(dirs_to_check),
                "wrong": len(missing_index),
                "correct": len(dirs_to_check) - len(missing_index),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("stale_index_entries"):
            total_index_links = 0
            stale: list[dict] = []
            for fp in md_files:
                if fp.name != "index.md":
                    continue
                rel = fp.relative_to(root).as_posix()
                try:
                    text = fp.read_text(encoding="utf-8")
                except Exception:
                    continue
                for link in _extract_wikilinks(text):
                    total_index_links += 1
                    target_path = _resolve_wikilink_target(link, fp.parent, root)
                    if target_path is None:
                        stale.append({
                            "file": rel,
                            "link": link,
                        })
            capped = _cap(stale, effective_limit)
            omitted_total += len(stale) - len(capped)
            findings.append({
                "check": "stale_index_entries",
                "total": total_index_links,
                "wrong": len(stale),
                "correct": total_index_links - len(stale),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("frontmatter"):
            fm_issues: list[dict] = []
            for fp in md_files:
                rel = fp.relative_to(root).as_posix()
                try:
                    text = fp.read_text(encoding="utf-8")
                except Exception:
                    continue
                fm = _parse_frontmatter(text)
                if fm is None:
                    fm_issues.append({
                        "file": rel,
                        "issue": "missing frontmatter",
                    })
                else:
                    is_index = fp.name.lower() == "index.md"
                    required = ("type", "updated") if is_index else REQUIRED_FM_FIELDS
                    if not is_index and "source" in fm and "sources" not in fm:
                        fm_issues.append({
                            "file": rel,
                            "issue": "source should be sources (singular -> plural)",
                            "can_autofix": True,
                        })
                        fm["sources"] = fm["source"]
                    missing = [f for f in required if f not in fm]
                    if missing:
                        fm_issues.append({
                            "file": rel,
                            "issue": f"missing fields: {', '.join(missing)}",
                        })
            if autofix:
                for item in fm_issues:
                    if not item.get("can_autofix"):
                        continue
                    fp = root / item["file"]
                    try:
                        text = fp.read_text(encoding="utf-8")
                    except Exception:
                        item["autofixed"] = False
                        continue
                    new_text = _fix_source_to_sources(text)
                    if new_text != text:
                        fp.write_text(new_text, encoding="utf-8")
                        item["autofixed"] = True
                    else:
                        item["autofixed"] = False
            capped = _cap(fm_issues, effective_limit)
            omitted_total += len(fm_issues) - len(capped)
            findings.append({
                "check": "frontmatter",
                "total": len(md_files),
                "wrong": len(fm_issues),
                "correct": len(md_files) - len(fm_issues),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("folder_structure"):
            # Scan the vault directory layout (non-raw folders + markdown
            # files) for structural problems: duplicated/overlapping date
            # segments (e.g. ``2020/2020``, ``2021/02/2021/02/08``) and
            # invalid month/day values.  Only the shortest offending path is
            # reported; its descendants are suppressed.
            dirs: list[str] = []
            if not files:
                for d in root.rglob("*"):
                    if not d.is_dir():
                        continue
                    rel = d.relative_to(root).as_posix()
                    if rel.startswith("raw/") or any(s.startswith(".") for s in rel.split("/")):
                        continue
                    dirs.append(rel)
            candidate: set[str] = set(dirs)
            for fp in md_files:
                rel = fp.relative_to(root).as_posix()
                candidate.add(rel)
                if files:
                    d = fp.parent
                    while d != root:
                        candidate.add(d.relative_to(root).as_posix())
                        d = d.parent
            ordered = sorted(candidate, key=lambda p: (p.count("/"), p))
            structure: list[dict] = []
            reported: list[str] = []
            for p in ordered:
                if any(p == r or p.startswith(r + "/") for r in reported):
                    continue
                issues = _folder_structure_issues(p)
                if issues:
                    structure.append({"folder": p, "issues": issues})
                    reported.append(p)
            capped = _cap(structure, effective_limit)
            omitted_total += len(structure) - len(capped)
            findings.append({
                "check": "folder_structure",
                "total": len(candidate),
                "wrong": len(structure),
                "correct": len(candidate) - len(structure),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("encoding"):
            encoding_issues: list[dict] = []
            for fp in md_files:
                rel = fp.relative_to(root).as_posix()
                try:
                    fp.read_text(encoding="utf-8")
                except UnicodeDecodeError as e:
                    item: dict[str, Any] = {
                        "file": rel,
                        "issue": f"UTF-8 decode error: {e.reason} at byte {e.start}",
                    }
                    if autofix:
                        modified, err = _fix_utf8(fp)
                        item["autofixed"] = modified
                        if err:
                            item["autofix_error"] = err
                        else:
                            item["can_autofix"] = True
                    else:
                        item["can_autofix"] = True
                    encoding_issues.append(item)
                except Exception as e:
                    encoding_issues.append({
                        "file": rel,
                        "issue": f"read error: {e}",
                    })
            if autofix:
                for item in encoding_issues:
                    if not item.get("can_autofix") or item.get("autofixed") is not None:
                        continue
                    fp = root / item["file"]
                    modified, err = _fix_utf8(fp)
                    item["autofixed"] = modified
                    if err:
                        item["autofix_error"] = err
            capped = _cap(encoding_issues, effective_limit)
            omitted_total += len(encoding_issues) - len(capped)
            findings.append({
                "check": "encoding",
                "total": len(md_files),
                "wrong": len(encoding_issues),
                "correct": len(md_files) - len(encoding_issues),
                "returned": len(capped),
                "items": capped,
            })

        if _run_check("filenames"):
            # Scan every filename/dirname in the vault (non-raw, non-hidden)
            # for broken UTF-8 bytes and illegal characters.  Same-named
            # files in different folders are reported once (dedup by name).
            # ``total`` is the number of non-raw, non-hidden paths actually
            # scanned — NOT the markdown file count used by other checks.
            scanned: list[Path] = [
                fp for fp in root.rglob("*")
                if not fp.relative_to(root).as_posix().startswith("raw/")
                and not any(s.startswith(".") for s in fp.relative_to(root).as_posix().split("/"))
            ]
            name_issues: list[dict] = []
            seen_names: set[str] = set()
            all_issues_for_autofix: list[tuple[Path, str, list[str], str]] = []
            for fp in scanned:
                name = fp.name
                issues = _filename_issues(name)
                if not issues:
                    continue
                suggestion = _valid_filename_suggestion(name)
                all_issues_for_autofix.append((fp, name, issues, suggestion))
                if name in seen_names:
                    continue
                seen_names.add(name)
                name_issues.append({
                    "file": fp.relative_to(root).as_posix(),
                    "name": name,
                    "issues": issues,
                    "suggestion": suggestion,
                })
            capped = _cap(name_issues, effective_limit)
            omitted_total += len(name_issues) - len(capped)
            findings.append({
                "check": "filenames",
                "total": len(scanned),
                "wrong": len(name_issues),
                "correct": len(scanned) - len(name_issues),
                "returned": len(capped),
                "items": capped,
            })

        if autofix and _run_check("filenames"):
            # Auto-fix: rename files with illegal names and update wikilinks.
            # Process ALL files with issues (including same basename in different
            # folders).  Only process items that have a valid, collision-free
            # suggestion.
            renamed: list[tuple[str, str]] = []  # (old_rel, new_rel)
            for fp, old_name, issues, suggestion in all_issues_for_autofix:
                if not suggestion or suggestion == old_name:
                    continue
                old_rel = fp.relative_to(root).as_posix()
                new_name = suggestion
                new_fp = fp.parent / new_name
                new_rel = new_fp.relative_to(root).as_posix()
                if new_fp.exists():
                    continue
                try:
                    fp.rename(new_fp)
                    renamed.append((old_rel, new_rel))
                except Exception:
                    pass
            # Now update wikilinks in all markdown files pointing to renamed files.
            if renamed:
                for fp in md_files:
                    try:
                        text = fp.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    new_text = text
                    for old_rel, new_rel in renamed:
                        old_name = Path(old_rel).name
                        new_name = Path(new_rel).name
                        # Pattern 1: bare filename link [[old_name]]
                        old_bare = f"[[{old_name}]]"
                        new_bare = f"[[{new_name}]]"
                        if old_bare in new_text:
                            new_text = new_text.replace(old_bare, new_bare)
                        # Pattern 2: vault-relative with path [[path/old_name]]
                        # Also handle [[path/old_name|alias]]
                        import re
                        old_escaped = re.escape(old_name)
                        pattern = rf"\[\[([^\[\]]*/)?{old_escaped}(\|[^\[\]]*)?\]\]"
                        def _repl(m):
                            prefix = m.group(1) or ""
                            alias = m.group(2) or ""
                            return f"[[{prefix}{new_name}{alias}]]"
                        new_text = re.sub(pattern, _repl, new_text)
                    if new_text != text:
                        try:
                            fp.write_text(new_text, encoding="utf-8")
                        except Exception:
                            pass

        total_wrong = sum(f["wrong"] for f in findings)
        returned = sum(len(f["items"]) for f in findings)
        total_correct = sum(f["correct"] for f in findings)
        autofix_count = 0
        if autofix:
            for f in findings:
                if f["check"] in ("dead_wikilinks", "link_format", "frontmatter", "filenames"):
                    autofix_count += sum(1 for item in f["items"] if item.get("autofixed"))

        summary_parts = []
        for f in findings:
            if f["wrong"] > 0:
                summary_parts.append(f"{f['wrong']}/{f['total']} {f['check'].replace('_', ' ')}")
        summary = ", ".join(summary_parts) if summary_parts else "all checks passed"

        message = f"Checked {len(md_files)} files. {total_wrong} issues, {total_correct} ok."
        if autofix_count > 0:
            message += f" {autofix_count} auto-fixed."
        if omitted_total > 0:
            message += f" ({omitted_total} more omitted, use limit=0 to see all)"
        message += f" [{summary}]"

        return (True, {
            "status": "success",
            "folder": resolved,
            "total_files": len(md_files),
            "checks": findings,
            "total_issues": total_wrong,
            "total_ok": total_correct,
            "returned": returned,
            "omitted": omitted_total,
            "message": message,
        })

    except Exception as e:
        import traceback
        return (False, {
            "status": "error",
            "message": f"Lint error: {str(e)}\n{traceback.format_exc()}",
        })


def _extract_date_from_path(rel_path: str) -> str:
    parts = rel_path.split("/")
    for i, p in enumerate(parts):
        if p.isdigit() and len(p) == 4 and 2000 <= int(p) <= 2030:
            mm = parts[i + 1] if i + 1 < len(parts) and parts[i + 1].isdigit() and 1 <= int(parts[i + 1]) <= 12 else None
            dd = parts[i + 2] if mm and i + 2 < len(parts) and parts[i + 2].isdigit() and 1 <= int(parts[i + 2]) <= 31 else None
            if dd:
                return f"{p}-{mm}-{dd}"
            if mm:
                return f"{p}-{mm}"
            return p
    return ""


def wiki_find_unlinked_raw(
    _session: Any,
    folder: str | None = None,
    limit: int = 20,
) -> tuple[bool, dict]:
    """Find raw files that are never referenced from any wiki page.

    Scans all ``.md`` files under ``raw/`` and cross-references them
    against all wikilinks in the non-raw part of the vault.  Files that
    are not linked anywhere are reported, sorted oldest-first by the
    date embedded in their folder structure.

    Results are capped to *limit* entries.  Use ``limit=0`` for all. Limit output to number of items you actually want to handle.

    Args:
        _session: The calling agent's session (bound automatically).
        folder: Optional wiki root path.  When omitted and there is
            exactly one subsession with agent type ``wiki``, its
            workspace is used.
        limit: Max items to return.  ``0`` means no limit.  Default: 20.

    Returns:
        A tuple of (success, result).  On success, result contains:
            - status: "success"
            - folder: str (resolved path)
            - total_raw: int
            - linked: int
            - unlinked: int
            - items: list of {"file": str, "date": str} sorted oldest first
            - message: str
    """
    try:
        resolved = _resolve_folder(folder, _session)
        if resolved is None:
            if _session is None:
                return (False, {"status": "error", "message": "folder is required when no session is available"})
            from server.models.sessions.session_version import SessionVersionModel
            wiki_paths = list(
                SessionVersionModel.objects.filter(
                    parent_session_version=_session.get_version_model(),
                    agent__name="wiki",
                    workspace__isnull=False,
                ).values_list("workspace__path", flat=True).distinct()
            )
            if not wiki_paths:
                return (False, {"status": "error", "message": "no wiki folder found"})
            path_list = "\n".join(f"  - {p}" for p in wiki_paths)
            return (False, {
                "status": "error",
                "message": f"more than one wiki folder found:\n{path_list}\nfolder parameter mandatory",
            })

        root = Path(resolved)
        if not root.is_dir():
            return (False, {"status": "error", "message": f"folder not found: {resolved}"})

        all_md = sorted(root.rglob("*.md"))
        raw_files = [fp for fp in all_md if fp.relative_to(root).as_posix().startswith("raw/")]
        raw_paths = {fp.relative_to(root).as_posix() for fp in raw_files}
        md_files = [fp for fp in all_md if fp not in raw_files]

        linked: set[str] = set()
        for fp in md_files:
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            for link in _extract_wikilinks(text):
                target_path = _resolve_wikilink_target(link, fp.parent, root)
                if target_path:
                    try:
                        target_rel = target_path.relative_to(root).as_posix()
                    except ValueError:
                        continue
                    if target_rel in raw_paths:
                        linked.add(target_rel)

        unlinked = sorted(
            (rp, _extract_date_from_path(rp))
            for rp in raw_paths
            if rp not in linked
        )
        unlinked.sort(key=lambda x: x[1] if x[1] else "9999")

        effective_limit = None if limit == 0 else limit
        capped = unlinked[:effective_limit]
        items = [{"file": rp, "date": dt} for rp, dt in capped]
        omitted = len(unlinked) - len(capped)

        message = f"{len(unlinked)} unlinked of {len(raw_paths)} raw files."
        if omitted > 0:
            message += f" ({omitted} more omitted, use limit=0 to see all)"

        return (True, {
            "status": "success",
            "folder": resolved,
            "total_raw": len(raw_paths),
            "linked": len(linked),
            "unlinked": len(unlinked),
            "returned": len(items),
            "items": items,
            "message": message,
        })

    except Exception as e:
        import traceback
        return (False, {
            "status": "error",
            "message": f"Error: {str(e)}\n{traceback.format_exc()}",
        })



if __name__ == "__main__":
    import argparse
    import json
    import sys
    import django
    import os

    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    parser = argparse.ArgumentParser(description="Wiki checks tool.")
    parser.add_argument("folder", type=str, nargs="?", default=None, help="Wiki root folder")
    parser.add_argument("--tool", "-t", type=str, default="check",
                        choices=["check", "find-unlinked-raw"],
                        help="Which tool to run (default: check)")
    parser.add_argument("--limit", type=int, default=20, help="Max findings per check (0=unlimited)")
    parser.add_argument("--checks", "-c", type=str, default="",
                        help="Comma-separated check names (default: all). "
                             f"Valid: {', '.join(CHECK_NAMES)}")
    parser.add_argument("--files", "-f", type=str, default="",
                        help="Comma-separated file paths/globs to scope checks to")
    parser.add_argument("--autofix", action="store_true", help="Auto-fix dead wikilinks, source→sources, and UTF-8 encoding issues")
    args = parser.parse_args()

    # Try current session; if none exists, pass None and skip resolve
    session = None
    try:
        from django.contrib.sessions.models import Session as DjangoSession
        from runtime.session.session import Session
        session = Session.objects.get_current_or_new()
    except Exception:
        pass

    sess_kw = dict(_session=None) if session is None else dict(_session=session)

    if args.tool == "find-unlinked-raw":
        success, result = wiki_find_unlinked_raw(**sess_kw, folder=args.folder, limit=args.limit)
    else:
        success, result = wiki_check(**sess_kw, folder=args.folder, limit=args.limit,
                                      checks=args.checks, files=args.files, autofix=args.autofix)
    print(json.dumps(result, indent=2, default=str))
    exit(0 if success else 1)
