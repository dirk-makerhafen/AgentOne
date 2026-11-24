"""Collapse dated/vendor-prefixed/model-variant duplicates onto one canonical card.

The upstream feeds publish the same model many times: with a date
(``claude-3-5-sonnet-20241022``, ``devstral-small-2507``, ``grok-4-0709``), a
variant tag (``...-v2``, ``...-instruct``, ``...-fp8``), a deployment suffix
(``...-tee``, ``...-maas``) or a vendor prefix (``anthropic-claude-...``).
Those are variants of one model card, not separate models.

This pass groups such IDs by their clean base, picks the newest dated variant
as the source of facts, and stores everything under the base slug.  Older IDs
survive in ``variants``, ``aliases`` and each offering's
``provider_model_ids``, so the exact strings needed for API calls are not lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from registry.catalog.normalize import sort_sources

_VENDOR_FAMILIES: dict[str, tuple[str, ...]] = {
    "anthropic": ("claude",),
    "openai": ("gpt", "o1", "o3", "o4", "codex"),
    "google": ("gemini", "gemma"),
    "meta": ("llama",),
    "deepseek": ("deepseek",),
    "qwen": ("qwen",),
    "xai": ("grok",),
    "moonshotai": ("kimi",),
    "ai21": ("jamba",),
    "cohere": ("command",),
    "nvidia": ("nemotron",),
    "perplexity": ("sonar",),
}

_VARIANT = re.compile(r"^v\d+$")
_CONTEXT_TOKEN = re.compile(r"^\d+[km]$", re.I)

# A few upstream feeds abbreviate a model ID by dropping its architecture tag.
# Keep this table explicit; fuzzy prefix matching would merge unrelated models.
MODEL_BASE_ALIASES: dict[str, str] = {
    "qwen3-235b": "qwen3-235b-a22b",
}

# Trailing tokens that describe a build/deployment/mode of the same model,
# rather than a different model.  Deliberately excludes product tiers such as
# ``flash``, ``pro``, ``lite``, ``mini`` and ``coder``, which are distinct
# models.  The allowlist is explicit so grouping stays deterministic.
_MODIFIERS = frozenset(
    {
        "instruct",
        "chat",
        "thinking",
        "reasoning",
        "non-reasoning",
        "exp",
        "preview",
        "fp8",
        "fp4",
        "fp16",
        "awq",
        "int4",
        "int8",
        "bf16",
        "turbo",
        "fast",
        "original",
        "abliterated",
        "hf",
        "lora",
        "tee",
        "tput",
        "maas",
        "cs",
        "multi-agent",
    }
)

RICH_FIELDS = (
    "release_date",
    "last_updated",
    "reasoning_options",
    "interleaved",
    "cost",
    "context_window",
    "modalities",
    "description",
)


@dataclass(frozen=True)
class VersionInfo:
    """Parsed identity parts of a canonical model slug."""

    base: str
    date: str  # normalized YYYYMMDD, with 00 for an unknown month/day
    variant: int  # trailing vN, or 0
    modifiers: tuple[str, ...]  # trailing build/deployment/mode tokens
    vendor_stripped: str


def _strip_vendor_prefix(slug: str) -> str:
    vendor, dash, remainder = slug.partition("-")
    if not dash or vendor not in _VENDOR_FAMILIES:
        return slug
    if remainder.startswith(_VENDOR_FAMILIES[vendor]):
        return remainder
    return slug


def _record_dates(record: dict[str, Any] | None) -> list[tuple[int, int, int]]:
    result: list[tuple[int, int, int]] = []
    for key in ("release_date", "last_updated"):
        value = str((record or {}).get(key) or "")
        match = re.match(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", value)
        if match:
            result.append((int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)))
    return result


def _year_for_month(month: int, record: dict[str, Any] | None) -> int:
    dates = _record_dates(record)
    for year, record_month, _ in dates:
        if record_month == month:
            return year
    return max((year for year, _, _ in dates), default=2000)


def _four_digit_date(token: str, record: dict[str, Any] | None) -> tuple[int, int, int] | None:
    """Disambiguate ``MMDD`` from ``YYMM`` using the record's dates when possible."""
    first, second = int(token[:2]), int(token[2:])
    for year, month, day in _record_dates(record):
        if first == month and (not day or second == day):
            return year, first, second
    if 1 <= first <= 12 and 1 <= second <= 31:
        return _year_for_month(first, record), first, second
    if 1 <= second <= 12:
        return 2000 + first, second, 0
    return None


