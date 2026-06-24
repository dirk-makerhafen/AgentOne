"""Sync upstream git repos into a staging directory for install repo consumption.

When upstream sources are configured, a combined staging directory is built:
upstream files first, then local files overlay on top so local always wins.
The staging directory is then used as the install repo's source root.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from registry.sources.types import SourceConfig, SourceResult

UPSTREAM_BASE = Path(os.path.expanduser("~/.agentone/upstream"))
STAGING_BASE = Path(os.path.expanduser("~/.agentone/staging"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_upstream_sources(
    agentone_root: Path,
    scope: str = "global",
    details: Optional[List[Dict[str, str]]] = None,
) -> Path:
    """Read source YAML files from ``agentone_root``, clone/fetch each
    upstream repo, and merge content into a staging directory.

    Returns the effective root path to use for the install repo:
      - If sources were found and merged → the staging directory path
      - If no sources configured → ``agentone_root`` (unchanged)
    """
    sources = _collect_sources(agentone_root)
    if not sources:
        return agentone_root

    staging_dir = STAGING_BASE / scope
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: rsync upstream repos into staging (base layer)
    for source in sources:
        _sync_one_source(source, staging_dir, details)

    # Phase 2: overlay local files on top (local wins)
    _rsync_into(agentone_root, staging_dir, exclude=[".git", "sources.yaml"])

    return staging_dir


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_sources(agentone_root: Path) -> List[SourceConfig]:
    """Walk known source YAML locations and return all upstream repos."""
    sources: List[SourceConfig] = []

    source_files = [
        agentone_root / "skills" / "skills.yaml",
        agentone_root / "agents" / "sources.yaml",
        agentone_root / "scripts" / "sources.yaml",
    ]
    for path in source_files:
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for entry in data.get("sources", []):
            if not isinstance(entry, dict):
                continue
            sources.append(
                SourceConfig(
                    repo=entry["repo"],
                    ref=entry.get("ref", "main"),
                    include=entry.get("include", []),
                )
            )

    return sources


def _clone_url_to_dirname(url: str) -> str:
    """Derive a short directory name from a git URL."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    h = hashlib.sha256(url.encode()).hexdigest()[:8]
    return f"{name}-{h}"


def _sync_one_source(
    source: SourceConfig,
    staging_dir: Path,
    details: Optional[List[Dict[str, str]]],
) -> None:
    """Clone/fetch a single upstream repo and rsync its content into staging."""
    dir_name = _clone_url_to_dirname(source.repo)
    clone_dir = UPSTREAM_BASE / dir_name

    # Clone or fetch
    if not (clone_dir / ".git").exists():
        try:
            clone_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--quiet", source.repo, str(clone_dir)],
                check=True, capture_output=True, text=True,
            )
            status = "cloned"
        except subprocess.CalledProcessError as exc:
            _record_error(details, dir_name, source,
                          f"Failed to clone {source.repo}: {exc.stderr.strip()}")
            return
    else:
        try:
            subprocess.run(
                ["git", "fetch", "--quiet", "origin"],
                cwd=clone_dir, check=True, capture_output=True, text=True,
            )
            status = "updated"
        except subprocess.CalledProcessError as exc:
            _record_error(details, dir_name, source,
                          f"Failed to fetch {source.repo}: {exc.stderr.strip()}")
            return

    # Checkout the desired ref
    try:
        subprocess.run(
            ["git", "checkout", "--quiet", source.ref],
            cwd=clone_dir, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        _record_error(details, dir_name, source,
                      f"Ref {source.ref!r} not found in {source.repo}: "
                      f"{exc.stderr.strip()}")
        return

    # Determine source path — upstream may have .agentone/ or be flat
    upstream_content = clone_dir / ".agentone"
    if not upstream_content.is_dir():
        upstream_content = clone_dir
    if not upstream_content.is_dir():
        _record_error(details, dir_name, source,
                      f"No content directory found in {source.repo}")
        return

    _rsync_into(upstream_content, staging_dir, exclude=[".git"])

    if details is not None:
        details.append({
            "name": dir_name,
            "type": "source",
            "action": status,
            "repo": source.repo,
            "ref": source.ref,
        })


def _rsync_into(
    src: Path, dest: Path, exclude: Optional[List[str]] = None,
) -> None:
    """Rsync *src* contents into *dest*, skipping files in *exclude*."""
    cmd = ["rsync", "-a", "--checksum"]
    for pattern in (exclude or []):
        cmd.extend(["--exclude", pattern])
    cmd.extend([f"{src}/", f"{dest}/"])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        # Fallback: copytree with dirs_exist_ok
        for item in src.iterdir():
            if item.name in (exclude or []):
                continue
            dest_item = dest / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            elif item.is_file():
                dest_item.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_item)


def _record_error(
    details: Optional[List[Dict[str, str]]],
    dir_name: str,
    source: SourceConfig,
    msg: str,
) -> None:
    """Record an upstream sync error in details."""
    if details is not None:
        details.append({
            "name": dir_name,
            "type": "source",
            "action": "error",
            "error": msg,
        })
