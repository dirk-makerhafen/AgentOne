from pathlib import Path
from typing import Any, List

import yaml
from django.core.management.base import BaseCommand, CommandError
from registry.install_repo import InstallRepo
from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_project_folder import load_project_folder
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.utils import find_agent_md_files


class Command(BaseCommand):
    """Load all manifests (``.agentone/``) into the database."""

    help = "Load all manifests (.agentone/) into the database."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "folder", type=str, help="Root folder containing .agentone/ subdir"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["folder"]).resolve()
        if not path.exists():
            raise CommandError(f"Folder not found: {path.as_posix()}")

        agentone_path = path / ".agentone"
        if not agentone_path.exists():
            raise CommandError(
                f"no .agentone subdir found in {path.as_posix()}"
            )

        # Sync global sources into install repo
        self.stdout.write("Syncing global install repo...")
        global_install = InstallRepo.for_global(source_root=agentone_path)
        global_install.sync()

        # Global scripts (no parent)
        scripts_dir = agentone_path / "scripts"
        if scripts_dir.is_dir():
            self.stdout.write("Loading global scripts...")
            load_scripts_manifest(scripts_dir, install_repo=global_install)

        # Global skills (no parent)
        skills_dir = agentone_path / "skills"
        if skills_dir.is_dir():
            self.stdout.write("Loading global skills...")
            for skill_md in sorted(skills_dir.glob("**/skill.md")):
                load_skill_manifest(skill_md, install_repo=global_install)

        # Global agents (no parent)
        agents_dir = agentone_path / "agents"
        if agents_dir.is_dir():
            self.stdout.write("Loading global agents...")
            for agent_md in find_agent_md_files(agents_dir):
                load_agent_manifest(agent_md, install_repo=global_install)

        # Projects
        projects_file = agentone_path / "projects.yaml"
        if projects_file.exists():
            with projects_file.open(encoding="utf-8") as f:
                project_paths: List[str] = yaml.safe_load(f) or []
            for project_path in project_paths:
                self.stdout.write(f"Loading project: {project_path}")
                load_project_folder(project_path)
