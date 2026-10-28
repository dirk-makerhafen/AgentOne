"""Project/workspace scope loader (DB-canonical).

Metadata (name, description, workspaces, agentone_dir) lives in the DB.
``project.md`` and ``projects.yaml`` are deprecated: when found on disk the
loader emits a warn-and-ignore entry and never creates/updates rows from
them. Existing rows are left untouched.

``load_project_folder(folder)`` is kept as a compatibility entry point:
it resolves the owning Project row (by path or manifest dir) and loads the
manifest tree underneath it. ``load_scope_dir(manifest_dir, project)`` is
the preferred direct entry point.
"""

from pathlib import Path

import frontmatter

from registry.install_repo import InstallRepo
from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_cron_manifest import load_cron_manifest
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.utils import find_agent_md_files
from server.models.cron import Cronjob
from server.models.project import Project


def cron_names_in_scope(manifest_dir: str | Path) -> set[str]:
    """Return the cron ``name`` values declared under ``<manifest_dir>/cronjobs``."""
    crons_dir = Path(manifest_dir) / "cronjobs"
    names: set[str] = set()
    if not crons_dir.is_dir():
        return names
    for cron_md in sorted(crons_dir.glob("*.md")):
        try:
            name = (frontmatter.load(cron_md).get("name") or "").strip()
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if name:
            names.add(name)
    return names


def load_scope_dir(
    manifest_dir: str | Path,
    project,
    details: list | None = None,
    cron_precedence: set[str] | None = None,
    archive_missing_crons: bool = True,
) -> None:
    """Load scripts/skills/agents/cronjobs from *manifest_dir* for *project*.

    ``cron_precedence`` names are owned by a more canonical scope (the
    project's own ``cronjobs/`` directory); they are left untouched when
    loading a workspace scope.  ``archive_missing_crons=False`` keeps a
    workspace scope from archiving project-level jobs it does not define.
    """
    project_folder = Path(manifest_dir)
    _warn_if_project_md(project_folder, details)

    install_repo = InstallRepo.for_project(
        project_name=project.name,
        source_root=project_folder,
    )
    install_repo.sync()

    scripts_dir = project_folder / "scripts"
    if scripts_dir.is_dir():
        load_scripts_manifest(
            scripts_dir, parent_project=project,
            install_repo=install_repo, details=details,
        )

    skills_dir = project_folder / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            load_skill_manifest(
                skill_md, parent_project=project,
                install_repo=install_repo, details=details,
            )

    agents_dir = project_folder / "agents"
    if agents_dir.is_dir():
        for agent_md in find_agent_md_files(agents_dir):
            load_agent_manifest(
                agent_md, parent_project=project,
                install_repo=install_repo, details=details,
            )

    crons_dir = project_folder / "cronjobs"
    if crons_dir.is_dir():
        seen = set()
        for cron_md in sorted(crons_dir.glob("*.md")):
            if cron_precedence:
                try:
                    name = (frontmatter.load(cron_md).get("name") or "").strip()
                except Exception:  # pylint: disable=broad-exception-caught
                    name = ""
                if name and name in cron_precedence:
                    seen.add(name)
                    continue
            load_cron_manifest(
                cron_md, parent_project=project,
                install_repo=install_repo, seen_names=seen, details=details,
            )
        if archive_missing_crons:
            # Only archive jobs that were loaded from this same scope.  A
            # project's canonical load must not archive workspace-owned jobs
            # (they share ``parent_project`` but live under another dir).
            scope_dir = Path(manifest_dir).as_posix()
            Cronjob.objects.filter(
                parent_project=project,
                is_archived=False,
                manifest_dir__in=["", scope_dir],
            ).exclude(name__in=seen).update(is_archived=True)


