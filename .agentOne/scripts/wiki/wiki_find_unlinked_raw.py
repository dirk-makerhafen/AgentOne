from __future__ import annotations

from pathlib import Path
from typing import Any

from wiki_checks import _resolve_folder, _resolve_wikilink_target, _extract_wikilinks


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

    parser = argparse.ArgumentParser(description="Find unlinked raw files in a wiki vault.")
    parser.add_argument("folder", type=str, nargs="?", default=None, help="Wiki root folder")
    parser.add_argument("--limit", type=int, default=20, help="Max items (0=unlimited)")
    args = parser.parse_args()

    session = None
    try:
        from django.contrib.sessions.models import Session as DjangoSession
        from runtime.session.session import Session
        session = Session.objects.get_current_or_new()
    except Exception:
        pass

    kwargs = dict(folder=args.folder, limit=args.limit)
    if session is None:
        success, result = wiki_find_unlinked_raw(_session=None, **kwargs)
    else:
        success, result = wiki_find_unlinked_raw(_session=session, **kwargs)
    print(json.dumps(result, indent=2, default=str))
    exit(0 if success else 1)
