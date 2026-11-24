import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import frontmatter
from django.core.management.base import BaseCommand, CommandError
from registry.install_repo import InstallRepo
from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_data_collection import load_data_collection_manifest
from registry.loader.load_project_folder import (
    load_project_folder,
    load_scope_dir,
    load_workspace_scope,
)
from registry.loader.load_providers import load_providers_dir
from registry.loader.load_providers_json import load_providers_json
from registry.loader.load_reporting import describe_exception, format_load_error, load_error
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.utils import find_agent_md_files
from registry.sources.manager import sync_upstream_sources
from runtime.paths import (
    agentone_home,
    central_projects_base,
    central_workspaces_base,
    user_agents_dir,
    user_scripts_dir,
    user_skills_dir,
)
from server.models.agents.agent import AgentModel
from server.models.skills.skill import SkillModel

logger = logging.getLogger(__name__)


ReloadResult = Dict[str, Any]
"""Structure returned by :func:`run_reload_all`:
    - status: "success" | "partial" | "error"
    - summary: human-readable summary string
    - counts: dict of category names → counts
    - details: list of per-item dicts (name, type, action)
    - errors: list of error strings (empty on full success)
"""


def _record_load_error(errors: list, context: str, path: Path | None, exc: Exception) -> None:
    """Add an error that names the file which failed, with a debug traceback."""
    logger.debug("Manifest load failed (%s): %s", context, describe_exception(exc), exc_info=True)
    errors.append(format_load_error(context, path=path, exc=exc))


def _collect_detail_errors(details: list, errors: list) -> None:
    """Promote loader-reported skips (bad files, bad sources) into errors.

    Loaders that keep going after a bad file append ``details`` with
    ``action="error"``. Without this, the reload reports success while the
    file's contents were never loaded.
    """
    for detail in details:
        if detail.get("action") != "error":
            continue
        message = detail.get("error") or detail.get("warning") or f"{detail.get('type', 'manifest')} {detail.get('name', '')} failed"
        if message not in errors:
            errors.append(message)