def load_project_folder(folder: str, details: list | None = None) -> None:
    """Compatibility entry: load the manifest tree rooted at *folder*.

    *folder* may be a project root (containing ``.agentone/``) or the
    ``.agentone`` manifest dir itself. The owning Project row is resolved
    by path — never created from ``project.md`` except as a legacy
    one-time import with a deprecation warning.
    """
    project_root = Path(folder)
    if project_root.name == ".agentone":
        project_folder = project_root
        project_root = project_root.parent
    else:
        project_folder = project_root / ".agentone"

    project = _resolve_project(project_root, project_folder, details)
    if project is None:
        if details is not None:
            details.append({
                "name": project_root.as_posix(), "type": "project",
                "action": "warning",
                "warning": "no Project row for this folder — create it in the UI first",
            })
        return

    manifest = project.get_agentone_dir()
    if not manifest.is_dir():
        # Fall back to the folder the caller pointed at.
        manifest = project_folder if project_folder.is_dir() else project_root
    if details is not None:
        details.append({"name": project.name, "type": "project", "action": "up to date"})
    load_scope_dir(manifest, project, details=details)


def load_workspace_scope(manifest_dir: str | Path, project,
                         details: list | None = None) -> None:
    """Load a workspace-scoped manifest tree under *project*'s namespace.

    Cron manifests already defined in the project's canonical scope win, and
    a workspace never archives project-level jobs it does not define.
    """
    try:
        precedence = cron_names_in_scope(project.get_agentone_dir())
    except Exception:  # pylint: disable=broad-exception-caught
        precedence = set()
    load_scope_dir(
        manifest_dir, project, details=details,
        cron_precedence=precedence, archive_missing_crons=False,
    )


def _ensure_root_workspace(project, folder: Path) -> None:
    """Link *folder* as *project*'s primary workspace (best effort)."""
    from server.models.workspace import WorkspaceModel

    try:
        ws, created = WorkspaceModel.objects.get_or_create(
            name=f"{project.name} project root",
            defaults={
                "path": folder.as_posix(),
                "description": "project root directory",
                "parent_project": project,
            },
        )
        if not created and ws.parent_project_id is None:
            ws.parent_project = project
            ws.save(update_fields=["parent_project"])
        if project.main_workspace_id is None:
            project.main_workspace = ws
            project.save(update_fields=["main_workspace"])
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def _warn_if_project_md(project_folder: Path, details: list | None) -> None:
    md = project_folder / "project.md"
    if md.is_file() and details is not None:
        details.append({
            "name": "project.md", "type": "project", "action": "warning",
            "warning": f"deprecated, ignored (DB-canonical): {md}",
        })


def _resolve_project(project_root: Path, project_folder: Path,
                     details: list | None):
    """Find the Project row for *project_root*, legacy-importing if needed."""
    project = (
        Project.objects.filter(agentone_dir=project_folder.as_posix()).first()
        or Project.objects.filter(main_workspace__path=project_root.as_posix()).first()
        or Project.objects.filter(main_workspace__path=project_folder.as_posix()).first()
    )
    if project is not None:
        _warn_if_project_md(project_folder, details)
        return project
    # Legacy one-time import: a project.md exists but no row yet.
    md = project_folder / "project.md"
    if md.is_file():
        try:
            data = frontmatter.load(md)
            name = (data.get("name") or project_root.name).strip()
            project = Project.objects.create(
                name=name or project_root.name,
                description=data.content or "",
                agentone_dir=project_folder.as_posix(),
            )
            _ensure_root_workspace(project, project_root)
            if details is not None:
                details.append({
                    "name": project.name, "type": "project",
                    "action": "created",
                    "warning": f"legacy import from deprecated {md}",
                })
            return project
        except Exception as exc:  # never break reload on a bad file
            if details is not None:
                details.append({
                    "name": project_root.as_posix(), "type": "project",
                    "action": "error", "error": f"legacy project.md unreadable: {exc}",
                })
            return None
    # DB-only fallback: create a minimal row so a bare manifest dir is
    # loadable without any deprecated files.
    try:
        project = Project.objects.create(
            name=project_root.name,
            description="",
            agentone_dir=project_folder.as_posix() if project_folder.is_dir() else "",
        )
        _ensure_root_workspace(project, project_root)
        if details is not None:
            details.append({
                "name": project.name, "type": "project", "action": "created",
            })
        return project
    except Exception:
        return None


def _project_to_database(*args, **kwargs):
    """Deprecated: metadata is DB-canonical, project.md is warn-and-ignore."""
    raise RuntimeError(
        "_project_to_database is removed: projects are DB-canonical, "
        "project.md is deprecated (warn-and-ignore)."
    )
