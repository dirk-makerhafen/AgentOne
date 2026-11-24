"""Deterministic extraction of free-offering leads from the upstream sources.

This is **part 1** of the free-tier workflow.  It only extracts and preserves
facts that the sources actually state: free markers in model IDs, zero costs,
quota/rate labels, ranks, quirks, capabilities and provenance.  It deliberately
does not decide whether an offering is free or usable -- that verification is a
later, agent-driven step.

Output is a small per-provider pointer file.  Model-level facts and raw source
records are moved into the regular provider model files (created when missing),
so part 2 can read compact free evidence without rereading model metadata.
"""

from __future__ import annotations

# The free extractor intentionally mirrors a few provenance helpers from the
# main builder; keeping them local avoids coupling the two build passes.
# pylint: disable=duplicate-code

import copy
import json
import re
from collections import defaultdict
from typing import Any, Iterable

from registry.catalog.build import (
    AWESOME,
    FREELLMAPI,
    MODEL_CUTOFF_YEAR,
    OPENCODE,
)
from registry.catalog.cards import DOC_SOURCE, SOURCE as SOURCE_CARDS
from registry.catalog.normalize import (
    GENERATED_BY,
    FREE_MODEL_SOURCE,
    canonical_model_slug,
    catalog_quirks,
    parse_budget_limits,
    parse_rate_limit,
    parse_size,
    resolve_provider_slug,
    sort_sources,
)
from registry.catalog.versions import model_base

SOURCE_LIVE = "opencode-live-models"
SOURCE_PROVIDER_MODELS = "provider-models-api"
SOURCE_CATALOG = "catalog-provider"
SCHEMA_VERSION = 3
FACT_PRIORITY = (SOURCE_LIVE, OPENCODE, FREELLMAPI, AWESOME, SOURCE_PROVIDER_MODELS)
SOURCE_ORDER = (
    SOURCE_LIVE,
    OPENCODE,
    FREELLMAPI,
    AWESOME,
    SOURCE_PROVIDER_MODELS,
)

_FREE_MARKER = re.compile(r"(?i)(?:^|[-_:./])free(?:$|[-_:./])")
_YEAR_PREFIX = re.compile(r"^(\d{4})")


def free_markers(*values: Any) -> list[str]:
    """Return explicit ``free`` tokens found in model IDs/names."""
    found: list[str] = []
    for value in values:
        text = str(value or "")
        for match in _FREE_MARKER.finditer(text):
            marker = match.group(0)
            if marker not in found:
                found.append(marker)
    return found


