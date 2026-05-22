from pathlib import Path
import frontmatter
from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.utils import find_agent_md_files
from server.models.project import Project


def load_project_folder(folder: str):
    """Load scripts, skills, and agents for a project folder."""
    project_folder = Path(folder) / ".agentone"
    project = _project_to_database(project_folder / "project.md")

    scripts_dir = project_folder / "scripts"
    if scripts_dir.is_dir():
        load_scripts_manifest(scripts_dir, parent_project=project)

    skills_dir = project_folder / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            load_skill_manifest(skill_md, parent_project=project)

    agents_dir = project_folder / "agents"
    if agents_dir.is_dir():
        for agent_md in find_agent_md_files(agents_dir):
            load_agent_manifest(agent_md, parent_project=project)


def _project_to_database(project_md_path: Path):
    """Create or get a Project from a project.md file."""
    project_md = frontmatter.load(project_md_path)
    project, _ = Project.objects.get_or_create(
        name=project_md.get("name"),
        description=project_md.content,
        defaults=dict(path=project_md_path.parent.as_posix()),
    )
    return project