def run_reload_all(folder: str) -> ReloadResult:
    """Load all manifests from ``folder/.agentone/`` into the database.

    This is the shared entry point used by both the ``reload_all``
    management command and the ``reload_project`` tool. Returns
    structured results with per-category counts and error collection.
    """
    path = Path(folder).resolve()
    if not path.exists():
        return {"status": "error", "summary": f"Folder not found: {path}", "counts": {}, "details": [], "errors": [f"Folder not found: {path}"]}

    agentone_path = path / ".agentone"
    if not agentone_path.exists():
        return {"status": "error", "summary": f"No .agentone/ directory in {path}", "counts": {}, "details": [], "errors": [f"No .agentone/ directory in {path}"]}

    details: List[Dict[str, str]] = []
    errors: List[str] = []
    counts: Dict[str, int] = {
        "agents": 0,
        "scripts": 0,
        "skills": 0,
        "cron_jobs": 0,
        "streams": 0,
        "sets": 0,
        "projects": 0,
        "providers": 0,
    }

    # Merge upstream sources (if configured) into a staging directory.
    # The effective root points at the staging dir when upstreams exist,
    # otherwise it stays at agentone_path.
    try:
        effective_root = sync_upstream_sources(agentone_path, details=details)
    except Exception as e:
        raise load_error("Upstream source sync", path=agentone_path, exc=e) from e

    # Sync global sources into install repo
    global_install = InstallRepo.for_global(source_root=effective_root)
    global_install.sync()

    # Global scripts (no parent)
    scripts_dir = effective_root / "scripts"
    if scripts_dir.is_dir():
        try:
            results = load_scripts_manifest(scripts_dir, install_repo=global_install, details=details)
            counts["scripts"] = len(results) if results else 0
        except Exception as e:
            _record_load_error(errors, "Scripts directory", scripts_dir, e)

    global_skill_names: set[str] = set()
    global_agent_names: set[str] = set()

    # Global skills (no parent)
    skills_dir = effective_root / "skills"
    if skills_dir.is_dir():
        skill_count = 0
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            global_skill_names.add(_manifest_name(skill_md, skill_md.parent.name))
            try:
                load_skill_manifest(skill_md, install_repo=global_install, details=details)
                skill_count += 1
            except Exception as e:
                _record_load_error(errors, f"Skill {skill_md.parent.name}", skill_md, e)
        counts["skills"] = skill_count

    # Global agents (no parent)
    agents_dir = effective_root / "agents"
    if agents_dir.is_dir():
        agent_count = 0
        for agent_md in find_agent_md_files(agents_dir):
            global_agent_names.add(_manifest_name(agent_md, agent_md.parent.name))
            try:
                load_agent_manifest(
                    agent_md,
                    install_repo=global_install,
                    details=details,
                )
                agent_count += 1
            except Exception as e:
                _record_load_error(errors, f"Agent {agent_md.parent.name}", agent_md, e)
        counts["agents"] = agent_count

    # Cron jobs are DB-canonical (created via the Web UI); no manifest files.

    # User scope (~/.agentone/{agents,skills,scripts}/).
    # Loads into the global namespace (same rows, new versions win).
    _load_user_scope(
        details=details,
        errors=errors,
        counts=counts,
        seen_skill_names=global_skill_names,
        seen_agent_names=global_agent_names,
    )

    # Global rows whose manifests disappeared are archived, never deleted,
    # so versions and history referencing them stay intact. Only prune a
    # domain when one of its global source dirs is present in this reload;
    # otherwise archiving every row would be a guess.
    _archive_missing_globals(
        global_agent_names,
        global_skill_names,
        agents_present=agents_dir.is_dir() or user_agents_dir().is_dir(),
        skills_present=skills_dir.is_dir() or user_skills_dir().is_dir(),
    )

    # Global streams (no parent)
    streams_dir = effective_root / "streams"
    if streams_dir.is_dir():
        stream_count = 0
        stream_seen: set[str] = set()
        for stream_md in sorted(streams_dir.glob("*.md")):
            try:
                load_data_collection_manifest(stream_md, seen_names=stream_seen, details=details)
                stream_count += 1
            except Exception as e:
                _record_load_error(errors, f"Stream {stream_md.stem}", stream_md, e)
        counts["streams"] = stream_count

    # Global sets (no parent)
    sets_dir = effective_root / "sets"
    if sets_dir.is_dir():
        set_count = 0
        set_seen: set[str] = set()
        for set_md in sorted(sets_dir.glob("*.md")):
            try:
                load_data_collection_manifest(set_md, seen_names=set_seen, details=details)
                set_count += 1
            except Exception as e:
                _record_load_error(errors, f"Set {set_md.stem}", set_md, e)
        counts["sets"] = set_count

    # Deprecated projects.yaml — warn-and-ignore, never read as registry.
    projects_file = agentone_path / "projects.yaml"
    if projects_file.exists():
        details.append({
            "name": "projects.yaml", "type": "project", "action": "warning",
            "warning": f"deprecated, ignored (projects are DB-canonical): {projects_file}",
        })

    # Projects — DB-driven. Existing rows are untouched; each row's
    # manifest dir (or legacy <path>/.agentone fallback) is loaded.
    # Workspace-scoped manifest dirs load under their parent project.
    _load_db_projects(details=details, errors=errors, counts=counts)

    # Orphan warnings: central dirs with no DB row (no autoscan/import).
    _warn_orphan_scope_dirs(details=details)

    # Providers + models.  The generated JSON dataset is the source of truth;
    # the old research-frontmatter loader stays as a fallback for installations
    # that still carry ``*.md`` cards.  Missing files disable (not delete)
    # rows so call history stays intact.
    providers_dir = effective_root / "providers"
    if providers_dir.is_dir():
        try:
            json_provider_count = load_providers_json(
                providers_dir,
                free_dir=effective_root / "free",
                details=details,
                disable_missing=True,
            )
        except Exception as e:
            _record_load_error(errors, "Providers/models (JSON)", providers_dir, e)
            json_provider_count = 0
        if json_provider_count:
            counts["providers"] = json_provider_count
        else:
            # No generated JSON dataset found: fall back to legacy markdown.
            try:
                provider_count = load_providers_dir(
                    providers_dir,
                    effective_root / "models",
                    details=details,
                    disable_missing=True,
                )
                counts["providers"] = provider_count
            except Exception as e:
                _record_load_error(errors, "Providers/models", providers_dir, e)

    # Non-fatal load failures (bad files that were skipped) must show up too.
    _collect_detail_errors(details, errors)

    # Build summary
    summary = _format_detailed_summary(details, errors)
    status = "success" if not errors else "partial"
    return {"status": status, "summary": summary, "counts": counts, "details": details, "errors": errors}


