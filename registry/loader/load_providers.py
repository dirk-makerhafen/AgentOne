from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import yaml

from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider

# Free-tier rate-limit keys found in a provider's ``free_info`` / model entry,
# mapped to the ``AiModel`` / ``ApiProvider`` limit fields they feed.  ``RPS`` /
# ``TPS`` have no per-second field, so they are converted to the nearest
# supported window (per-minute).  When several keys resolve to the same field,
# the most conservative (lowest) bound wins.
RATE_LIMIT_MAP: Dict[str, tuple[str, int]] = {
    "RPM": ("limit_request_per_minute", 1),
    "RPH": ("limit_request_per_hour", 1),
    "RPD": ("limit_request_per_day", 1),
    "RPS": ("limit_request_per_minute", 60),   # no per-second field → per-minute
    "TPM": ("limit_tokens_per_minute", 1),
    "TPH": ("limit_tokens_per_hour", 1),
    "TPD": ("limit_tokens_per_day", 1),
    "TPS": ("limit_tokens_per_minute", 60),    # no per-second field → per-minute
}

# Limit fields present on both ``ApiProvider`` and ``AiModel``.
LIMIT_FIELDS: tuple[str, ...] = (
    "limit_request_per_minute",
    "limit_request_per_hour",
    "limit_request_per_day",
    "limit_tokens_per_minute",
    "limit_tokens_per_hour",
    "limit_tokens_per_day",
    "limit_parallel_calls",
)


def _rate_limit_defaults(info: Dict[str, Any]) -> Dict[str, int]:
    """Map ``free_info`` rate-limit keys onto ``AiModel`` limit field values.

    Unknown / non-numeric values are ignored.  0 (or absent) means unlimited,
    so only positive bounds are returned.
    """
    defaults: Dict[str, int] = {}
    for key, (field, multiplier) in RATE_LIMIT_MAP.items():
        value = info.get(key)
        if value is None:
            continue
        try:
            bound = int(float(value)) * multiplier
        except (TypeError, ValueError):
            continue
        if bound <= 0:
            continue
        if field in defaults:
            defaults[field] = min(defaults[field], bound)
        else:
            defaults[field] = bound

    if "parallel_calls" in info:
        try:
            parallel = int(float(info["parallel_calls"]))
        except (TypeError, ValueError):
            parallel = 0
        if parallel > 0:
            defaults["limit_parallel_calls"] = parallel
    return defaults


