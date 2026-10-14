# ---------------------------------------------------------------------------
# Skill loader (skill.md)
# ---------------------------------------------------------------------------

import frontmatter
from pathlib import Path
from typing import Any, Tuple

from registry.install_repo import InstallRepo
from registry.loader.load_scripts_manifest import load_scripts_manifest
from runtime.paths import runtime_base as _runtime_base
from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion


def _runtime_for_pk(pk: object) -> Path:
    return _runtime_base() / str(pk)


RUNTIME_BASE = _runtime_base()


def load_skill_manifest(
    skill_md_path: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    parent_agent: Any = None,
    details: list | None = None,
) -> Tuple[SkillModel, SkillModelVersion]:
    """Load a ``skill.md`` manifest into the database.

    Creates or retrieves the ``SkillModel`` and ``SkillModelVersion``, then
    recursively loads any scripts from the ``scripts/`` subfolder.

    Version identifiers are deterministic git tree SHAs from *install_repo*.
    Files are extracted to ``~/.agentone/runtime/<version_pk>/`` so that
    the view reads a versioned copy, not whatever is on disk in the source tree.
    """
    manifest = frontmatter.load(skill_md_path)
    skill_dir = skill_md_path.parent
    commit = install_repo.tree_sha(skill_dir)

    skill, _ = SkillModel.objects.get_or_create(
        name=manifest.get("name"),
        parent_agent=parent_agent,
        parent_project=parent_project,
    )
    # Record where this skill's manifest lives (drift-tolerant: reloads
    # from a moved tree update the row instead of orphaning it).
    manifest_dir = skill_dir.as_posix()
    if (skill.manifest_dir or "") != manifest_dir:
        SkillModel.objects.filter(pk=skill.pk).update(manifest_dir=manifest_dir)
        skill.manifest_dir = manifest_dir
    skill_version, created = SkillModelVersion.objects.get_or_create(
        skill=skill,
        commit=commit,
        defaults={
            "description": manifest.get("description", ""),
            "path": "",
        },
    )
    if created:
        SkillModel.objects.filter(pk=skill.pk).update(
            latest_skill_version=skill_version
        )
        # Extract versioned files to runtime folder
        dest = _runtime_for_pk(skill_version.pk)
        install_repo.checkout_tree(tree_sha=commit, dest=dest)
        extracted_md = dest / skill_md_path.name
        SkillModelVersion.objects.filter(pk=skill_version.pk).update(
            path=extracted_md.as_posix(),
        )
    if details is not None:
        action = "created" if created else "up to date"
        details.append({"name": skill.name, "type": "skill", "action": action})

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
