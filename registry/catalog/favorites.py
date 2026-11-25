"""Curated model favourites.

The favourites file lives next to the catalog at
``<root>/.agentone/models/favorites.yaml``::

    favorites:
      - glm-5.3
      - qwen3-8-flash

Entries match ``AiModel.slug``, ``name`` or ``canonical_id``.  Curated stars
are reapplied on every catalog reload; a star the user set from the UI
(``favorite_origin="user"``) is never touched, and a stale curated star is
removed when its entry disappears from the file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

FAVORITES_RELATIVE = Path("models") / "favorites.yaml"


def favorites_path(base_dir: Path) -> Path:
    return Path(base_dir) / FAVORITES_RELATIVE


def load_favorite_tokens(base_dir: Path) -> list[str] | None:
    """Read the curated favourites list (``None`` when the file is absent)."""
    path = favorites_path(base_dir)
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(data, list):
        entries: Any = data
    elif isinstance(data, dict):
        entries = data.get("favorites", data.get("models", []))
    else:
        return None
    if not isinstance(entries, (list, tuple)):
        return None
    tokens: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            token = entry.strip()
        elif isinstance(entry, dict):
            token = str(entry.get("slug") or entry.get("name") or "").strip()
        else:
            token = ""
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def apply_curated_favorites(base_dir: Path) -> int:
    """Apply the curated favourites file to ``AiModel`` rows.

    Returns the number of rows changed.  Missing file = no-op, so a hand-made
    deployment that never creates the file keeps its user stars untouched.
    """
    tokens = load_favorite_tokens(base_dir)
    if tokens is None:
        return 0

    from django.db.models import Q

    from server.models.providers.ai_model import AiModel

    query = Q()
    for token in tokens:
        query |= Q(slug=token) | Q(name=token) | Q(canonical_id=token)
    curated_ids = set(AiModel.objects.filter(query).values_list("pk", flat=True)) if tokens else set()

    changed = 0
    for model in AiModel.objects.filter(pk__in=curated_ids).exclude(favorite_origin="user"):
        if model.is_favorite and model.favorite_origin == "curated":
            continue
        model.is_favorite = True
        model.favorite_origin = "curated"
        model.save(update_fields=["is_favorite", "favorite_origin"])
        changed += 1

    for model in AiModel.objects.filter(favorite_origin="curated").exclude(pk__in=curated_ids):
        model.is_favorite = False
        model.favorite_origin = ""
        model.save(update_fields=["is_favorite", "favorite_origin"])
        changed += 1
    return changed