def _manifest_name(manifest_path: Path, default: str) -> str:
    """Return a manifest's declared ``name`` (folder name as fallback)."""
    try:
        name = frontmatter.load(manifest_path).get("name")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Could not read manifest name from %s: %s",
            manifest_path, describe_exception(e), exc_info=True,
        )
        name = None
    return (name or default or "").strip()


def _load_user_scope(details: list, errors: list, counts: Dict[str, int],
                     seen_skill_names: set[str] | None = None,
                     seen_agent_names: set[str] | None = None) -> None:
    """Load ``~/.agentone/{scripts,skills,agents}/`` as user scope.

    Loads into the global namespace (same DB rows, user versions win by
    loading after global). Missing dirs are skipped silently. Names are
    added to *seen_skill_names* / *seen_agent_names* so the caller can
    archive globals that no longer have a manifest.
    """
    root = agentone_home()
    if not root.is_dir():
        return
    user_install = InstallRepo.for_user(source_root=root)
    try:
        user_install.sync(excludes=[
            # Current layout (everything except the user manifest dirs).
            "var", "secrets", "projects", "workspaces", "memory",
            "config.yaml", "sleep_guard.pid", ".DS_Store",
            # Pre-var/ leftovers, cleaned out of the repo after migration.
            "install", "runtime", "sessions", "browser", "upstream",
            "staging", "terminals",
        ])
    except Exception as e:
        _record_load_error(errors, "User scope sync", root, e)
        return

    scripts_dir = user_scripts_dir()
    if scripts_dir.is_dir():
        try:
            results = load_scripts_manifest(scripts_dir, install_repo=user_install, details=details)
            counts["scripts"] = counts.get("scripts", 0) + (len(results) if results else 0)
        except Exception as e:
            _record_load_error(errors, "User scripts", scripts_dir, e)

    skills_dir = user_skills_dir()
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            if seen_skill_names is not None:
                seen_skill_names.add(_manifest_name(skill_md, skill_md.parent.name))
            try:
                load_skill_manifest(skill_md, install_repo=user_install, details=details)
            except Exception as e:
                _record_load_error(errors, f"User skill {skill_md.parent.name}", skill_md, e)

    agents_dir = user_agents_dir()
    if agents_dir.is_dir():
        for agent_md in find_agent_md_files(agents_dir):
            if seen_agent_names is not None:
                seen_agent_names.add(_manifest_name(agent_md, agent_md.parent.name))
            try:
                load_agent_manifest(agent_md, install_repo=user_install, details=details)
            except Exception as e:
                _record_load_error(errors, f"User agent {agent_md.parent.name}", agent_md, e)



def _archive_missing_globals(
    seen_agent_names: set[str],
    seen_skill_names: set[str],
    *,
    agents_present: bool = True,
    skills_present: bool = True,
) -> None:
    """Archive global agents/skills with no manifest in this reload.

    Rows are kept (not deleted) so versions, sessions and call history
    stay intact. A manifest that reappears unarchives the row in its
    loader. ``*_present`` gates a domain whose global source dir did not
    exist at all in this reload, to avoid archiving everything by accident.
    """
    if agents_present:
        stale_agents = list(
            AgentModel.objects.filter(
                parent_agent__isnull=True,
                parent_project__isnull=True,
                parent_skill__isnull=True,
                is_archived=False,
            ).exclude(name__in=seen_agent_names).values_list("pk", flat=True)
        )
        if stale_agents:
            for _pk in stale_agents:
                AgentModel.atomic_update_by_pk(_pk, is_archived=True)

    if skills_present:
        stale_skills = list(
            SkillModel.objects.filter(
                parent_agent__isnull=True,
                parent_project__isnull=True,
                parent_skill__isnull=True,
                is_archived=False,
            ).exclude(name__in=seen_skill_names).values_list("pk", flat=True)
        )
        if stale_skills:
            for _pk in stale_skills:
                SkillModel.atomic_update_by_pk(_pk, is_archived=True)


