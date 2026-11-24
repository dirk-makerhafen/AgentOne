"""Build the provider-local JSON dataset from raw upstream payloads.

OpenCode's curated models fixture is the base: it decides which providers and
models exist.  The two free-LLM catalogs are a second pass that only adds
providers and models OpenCode does not list; they never overwrite an existing
OpenCode record.  Every model file lives next to its provider file, so there is
no global ``models/`` output.

This is a pure transform: no network, no database, no filesystem writes.  For a
new record, source priority is fixed in ``normalize.SOURCE_PRIORITY``.  This
step deliberately does *not* decide whether anything is free; raw costs, quota
labels and limits are kept for a later verification pass.  Models whose newest
known release/update date predates ``MODEL_CUTOFF_YEAR`` are removed.
"""

from __future__ import annotations

import re
from typing import Any

from registry.catalog.normalize import (
    GENERATED_BY,
    SDK_DEFAULT_API_BASES,
    SOURCE_PRIORITY,
    canonical_model_slug,
    catalog_quirks,
    infer_developer,
    parse_size,
    resolve_provider_slug,
    sort_sources,
)
from registry.catalog.sources import SourceBundle
from registry.catalog.versions import consolidate_versions, model_base

AWESOME = "awesome-free-llm-apis"
FREELLMAPI = "freellmapi-catalog"
OPENCODE = "opencode-models-api"

# Models whose newest known date predates this year are too old to keep.
MODEL_CUTOFF_YEAR = 2025
_YEAR_PREFIX = re.compile(r"^(\d{4})")


def _source_ref(source: str, provider: Any, raw_id: Any) -> dict[str, str]:
    return {"source": source, "provider": str(provider or ""), "raw_id": str(raw_id or "")}


def _add_source(record: dict[str, Any], ref: dict[str, str]) -> None:
    sources = record.setdefault("sources", [])
    if ref not in sources:
        sources.append(ref)


def _new_provider(slug: str) -> dict[str, Any]:
    return {"_generated_by": GENERATED_BY, "slug": slug, "aliases": set(), "sources": []}


def _new_model(provider: str, slug: str) -> dict[str, Any]:
    return {
        "_generated_by": GENERATED_BY,
        "provider": provider,
        "model": slug,
        "provider_model_ids": [],
        "aliases": set(),
        "sources": [],
    }


def _add_fields(record: dict[str, Any], fields: dict[str, Any]) -> None:
    for field, value in fields.items():
        if value not in (None, "", [], {}):
            record.setdefault(field, value)


def _add_raw_model_id(record: dict[str, Any], raw_id: Any, display_name: Any = None) -> None:
    raw = str(raw_id)
    if raw not in record["provider_model_ids"]:
        record["provider_model_ids"].append(raw)
    record.setdefault("provider_model_id", raw)
    record["aliases"].add(raw)
    if display_name:
        record["aliases"].add(str(display_name))


def _ingest_opencode(
    payload: dict[str, Any],
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
) -> None:
    # pylint: disable=too-many-locals
    for provider_id in sorted(payload):
        raw_provider = payload[provider_id]
        if not isinstance(raw_provider, dict):
            continue
        slug = resolve_provider_slug(provider_id, raw_provider.get("name"))
        provider = providers.setdefault(slug, _new_provider(slug))
        ref = _source_ref(OPENCODE, provider_id, provider_id)
        _add_source(provider, ref)
        provider["aliases"].add(str(provider_id))
        if raw_provider.get("name"):
            provider["aliases"].add(str(raw_provider["name"]))

        _add_fields(
            provider,
            {
                "name": raw_provider.get("name"),
                "api_base": raw_provider.get("api"),
                "doc": raw_provider.get("doc"),
                "env": raw_provider.get("env"),
                "npm": raw_provider.get("npm"),
            },
        )
        npm = raw_provider.get("npm")
        if npm and npm in SDK_DEFAULT_API_BASES:
            provider.setdefault("sdk_default_api_base", SDK_DEFAULT_API_BASES[str(npm)])

        for model_id in sorted(raw_provider.get("models") or {}):
            raw_model = raw_provider["models"][model_id]
            if not isinstance(raw_model, dict):
                continue
            model_slug = canonical_model_slug(model_id)
            key = (slug, model_slug)
            record = models.setdefault(key, _new_model(slug, model_slug))
            model_ref = _source_ref(OPENCODE, provider_id, model_id)
            _add_source(record, model_ref)
            _add_raw_model_id(record, model_id, raw_model.get("name"))

            limit = raw_model.get("limit") or {}
            _add_fields(
                record,
                {
                    "name": raw_model.get("name"),
                    "family": raw_model.get("family"),
                    "description": raw_model.get("description"),
                    "reasoning": raw_model.get("reasoning"),
                    "reasoning_options": raw_model.get("reasoning_options"),
                    "tool_call": raw_model.get("tool_call"),
                    "interleaved": raw_model.get("interleaved"),
                    "structured_output": raw_model.get("structured_output"),
                    "temperature": raw_model.get("temperature"),
                    "attachment": raw_model.get("attachment"),
                    "knowledge_cutoff": raw_model.get("knowledge"),
                    "release_date": raw_model.get("release_date"),
                    "last_updated": raw_model.get("last_updated"),
                    "modalities": raw_model.get("modalities"),
                    "open_weights": raw_model.get("open_weights"),
                    "context_window": limit.get("context") if isinstance(limit, dict) else None,
                    "max_output_tokens": limit.get("output") if isinstance(limit, dict) else None,
                    "cost": raw_model.get("cost"),
                    "status": raw_model.get("status"),
                    "experimental": raw_model.get("experimental"),
                    "canonical_id": str(model_id) if "/" in str(model_id) else None,
                    "endpoint": (
                        raw_model["provider"].get("api")
                        if isinstance(raw_model.get("provider"), dict)
                        else None
                    ),
                },
            )


