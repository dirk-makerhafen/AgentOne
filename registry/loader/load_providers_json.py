"""Load the generated JSON provider/model catalog into the database.

The research ``*.md`` cards were retired in favour of the deterministic JSON
dataset under ``.agentone/providers/<provider>/``.  This loader is the DB-side
counterpart to :mod:`registry.catalog`: it consumes that dataset plus the
free-tier candidates/verdicts in ``.agentone/free/`` and upserts the same
``ApiProvider`` / ``AiModel`` / ``AiModelOffering`` rows the markdown loader
used to maintain.  Free status combines reviewed verdicts with the explicit
``isFree`` / zero-pricing / ``:free`` signals on generated model records; where
neither source has an opinion, previously curated free state is preserved.

Rank fields are the important detail: the JSON files store either an exact
``leaderboard_rank`` (integer) or a ``leaderboard_rank_estimated`` string such
as ``"~120"``.  Both land in the single sortable ``AiModel.leaderboard_rank``
integer here, with ``leaderboard_rank_is_estimate`` marking the latter, which
is exactly what the insights UI expects.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from registry.catalog.free import free_markers
from registry.catalog.normalize import GENERATED_BY
from registry.catalog.write import FREE_MODEL_SOURCE
from registry.loader.load_providers import (
    RATE_LIMIT_MAP,
    _is_loopback_url,
    _modalities_to_flags,
)
from server.models.providers.ai_model import AiModel as RawModel
from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_provider import ApiProvider

# Keys from free-tier candidate ``limits:`` objects (lowercase in the feed).
_CANDIDATE_RATE_LIMIT_MAP = {k.lower(): v for k, v in RATE_LIMIT_MAP.items()}


def _read_json(path: Path) -> dict[str, Any]:
    """Read one JSON record; return {} for missing/invalid files."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _generated(record: dict[str, Any]) -> bool:
    """Whether a JSON record belongs to the generated catalog dataset."""
    marker = record.get("_generated_by")
    return marker == GENERATED_BY or record.get("generated_from") == FREE_MODEL_SOURCE


def _zero_pricing(record: dict[str, Any]) -> bool:
    """Whether the model record publishes explicit zero prompt/completion cost."""
    pricing = record.get("pricing")
    if not isinstance(pricing, dict):
        return False
    for key in ("prompt", "completion"):
        value = pricing.get(key)
        try:
            if value is None or float(value) != 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def _free_evidence(
    record: dict[str, Any], verdict: dict[str, Any], provider_model_id: str
) -> tuple[bool, str, str] | None:
    """Return ``(is_free, conditions, free_verified)`` for an offering.

    Returns ``None`` when neither source carries a decision, so the caller can
    keep whatever a previous (curated) load stored instead of wiping it:

    * a reviewed verdict is authoritative — ``free`` sets the conditions and
      verification date, ``rejected`` / ``payment_gated`` clear the free flag;
    * otherwise the generated model record's explicit ``isFree`` flag, zero
      pricing or a ``:free`` / ``-free`` model-id lane is evidence of a standing
      free route (unreviewed, so without a verification date);
    * bare leads with no evidence stay untouched.
    """
    decision = verdict.get("verdict")
    if decision == "free":
        return (
            True,
            _first_str(verdict.get("conditions")),
            _first_str(verdict.get("verified")),
        )
    if decision in ("rejected", "payment_gated"):
        return False, "", ""
    if (
        record.get("isFree") is True
        or _zero_pricing(record)
        or free_markers(provider_model_id, record.get("name", ""))
    ):
        conditions = _first_str(verdict.get("conditions"), verdict.get("notes"))
        return True, conditions, ""
    return None


def _parse_rank(record: dict[str, Any]) -> tuple[int | None, bool]:
    """Return ``(rank, is_estimate)`` from a model JSON record.

    Matches ``parse_rank_cell`` / ``apply_ranks`` semantics: an exact integer
    rank is authoritative, a ``~N`` estimate supplies the digits plus the
    estimate flag, and the two fields are mutually exclusive in generated data.
    """
    rank = record.get("leaderboard_rank")
    try:
        if rank is not None:
            return int(rank), False
    except (TypeError, ValueError):
        pass
    estimated = record.get("leaderboard_rank_estimated")
    if estimated is not None:
        digits = "".join(c for c in str(estimated) if c.isdigit())
        if digits:
            return int(digits), True
    return None, False


