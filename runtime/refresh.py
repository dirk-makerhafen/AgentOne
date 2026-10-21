"""Helpers for reloading manifest-backed rows from disk."""

from __future__ import annotations

from pathlib import Path

from registry.install_repo import InstallRepo
from runtime.paths import agentone_home, agentone_root


def install_repo_for_path(path: Path):
    """Return ``(source_root, install_repo)`` for a manifest path.

    Picks the nearest manifest root so that ``tree_sha`` resolves against
    the same git repo the original load used. Falls back to the path's
    parent when no known root contains it.
    """
    from server.models.project import Project

    p = Path(path)
    # Project-owned manifest tree.
    for project in Project.objects.all():
        try:
            md = project.get_agentone_dir()
            p.relative_to(md)
            return md, InstallRepo.for_project(project.name, source_root=md)
        except ValueError:
            continue
        except Exception:  # pylint: disable=broad-exception-caught
            continue
    # User scope (~/.agentone).
    home = agentone_home()
    try:
        p.relative_to(home)
        return home, InstallRepo.for_user(source_root=home)
    except ValueError:
        pass
    # Global repo scope.
    root = agentone_root()
    try:
        p.relative_to(root)
        return root, InstallRepo.for_global(source_root=root)
    except ValueError:
        pass
    # Fallback: treat the parent as the source root.
    sr = p.parent if p.is_file() else p
    from runtime.paths import install_base

    return sr, InstallRepo(repo_path=install_base() / "adhoc", source_root=sr)
