"""Deterministic writer for the provider-local JSON dataset.

OpenCode-style layout only: ``providers/<provider>/<provider>.json`` plus one
``<model>.json`` per model in the same directory.  There is no global
``models/`` JSON output.  Writes are atomic and byte-stable (sorted keys,
UTF-8, trailing newline).

Pruning is marker-based: only files carrying our ``_generated_by`` marker are
ever removed, so hand-written JSON and the markdown research cards are left
alone.  Legacy generated ``models/*.json`` files are removed; stale provider
directories are removed once empty.  Free candidates are split into one file
per provider plus a small index in the free-tier cache, so an LLM can read them
incrementally.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from registry.catalog.normalize import FREE_MODEL_SOURCE, GENERATED_BY, slugify
from registry.catalog.sources import read_json



def write_json(path: Path, data: Any) -> None:
    """Write one canonical JSON file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


FREE_INDEX_FILE = "index.json"
CATALOG_UPDATED_AT = "catalog_updated_at"


def dataset_paths(
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
    root: Path,
) -> dict[Path, dict[str, Any]]:
    """Map every expected output path to its record."""
    root = Path(root)
    expected: dict[Path, dict[str, Any]] = {}

    for slug, record in providers.items():
        expected[root / "providers" / slug / f"{slug}.json"] = record
    for (provider_slug, model_slug), record in models.items():
        path = root / "providers" / provider_slug / f"{model_slug}.json"
        if path in expected:
            raise ValueError(f"Catalog filename collision: {path}")
        expected[path] = record
    return expected


CURATED_PROVIDER_FIELDS = (
    "description",
    "setup_instructions",
    "url",
    "api_key_url",
    "default_api_key",
    "doc",
    "litellm_prefix",
    "wire",
    "research_sources",
)
CURATED_RANK_FIELDS = (
    "leaderboard_id",
    "leaderboard_rank",
    "leaderboard_rank_estimated",
)


def _is_generated(path: Path) -> bool:
    payload = read_json(path, {})
    return isinstance(payload, dict) and payload.get("_generated_by") == GENERATED_BY


def _is_free_generated(path: Path) -> bool:
    payload = read_json(path, {})
    return isinstance(payload, dict) and payload.get("generated_from") == FREE_MODEL_SOURCE