def _limit_defaults(info: Any, uppercase: bool = False) -> dict[str, int]:
    """Map a JSON ``limits`` object onto flat limit-field values."""
    if not isinstance(info, dict):
        return {}
    mapping = RATE_LIMIT_MAP if uppercase else _CANDIDATE_RATE_LIMIT_MAP
    defaults: dict[str, int] = {}
    for key, value in info.items():
        spec = mapping.get(key if uppercase else str(key).lower())
        if spec is None:
            continue
        field, multiplier = spec
        try:
            bound = int(float(value)) * multiplier
        except (TypeError, ValueError):
            continue
        if bound <= 0:
            continue
        defaults[field] = min(defaults.get(field, bound), bound)
    parallel = info.get("parallel_calls")
    try:
        parallel = int(float(parallel))
    except (TypeError, ValueError):
        parallel = 0
    if parallel > 0:
        defaults["limit_parallel_calls"] = parallel
    return defaults


def _as_int(value: Any) -> int | None:
    """Best-effort int conversion for JSON numeric fields."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _first_str(*values: Any) -> str:
    """First non-empty value coerced to a stripped string."""
    for value in values:
        if value not in (None, "", [], {}):
            return str(value).strip()
    return ""


def _model_slug(record: dict[str, Any]) -> str:
    """Stable raw-model identity for a JSON record."""
    return _first_str(record.get("model"), record.get("slug"),
                      record.get("canonical_id"), record.get("name"))


def _provider_model_ids(record: dict[str, Any]) -> list[str]:
    """Every API model id an offering record exposes."""
    ids: list[str] = []
    explicit = record.get("provider_model_ids") or record.get("provider_model_id")
    sources = (explicit,) if explicit else (record.get("model"),)
    for value in sources:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, (list, tuple)):
            candidates = list(value)
        else:
            continue
        for candidate in candidates:
            candidate = str(candidate).strip()
            if candidate and candidate not in ids:
                ids.append(candidate)
    return ids


def _model_defaults(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge raw-model facts from every offering of one canonical model."""
    merged: dict[str, Any] = {}
    rank: int | None = None
    is_estimate = False
    flags: dict[str, bool] = {}
    for record in records:
        modalities = record.get("modalities")
        if isinstance(modalities, dict):
            for key, value in _modalities_to_flags(modalities).items():
                flags[key] = flags.get(key, False) or value
        for key in ("name", "developer", "canonical_id", "family", "description",
                    "knowledge_cutoff"):
            if not merged.get(key):
                value = record.get(key)
                if value not in (None, "", [], {}):
                    merged[key] = str(value)
        for key, sources in (("context_length", ("context_length", "context_window")),
                             ("max_output_tokens", ("max_output_tokens", "max_tokens")),
                             ("filesize", ("filesize",))):
            if key in merged:
                continue
            for source in sources:
                value = record.get(source)
                if value in (None, "", [], {}):
                    continue
                try:
                    merged[key] = int(float(value))
                except (TypeError, ValueError):
                    continue
                break
        for key, source in (("open_weights", "open_weights"),
                            ("supports_reasoning", "reasoning"),
                            ("requires_reasoning_echo", "requires_reasoning_echo"),
                            ("supports_tool_call", "tool_call"),
                            ("structured_output", "structured_output"),
                            ("temperature", "temperature")):
            if key not in merged:
                value = record.get(source, record.get(key))
                if value is not None:
                    merged[key] = bool(value)
        for key in ("total_parameters", "active_parameters"):
            if key not in merged and record.get(key) is not None:
                try:
                    merged[key] = float(record[key])
                except (TypeError, ValueError):
                    pass
        if not merged.get("quantization") and record.get("quantization"):
            merged["quantization"] = str(record["quantization"])
        current_rank, current_estimate = _parse_rank(record)
        if current_rank is not None and (rank is None or current_rank < rank):
            rank, is_estimate = current_rank, current_estimate

    defaults = {
        "name": merged.get("name") or _model_slug(records[0] if records else {}),
        "developer": merged.get("developer", ""),
        "canonical_id": merged.get("canonical_id", ""),
        "family": merged.get("family", ""),
        "description": merged.get("description", ""),
        "leaderboard_id": _first_str(*(r.get("leaderboard_id") for r in records)),
        "leaderboard_rank": rank,
        "leaderboard_rank_is_estimate": is_estimate,
        "context_length": merged.get("context_length", 1000000),
        "max_output_tokens": merged.get("max_output_tokens", 1000000),
        "open_weights": merged.get("open_weights", False),
        "supports_reasoning": merged.get("supports_reasoning", False),
        "requires_reasoning_echo": merged.get("requires_reasoning_echo", False),
        "supports_tool_call": merged.get("supports_tool_call", False),
        "structured_output": merged.get("structured_output", False),
        "temperature": merged.get("temperature", False),
        "vision": flags.get("vision", False),
        "audio": flags.get("audio", False),
        "video": flags.get("video", False),
        "knowledge_cutoff": merged.get("knowledge_cutoff", ""),
        "filesize": merged.get("filesize", -1),
        "total_parameters": merged.get("total_parameters", 0),
        "active_parameters": merged.get("active_parameters", 0),
        "quantization": merged.get("quantization", ""),
    }
    return defaults