def _ingest_freellmapi(
    payload: dict[str, Any],
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
) -> None:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    platform_names = {
        item.get("id"): item.get("name") or item.get("id")
        for item in payload.get("platforms") or []
        if isinstance(item, dict) and item.get("id")
    }
    for platform_id, display_name in sorted(platform_names.items()):
        slug = resolve_provider_slug(platform_id, display_name)
        provider = providers.setdefault(slug, _new_provider(slug))
        ref = _source_ref(FREELLMAPI, platform_id, platform_id)
        _add_source(provider, ref)
        provider["aliases"].add(str(platform_id))
        provider["aliases"].add(str(display_name))
        _add_fields(
            provider,
            {
                "catalog_name": display_name,
                "catalog_version": payload.get("version"),
                "catalog_quirks": catalog_quirks(payload, str(platform_id)),
            },
        )

    for item in sorted(payload.get("models") or [], key=lambda row: str(row.get("modelId", ""))):
        if not isinstance(item, dict):
            continue
        platform_id = str(item.get("platform") or "")
        model_id = str(item.get("modelId") or "")
        if not model_id:
            continue
        provider_slug = resolve_provider_slug(platform_id, platform_names.get(platform_id, ""))
        model_slug = canonical_model_slug(model_id)
        model_fields = {
            "name": item.get("displayName"),
            "context_window": item.get("contextWindow"),
            "tool_call": item.get("supportsTools"),
            "catalog_intelligence_rank": item.get("intelligenceRank"),
            "catalog_speed_rank": item.get("speedRank"),
            "catalog_size_label": item.get("sizeLabel"),
            "catalog_media_note": item.get("mediaNote"),
            "catalog_request_style": item.get("requestStyle"),
            "catalog_enabled": item.get("enabled"),
        }
        if item.get("supportsVision"):
            model_fields["modalities"] = {"input": ["text", "image"], "output": ["text"]}
        base = model_base(model_slug, model_fields)
        if (provider_slug, base) in models:  # OpenCode already has this model
            continue

        key = (provider_slug, model_slug)
        record = models.setdefault(key, _new_model(provider_slug, model_slug))
        model_ref = _source_ref(FREELLMAPI, platform_id, model_id)
        _add_source(record, model_ref)
        _add_raw_model_id(record, model_id, item.get("displayName"))
        _add_fields(record, model_fields)

        _add_fields(
            record,
            {
                "quota_label": item.get("monthlyTokenBudget"),
                "premium_since": item.get("premiumSince"),
                "request_style": item.get("requestStyle"),
                "media_note": item.get("mediaNote"),
                "catalog_quirks": catalog_quirks(payload, platform_id, model_id),
            },
        )