def _load_db_projects(details: list, errors: list, counts: Dict[str, int]) -> None:
    """Load manifest dirs for every Project row + managed Workspace rows."""
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel

    try:
        projects = list(Project.objects.all().order_by("name"))
    except Exception as e:
        errors.append(f"Projects DB: {e}")
        return
    for project in projects:
        manifest = None
        try:
            manifest = project.get_agentone_dir()
            if not manifest.is_dir():
                details.append({
                    "name": project.name, "type": "project",
                    "action": "warning", "path": str(manifest),
                    "warning": f"manifest dir missing, skipped: {manifest}",
                })
                continue
            load_scope_dir(manifest, project, details=details)
            counts["projects"] = counts.get("projects", 0) + 1
        except Exception as e:
            _record_load_error(errors, f"Project {project.name}", manifest, e)

    try:
        workspaces = list(WorkspaceModel.objects.all().order_by("name"))
    except Exception as e:
        errors.append(f"Workspaces DB: {e}")
        return
    for ws in workspaces:
        manifest = None
        try:
            manifest = ws.get_agentone_dir()
            if not manifest.is_dir():
                details.append({
                    "name": ws.name, "type": "workspace",
                    "action": "warning", "path": str(manifest),
                    "warning": f"manifest dir missing, skipped: {manifest}",
                })
                continue
            # Crons are project-scoped: the project's canonical cronjobs/
            # manifests win over workspace copies, and a workspace must not
            # archive jobs it does not define. A standalone workspace (no
            # parent_project) is valid and loads into the global namespace.
            load_workspace_scope(manifest, ws, details=details)
        except Exception as e:
            _record_load_error(errors, f"Workspace {ws.name}", manifest, e)


def _warn_orphan_scope_dirs(details: list) -> None:
    """Warn for central dirs with no DB row (no autoscan/import by design)."""
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel

    for base, model, field in (
        (central_projects_base(), Project, "agentone_dir"),
        (central_workspaces_base(), WorkspaceModel, "agentone_dir"),
    ):
        try:
            if not base.is_dir():
                continue
            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue
                try:
                    exists = model.objects.filter(agentone_dir=entry.as_posix()).exists()
                except Exception:
                    continue
                if not exists:
                    # Also match by central name convention for rows that
                    # store a different but equivalent path.
                    details.append({
                        "name": entry.name, "type": "orphan",
                        "action": "warning", "path": str(entry),
                        "warning": f"{entry} has no database entry — create it in the UI or delete the dir",
                    })
        except Exception:
            continue


TYPE_LABELS: Dict[str, str] = {
    "agent": "agents",
    "script": "scripts/tools",
    "skill": "skills",
    "cron": "cron jobs",
    "stream": "streams",
    "set": "sets",
    "project": "projects",
    "workspace": "workspaces",
    "provider": "providers",
    "model": "models",
    "orphan": "orphans",
    "source": "sources",
}

_SINGULAR_LABELS: Dict[str, str] = {
    "agent": "agent",
    "script": "script/tool",
    "skill": "skill",
    "cron": "cron job",
    "stream": "stream",
    "set": "set",
    "project": "project",
    "workspace": "workspace",
    "provider": "provider",
    "model": "model",
}