def _is_loopback_url(url: str) -> bool:
    """Whether a provider URL points at a loopback / local machine address."""
    try:
        host = urlparse(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    host = host.lower().rstrip(".")
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.startswith("127.")


def _load_models_catalog(catalog_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load the canonical model catalog (``models.yaml``) keyed by model name.

    Entries carry shared metadata (family, context, capabilities, parameter
    counts, description).  Providers reference these names from their
    ``free_info.free_models`` mapping and add only their provider-internal
    ``id`` plus any per-provider overrides.
    """
    if not catalog_path.exists():
        return {}
    with catalog_path.open(encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for model in data.get("models") or []:
        name = model.get("name")
        if name:
            catalog[name] = model
    return catalog


def _iter_model_entries(
    provider_data: Dict[str, Any],
    catalog: Dict[str, Dict[str, Any]],
):
    """Yield ``(spec, display_label)`` for manifest and curated free models.

    ``spec["name"]`` is the raw provider id (what is sent to the API) and
    ``spec["display_name"]`` the human label.  Top-level ``models`` entries
    are self-contained (``name`` is the API id).  Entries under
    ``free_info.free_models`` reference the catalog by ``model`` name and carry
    the provider-internal ``id``; the merged spec inherits catalog metadata and
    lets the entry override context, capabilities and per-model rate limits.
    """
    for model_data in provider_data.get("models") or []:
        spec = dict(model_data)
        spec.setdefault("display_name", model_data.get("name", ""))
        yield spec, model_data.get("name", "")

    free_info = provider_data.get("free_info") or {}
    for entry in free_info.get("free_models") or []:
        model_ref = entry.get("model")
        label = model_ref or entry.get("id") or entry.get("name") or ""
        entry_fields = {
            k: v for k, v in entry.items() if k not in ("model", "id", "name")
        }
        if "context" in entry_fields and "context_length" not in entry_fields:
            entry_fields["context_length"] = entry_fields.pop("context")
        if "image" in entry_fields and "vision" not in entry_fields:
            entry_fields["vision"] = entry_fields.pop("image")

        if model_ref:
            catalog_spec = catalog.get(model_ref)
            if catalog_spec is None:
                yield None, label
                continue
            spec = dict(catalog_spec)
            spec.pop("name", None)
            spec.update(entry_fields)
        else:
            spec = entry_fields
        spec["name"] = entry.get("id") or label
        spec.setdefault("display_name", label)
        spec.setdefault("description", label)
        yield spec, label


def load_providers_manifest(
    manifest_path: Path,
    details: List[Dict[str, str]],
) -> int:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Upsert providers and models from a YAML manifest.

    Expected format::

    # .agentone/models.yaml — canonical model metadata (loaded by name)
    models:
      - name: Gemini 3.6 Flash
        family: gemini
        context_length: 1000000
        vision: true
        supports_reasoning: true

    # .agentone/providers.yaml
    providers:
      - name: Google
        url: "https://generativelanguage.googleapis.com/v1beta/"
        models:
          - name: gemini-2.5-flash
            family: gemini
            supports_tool_call: true
        free_info:
          RPM: 15
          free_models:
            - model: Gemini 3.6 Flash   # name in models.yaml
              id: gemini-3.6-flash      # provider-internal API id
              RPM: 15                   # optional per-provider overrides

    Curated ``free_info.free_models`` entries reference the catalog by
    ``model`` name and add a provider-internal ``id``.  The merged spec
    inherits catalog metadata; per-provider context/capability overrides and
    per-model rate limits (``RPM``/``RPD``/``TPH``/… or long-form fields) may
    be set on the entry.  ``id`` becomes ``AiModel.provider_model_id`` (what is
    sent to the API) and the catalog name becomes ``AiModel.name`` (the display
    label).

    Returns the number of providers loaded.
    """
    if not manifest_path.exists():
        return 0

    catalog = _load_models_catalog(manifest_path.parent / "models.yaml")

    with manifest_path.open(encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}

    providers_list: List[Dict[str, Any]] = data.get("providers") or []
    if not providers_list:
        return 0

    count = 0
    for provider_data in providers_list:
        name = provider_data["name"]
        is_local = provider_data.get("is_local", False) or provider_data.get("type") == "local"
        provider, created = ApiProvider.objects.get_or_create(
            name=name,
            defaults={
                "url": provider_data.get("url", ""),
                "is_local": is_local,
            },
        )
        if not created:
            url = provider_data.get("url")
            if url is not None and provider.url != url:
                provider.url = url
                provider.save()
                action = "updated"
            elif provider.is_local != is_local:
                provider.is_local = is_local
                provider.save()
                action = "updated"
            else:
                action = "up to date"
        else:
            action = "created"

        # Store free-tier / setup info in raw_data
        free_info = provider_data.get("free_info")
        if free_info or provider_data.get("api_key_url") or provider_data.get("setup_instructions"):
            info = free_info or {}
            if provider_data.get("api_key_url"):
                info["api_key_url"] = provider_data["api_key_url"]
            if provider_data.get("setup_instructions"):
                info["setup_instructions"] = provider_data["setup_instructions"]
            provider.data = info
            provider.save(update_fields=["raw_data"])

        # Persist free-tier rate limits onto the provider itself.  These are
        # provider-wide caps (e.g. "Nvidia NIM 40 RPM"), not per-model caps, so
        # they belong on ``ApiProvider`` only and are NOT inherited into models.
        # A model gets a limit only through an explicit per-model key below.
        rate_limits = _rate_limit_defaults(free_info or {})
        provider_limit_changed = False
        for field in LIMIT_FIELDS:
            value = rate_limits.get(field)
            if value is None:
                continue
            if getattr(provider, field) == value:
                continue
            setattr(provider, field, value)
            provider_limit_changed = True
        if provider_limit_changed:
            provider.save(update_fields=list(rate_limits.keys()))

        details.append({
            "type": "provider",
            "name": name,
            "action": action,
        })

        for model_data, detail_label in _iter_model_entries(provider_data, catalog):
            if model_data is None:
                details.append({
                    "type": "model",
                    "name": f"{name}/{detail_label}",
                    "action": "skipped",
                })
                continue
            provider_model_id: str = model_data["name"]
            display_name: str = model_data.get("display_name") or provider_model_id

            # Model-level limits: provider-free-tier caps live on the provider, not on
            # models, so a model starts unlimited (0) and is bounded only by
            # explicit keys — long form (``limit_tokens_per_day``) or shorthand
            # (``RPM``/``RPD``/etc.).
            model_limits: Dict[str, int] = _rate_limit_defaults(model_data)
            for k in LIMIT_FIELDS:
                if k in model_data:
                    model_limits[k] = model_data[k]

            defaults = {
                "name": display_name,
                "provider_model_id": provider_model_id,
                "family": model_data.get("family", ""),
                "is_cloud": model_data.get("is_cloud", True),
                "open_weights": model_data.get("open_weights", False),
                "supports_reasoning": model_data.get("supports_reasoning", False),
                "requires_reasoning_echo": model_data.get("requires_reasoning_echo", False),
                "supports_tool_call": model_data.get("supports_tool_call", False),
                "vision": model_data.get("vision", False),
                "audio": model_data.get("audio", False),
                "video": model_data.get("video", False),
                "total_parameters": model_data.get("total_parameters", 0),
                "active_parameters": model_data.get("active_parameters", 0),
                "quantization": model_data.get("quantization", ""),
                "context_length": model_data.get("context_length", 1000000),
                "description": model_data.get("description", ""),
                "enabled": model_data.get("enabled", True),
                "max_prompt_tokens": model_data.get("max_prompt_tokens", 1000000),
                "max_response_tokens": model_data.get("max_response_tokens", 1000000),
                "filesize": model_data.get("filesize", -1),
                "limit_request_per_minute": model_limits.get("limit_request_per_minute", 0),
                "limit_request_per_hour": model_limits.get("limit_request_per_hour", 0),
                "limit_request_per_day": model_limits.get("limit_request_per_day", 0),
                "limit_tokens_per_minute": model_limits.get("limit_tokens_per_minute", 0),
                "limit_tokens_per_hour": model_limits.get("limit_tokens_per_hour", 0),
                "limit_tokens_per_day": model_limits.get("limit_tokens_per_day", 0),
                "limit_parallel_calls": model_limits.get("limit_parallel_calls", 0),
            }

            model_obj, model_created = AiModel.objects.get_or_create(
                api_provider=provider,
                provider_model_id=provider_model_id,
                defaults=defaults,
            )
            model_updated = False
            if not model_created:
                fields_changed = any(
                    getattr(model_obj, k) != v for k, v in defaults.items()
                )
                if fields_changed:
                    for k, v in defaults.items():
                        setattr(model_obj, k, v)
                    model_obj.save()
                    model_updated = True

            if model_created:
                model_action = "created"
            elif model_updated:
                model_action = "updated"
            else:
                model_action = "up to date"

            details.append({
                "type": "model",
                "name": f"{name}/{detail_label}",
                "action": model_action,
            })

        count += 1

    return count
