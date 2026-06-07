"""Data collection manifest loader — loads stream/set definitions from YAML frontmatter files.

Streams are loaded from ``.agentone/streams/*.md``.
Sets are loaded from ``.agentone/sets/*.md``.
"""
from __future__ import annotations

from pathlib import Path

import frontmatter

from server.models.collections import DataCollection


def _infer_collection_type(file_path: Path) -> str:
    """Infer the collection type from the parent directory name."""
    parent = file_path.parent.name
    if parent == "streams":
        return "stream"
    if parent == "sets":
        return "set"
    # Fallback — try explicit ``type`` key in the manifest
    return "stream"


def load_data_collection_manifest(
    md_path: Path,
    seen_names: set[str] | None = None,
) -> DataCollection:
    """Create or update a ``DataCollection`` from a YAML frontmatter file.

    Parameters
    ----------
    md_path:
        Path to the ``.md`` file with YAML frontmatter.
    seen_names:
        Optional set — the collection's name is added so that the caller can
        later archive any collections that were not mentioned in the
        manifest files.

    Returns
    -------
    The created or updated ``DataCollection`` instance.
    """
    # pylint: disable=too-many-locals
    manifest = frontmatter.load(md_path)

    name = manifest.get("name", "")
    if not name:
        raise ValueError(f"Data-collection file {md_path} is missing 'name'")
    if seen_names is not None:
        seen_names.add(name)

    # --- infer / normalise type -------------------------------------------
    collection_type = manifest.get("type", "") or _infer_collection_type(md_path)
    if collection_type not in ("stream", "set"):
        raise ValueError(
            f"Collection '{name}': type must be 'stream' or 'set', "
            f"got {collection_type!r}"
        )

    # --- sources -----------------------------------------------------------
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        sources = [sources]

    # --- processor ---------------------------------------------------------
    processor = manifest.get("processor", {})
    if not isinstance(processor, dict):
        processor = {}

    # --- on_removed (sets only) --------------------------------------------
    on_removed = manifest.get("on_removed", {})
    if not isinstance(on_removed, dict):
        on_removed = {}

    # --- member / score field lambdas (sets only) --------------------------
    member_field = manifest.get("member_field", "") or ""
    score_field = manifest.get("score_field", "") or ""

    # --- reprocess / backfill ----------------------------------------------
    retroactive_on_source_change = int(
        manifest.get("retroactive_on_source_change", 0) or 0
    )
    max_reprocess = int(manifest.get("max_reprocess", 0) or 0)
    # also accept older/spelled-out field names
    if "on_source_update_retroactive_add" in manifest:
        retroactive_on_source_change = int(
            manifest["on_source_update_retroactive_add"]
        )
    if "on_processor_updated_max_reprocess" in manifest:
        max_reprocess = int(manifest["on_processor_updated_max_reprocess"])

    # --- upsert ------------------------------------------------------------
    # Snapshot old sources before update to detect changes for retroactive
    old_sources = None
    try:
        existing = DataCollection.objects.get(name=name)
        old_sources = existing.sources
    except DataCollection.DoesNotExist:
        pass

    collection, created = DataCollection.objects.update_or_create(
        name=name,
        defaults={
            "description": manifest.get("description", "") or "",
            "collection_type": collection_type,
            "is_active": manifest.get("is_active", True),
            "sources": sources,
            "processor": processor,
            "on_removed": on_removed,
            "member_field": member_field,
            "score_field": score_field,
            "retroactive_on_source_change": retroactive_on_source_change,
            "max_reprocess": max_reprocess,
        },
    )

    # If sources changed and retroactive processing is configured, trigger it
    if (
        not created
        and old_sources is not None
        and old_sources != sources
        and retroactive_on_source_change > 0
    ):
        from server.tasks.reprocess_collection import reprocess_collection
        try:
            reprocess_collection.delay(name, max_items=retroactive_on_source_change)
        except Exception:
            pass  # Celery may not be available (e.g., in tests)

    return collection
