from pathlib import Path

import frontmatter
from registry.install_repo import InstallRepo
from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_cron_manifest import load_cron_manifest
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.utils import find_agent_md_files
from runtime.workspace_access import validate_workspace_access
from server.models.cron import Cronjob
from server.models.project import Project
from server.models.workspace import WorkspaceModel


def load_project_folder(folder: str, details: list | None = None) -> None:
    """Load scripts, skills, agents, cron jobs, and workspaces for a project.

    Expects a ``.agentone/`` directory at the root of *folder* with the
    standard subdirectory layout (``scripts/``, ``skills/``, ``agents/``, ``crons/``).

    Files are first synced into a per-project install repo, then version
    identifiers are derived from git tree SHAs for each manifest folder.
    """
    project_root = Path(folder)
    project_folder = project_root / ".agentone"
    project, project_created = _project_to_database(project_folder / "project.md", project_root=project_root)
    if details is not None:
        details.append({"name": project.name, "type": "project", "action": "created" if project_created else "up to date"})

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
            load_cron_manifest(
                cron_md, parent_project=project,
                install_repo=install_repo, seen_names=seen, details=details,
            )
        Cronjob.objects.filter(parent_project=project, is_archived=False).exclude(name__in=seen).update(is_archived=True)


def _project_to_database(project_md_path: Path, project_root: Path | None = None) -> tuple[Project, bool]:
    """Create or return a ``Project`` from a ``project.md`` file.

    Reads the YAML frontmatter for ``name`` and uses the body as the
    project description.

    If the frontmatter contains a ``workspaces`` list, each entry is
    created or updated as a ``WorkspaceModel``. Relative paths are
    resolved against *project_root*.

    Returns ``(project, created)`` where *created* indicates whether
    the ``Project`` row was newly created.
    """
    project_md = frontmatter.load(project_md_path)
    project, created = Project.objects.get_or_create(
        name=project_md.get("name"),
        
        defaults={
            "path": project_md_path.parent.as_posix(),
            "description": project_md.content,
        },
    )

    for entry in project_md.get("workspaces") or []:
        name = (entry or {}).get("name", "").strip()
        desc = (entry or {}).get("description", "")
        raw_path = (entry or {}).get("path", "")
        access = (entry or {}).get("access")
        if not name or not raw_path:
            continue

        validate_workspace_access(access, source=f"project.md workspace {name!r}")

        p = Path(raw_path)
        if not p.is_absolute() and project_root is not None:
            p = project_root / raw_path
        resolved = p.resolve().as_posix() if p.exists() else p.as_posix()

        WorkspaceModel.objects.update_or_create(
            name=name,
            defaults={
                "description": desc or "",
                "path": resolved,
                # Only touch access when the manifest declares it: the
                # workspace UI edits the same field, and an unconditional
                # write here would silently wipe UI-made policy on every
                # reload.  Absent key = leave the DB value alone.
                **({"access": access or {}} if "access" in (entry or {}) else {}),
            },
        )

    return project, created