def _take_date(parts: list[str], record: dict[str, Any] | None) -> str:
    # pylint: disable=too-many-branches,too-many-return-statements
    """Remove a trailing date token from *parts* and return normalized YYYYMMDD."""
    if len(parts) >= 3:
        first, second, third = parts[-3:]
        if all(part.isdigit() for part in (first, second, third)):
            if len(first) == 4 and len(second) == 2 and len(third) == 2:
                del parts[-3:]
                return first + second + third
            if len(first) == 2 and len(second) == 2 and len(third) == 4 and third[:2] in ("19", "20"):
                del parts[-3:]
                return third + first + second

    if len(parts) >= 2:
        first, second = parts[-2:]
        if first.isdigit() and second.isdigit():
            if len(first) == 2 and len(second) == 4 and second[:2] in ("19", "20"):
                del parts[-2:]
                return second + first + "00"
            if len(first) == 4 and first[:2] in ("19", "20") and len(second) == 2:
                del parts[-2:]
                return first + second + "00"
            if len(first) == 2 and len(second) == 2:
                if 1 <= int(first) <= 12:
                    del parts[-2:]
                    return f"{_year_for_month(int(first), record):04d}{first}{second}"
                parsed = _four_digit_date(first + second, record)
                if parsed:
                    del parts[-2:]
                    year, month, day = parsed
                    return f"{year:04d}{month:02d}{day:02d}"

    last = parts[-1]
    if not last.isdigit():
        return ""
    if len(last) == 8 and last[:2] in ("19", "20"):
        parts.pop()
        return last
    if len(last) == 6:
        parts.pop()
        return last + "00" if last[:2] in ("19", "20") else "20" + last
    if len(last) == 4:
        parsed = _four_digit_date(last, record)
        if parsed:
            parts.pop()
            year, month, day = parsed
            return f"{year:04d}{month:02d}{day:02d}"
    return ""


def _is_modifier(token: str) -> bool:
    return token.lower() in _MODIFIERS or bool(_CONTEXT_TOKEN.match(token))


def version_info(slug: str, record: dict[str, Any] | None = None) -> VersionInfo:
    """Split a slug into its clean base, embedded date, variant and modifiers."""
    clean = _strip_vendor_prefix(slug)
    parts = clean.split("-")

    variant = 0
    while parts:
        if _VARIANT.match(parts[-1]):
            variant = int(parts[-1][1:])
            parts.pop()
            continue
        if len(parts) >= 2 and parts[-1].isdigit() and _VARIANT.match(parts[-2]):
            variant = int(parts[-2][1:])
            del parts[-2:]
            continue
        break

    modifiers: list[str] = []
    date = ""
    while parts:
        changed = False
        while parts and _is_modifier(parts[-1]):
            modifiers.insert(0, parts.pop())
            changed = True
        found = _take_date(parts, record)
        if found:
            date = max(date, found)
            changed = True
        if not changed:
            break

    base = "-".join(parts) or clean
    return VersionInfo(
        base=base,
        date=date,
        variant=variant,
        modifiers=tuple(modifiers),
        vendor_stripped=clean,
    )


def _rank(slug: str, record: dict[str, Any]) -> tuple[Any, ...]:
    """Newest dated variant wins; other fields are deterministic tie-breakers."""
    info = version_info(slug, record)
    return (
        info.date,
        info.variant,
        str(record.get("last_updated") or ""),
        str(record.get("release_date") or ""),
        len(record.get("sources") or []),
        sum(field in record for field in RICH_FIELDS),
    )


