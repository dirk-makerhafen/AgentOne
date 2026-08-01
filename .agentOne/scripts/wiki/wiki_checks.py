from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


WIKILINK_RE = re.compile(r'\[\[([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]')
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)
REQUIRED_FM_FIELDS = ('type', 'date', 'updated', 'tags', 'sources')
CHECK_NAMES = ("dead_wikilinks", "orphan_pages", "missing_index", "stale_index_entries", "frontmatter")


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
    - Orphan pages (no inbound wikilinks from non-archive pages)
    - Missing ``index.md`` files in subdirectories
    - Stale entries in ``index.md`` that point to non-existent files
    - Missing or invalid YAML frontmatter

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
            for all checks. Valid names: ``dead_wikilinks``, ``orphan_pages``,
            ``missing_index``, ``stale_index_entries``, ``frontmatter``.
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

        def _compute_rel_path(source_rel: str, target_rel: str) -> str:
            from os.path import relpath
            return relpath(target_rel, Path(source_rel).parent.as_posix())

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
                                item["suggestion"] = _compute_rel_path(rel, unique)
                        dead.append(item)
            if autofix:
                autofix_count_dead = 0
                for item in dead:
                    if "suggestion" not in item:
                        continue
                    fp = root / item["file"]
                    old_bracketed = f"[[{item['link']}]]"
                    new_bracketed = f"[[{item['suggestion']}]]"
                    try:
                        text = fp.read_text(encoding="utf-8")
                        if old_bracketed in text:
                            text = text.replace(old_bracketed, new_bracketed)
                        else:
                            old_re = re.compile(r'\[\[' + re.escape(item['link']) + r'\|')
                            text = old_re.sub(f'[[{item["suggestion"]}|', text)
                        fp.write_text(text, encoding="utf-8")
                        item["autofixed"] = True
                        autofix_count_dead += 1
                    except Exception:
                        item["autofixed"] = False
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

        total_wrong = sum(f["wrong"] for f in findings)
        returned = sum(len(f["items"]) for f in findings)
        total_correct = sum(f["correct"] for f in findings)
        autofix_count = 0
        if autofix:
            for f in findings:
                if f["check"] in ("dead_wikilinks", "frontmatter"):
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

    Results are capped to *limit* entries.  Use ``limit=0`` for all.

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
    parser.add_argument("--autofix", action="store_true", help="Auto-fix dead wikilinks and source→sources")
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