def _format_detailed_summary(
    details: List[Dict[str, str]],
    errors: List[str],
) -> str:
    """Build a detailed summary string from per-item details."""
    lines: List[str] = []

    # Group details by type
    by_type: Dict[str, List[Dict[str, str]]] = {}
    for d in details:
        by_type.setdefault(d["type"], []).append(d)

    total_items = len(details)

    created_count = sum(1 for d in details if d["action"] == "created")
    updated_count = sum(1 for d in details if d["action"] == "updated")
    uptodate_count = sum(1 for d in details if d["action"] == "up to date")

    action_parts = []
    if created_count:
        action_parts.append(f"{created_count} created")
    if updated_count:
        action_parts.append(f"{updated_count} updated")
    if uptodate_count:
        action_parts.append(f"{uptodate_count} up to date")
    action_summary = ", ".join(action_parts) if action_parts else "all up to date"

    lines.append(f"Checked {total_items} manifests in .agentone/ — {action_summary}")
    lines.append("")

    for t in ("agent", "script", "skill", "cron", "stream", "set", "project", "workspace", "provider", "model"):
        label = TYPE_LABELS.get(t, t + "s")
        items = by_type.get(t)
        if not items:
            lines.append(f"  {label}: (none)")
            continue

        c = len(items)
        created = [d for d in items if d["action"] == "created"]
        updated = [d for d in items if d["action"] == "updated"]
        uptodate = [d for d in items if d["action"] == "up to date"]

        parts = []
        if created:
            parts.append(f"{len(created)} created")
        if updated:
            parts.append(f"{len(updated)} updated")
        if uptodate:
            parts.append(f"{len(uptodate)} up to date")
        status_str = f" ({', '.join(parts)})" if parts else ""

        lines.append(f"  {label}: {c}{status_str}")
        for item in created + updated:
            action_prefix = "+" if item["action"] == "created" else "~"
            lines.append(f"    {action_prefix} {item['name']}")
        if uptodate and len(uptodate) <= 10:
            for item in uptodate:
                lines.append(f"      {item['name']}")
        elif uptodate:
            lines.append(f"      ({len(uptodate)} up to date)")

    if total_items > 0:
        lines.append("")
        parts = []
        for t in ("agent", "script", "skill", "cron", "stream", "set", "project", "workspace", "provider", "model"):
            items = by_type.get(t)
            if items:
                label = TYPE_LABELS.get(t, t + "s")
                parts.append(f"{len(items)} {label}")
        total_line = "Ok: " + ", ".join(parts) + "."
        if created_count:
            total_line += f" ({created_count} new)"
        lines.append(total_line)

    issues = [
        d for d in details
        if d.get("action") != "error"
        and (d.get("error") or d.get("warning") or str(d.get("action", "")).startswith("skipped"))
    ]
    if issues:
        lines.append("")
        lines.append(f"Skipped / warnings ({len(issues)}):")
        for item in issues:
            path = item.get("path") or ""
            location = f" [{path}]" if path else ""
            reason = item.get("error") or item.get("warning") or item.get("action", "")
            item_type = item.get("type", "manifest")
            label = _SINGULAR_LABELS.get(item_type, item_type)
            lines.append(f"  - {label} {item.get('name', '')}{location}: {reason}")

    if errors:
        lines.append("")
        lines.append(f"Errors ({len(errors)}):")
        for e in errors:
            lines.append(f"  - {e}")
        hints = _build_error_hints(errors)
        if hints:
            lines.append("")
            lines.append("Hints:")
            for h in hints:
                lines.append(f"  - {h}")

    return "\n".join(lines)


def _build_error_hints(errors: List[str]) -> List[str]:
    """Build actionable hints that explain how separate errors relate."""
    hints: List[str] = []
    # Errors are now prefixed "Scripts directory (...)" / "User scripts (...)".
    has_script_error = any(e.startswith(("Scripts:", "Scripts ", "User scripts ")) for e in errors)
    has_task_error = any("No Task Definition found" in e for e in errors)
    has_chain_error = any("Chain step" in e for e in errors)

    if has_chain_error:
        hints.append(
            "A chain/group step could not be resolved. Chain steps must "
            "reference tasks defined as standalone tools/tasks/commands "
            "(function or script) in a scripts.md under the scripts directory. "
            "A missing step is usually a typo, a renamed definition, or a name "
            "that only exists outside this scripts directory — check the "
            "'missing step(s)' list in the error above."
        )
    if has_script_error and has_task_error:
        hints.append(
            "The 'No Task Definition found' agent errors are almost certainly "
            "a cascade: when scripts fail to load (see the 'Scripts' error, "
            "which names the failing scripts.md), no task definitions are "
            "created, so agents that reference those tools cannot resolve "
            "them. Fix the scripts error first, then reload again."
        )
    return hints


class Command(BaseCommand):
    """Load all manifests (``.agentone/``) into the database."""

    help = "Load all manifests (.agentone/) into the database."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "folder", type=str, help="Root folder containing .agentone/ subdir"
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        folder = options["folder"]
        result = run_reload_all(folder)
        self.stdout.write(result["summary"])
        if result["status"] == "error":
            raise CommandError(result["summary"])
        return
