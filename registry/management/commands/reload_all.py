from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from django.core.management.base import BaseCommand, CommandError
from registry.install_repo import InstallRepo
from registry.loader.load_agent_manifest import load_agent_manifest
from registry.loader.load_cron_manifest import load_cron_manifest
from registry.loader.load_data_collection import load_data_collection_manifest
from registry.loader.load_project_folder import load_project_folder
from registry.loader.load_providers import load_providers_manifest
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.utils import find_agent_md_files
from registry.sources.manager import sync_upstream_sources
from server.models.cron import Cronjob


ReloadResult = Dict[str, Any]
"""Structure returned by :func:`run_reload_all`:
    - status: "success" | "partial" | "error"
    - summary: human-readable summary string
    - counts: dict of category names → counts
    - details: list of per-item dicts (name, type, action)
    - errors: list of error strings (empty on full success)
"""


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
    effective_root = sync_upstream_sources(agentone_path, details=details)

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
            errors.append(f"Scripts: {e}")

    # Global skills (no parent)
    skills_dir = effective_root / "skills"
    if skills_dir.is_dir():
        skill_count = 0
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            try:
                load_skill_manifest(skill_md, install_repo=global_install, details=details)
                skill_count += 1
            except Exception as e:
                errors.append(f"Skill {skill_md.stem}: {e}")
        counts["skills"] = skill_count

    # Global agents (no parent)
    agents_dir = effective_root / "agents"
    if agents_dir.is_dir():
        agent_count = 0
        for agent_md in find_agent_md_files(agents_dir):
            try:
                load_agent_manifest(
                    agent_md,
                    install_repo=global_install,
                    details=details,
                )
                agent_count += 1
            except Exception as e:
                agent_name = agent_md.parent.name
                errors.append(f"Agent {agent_name}: {e}")
        counts["agents"] = agent_count

    # Global cron jobs (no parent)
    crons_dir = effective_root / "cronjobs"
    if crons_dir.is_dir():
        cron_count = 0
        seen = set()
        for cron_md in sorted(crons_dir.glob("*.md")):
            try:
                load_cron_manifest(cron_md, install_repo=global_install, seen_names=seen, details=details)
                cron_count += 1
            except Exception as e:
                errors.append(f"Cron {cron_md.stem}: {e}")
        Cronjob.objects.filter(parent_project__isnull=True, is_archived=False).exclude(name__in=seen).update(is_archived=True)
        counts["cron_jobs"] = cron_count

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
                errors.append(f"Stream {stream_md.stem}: {e}")
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
                errors.append(f"Set {set_md.stem}: {e}")
        counts["sets"] = set_count

    # Projects
    projects_file = agentone_path / "projects.yaml"
    if projects_file.exists():
        try:
            with projects_file.open(encoding="utf-8") as f:
                project_paths: List[str] = yaml.safe_load(f) or []
        except Exception as e:
            errors.append(f"projects.yaml: {e}")
            project_paths = []

        for project_path in project_paths:
            try:
                load_project_folder(project_path, details=details)
                counts["projects"] += 1
            except Exception as e:
                errors.append(f"Project {project_path}: {e}")

    # Providers
    providers_file = effective_root / "providers.yaml"
    if providers_file.exists():
        try:
            provider_count = load_providers_manifest(providers_file, details=details)
            counts["providers"] = provider_count
        except Exception as e:
            errors.append(f"Providers: {e}")

    # Build summary
    summary = _format_detailed_summary(details, errors)
    status = "success" if not errors else "partial"
    return {"status": status, "summary": summary, "counts": counts, "details": details, "errors": errors}


TYPE_LABELS: Dict[str, str] = {
    "agent": "agents",
    "script": "scripts/tools",
    "skill": "skills",
    "cron": "cron jobs",
    "stream": "streams",
    "set": "sets",
    "project": "projects",
    "provider": "providers",
    "model": "models",
}

_SINGULAR_LABELS: Dict[str, str] = {
    "agent": "agent",
    "script": "script/tool",
    "skill": "skill",
    "cron": "cron job",
    "stream": "stream",
    "set": "set",
    "project": "project",
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

    for t in ("agent", "script", "skill", "cron", "stream", "set", "project", "provider", "model"):
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
        for t in ("agent", "script", "skill", "cron", "stream", "set", "project", "provider", "model"):
            items = by_type.get(t)
            if items:
                label = TYPE_LABELS.get(t, t + "s")
                parts.append(f"{len(items)} {label}")
        total_line = "Ok: " + ", ".join(parts) + "."
        if created_count:
            total_line += f" ({created_count} new)"
        lines.append(total_line)

    if errors:
        lines.append("")
        lines.append(f"Errors ({len(errors)}):")
        for e in errors:
            lines.append(f"  - {e}")

    return "\n".join(lines)


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
