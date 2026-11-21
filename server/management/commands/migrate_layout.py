"""Migrate ``~/.agentone`` and scope manifest trees to the ``var/`` layout.

Moves the pre-``var/`` home containers into ``~/.agentone/var/`` and moves
each project/workspace ``sessions/`` dir into its own ``var/sessions/``.
Install repos are re-keyed from ``project_<name>`` / ``workspace_<name>`` to
``projects/<pk>`` / ``workspaces/<pk>`` while preserving ``.git`` (so stored
tree SHAs keep resolving).

Idempotent: missing legacy paths are skipped, existing destinations are
merged.  Use ``--dry-run`` to print the plan without touching disk.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand

from runtime.paths import (
    agentone_home,
    central_projects_base,
    central_workspaces_base,
    install_base,
    legacy_install_base,
    secrets_dir,
    var_base,
    ScopeRef,
)

MANIFEST_DIRS = ("agents", "skills", "scripts", "cronjobs", "dashboard", "memory")
SECRET_FILES = ("django_secret_key", "agent_server_secret_key")
USER_REPO_LEAKS = (".DS_Store", "config.yaml", "sleep_guard.pid", *SECRET_FILES)
SCOPE_REPO_LEAKS = (
    ".DS_Store", "memory", "dashboard", "sessions", "var",
    "install", "runtime", "browser", "upstream", "staging", "terminals",
)


class Command(BaseCommand):
    help = "Move ~/.agentone and scope trees to the var/ layout (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the plan without moving anything.",
        )

    def handle(self, *args, **options) -> None:
        self.dry = bool(options["dry_run"])
        self.actions: list[str] = []
        home = agentone_home()

        self._migrate_secrets(home)
        self._move(home / "sessions", var_base() / "sessions")
        self._move(home / "runtime", var_base() / "cache" / "runtime")
        self._move(home / "upstream", var_base() / "cache" / "upstream")
        self._move(home / "staging", var_base() / "cache" / "staging")
        self._move(home / "browser", var_base() / "browser")
        self._move(home / "terminals", var_base() / "log" / "terminals")
        self._move(home / "sleep_guard.pid", var_base() / "run" / "sleep_guard.pid")
        self._migrate_install()
        self._migrate_scope_dirs()
        self._clean_install_repos()

        prefix = "[dry-run] " if self.dry else ""
        if not self.actions:
            self.stdout.write(self.style.SUCCESS("Layout already migrated; nothing to do."))
            return
        for action in self.actions:
            self.stdout.write(f"{prefix}{action}")
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{len(self.actions)} change(s)."
        ))
        if not self.dry:
            self.stdout.write(
                "Rotate django_secret_key / agent_server_secret_key if they were "
                "ever committed to an install repo."
            )

    # ------------------------------------------------------------------
    # Home containers
    # ------------------------------------------------------------------

    def _migrate_secrets(self, home: Path) -> None:
        for name in SECRET_FILES:
            self._move(home / name, secrets_dir() / name)
        if not self.dry and secrets_dir().is_dir():
            try:
                secrets_dir().chmod(0o700)
            except OSError:
                pass
            for child in secrets_dir().iterdir():
                if child.is_file():
                    try:
                        child.chmod(0o600)
                    except OSError:
                        pass

    # ------------------------------------------------------------------
    # Install repos
    # ------------------------------------------------------------------

    def _migrate_install(self) -> None:
        legacy = legacy_install_base()
        if not legacy.is_dir():
            return

        from server.models.project import Project
        from server.models.workspace import WorkspaceModel

        projects = list(Project.objects.all())
        workspaces = list(WorkspaceModel.objects.all())

        for entry in sorted(legacy.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                continue
            if entry.name in ("global", "user"):
                self._move(entry, install_base() / entry.name)
                continue
            if entry.name.startswith("project_"):
                suffix = entry.name[len("project_"):]
                row = self._match_by_name(projects, suffix)
                if row is not None:
                    dest = ScopeRef.for_project(row).new_install_repo_path()
                else:
                    dest = install_base() / "projects" / f"_orphan_{suffix}"
                self._move(entry, dest)
                continue
            if entry.name.startswith("workspace_"):
                suffix = entry.name[len("workspace_"):]
                row = self._match_by_name(workspaces, suffix)
                if row is not None:
                    dest = ScopeRef.for_workspace(row).new_install_repo_path()
                else:
                    dest = install_base() / "workspaces" / f"_orphan_{suffix}"
                self._move(entry, dest)
                continue
            self._move(entry, install_base() / entry.name)

    @staticmethod
    def _match_by_name(rows: list, suffix: str):
        for row in rows:
            key = str(getattr(row, "name", "") or "").strip().replace(" ", "_").replace("/", "_")
            if key == suffix:
                return row
        return None

    def _clean_install_repos(self) -> None:
        """Drop non-manifest files that older syncs committed."""
        if not install_base().is_dir():
            return
        for repo in self._repo_roots():
            leaks = USER_REPO_LEAKS if repo.name == "user" else SCOPE_REPO_LEAKS
            removed = False
            for name in leaks:
                target = repo / name
                if not target.exists():
                    continue
                self.actions.append(f"remove non-manifest {target}")
                if self.dry:
                    continue
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink(missing_ok=True)
                removed = True
            if removed and not self.dry and (repo / ".git").exists():
                subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
                subprocess.run(
                    ["git", "commit", "--quiet", "-m",
                     "migrate layout: drop non-manifest files"],
                    cwd=repo, capture_output=True,
                )

    def _repo_roots(self) -> list[Path]:
        roots: list[Path] = []
        for candidate in [install_base()] + sorted(install_base().iterdir()):
            if candidate.name in ("projects", "workspaces"):
                roots.extend(sorted(p for p in candidate.iterdir() if p.is_dir()))
            elif candidate.is_dir():
                roots.append(candidate)
        return [r for r in roots if (r / ".git").exists()]

    # ------------------------------------------------------------------
    # Per-scope sessions + .gitignore
    # ------------------------------------------------------------------

    def _migrate_scope_dirs(self) -> None:
        from server.models.project import Project
        from server.models.workspace import WorkspaceModel

        dirs: set[Path] = set()
        for project in Project.objects.all():
            try:
                dirs.add(Path(project.get_agentone_dir()).expanduser())
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        for workspace in WorkspaceModel.objects.all():
            try:
                dirs.add(Path(workspace.get_agentone_dir()).expanduser())
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        for base in (central_projects_base(), central_workspaces_base()):
            if base.is_dir():
                dirs.update(d for d in base.iterdir() if d.is_dir())

        for manifest_dir in sorted(dirs):
            if not manifest_dir.is_dir():
                continue
            self._move(manifest_dir / "sessions", manifest_dir / "var" / "sessions")
            self._ensure_gitignore(manifest_dir)

    def _ensure_gitignore(self, manifest_dir: Path) -> None:
        if not any((manifest_dir / name).is_dir() for name in MANIFEST_DIRS):
            return
        gitignore = manifest_dir / ".gitignore"
        try:
            existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        except OSError:
            return
        lines = {line.strip() for line in existing.splitlines()}
        if "var/" in lines:
            return
        self.actions.append(f"add 'var/' to {gitignore}")
        if self.dry:
            return
        try:
            separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
            gitignore.write_text(f"{existing}{separator}var/\n", encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Move helpers
    # ------------------------------------------------------------------

    def _move(self, src: Path, dst: Path) -> bool:
        """Move *src* to *dst*, merging directories.  Returns True if changed."""
        if not src.exists() or src == dst:
            return False
        if dst.exists() and src.is_dir() and dst.is_dir():
            self.actions.append(f"merge {src} -> {dst}")
            if not self.dry:
                for child in sorted(src.iterdir()):
                    self._move(child, dst / child.name)
                try:
                    src.rmdir()
                except OSError:
                    pass
            return True

        self.actions.append(f"move {src} -> {dst}")
        if self.dry:
            return True
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            # File collision: keep the destination, park the source aside.
            backup = dst.with_name(dst.name + ".pre-migrate")
            counter = 1
            while backup.exists():
                backup = dst.with_name(f"{dst.name}.pre-migrate-{counter}")
                counter += 1
            shutil.move(str(src), str(backup))
        else:
            shutil.move(str(src), str(dst))
        return True
