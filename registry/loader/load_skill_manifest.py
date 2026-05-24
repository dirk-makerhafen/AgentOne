# ---------------------------------------------------------------------------
# Skill loader (skill.md)
# ---------------------------------------------------------------------------

from pathlib import Path
from pathlib import Path
from typing import Any, Tuple

import frontmatter
from registry.install_repo import InstallRepo
from registry.loader.load_scripts_manifest import load_scripts_manifest
from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion


def load_skill_manifest(
    skill_md_path: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    parent_agent: Any = None,
) -> Tuple[SkillModel, SkillModelVersion]:
    """Load a ``skill.md`` manifest into the database.

    Creates or retrieves the ``SkillModel`` and ``SkillModelVersion``, then
    recursively loads any scripts from the ``scripts/`` subfolder.

    Version identifiers are deterministic git tree SHAs from *install_repo*.
    """
    manifest = frontmatter.load(skill_md_path)
    skill_dir = skill_md_path.parent
    commit = install_repo.tree_sha(skill_dir)

    skill, _ = SkillModel.objects.get_or_create(
        name=manifest.get("name"),
        parent_agent=parent_agent,
        parent_project=parent_project,
    )
    skill_version, created = SkillModelVersion.objects.get_or_create(
        skill=skill,
        description=manifest.get("description", ""),
        path=skill_md_path.as_posix(),
        commit=commit,
    )
    if created:
        SkillModel.objects.filter(pk=skill.pk).update(
            latest_skill_version=skill_version
        )

    # Load scripts from scripts/ subfolder
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        load_scripts_manifest(
            scripts_dir,
            parent_project=parent_project,
            parent_agent=parent_agent,
            parent_skill=skill,
            install_repo=install_repo,
        )

    return skill, skill_version