def all_zero_prices(value: Any) -> bool:
    """True when a cost structure contains numbers and every one is zero."""
    prices: list[float | int] = []

    def collect(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                collect(child)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            prices.append(item)

    collect(value)
    return bool(prices) and all(price == 0 for price in prices)


def model_list_items(payload: Any) -> list[dict[str, Any]]:
    # pylint: disable=too-many-return-statements
    """Normalize the common provider ``/models`` response shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("models"), list):
        return [item for item in data["models"] if isinstance(item, dict)]

    models = payload.get("models")
    if isinstance(models, list):
        return [item for item in models if isinstance(item, dict)]
    if isinstance(models, dict):
        return [
            {**value, "id": key} if isinstance(value, dict) else {"id": key}
            for key, value in models.items()
        ]

    items: list[dict[str, Any]] = []
    for key, value in payload.items():
        if key.startswith("_"):
            continue
        items.append({**value, "id": key} if isinstance(value, dict) else {"id": key})
    return items


def model_item_id(item: dict[str, Any]) -> str:
    """Best-effort raw model ID from an arbitrary provider model item."""
    for key in ("id", "model", "model_id", "name", "slug"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _new_candidate(provider: str, slug: str) -> dict[str, Any]:
    return {
        "_generated_by": GENERATED_BY,
        "provider": provider,
        "slug": slug,
        "provider_model_ids": set(),
        "aliases": set(),
        "variants": set(),
        "signals": set(),
        "sources": [],
        "api_bases": set(),
        "raw": {},
        "_facts": {},
    }


def _add_source(candidate: dict[str, Any], ref: dict[str, str]) -> None:
    if ref not in candidate["sources"]:
        candidate["sources"].append(ref)


def _add_raw(candidate: dict[str, Any], source: str, item: dict[str, Any]) -> None:
    bucket = candidate["raw"].setdefault(source, {})
    key = json.dumps(item, sort_keys=True, ensure_ascii=False)
    bucket[key] = item


def _add_facts(candidate: dict[str, Any], source: str, facts: dict[str, Any]) -> None:
    current = candidate["_facts"].setdefault(source, {})
    for key, value in facts.items():
        if value not in (None, "", [], {}) and key not in current:
            current[key] = value


def _add_signals(candidate: dict[str, Any], signals: Iterable[str]) -> None:
    candidate["signals"].update(signal for signal in signals if signal)


def _add_item(
    candidates: dict[tuple[str, str], dict[str, Any]],
    *,
    source: str,
    provider: str,
    raw_id: Any,
    item: dict[str, Any],
    signals: Iterable[str] = (),
    aliases: Iterable[Any] = (),
    source_provider: Any = None,
) -> dict[str, Any]:
    # pylint: disable=too-many-arguments
    slug = model_base(canonical_model_slug(raw_id), item)
    key = (provider, slug)
    candidate = candidates.setdefault(key, _new_candidate(provider, slug))
    raw = str(raw_id)
    candidate["provider_model_ids"].add(raw)
    candidate["aliases"].update(alias for alias in (raw, *aliases) if alias not in (None, ""))
    if slug != raw:
        candidate["variants"].add(raw)
    _add_signals(candidate, signals)
    _add_source(
        candidate,
        {"source": source, "provider": str(source_provider if source_provider is not None else provider), "raw_id": raw},
    )
    _add_raw(candidate, source, item)
    _add_facts(candidate, source, _extract_facts(source, item))
    return candidate


def _capability(capabilities: Any, key: str) -> Any:
    if not isinstance(capabilities, dict):
        return None
    value = capabilities.get(key)
    if isinstance(value, dict):
        return value.get("supported")
    return value


def _live_facts(item: dict[str, Any]) -> dict[str, Any]:
    limit = item.get("limit") if isinstance(item.get("limit"), dict) else {}
    capabilities = item.get("capabilities")
    reasoning = _capability(capabilities, "reasoning")
    options: list[dict[str, Any]] = []
    if isinstance(capabilities, dict) and isinstance(capabilities.get("reasoning"), dict):
        effort = capabilities["reasoning"].get("effort")
        if isinstance(effort, list) and effort:
            options.append({"type": "effort", "values": effort})
    api_bases = [
        spec.get("base_url")
        for spec in (item.get("api") or {}).values()
        if isinstance(spec, dict) and spec.get("base_url")
    ] if isinstance(item.get("api"), dict) else []
    return {
        "name": item.get("name"),
        "canonical_id": item.get("canonical_id"),
        "description": item.get("description"),
        "family": item.get("family"),
        "type": item.get("type"),
        "knowledge_cutoff": item.get("knowledge"),
        "release_date": item.get("release_date"),
        "last_updated": item.get("last_updated"),
        "modalities": item.get("modalities"),
        "open_weights": item.get("open_weights"),
        "context_window": limit.get("context"),
        "max_output_tokens": limit.get("output"),
        "reasoning": reasoning,
        "reasoning_options": options,
        "tool_call": _capability(capabilities, "tools"),
        "structured_output": capabilities.get("structured_output") if isinstance(capabilities, dict) else None,
        "temperature": capabilities.get("temperature") if isinstance(capabilities, dict) else None,
        "cost": item.get("cost"),
        "api_bases": api_bases,
    }


def _fixture_facts(item: dict[str, Any]) -> dict[str, Any]:
    limit = item.get("limit") if isinstance(item.get("limit"), dict) else {}
    provider = item.get("provider") if isinstance(item.get("provider"), dict) else {}
    return {
        "name": item.get("name"),
        "canonical_id": item.get("canonical_id"),
        "family": item.get("family"),
        "description": item.get("description"),
        "knowledge_cutoff": item.get("knowledge"),
        "release_date": item.get("release_date"),
        "last_updated": item.get("last_updated"),
        "modalities": item.get("modalities"),
        "open_weights": item.get("open_weights"),
        "context_window": limit.get("context"),
        "max_output_tokens": limit.get("output"),
        "reasoning": item.get("reasoning"),
        "reasoning_options": item.get("reasoning_options"),
        "tool_call": item.get("tool_call"),
        "interleaved": item.get("interleaved"),
        "structured_output": item.get("structured_output"),
        "temperature": item.get("temperature"),
        "cost": item.get("cost"),
        "status": item.get("status"),
        "api_bases": [provider.get("api")] if provider.get("api") else [],
    }


def _clean_limits(value: Any) -> dict[str, int]:
    """Drop the null placeholders used by the FreeLLMAPI ``limits`` object."""
    if not isinstance(value, dict):
        return {}
    return {
        str(key): int(amount)
        for key, amount in value.items()
        if isinstance(amount, (int, float)) and not isinstance(amount, bool)
    }


def _freellmapi_facts(item: dict[str, Any]) -> dict[str, Any]:
    # Parsed quota labels fill the gaps; the structured fields take precedence
    # where both exist.  The original label stays in ``quota_label`` and the
    # complete raw item is kept under ``raw``.
    limits = parse_budget_limits(item.get("monthlyTokenBudget"))
    limits.update(_clean_limits(item.get("limits")))
    return {
        "name": item.get("displayName"),
        "context_window": item.get("contextWindow"),
        "tool_call": item.get("supportsTools"),
        "reasoning_vision_hint": item.get("supportsVision"),
        "modalities": (
            {"input": ["text", "image"], "output": ["text"]}
            if item.get("supportsVision")
            else None
        ),
        "limits": limits,
        "quota_label": item.get("monthlyTokenBudget"),
        "catalog_intelligence_rank": item.get("intelligenceRank"),
        "catalog_speed_rank": item.get("speedRank"),
        "catalog_size_label": item.get("sizeLabel"),
        "catalog_enabled": item.get("enabled"),
        "catalog_quirks": item.get("quirks"),
    }


def _awesome_facts(item: dict[str, Any]) -> dict[str, Any]:
    limits = parse_rate_limit(item.get("rateLimit"))
    return {
        "name": item.get("name"),
        "context_window": parse_size(item.get("context")),
        "max_output_tokens": parse_size(item.get("maxOutput")),
        "modality_label": item.get("modality"),
        "rate_limit_label": item.get("rateLimit"),
        "limits": limits,
        "canonical_id": item.get("id") if "/" in str(item.get("id") or "") else None,
    }


def _extract_facts(source: str, item: dict[str, Any]) -> dict[str, Any]:
    if source == SOURCE_LIVE:
        return _live_facts(item)
    if source == OPENCODE:
        return _fixture_facts(item)
    if source == FREELLMAPI:
        return _freellmapi_facts(item)
    if source == AWESOME:
        return _awesome_facts(item)
    return {key: value for key, value in item.items() if key not in ("id", "name") and value not in (None, "")}


def _item_signals(source: str, raw_id: Any, item: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    for marker in free_markers(raw_id, item.get("name"), item.get("canonical_id")):
        signals.append(f"free-marker:{marker}")
    if all_zero_prices(item.get("cost")):
        signals.append("zero-cost")
    if source == FREELLMAPI:
        signals.append("freellmapi:monthly-catalog")
        if "free" in str(item.get("monthlyTokenBudget") or "").lower():
            signals.append("freellmapi:free-budget-label")
    if source == AWESOME:
        signals.append("awesome:free-llm-provider")
    if source == SOURCE_LIVE:
        signals.append("opencode-live:model-list")
    if source == SOURCE_PROVIDER_MODELS:
        signals.append("provider-models:model-list")
    return signals


def _ingest_live(bundle: Any, candidates: dict[tuple[str, str], dict[str, Any]]) -> None:
    for item in bundle.opencode_live.get("data") or []:
        if not isinstance(item, dict):
            continue
        raw_id = model_item_id(item)
        if not raw_id:
            continue
        signals = _item_signals(SOURCE_LIVE, raw_id, item)
        if not any(signal.startswith("free-marker:") or signal == "zero-cost" for signal in signals):
            continue
        candidate = _add_item(
            candidates,
            source=SOURCE_LIVE,
            provider=resolve_provider_slug(item.get("owned_by") or "opencode", "OpenCode Zen"),
            raw_id=raw_id,
            item=item,
            signals=signals,
            aliases=[item.get("name")],
        )
        for base in _live_facts(item).get("api_bases") or []:
            candidate["api_bases"].add(str(base))


def _ingest_fixture(bundle: Any, candidates: dict[tuple[str, str], dict[str, Any]]) -> None:
    for provider_id, raw_provider in sorted(bundle.opencode.items()):
        if not isinstance(raw_provider, dict):
            continue
        provider = resolve_provider_slug(provider_id, raw_provider.get("name"))
        for model_id, item in sorted((raw_provider.get("models") or {}).items()):
            if not isinstance(item, dict):
                continue
            signals = _item_signals(OPENCODE, model_id, item)
            if not any(signal.startswith("free-marker:") or signal == "zero-cost" for signal in signals):
                continue
            _add_item(
                candidates,
                source=OPENCODE,
                provider=provider,
                raw_id=model_id,
                item=item,
                signals=signals,
                aliases=[item.get("name")],
            )


def _ingest_freellmapi(
    bundle: Any,
    candidates: dict[tuple[str, str], dict[str, Any]],
    provider_signals: dict[str, set[str]],
) -> None:
    payload = bundle.freellmapi
    platform_names = {
        item.get("id"): item.get("name") or item.get("id")
        for item in payload.get("platforms") or []
        if isinstance(item, dict) and item.get("id")
    }
    for platform_id, display_name in sorted(platform_names.items()):
        provider = resolve_provider_slug(platform_id, display_name)
        provider_signals.setdefault(provider, set()).add("freellmapi:monthly-catalog")
    for item in sorted(payload.get("models") or [], key=lambda row: str(row.get("modelId", ""))):
        if not isinstance(item, dict) or not item.get("modelId"):
            continue
        provider = resolve_provider_slug(item.get("platform"), platform_names.get(item.get("platform"), ""))
        quirks = catalog_quirks(payload, str(item.get("platform") or ""), str(item.get("modelId") or ""))
        enriched = {**item, "quirks_resolved": quirks}
        _add_item(
            candidates,
            source=FREELLMAPI,
            provider=provider,
            raw_id=item["modelId"],
            item=enriched,
            signals=_item_signals(FREELLMAPI, item["modelId"], item),
            aliases=[item.get("displayName")],
            source_provider=item.get("platform"),
        )


def _ingest_awesome(
    bundle: Any,
    candidates: dict[tuple[str, str], dict[str, Any]],
    provider_signals: dict[str, set[str]],
) -> None:
    for raw_provider in sorted(bundle.awesome.get("providers") or [], key=lambda row: str(row.get("name", ""))):
        if not isinstance(raw_provider, dict):
            continue
        name = str(raw_provider.get("name") or "")
        provider = resolve_provider_slug(name, name)
        if "free" in str(raw_provider.get("description") or "").lower():
            provider_signals.setdefault(provider, set()).add("awesome:free-tier-description")
        for item in raw_provider.get("models") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            _add_item(
                candidates,
                source=AWESOME,
                provider=provider,
                raw_id=item["id"],
                item={**item, "platform": name, "baseUrl": raw_provider.get("baseUrl")},
                signals=_item_signals(AWESOME, item["id"], item),
                aliases=[item.get("name")],
                source_provider=name,
            )


def _ingest_provider_models(
    bundle: Any,
    candidates: dict[tuple[str, str], dict[str, Any]],
    provider_signals: dict[str, set[str]],
) -> None:
    for provider, cached in sorted(bundle.provider_models.items()):
        meta = cached.get("_meta") or {}
        provider_signals.setdefault(provider, set()).add("provider-models:model-list")
        for item in model_list_items(cached.get("data")):
            raw_id = model_item_id(item)
            if not raw_id:
                continue
            signals = _item_signals(SOURCE_PROVIDER_MODELS, raw_id, item)
            if not any(signal.startswith("free-marker:") for signal in signals):
                continue
            candidate = _add_item(
                candidates,
                source=SOURCE_PROVIDER_MODELS,
                provider=provider,
                raw_id=raw_id,
                item=item,
                signals=signals,
                aliases=[item.get("name"), item.get("displayName")],
            )
            if meta.get("url"):
                candidate["api_bases"].add(str(meta["url"]))


def _too_old(facts: dict[str, Any]) -> bool:
    years: list[int] = []
    for key in ("release_date", "last_updated"):
        match = _YEAR_PREFIX.match(str(facts.get(key) or ""))
        if match:
            years.append(int(match.group(1)))
    return bool(years) and max(years) < MODEL_CUTOFF_YEAR


def _finalize_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    facts: dict[str, Any] = {}
    for source in FACT_PRIORITY:
        for key, value in (candidate["_facts"].get(source) or {}).items():
            facts.setdefault(key, value)
    if _too_old(facts):
        return None

    # Quotas describe the free offering, not the model itself: they stay on the
    # compact free candidate and are kept out of model JSON files.
    limits = facts.pop("limits", None)

    raw = {
        source: [bucket[key] for key in sorted(bucket)]
        for source, bucket in sorted(candidate["raw"].items())
    }
    return {
        "_generated_by": GENERATED_BY,
        "provider": candidate["provider"],
        "slug": candidate["slug"],
        "signals": sorted(candidate["signals"]),
        "aliases": sorted(candidate["aliases"]),
        "provider_model_ids": sorted(candidate["provider_model_ids"]),
        "variants": sorted(candidate["variants"]),
        "api_bases": sorted(candidate["api_bases"]),
        "limits": limits or {},
        "facts": facts,
        "raw": raw,
        "sources": sort_sources(candidate["sources"]),
        "source_names": sorted({ref["source"] for ref in candidate["sources"]}),
    }


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        key = _json_key(record)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


def _dedupe_values(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    for value in values:
        if value not in (None, ""):
            seen.add(str(value))
    return sorted(seen)


def _api_base(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    return text[: -len("/models")] if text.endswith("/models") else text


def _merge_model(
    existing: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    # pylint: disable=too-many-branches
    """Put candidate model data into a model record; existing values win.

    A brand-new model record receives the facts at the top level.  When the
    base catalog already has the model, only genuinely new evidence is stored
    under ``candidate_evidence`` so the regular catalog rebuild can preserve it
    without letting free data overwrite canonical fields.
    """
    facts = {
        key: value
        for key, value in (candidate.get("facts") or {}).items()
        if key not in ("api_bases", "limits") and value not in (None, "", [], {})
    }
    api_bases = _dedupe_values(
        [
            *(candidate.get("api_bases") or []),
            *((candidate.get("facts") or {}).get("api_bases") or []),
        ]
    )

    if existing is None:
        record: dict[str, Any] = {
            "_generated_by": GENERATED_BY,
            "generated_from": FREE_MODEL_SOURCE,
            "provider": candidate["provider"],
            "model": candidate["slug"],
        }
        record.update(facts)
        if api_bases:
            record["api_bases"] = api_bases
        for field in ("provider_model_ids", "aliases", "variants"):
            values = _dedupe_values(candidate.get(field) or [])
            if values:
                record[field] = values
        if candidate.get("sources"):
            record["sources"] = sort_sources(candidate["sources"])
        if candidate.get("raw"):
            record["raw"] = copy.deepcopy(candidate["raw"])
        return record

    record = copy.deepcopy(existing)
    evidence: dict[str, Any] = {}

    new_facts = {key: value for key, value in facts.items() if key not in record}
    if new_facts:
        evidence["facts"] = new_facts

    known_bases = {str(value) for value in record.get("api_bases") or []}
    new_bases = [value for value in api_bases if value not in known_bases]
    if new_bases:
        evidence["api_bases"] = new_bases

    for field in ("provider_model_ids", "aliases", "variants"):
        known = {str(value) for value in record.get(field) or []}
        values = [str(value) for value in candidate.get(field) or [] if str(value) not in known]
        if values:
            evidence[field] = sorted(set(values))

    known_sources = {_json_key(source) for source in record.get("sources") or []}
    new_sources = [source for source in candidate.get("sources") or [] if _json_key(source) not in known_sources]
    if new_sources:
        evidence["sources"] = sort_sources(new_sources)
    if candidate.get("raw"):
        evidence["raw"] = copy.deepcopy(candidate["raw"])

    if evidence:
        record["candidate_evidence"] = _merge_evidence(record.get("candidate_evidence"), evidence)
    return record


def _merge_evidence(
    previous: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine candidate evidence from multiple leads for one model."""
    result: dict[str, Any] = copy.deepcopy(previous or {})
    incoming = incoming or {}

    facts = {**(result.get("facts") or {}), **(incoming.get("facts") or {})}
    if facts:
        result["facts"] = facts

    raw = copy.deepcopy(result.get("raw") or {})
    for source, items in (incoming.get("raw") or {}).items():
        raw[source] = _dedupe_records([*(raw.get(source) or []), *items])
    if raw:
        result["raw"] = raw

    for field in ("api_bases", "provider_model_ids", "aliases", "variants"):
        values = _dedupe_values(
            [*(result.get(field) or []), *(incoming.get(field) or [])]
        )
        if values:
            result[field] = values
    if incoming.get("sources"):
        result["sources"] = sort_sources(
            _dedupe_records([*(result.get("sources") or []), *incoming["sources"]])
        )
    return result


def _api_base_source(records: list[dict[str, Any]], base: str) -> str:
    labels = {
        SOURCE_CARDS: "curated-card",
        DOC_SOURCE: "provider-doc",
        SOURCE_CATALOG: "provider-catalog",
        AWESOME: "free-catalog",
        SOURCE_LIVE: "live-model-list",
        SOURCE_PROVIDER_MODELS: "model-list",
    }
    for source, label in labels.items():
        for record in records:
            values = [
                *(record.get("api_bases") or []),
                *((record.get("facts") or {}).get("api_bases") or []),
            ]
            if any(_api_base(value) == base for value in values) and any(
                ref.get("source") == source for ref in record.get("sources") or []
            ):
                return label
    return "extracted"


def _free_provider_record(
    provider: str,
    records: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Minimal provider record for a provider missing from the base catalog."""
    sources = _dedupe_records([source for record in records for source in record["sources"]])
    result: dict[str, Any] = {
        "_generated_by": GENERATED_BY,
        "generated_from": FREE_MODEL_SOURCE,
        "slug": provider,
        "name": summary.get("name") or provider,
        "model_count": len(records),
    }
    aliases = _dedupe_values(
        [provider, summary.get("name"), *(source.get("provider") for source in sources)]
    )
    if aliases:
        result["aliases"] = aliases
    bases = _dedupe_values(
        [
            *(value for item in records for value in (item.get("api_bases") or [])),
            *(
                value
                for item in records
                for value in ((item.get("facts") or {}).get("api_bases") or [])
            ),
        ]
    )
    cleaned = [base for base in (_api_base(value) for value in bases) if base]
    if cleaned:
        result["api_base"] = cleaned[0]
        result["api_base_source"] = _api_base_source(records, cleaned[0])
    if sources:
        result["sources"] = sort_sources(sources)
    return result


def _record_identities(record: dict[str, Any]) -> set[str]:
    values = {str(value) for value in record.get("provider_model_ids") or []}
    values.update(str(value) for value in record.get("aliases") or [])
    for field in ("canonical_id", "model"):
        if record.get(field):
            values.add(str(record[field]))
    return values


def _candidate_identities(candidate: dict[str, Any]) -> set[str]:
    values = {str(value) for value in candidate.get("provider_model_ids") or []}
    values.update(str(value) for value in candidate.get("aliases") or [])
    canonical = (candidate.get("facts") or {}).get("canonical_id")
    if canonical:
        values.add(str(canonical))
    if candidate.get("slug"):
        values.add(str(candidate["slug"]))
    return values


def _identity_index(models: dict[tuple[str, str], dict[str, Any]]) -> dict[tuple[str, str], list[tuple[str, str]]]:
    index: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for key, record in models.items():
        for value in _record_identities(record):
            index[(key[0], value)].append(key)
    return index


def _resolve_existing_key(
    candidate: dict[str, Any],
    base_models: dict[tuple[str, str], dict[str, Any]],
    identity_index: dict[tuple[str, str], list[tuple[str, str]]],
) -> tuple[str, str]:
    """Map a free candidate onto an existing model when raw IDs agree."""
    provider = candidate["provider"]
    key = (provider, candidate["slug"])
    if key in base_models:
        return key

    identities = _candidate_identities(candidate)
    candidates: set[tuple[str, str]] = set()
    for value in identities:
        candidates.update(identity_index.get((provider, value), []))

    best = None
    best_score = 0
    for match in sorted(candidates):
        score = len(identities & _record_identities(base_models[match]))
        if score > best_score or (score == best_score and best is not None and match < best):
            best = match
            best_score = score
    return best or key


def _apply_api_base_sources(
    candidates: list[dict[str, Any]],
    api_bases: dict[str, dict[str, Any]],
    providers: dict[str, dict],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Attach known API bases to candidates that do not carry one yet."""
    enriched: list[dict[str, Any]] = []
    used: set[str] = set()
    for source_candidate in candidates:
        provider = source_candidate["provider"]
        card = api_bases.get(provider)
        candidate = copy.deepcopy(source_candidate)
        if card:
            source = card
        else:
            # The base provider record is already canonical provenance; adding
            # it to every free entry would bloat the thin pointer files.
            catalog_base = (providers.get(provider) or {}).get("api_base")
            base = _api_base(catalog_base)
            bases = {_api_base(value) for value in candidate.get("api_bases") or []}
            if base and base not in bases:
                candidate["api_bases"] = sorted({*(candidate.get("api_bases") or []), base})
            enriched.append(candidate)
            continue

        base = _api_base(source["api_base"])
        bases = {_api_base(value) for value in candidate.get("api_bases") or []}
        if base not in bases:
            candidate["api_bases"] = sorted({*(candidate.get("api_bases") or []), base})
        candidate["sources"] = sort_sources([*(candidate.get("sources") or []), source["ref"]])
        candidate["source_names"] = sorted({*(candidate.get("source_names") or []), source["source"]})
        candidate["signals"] = sorted({*(candidate.get("signals") or []), f"{source['source']}:api-base"})
        used.add(source["source"])
        enriched.append(candidate)
    return enriched, used


def prepare_free_output(
    candidates: dict[str, Any],
    providers: dict[str, dict] | None = None,
    models: dict[tuple[str, str], dict] | None = None,
    api_bases: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # pylint: disable=too-many-locals
    """Return compact free files plus the model records that back them.

    Existing catalog values are never overwritten; free-only evidence fills the
    gaps.  The returned ``dataset`` contains compact model references with the
    exact provider-side ID needed to call the API.
    """
    base_providers = providers or {}
    base_models = models or {}
    identity_index = _identity_index(base_models)
    candidate_records, used_api_sources = _apply_api_base_sources(
        list(candidates.get("candidates") or []),
        api_bases or {},
        base_providers,
    )
    resolved: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidate_records:
        key = _resolve_existing_key(candidate, base_models, identity_index)
        resolved.setdefault(key, []).append(candidate)

    extra_models: dict[tuple[str, str], dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    compact: list[dict[str, Any]] = []
    created: list[str] = []
    enriched: list[str] = []

    for (provider, slug), group in sorted(resolved.items()):
        existing = base_models.get((provider, slug))
        merged: dict[str, Any] | None = None
        for candidate in group:
            merged = _merge_model(merged if merged is not None else existing, candidate)
        record = merged or {}
        extra_models[(provider, slug)] = record
        (created if existing is None else enriched).append(f"{provider}/{slug}")
        grouped.setdefault(provider, []).extend(group)
        limits: dict[str, int] = {}
        for item in group:
            for key, value in (item.get("limits") or {}).items():
                limits.setdefault(key, value)
        provider_model_ids = [
            str(value) for value in record.get("provider_model_ids") or [] if value
        ]
        compact.append(
            {
                "_generated_by": GENERATED_BY,
                "provider": provider,
                "model": slug,
                "model_name": str(record.get("name") or slug),
                "provider_model_id": str(
                    record.get("provider_model_id")
                    or (provider_model_ids[0] if provider_model_ids else slug)
                ),
                **({"limits": limits} if limits else {}),
            }
        )

    extra_providers: dict[str, dict[str, Any]] = {}
    summaries = candidates.get("providers") or {}
    for provider, records in grouped.items():
        if provider not in base_providers:
            raw_summary = summaries.get(provider) if isinstance(summaries, dict) else {}
            extra_providers[provider] = _free_provider_record(provider, records, raw_summary or {})

    dataset = {
        key: value
        for key, value in candidates.items()
        if key not in ("candidates", "providers")
    }
    dataset["schema_version"] = SCHEMA_VERSION
    if used_api_sources:
        dataset["sources"] = sorted({*(dataset.get("sources") or []), *used_api_sources})
    dataset["providers"] = {
        provider: {key: value for key, value in summary.items() if key != "api_base"}
        for provider, summary in summaries.items()
    } if isinstance(summaries, dict) else {}
    dataset["candidates"] = compact

    return {
        "dataset": dataset,
        "providers": extra_providers,
        "models": extra_models,
        "created": sorted(created),
        "enriched": sorted(enriched),
    }


def build_free_dataset(
    bundle: Any,
    providers: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Return the deterministic free-offering candidate document."""
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    provider_signals: dict[str, set[str]] = {}
    _ingest_live(bundle, candidates)
    _ingest_fixture(bundle, candidates)
    _ingest_freellmapi(bundle, candidates, provider_signals)
    _ingest_awesome(bundle, candidates, provider_signals)
    _ingest_provider_models(bundle, candidates, provider_signals)

    finalized = [
        record
        for key in sorted(candidates)
        if (record := _finalize_candidate(candidates[key])) is not None
    ]

    candidate_counts: dict[str, int] = {}
    for record in finalized:
        candidate_counts[record["provider"]] = candidate_counts.get(record["provider"], 0) + 1

    summaries: dict[str, Any] = {}
    for provider, count in sorted(candidate_counts.items()):
        base = (providers or {}).get(provider) or {}
        summaries[provider] = {
            "provider": provider,
            "name": base.get("name") or provider,
            "candidate_count": count,
            "signals": sorted(provider_signals.get(provider, set())),
        }

    contributed = {
        name
        for record in finalized
        for name in record["source_names"]
    }
    return {
        "_generated_by": GENERATED_BY,
        "schema_version": SCHEMA_VERSION,
        "sources": [name for name in SOURCE_ORDER if name in contributed],
        "counts": {
            "providers": len(summaries),
            "candidates": len(finalized),
        },
        "providers": summaries,
        "candidates": finalized,
    }