def _ingest_awesome(
    payload: dict[str, Any],
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
) -> None:
    # pylint: disable=too-many-locals,too-many-branches
    for raw_provider in sorted(payload.get("providers") or [], key=lambda row: str(row.get("name", ""))):
        if not isinstance(raw_provider, dict):
            continue
        name = str(raw_provider.get("name") or "")
        slug = resolve_provider_slug(name, name)
        provider = providers.setdefault(slug, _new_provider(slug))
        ref = _source_ref(AWESOME, name, name)
        _add_source(provider, ref)
        provider["aliases"].add(name)
        _add_fields(
            provider,
            {
                "name": name,
                "api_base": raw_provider.get("baseUrl"),
                "url": raw_provider.get("url"),
                "description": raw_provider.get("description"),
                "country": raw_provider.get("country"),
                "flag": raw_provider.get("flag"),
                "category": raw_provider.get("category"),
                "footnote_ref": raw_provider.get("footnoteRef"),
            },
        )

        for item in raw_provider.get("models") or []:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "")
            if not model_id:
                continue
            model_slug = canonical_model_slug(model_id)
            model_fields = {
                "name": item.get("name"),
                "context_label": item.get("context"),
                "max_output_label": item.get("maxOutput"),
                "modality_label": item.get("modality"),
                "canonical_id": model_id if "/" in model_id else None,
                "context_window": parse_size(item.get("context")),
                "max_output_tokens": parse_size(item.get("maxOutput")),
            }
            if model_base(model_slug, model_fields) in {
                slug for provider_slug, slug in models if provider_slug == provider["slug"]
            }:
                continue

            key = (provider["slug"], model_slug)
            record = models.setdefault(key, _new_model(provider["slug"], model_slug))
            model_ref = _source_ref(AWESOME, name, model_id)
            _add_source(record, model_ref)
            _add_raw_model_id(record, model_id, item.get("name"))
            _add_fields(record, model_fields)
            _add_fields(record, {"rate_limit_label": item.get("rateLimit")})


def _finalize(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize accumulators into stable, JSON-serializable records."""
    result: dict[str, Any] = {}
    for key, value in record.items():
        if key == "aliases":
            result[key] = sorted(value)
        elif key == "sources":
            result[key] = sort_sources(value)
        elif key == "provider_model_ids":
            result[key] = list(dict.fromkeys(value))
        elif value not in (None, "", [], {}):
            result[key] = value
    raw_ids = record.get("aliases", set())
    if "developer" not in result and record.get("slug"):
        developer = infer_developer(str(record["slug"]), raw_ids)
        if developer:
            result["developer"] = developer
    return result


def _prune_unusable_providers(
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
) -> None:
    """Keep only providers AgentOne can actually call."""
    for slug, record in list(providers.items()):
        sdk_default = record.pop("sdk_default_api_base", "")
        if record.get("api_base"):
            continue
        if sdk_default:
            record["api_base"] = sdk_default
            record["api_base_source"] = "sdk-default"
            continue
        endpoints = {
            record["endpoint"]
            for (provider_slug, _), record in models.items()
            if provider_slug == slug and record.get("endpoint")
        }
        if len(endpoints) == 1:
            record["api_base"] = next(iter(endpoints))
            record["api_base_source"] = "offering-endpoint"
            continue
        providers.pop(slug)

    for key in list(models):
        if key[0] not in providers:
            models.pop(key)


def _prune_old_models(
    providers: dict[str, dict],
    models: dict[tuple[str, str], dict],
) -> None:
    """Drop models whose newest known release/update year predates the cutoff."""
    for key, record in list(models.items()):
        years = []
        for field in ("release_date", "last_updated"):
            match = _YEAR_PREFIX.match(str(record.get(field) or ""))
            if match:
                years.append(int(match.group(1)))
        if years and max(years) < MODEL_CUTOFF_YEAR:
            models.pop(key)

    used_providers = {provider_slug for provider_slug, _ in models}
    for slug in list(providers):
        if slug not in used_providers:
            providers.pop(slug)


def build_dataset(bundle: SourceBundle) -> tuple[dict[str, dict], dict[tuple[str, str], dict]]:
    """Return ``(providers, provider_local_models)`` keyed by canonical IDs.

    OpenCode supplies the base set; the free-LLM catalogs only add what it
    misses.  Records are pure source facts; no free-tier verdict is computed.
    """
    providers: dict[str, dict] = {}
    models: dict[tuple[str, str], dict] = {}

    ingesters = {
        OPENCODE: _ingest_opencode,
        FREELLMAPI: _ingest_freellmapi,
        AWESOME: _ingest_awesome,
    }
    payloads = {
        OPENCODE: bundle.opencode,
        FREELLMAPI: bundle.freellmapi,
        AWESOME: bundle.awesome,
    }
    for source in SOURCE_PRIORITY:
        payload = payloads.get(source) or {}
        if not payload:
            continue
        ingesters[source](payload, providers, models)
        if source == OPENCODE:
            consolidate_versions(models)
    consolidate_versions(models)

    _prune_unusable_providers(providers, models)
    _prune_old_models(providers, models)

    for provider_slug, _ in models:
        providers[provider_slug].setdefault("model_count", 0)
        providers[provider_slug]["model_count"] += 1

    final_providers = {slug: _finalize(record) for slug, record in sorted(providers.items())}
    final_models = {key: _finalize(record) for key, record in sorted(models.items())}
    return final_providers, final_models