def _load_free_verdicts(free_dir: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    """Index reviewed free-tier candidates by (provider, provider model id)."""
    verdicts: dict[tuple[str, str], dict[str, Any]] = {}
    if free_dir is None or not free_dir.is_dir():
        return verdicts
    for path in sorted(free_dir.glob("*.json")):
        data = _read_json(path)
        if not _generated(data) and data.get("generated_from") != "free-reviews":
            continue
        provider = _first_str(data.get("provider"), data.get("name"), path.stem)
        for candidate in data.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            model_id = _first_str(candidate.get("provider_model_id"),
                                  candidate.get("model"))
            if not model_id:
                continue
            verdicts[(provider, model_id)] = candidate
            # Some feeds use the canonical slug as the candidate id; index it
            # as a fallback for offering records keyed by model slug.
            model = _first_str(candidate.get("model"))
            if model and model != model_id:
                verdicts.setdefault((provider, model), candidate)
    return verdicts


def _upsert_provider(slug: str, record: dict[str, Any], details: list) -> ApiProvider | None:
    """Upsert one ``ApiProvider`` from ``<slug>/<slug>.json``."""
    existing = ApiProvider.objects.filter(slug=slug).first()
    user_managed = existing is not None and existing.api_keys.exists()
    api_base = _first_str(record.get("api_base"), record.get("url"))
    if not api_base and existing is not None:
        # Generated free-candidate providers often have no api_base; keep the
        # previously curated endpoint so routing does not silently break.
        api_base = existing.url
    if not api_base:
        details.append({"type": "provider", "name": slug,
                        "action": "skipped (no api_base)"})
        return None
    if user_managed:
        details.append({"type": "provider", "name": existing.name,
                        "action": "up to date (user-managed)"})
        return existing

    defaults = {
        "name": _first_str(record.get("name"), slug),
        "url": api_base,
        "is_local": _is_loopback_url(api_base),
        "litellm_prefix": _first_str(record.get("litellm_prefix")),
        "enabled": True,
        "description": _first_str(record.get("description")),
        "setup_instructions": _first_str(record.get("setup_instructions")),
        "api_key_url": _first_str(record.get("api_key_url")),
        "default_api_key": _first_str(record.get("default_api_key")),
    }
    provider, created = ApiProvider.objects.update_or_create(slug=slug, defaults=defaults)
    changed = [f for f, v in defaults.items() if getattr(provider, f) != v]
    if changed:
        provider.save(update_fields=changed)
    details.append({"type": "provider", "name": provider.name,
                    "action": "created" if created else ("updated" if changed else "up to date")})
    return provider


def load_providers_json(
    providers_dir: Path,
    free_dir: Path | None = None,
    details: list[dict[str, str]] | None = None,
    disable_missing: bool = False,
) -> int:
    """Upsert providers, raw models and offerings from the generated JSON dataset.

    ``providers_dir`` is ``<root>/.agentone/providers``.  ``free_dir`` is the
    reviewed ``<root>/.agentone/free`` dataset; when supplied, ``verdict:
    free`` candidates set ``is_free`` / ``conditions`` / ``free_verified`` on
    the matching offering.  Returns the number of providers loaded.

    With ``disable_missing``, providers and offerings absent from the JSON
    dataset are disabled instead of deleted so call history stays intact.
    """
    if details is None:
        details = []
    providers_dir = Path(providers_dir)
    if not providers_dir.is_dir():
        return 0

    # 1. Read every generated record into provider-local groups.
    by_provider: dict[str, dict[str, Any]] = {}
    model_records: dict[str, list[dict[str, Any]]] = {}
    for provider_dir in sorted(p for p in providers_dir.iterdir() if p.is_dir()):
        provider_record = _read_json(provider_dir / f"{provider_dir.name}.json")
        if not _generated(provider_record):
            continue
        by_provider[provider_dir.name] = provider_record
        for path in sorted(provider_dir.glob("*.json")):
            if path.stem == provider_dir.name:
                continue
            record = _read_json(path)
            if not _generated(record) or record.get("catalog_enabled") is False:
                continue
            slug = _model_slug(record)
            if not slug:
                continue
            model_records.setdefault(slug, []).append(record)

    free_verdicts = _load_free_verdicts(free_dir)

    # 2. Upsert the provider-independent raw model catalog (one row per slug).
    raw_models: dict[str, RawModel] = {}
    for slug, records in sorted(model_records.items()):
        defaults = _model_defaults(records)
        raw, _ = RawModel.objects.update_or_create(slug=slug, defaults=defaults)
        changed = [f for f, v in defaults.items() if getattr(raw, f) != v]
        if changed:
            raw.save(update_fields=changed)
        raw_models[slug] = raw

    # 3. Upsert providers and their offerings.
    seen_providers: set[str] = set()
    seen_offerings: set[tuple[int, str]] = set()
    count = 0
    for provider_slug, provider_record in sorted(by_provider.items()):
        provider = _upsert_provider(provider_slug, provider_record, details)
        if provider is None:
            continue
        seen_providers.add(provider_slug)
        count += 1

        for path in sorted((providers_dir / provider_slug).glob("*.json")):
            if path.stem == provider_slug:
                continue
            record = _read_json(path)
            if not _generated(record) or record.get("catalog_enabled") is False:
                continue
            slug = _model_slug(record)
            raw = raw_models.get(slug)
            if raw is None:
                continue
            ids = _provider_model_ids(record)
            if not ids:
                details.append({"type": "model", "name": f"{provider.name}/{path.stem}",
                                "action": "skipped (no model id)"})
                continue
            for provider_model_id in ids:
                verdict = free_verdicts.get((provider_slug, provider_model_id)) or {}
                free_fields = _free_evidence(record, verdict, provider_model_id)
                if free_fields is None:
                    # No verdict and no explicit free signal: keep a curated
                    # value from a previous load instead of wiping it.
                    previous = AiModelOffering.objects.filter(
                        api_provider=provider, provider_model_id=provider_model_id
                    ).first()
                    free_fields = (
                        (previous.is_free, previous.conditions, previous.free_verified)
                        if previous else (False, "", "")
                    )
                is_free, conditions, free_verified = free_fields
                defaults: dict[str, Any] = {
                    "model": raw,
                    "name": raw.name,
                    "is_free": is_free,
                    "conditions": conditions,
                    "free_verified": free_verified,
                    "enabled": True,
                    "is_cloud": not provider.is_local,
                }
                limits = record.get("limit")
                if isinstance(limits, dict):
                    # ``limit: {context, output}`` is a context/output cap,
                    # not a rate limit (those use RPM/TPD/... keys).
                    context = _as_int(limits.get("context"))
                    output = _as_int(limits.get("output"))
                    if context:
                        defaults["context_window_override"] = context
                    if output:
                        defaults["max_output_tokens_override"] = output
                    for key, value in _limit_defaults(limits).items():
                        defaults[key] = value
                for key, value in _limit_defaults(verdict.get("limits")).items():
                    defaults[key] = value
                context = _as_int(record.get("context_window"))
                output = _as_int(record.get("max_output_tokens"))
                if context:
                    defaults["context_window_override"] = context
                if output:
                    defaults["max_output_tokens_override"] = output

                offering, created = AiModelOffering.objects.update_or_create(
                    api_provider=provider,
                    provider_model_id=provider_model_id,
                    defaults=defaults,
                )
                changed = [f for f, v in defaults.items() if getattr(offering, f) != v]
                if changed:
                    offering.save(update_fields=changed)
                seen_offerings.add((provider.pk, provider_model_id))
                details.append({
                    "type": "model",
                    "name": f"{provider.name}/{provider_model_id}",
                    "action": "created" if created else ("updated" if changed else "up to date"),
                })

    if disable_missing:
        stale_providers = ApiProvider.objects.exclude(slug__in=list(seen_providers)).filter(
            enabled=True, is_local=False, api_keys__isnull=True,
        )
        for provider in stale_providers:
            provider.enabled = False
            provider.save(update_fields=["enabled"])
            details.append({"type": "provider", "name": provider.name,
                            "action": "disabled (no JSON file)"})
        for offering in AiModelOffering.objects.filter(enabled=True, is_cloud=True):
            if (offering.api_provider_id, offering.provider_model_id) in seen_offerings:
                continue
            offering.enabled = False
            offering.save(update_fields=["enabled"])
            details.append({"type": "model",
                            "name": f"{offering.api_provider.name}/{offering.provider_model_id}",
                            "action": "disabled (no JSON record)"})

    return count