def model_base(slug: str, record: dict[str, Any] | None = None) -> str:
    """Return the canonical base slug used to group provider-local variants."""
    base = version_info(slug, record).base
    return MODEL_BASE_ALIASES.get(base, base)


def _merge_model_into(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Fill missing fields and union provenance from a lower-ranked record."""
    for key, value in source.items():
        if key in ("aliases", "sources", "variants", "provider_model_ids"):
            continue
        if target.get(key) in (None, "", [], {}):
            target[key] = value
    target["aliases"] = sorted(set(target.get("aliases") or []) | set(source.get("aliases") or []))
    target["sources"] = sort_sources(list(target.get("sources") or []) + list(source.get("sources") or []))
    target["variants"] = sorted(set(target.get("variants") or []) | set(source.get("variants") or []))


def consolidate_versions(
    models: dict[tuple[str, str], dict],
) -> dict[tuple[str, str], list[str]]:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Collapse provider-local version aliases in place.

    Models are keyed by ``(provider_slug, model_slug)``.  Grouping is scoped to
    one provider so two providers publishing the same model are not merged into
    a single file.  Returns ``(provider, base) -> original slugs`` for groups
    that actually collapsed.
    """
    infos = {key: version_info(key[1], record) for key, record in models.items()}
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for key, info in infos.items():
        base = MODEL_BASE_ALIASES.get(info.base, info.base)
        groups.setdefault((key[0], base), []).append(key)

    collapsed: dict[tuple[str, str], list[str]] = {}
    replacements: dict[tuple[str, str], tuple[str, str, str]] = {}
    for (provider_slug, base), keys in sorted(groups.items()):
        if len(keys) == 1 and keys[0] == (provider_slug, base):
            continue
        ranked = sorted(keys, key=lambda key: _rank(key[1], models[key]), reverse=True)
        winner_key = ranked[0]
        merged = dict(models[winner_key])
        primary_id = merged.get("provider_model_id") or ""
        ids = list(merged.get("provider_model_ids") or [])
        merged["model"] = base
        merged["slug"] = base
        for key in ranked:
            if key == winner_key:
                continue
            ids.extend(models[key].get("provider_model_ids") or [])
            _merge_model_into(merged, models[key])
        aliases = set(merged.get("aliases") or []) | {key[1] for key in keys} | {base}
        # Prefer an exact-base canonical_id, then any other undated variant.
        undated = [key for key in ranked if not infos[key].date]
        candidates = (
            ([winner_key] if winner_key[1] == base else [])
            + [key for key in undated if key[1] == base]
            + [key for key in undated if key[1] != base]
        )
        for key in candidates:
            candidate = models[key].get("canonical_id")
            if candidate:
                merged["canonical_id"] = candidate
                break
        merged["aliases"] = sorted(aliases)
        merged["provider_model_ids"] = list(dict.fromkeys(ids + ([primary_id] if primary_id else [])))
        variants = sorted({key[1] for key in keys} - {base})
        if variants:
            merged["variants"] = variants
        collapsed[(provider_slug, base)] = variants
        for key in keys:
            replacements[key] = (provider_slug, base, key[1])
            if key != (provider_slug, base):
                models.pop(key, None)
        models[(provider_slug, base)] = merged

    if not replacements:
        return collapsed

    # Re-key any records that were collapsed more than once (for example when
    # a free-catalog pass runs after the opencode base pass).
    for old_key in list(models):
        provider_slug, base, old_slug = replacements.get(old_key, (old_key[0], old_key[1], old_key[1]))
        if (provider_slug, base) != old_key:
            record = models.pop(old_key)
            record["model"] = base
            models[(provider_slug, base)] = record
        elif old_slug != base:
            models[old_key]["model"] = base
    return collapsed
