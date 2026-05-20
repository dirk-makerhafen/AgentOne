import yaml
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
import frontmatter
from server.models.project import Project
from registry.manifest_loader import (
    load_scripts_manifest,
    load_skill_manifest,
    load_agent_manifest,
)


def project_to_database(project_md_path: Path):
    """Create or get a Project from a project.md file."""
    project_md = frontmatter.load(project_md_path)
    project, _ = Project.objects.get_or_create(
        name=project_md.get("name"),
        description=project_md.content,
        defaults=dict(path=project_md_path.parent.as_posix()),
    )
    return project


def load_project_folder(folder: str):
    """Load scripts, skills, and agents for a project folder."""
    project_folder = Path(folder) / ".agentone"
    project = project_to_database(project_folder / "project.md")

    scripts_dir = project_folder / "scripts"
    if scripts_dir.is_dir():
        load_scripts_manifest(scripts_dir, parent_project=project)

    skills_dir = project_folder / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            load_skill_manifest(skill_md, parent_project=project)

    agents_dir = project_folder / "agents"
    if agents_dir.is_dir():
        for agent_md in _find_agent_md_files(agents_dir):
            load_agent_manifest(agent_md, parent_project=project)


def _find_agent_md_files(root_dir: Path):
    """Recursively find agent.md files, deduplicating nested paths."""
    paths = sorted(root_dir.glob("**/agent.md"),
                   key=lambda p: len(p.parts))
    result = []
    for p in paths:
        parent_str = p.parent.as_posix()
        if not any(
            parent_str.startswith(other.parent.as_posix())
            for other in result
        ):
            result.append(p)
    return result


class Command(BaseCommand):
    help = "Load all manifests (.agentone/) into the database."

    def add_arguments(self, parser):
        parser.add_argument("folder", type=str,
                            help="Root folder containing .agentone/ subdir")

    def handle(self, *args, **options):
        path = Path(options["folder"]).resolve()
        if not path.exists():
            raise CommandError(f"Folder not found: {path.as_posix()}")

        agentone_path = path / ".agentone"
        if not agentone_path.exists():
            raise CommandError(
                f"no .agentone subdir found in {path.as_posix()}"
            )

        # Global scripts (no parent)
        scripts_dir = agentone_path / "scripts"
        if scripts_dir.is_dir():
            self.stdout.write("Loading global scripts...")
            load_scripts_manifest(scripts_dir)

        # Global skills (no parent)
        skills_dir = agentone_path / "skills"
        if skills_dir.is_dir():
            self.stdout.write("Loading global skills...")
            for skill_md in sorted(skills_dir.glob("**/skill.md")):
                load_skill_manifest(skill_md)

        # Global agents (no parent)
        agents_dir = agentone_path / "agents"
        if agents_dir.is_dir():
            self.stdout.write("Loading global agents...")
            for agent_md in _find_agent_md_files(agents_dir):
                load_agent_manifest(agent_md)

        # Projects
        projects_file = agentone_path / "projects.yaml"
        if projects_file.exists():
            with projects_file.open(encoding="utf-8") as f:
                project_paths = yaml.safe_load(f) or []
            for project_path in project_paths:
                self.stdout.write(f"Loading project: {project_path}")
                load_project_folder(project_path)

        # Pass 2 (no longer needed — each agent resolves tasks during load)