def _with_preserved_evidence(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Keep free-candidate evidence attached to an existing model file."""
    existing = read_json(path, {})
    if isinstance(existing, dict) and isinstance(existing.get("candidate_evidence"), dict):
        return {**record, "candidate_evidence": existing["candidate_evidence"]}
    return record


def _with_preserved_provider_fields(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Keep agent-curated provider prose from being lost on regeneration."""
    if path.parent.name != path.stem:
        return record
    existing = read_json(path, {})
    if not isinstance(existing, dict):
        return record
    curated = {
        key: existing[key]
        for key in CURATED_PROVIDER_FIELDS
        if existing.get(key) not in (None, "", [], {})
    }
    return {**record, **curated} if curated else record


def _with_preserved_rank_fields(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Keep curated leaderboard ranks on generated model files."""
    if path.parent.name == path.stem:
        return record
    existing = read_json(path, {})
    if not isinstance(existing, dict):
        return record
    curated = {
        key: existing[key]
        for key in CURATED_RANK_FIELDS
        if existing.get(key) not in (None, "", [], {})
    }
    return {**record, **curated} if curated else record


def generation_timestamp() -> str:
    """UTC ISO-8601 stamp used for records whose content changed."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _without_timestamp(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != CATALOG_UPDATED_AT}


def _with_update_timestamp(
    path: Path,
    record: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    """Stamp a record when its content changes; keep the old stamp otherwise."""
    existing = read_json(path, {})
    if isinstance(existing, dict) and _without_timestamp(existing) == _without_timestamp(record):
        previous = existing.get(CATALOG_UPDATED_AT)
        if previous:
            return {**record, CATALOG_UPDATED_AT: previous}
    return {**record, CATALOG_UPDATED_AT: updated_at}


def _remove_empty_dirs(base: Path, *, remove_base: bool = False) -> None:
    if not base.is_dir():
        return
    for child in sorted(base.iterdir(), reverse=True):
        if child.is_dir() and not any(child.iterdir()):
            child.rmdir()
    if remove_base and not any(base.iterdir()):
        base.rmdir()


def sync_dataset(  # pylint: disable=too-many-arguments
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
    root: Path,
    *,
    dry_run: bool = False,
    prune: bool = True,
    updated_at: str | None = None,
) -> dict[str, Any]:
    # pylint: disable=too-many-locals,too-many-branches
    """Write the dataset and remove generated files no longer in the sources.

    Returns a summary with written/removed counts and example paths.  When
    ``dry_run`` is true nothing is written or deleted; the summary describes
    what would change.
    """
    root = Path(root)
    expected = dataset_paths(providers, models, root)
    stamp = updated_at or generation_timestamp()
    written = 0
    unchanged = 0
    removed: list[str] = []

    for path, record in sorted(expected.items(), key=lambda item: str(item[0])):
        record = _with_preserved_evidence(path, record)
        record = _with_preserved_provider_fields(path, record)
        record = _with_preserved_rank_fields(path, record)
        record = _with_update_timestamp(path, record, stamp)
        text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if path.exists():
            if path.read_text(encoding="utf-8") == text:
                unchanged += 1
                continue
            if not _is_generated(path):
                raise ValueError(f"Refusing to overwrite non-generated file: {path}")
        if not dry_run:
            write_json(path, record)
        written += 1

    if prune:
        for base in (root / "providers", root / "models"):
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.json")):
                if path.name.endswith(".tmp") or path in expected or not _is_generated(path):
                    continue
                if _is_free_generated(path):
                    continue
                if not dry_run:
                    path.unlink()
                removed.append(path.relative_to(root).as_posix())

        if not dry_run:
            _remove_empty_dirs(root / "providers")
            _remove_empty_dirs(root / "models", remove_base=True)

    return {
        "written": written,
        "unchanged": unchanged,
        "removed": len(removed),
        "removed_examples": removed[:20],
        "total_files": len(expected),
        "dry_run": dry_run,
    }


def sync_free_models(
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
    root: Path,
    *,
    dry_run: bool = False,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Write free-backed model files and prune only those generated by us."""
    root = Path(root)
    expected = dataset_paths(providers, models, root)
    stamp = updated_at or generation_timestamp()
    written = 0
    unchanged = 0
    removed: list[str] = []

    for path, record in sorted(expected.items(), key=lambda item: str(item[0])):
        record = _with_preserved_evidence(path, record)
        record = _with_preserved_provider_fields(path, record)
        record = _with_preserved_rank_fields(path, record)
        record = _with_update_timestamp(path, record, stamp)
        text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if path.exists():
            if path.read_text(encoding="utf-8") == text:
                unchanged += 1
                continue
            if not _is_generated(path):
                raise ValueError(f"Refusing to overwrite non-generated file: {path}")
        if not dry_run:
            write_json(path, record)
        written += 1

    base = root / "providers"
    if base.is_dir():
        for path in sorted(base.rglob("*.json")):
            if path in expected or not _is_free_generated(path):
                continue
            if not dry_run:
                path.unlink()
            removed.append(path.relative_to(root).as_posix())
        if not dry_run:
            _remove_empty_dirs(base)

    return {
        "written": written,
        "unchanged": unchanged,
        "removed": len(removed),
        "removed_examples": removed[:20],
        "total_files": len(expected),
        "dry_run": dry_run,
    }


def _free_paths(candidates: dict[str, Any], output_dir: Path) -> dict[Path, dict[str, Any]]:
    """Map output paths to provider-local free-candidate documents."""
    base = Path(output_dir)
    schema_version = candidates.get("schema_version", 1)
    sources = candidates.get("sources") or []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in candidates.get("candidates") or []:
        grouped.setdefault(str(record.get("provider") or "unknown"), []).append(record)

    filenames: dict[str, str] = {}
    expected: dict[Path, dict[str, Any]] = {}
    for provider in sorted(grouped):
        filename = slugify(provider) + ".json"
        if filename in filenames:
            raise ValueError(f"Free-candidate filename collision: {provider}")
        filenames[provider] = filename
        summary = (candidates.get("providers") or {}).get(provider) or {}
        # The envelope already carries the generation marker and provider.
        # Keep only candidate-specific fields; drop legacy names/evidence that
        # used to be repeated on every entry.
        records = [
            {
                key: value
                for key, value in item.items()
                if key not in ("_generated_by", "provider", "slug", "model_file", "signals", "source_names")
            }
            for item in sorted(grouped[provider], key=lambda item: str(item.get("model") or ""))
        ]
        expected[base / filename] = {
            "_generated_by": GENERATED_BY,
            "schema_version": schema_version,
            "sources": sources,
            "provider": provider,
            "name": summary.get("name") or provider,
            "signals": sorted(summary.get("signals") or []),
            "candidate_count": len(records),
            "candidates": records,
        }

    index = {
        "_generated_by": GENERATED_BY,
        "schema_version": schema_version,
        "sources": sources,
        "counts": candidates.get("counts") or {},
        "providers": [
            {
                "provider": provider,
                "file": filenames[provider],
                "name": ((candidates.get("providers") or {}).get(provider) or {}).get("name") or provider,
                "candidate_count": len(grouped[provider]),
            }
            for provider in sorted(grouped)
        ],
    }
    expected[base / FREE_INDEX_FILE] = index
    return expected


def sync_free_candidates(
    candidates: dict[str, Any],
    output_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write provider-local free candidates and prune stale generated files.

    A pre-existing manual file is never overwritten; generated output is
    replaced atomically and is byte-stable like the main dataset. ``output_dir``
    is the free-tier cache's candidates directory, not the versioned root.
    """
    output_dir = Path(output_dir)
    expected = _free_paths(candidates, output_dir)
    written = 0
    unchanged = 0
    removed: list[str] = []

    for path, record in sorted(expected.items(), key=lambda item: str(item[0])):
        text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        if path.exists():
            current = path.read_text(encoding="utf-8")
            if current == text:
                unchanged += 1
                continue
            if not _is_generated(path):
                raise ValueError(f"Refusing to overwrite non-generated file: {path}")
        if not dry_run:
            write_json(path, record)
        written += 1

    if output_dir.is_dir():
        for path in sorted(output_dir.glob("*.json")):
            if path in expected or not _is_generated(path):
                continue
            if not dry_run:
                path.unlink()
            removed.append(path.name)

    return {
        "written": written,
        "unchanged": unchanged,
        "removed": len(removed),
        "removed_examples": removed[:20],
        "total_files": len(expected),
        "directory": output_dir.as_posix(),
        "dry_run": dry_run,
    }
