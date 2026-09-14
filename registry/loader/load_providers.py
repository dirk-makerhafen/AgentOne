from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import frontmatter
import yaml

from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


def _slugify(name: str) -> str:
    """Stable filename-style slug (mirrors the migration backfill)."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "provider"

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


def _read_md_frontmatter(path: Path) -> Dict[str, Any]:
    """Parse the YAML frontmatter of a research ``*.md`` file."""
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    meta = post.metadata if isinstance(post, frontmatter.Post) else (post or {})
    return dict(meta) if isinstance(meta, dict) else {}


# Nested ``limits:`` periods (research frontmatter) mapped to the flat
# ``AiModel`` / ``ApiProvider`` limit fields.  ``second`` has no per-second
# field, so it is converted to the nearest supported window (per-minute),
# mirroring the RPS/TPS handling in ``RATE_LIMIT_MAP``.
NESTED_LIMIT_MAP: Dict[Tuple[str, str], Tuple[str, int]] = {
    ("requests", "second"): ("limit_request_per_minute", 60),
    ("requests", "minute"): ("limit_request_per_minute", 1),
    ("requests", "hour"): ("limit_request_per_hour", 1),
    ("requests", "day"): ("limit_request_per_day", 1),
    ("requests", "week"): ("limit_request_per_week", 1),
    ("requests", "month"): ("limit_request_per_month", 1),
    ("tokens", "second"): ("limit_tokens_per_minute", 60),
    ("tokens", "minute"): ("limit_tokens_per_minute", 1),
    ("tokens", "hour"): ("limit_tokens_per_hour", 1),
    ("tokens", "day"): ("limit_tokens_per_day", 1),
    ("tokens", "week"): ("limit_tokens_per_week", 1),
    ("tokens", "month"): ("limit_tokens_per_month", 1),
}


def _nested_limits_to_flat(limits: Any) -> Dict[str, int]:
    """Map nested research ``limits:`` onto flat limit field values.

    Only documented values are mapped; unknown shapes are ignored.  A
    0 (or absent) value means unlimited, so only positive bounds land
    in the result.  ``tokens:`` split into ``input:``/``output:`` caps is
    summed into the combined field (the rate limiter only tracks combined
    budgets).
    """
    flat: Dict[str, int] = {}

    def _add(category: str, period: str, value: Any, combine: bool = False) -> None:
        mapping = NESTED_LIMIT_MAP.get((category, period))
        if mapping is None:
            return
        field, multiplier = mapping
        try:
            bound = int(float(value)) * multiplier
        except (TypeError, ValueError):
            return
        if bound <= 0:
            return
        if field in flat:
            # Input/output splits sum into the combined budget; repeated
            # plain keys keep the most conservative bound.
            flat[field] = flat[field] + bound if combine else min(flat[field], bound)
        else:
            flat[field] = bound

    if not isinstance(limits, dict):
        return flat
    for category in ("requests", "tokens"):
        section = limits.get(category)
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            if key in ("input", "output") and isinstance(value, dict):
                # Split caps (``tokens: {input: {minute: …}, output: …}``):
                # sum both sides into the combined field per period.
                for period, num in value.items():
                    if isinstance(num, dict):
                        try:
                            num = sum(int(float(v)) for v in num.values())
                        except (TypeError, ValueError):
                            continue
                    _add(category, period, num, combine=True)
            elif isinstance(value, dict):
                try:
                    value = sum(int(float(v)) for v in value.values())
                except (TypeError, ValueError):
                    continue
                _add(category, key, value)
            else:
                _add(category, key, value)
    return flat


def _parse_leaderboard_rank(meta: Dict[str, Any]) -> Tuple[int | None, bool]:
    """Return ``(rank, is_estimate)`` from card frontmatter.

    Both ``leaderboard_rank: 53`` and ``leaderboard_rank_estimated: "~25"``
    land in the single sortable ``AiModel.leaderboard_rank`` integer; the
    flag preserves estimated-ness for display.
    """
    rank = meta.get("leaderboard_rank")
    try:
        if rank is not None:
            return int(rank), False
    except (TypeError, ValueError):
        pass
    estimated = meta.get("leaderboard_rank_estimated")
    if estimated is not None:
        digits = "".join(c for c in str(estimated) if c.isdigit())
        if digits:
            return int(digits), True
    return None, False


def _modalities_to_flags(modalities: Any) -> Dict[str, bool]:
    """Fold card ``modalities: {input: [...], output: [...]}`` into flags."""
    flags = {"vision": False, "audio": False, "video": False}
    if not isinstance(modalities, dict):
        return flags
    seen = set()
    for side in ("input", "output"):
        values = modalities.get(side) or []
        if isinstance(values, str):
            values = [values]
        seen.update(str(v).lower() for v in values if isinstance(values, list))
    return {
        "vision": "image" in seen,
        "audio": "audio" in seen,
        "video": "video" in seen,
    }


def load_providers_manifest(
    manifest_path: Path,
    details: List[Dict[str, str]],
) -> int:
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Upsert providers and models from a legacy YAML manifest.

    Legacy path (kept for tests and one-off imports) — production loading
    goes through :func:`load_providers_dir` from ``providers/*.md`` +
    ``models/*.md`` frontmatter.  Expected format::

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
        litellm_prefix: gemini        # optional; omit = OpenAI-compatible (api_base = url)
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
                "slug": _slugify(name),
                "url": provider_data.get("url", ""),
                "is_local": is_local,
                "litellm_prefix": provider_data.get("litellm_prefix", ""),
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
            litellm_prefix = provider_data.get("litellm_prefix", "")
            if provider.litellm_prefix != litellm_prefix:
                provider.litellm_prefix = litellm_prefix
                provider.save(update_fields=["litellm_prefix"])
                action = "updated"
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


def _upsert_provider_from_frontmatter(
    slug: str,
    meta: Dict[str, Any],
    details: List[Dict[str, str]],
) -> ApiProvider | None:
    """Upsert one ``ApiProvider`` from a ``providers/<slug>.md`` frontmatter.

    Returns None (and records a skipped detail) when the file carries no
    usable API endpoint.
    """
    name = meta.get("name") or slug
    api_base = str(meta.get("api_base") or "")
    if not api_base:
        # Only inherit ``url:`` when it already points at an API surface —
        # never a marketing homepage (e.g. region-specific endpoints like
        # IBM watsonx have no fixed base and must stay unloaded).
        url = str(meta.get("url") or "")
        if any(hint in url for hint in ("/v1", "/v2", "/v3", "/api/", "compatible-mode", "/openai")):
            api_base = url
    if not api_base:
        details.append({"type": "provider", "name": name, "action": "skipped (no api_base)"})
        return None
    is_local = bool(meta.get("is_local", False)) or _is_loopback_url(str(api_base))

    provider, created = ApiProvider.objects.update_or_create(
        slug=slug,
        defaults={
            "name": name,
            "url": str(api_base),
            "is_local": is_local,
            "litellm_prefix": meta.get("litellm_prefix") or "",
            "enabled": True,
        },
    )

    info: Dict[str, Any] = {
        "api_key_url": meta.get("api_key_url") or "",
        "setup_instructions": meta.get("setup_instructions") or "",
    }
    if meta.get("default_api_key"):
        info["default_api_key"] = meta["default_api_key"]
    if meta.get("wire"):
        info["wire"] = meta["wire"]
    provider.data = info
    provider.save(update_fields=["raw_data"])

    flat = _nested_limits_to_flat(meta.get("limits"))
    nested = meta.get("limits")
    if isinstance(nested, dict) and "parallel_calls" in nested:
        try:
            parallel = int(float(nested["parallel_calls"]))
            if parallel > 0:
                flat["limit_parallel_calls"] = parallel
        except (TypeError, ValueError):
            pass
    changed_fields = []
    for field, value in flat.items():
        if field in LIMIT_FIELDS + ("limit_parallel_calls",) and getattr(provider, field) != value:
            setattr(provider, field, value)
            changed_fields.append(field)
    if changed_fields:
        provider.save(update_fields=changed_fields)

    details.append({
        "type": "provider",
        "name": name,
        "action": "created" if created else "updated",
    })
    return provider


def _upsert_model_from_card_entry(
    provider: ApiProvider,
    card_meta: Dict[str, Any],
    card_slug: str,
    entry: Dict[str, Any],
    details: List[Dict[str, str]],
) -> Tuple[str, str | None]:
    """Upsert one ``AiModel`` from a model-card ``providers[]`` entry.

    Returns ``(detail_label, seen_key)`` where ``seen_key`` is the
    ``(provider_id, provider_model_id)`` identity, or None when skipped.
    """
    label = entry.get("model_id") or card_meta.get("name") or card_slug
    if entry.get("gate"):
        details.append({
            "type": "model",
            "name": f"{provider.name}/{label}",
            "action": "skipped (payment-gated)",
        })
        return label, None

    model_ids = entry.get("model_id") or []
    if isinstance(model_ids, str):
        model_ids = [model_ids]
    if not model_ids:
        details.append({
            "type": "model",
            "name": f"{provider.name}/{label}",
            "action": "skipped (no model_id)",
        })
        return label, None

    rank, is_estimate = _parse_leaderboard_rank(card_meta)
    flags = _modalities_to_flags(card_meta.get("modalities"))
    card_wire = card_meta.get("wire") or {}
    entry_wire = entry.get("wire") or {}
    wire = {**card_wire, **entry_wire} if isinstance(card_wire, dict) and isinstance(entry_wire, dict) else (entry_wire or card_wire or None)

    seen_key: str | None = None
    for provider_model_id in model_ids:
        provider_model_id = str(provider_model_id)
        model_limits = _nested_limits_to_flat(entry.get("limits"))
        for k in LIMIT_FIELDS:
            if k in entry:
                model_limits[k] = entry[k]

        defaults = {
            "name": card_meta.get("name") or provider_model_id,
            "family": card_meta.get("family") or "",
            "developer": card_meta.get("developer") or "",
            "canonical_id": card_meta.get("canonical_id") or "",
            "leaderboard_id": card_meta.get("leaderboard_id") or "",
            "leaderboard_rank": rank,
            "leaderboard_rank_is_estimate": is_estimate,
            "is_cloud": entry.get("is_cloud", card_meta.get("is_cloud", True)),
            "open_weights": card_meta.get("open_weights", False),
            "supports_reasoning": card_meta.get("reasoning", card_meta.get("supports_reasoning", False)),
            "supports_tool_call": card_meta.get("tool_call", card_meta.get("supports_tool_call", False)),
            "vision": entry.get("vision", flags["vision"]),
            "audio": entry.get("audio", flags["audio"]),
            "video": entry.get("video", flags["video"]),
            "context_length": entry.get("context_window", card_meta.get("context_window", 1000000)),
            "max_response_tokens": entry.get("max_output_tokens", card_meta.get("max_output_tokens", 1000000)),
            "description": card_meta.get("description") or "",
            "enabled": True,
            "limit_request_per_minute": model_limits.get("limit_request_per_minute", 0),
            "limit_request_per_hour": model_limits.get("limit_request_per_hour", 0),
            "limit_request_per_day": model_limits.get("limit_request_per_day", 0),
            "limit_tokens_per_minute": model_limits.get("limit_tokens_per_minute", 0),
            "limit_tokens_per_hour": model_limits.get("limit_tokens_per_hour", 0),
            "limit_tokens_per_day": model_limits.get("limit_tokens_per_day", 0),
            "limit_parallel_calls": model_limits.get("limit_parallel_calls", 0),
        }
        # Week/month caps: same explicit-only rule as the yaml path.
        for k in ("limit_request_per_week", "limit_request_per_month",
                  "limit_tokens_per_week", "limit_tokens_per_month"):
            if k in model_limits:
                defaults[k] = model_limits[k]

        model_obj, model_created = AiModel.objects.update_or_create(
            api_provider=provider,
            provider_model_id=provider_model_id,
            defaults=defaults,
        )
        model_obj.data = {
            "card": card_slug,
            "conditions": entry.get("conditions") or "",
            "verified": entry.get("verified") or "",
            "wire": wire,
        }
        model_obj.save(update_fields=["raw_data"])

        details.append({
            "type": "model",
            "name": f"{provider.name}/{provider_model_id}",
            "action": "created" if model_created else "updated",
        })
        seen_key = f"{provider.pk}:{provider_model_id}"

    return label, seen_key


def load_providers_dir(
    providers_dir: Path,
    models_dir: Path | None = None,
    details: List[Dict[str, str]] | None = None,
    disable_missing: bool = False,
) -> int:
    """Upsert providers and models from research ``*.md`` frontmatter.

    ``providers_dir`` holds one ``<slug>.md`` per provider (slug = filename
    stem, the stable upsert key).  ``models_dir`` holds model cards whose
    frontmatter ``providers[]`` entries (``file:`` = provider slug,
    ``model_id:`` = provider-side id) supply the ``AiModel`` rows — the
    1:1 machine-readable mirror of each card's providers table.

    With ``disable_missing=True`` (used by ``reload_all``), providers whose
    slug has no file and models with no card row are set ``enabled=False``
    instead of being deleted, so call history stays intact.  Pass False for
    scoped/test loads so a partial directory never disables the world.
    """
    # pylint: disable=too-many-locals,too-many-branches
    if details is None:
        details = []
    providers_dir = Path(providers_dir)
    if not providers_dir.is_dir():
        return 0

    by_slug: Dict[str, ApiProvider] = {}
    count = 0
    for md_path in sorted(providers_dir.glob("*.md")):
        try:
            meta = _read_md_frontmatter(md_path)
        except Exception as e:  # noqa: BLE001 — one bad file must not abort the reload
            details.append({"type": "provider", "name": md_path.stem, "action": f"skipped ({e})"})
            continue
        provider = _upsert_provider_from_frontmatter(md_path.stem, meta, details)
        if provider is not None:
            by_slug[md_path.stem] = provider
            count += 1

    seen_models: set[str] = set()
    if models_dir is not None and Path(models_dir).is_dir():
        for card_path in sorted(Path(models_dir).glob("*.md")):
            try:
                card_meta = _read_md_frontmatter(card_path)
            except Exception as e:  # noqa: BLE001 — see above
                details.append({"type": "model", "name": card_path.stem, "action": f"skipped ({e})"})
                continue
            for entry in card_meta.get("providers") or []:
                if not isinstance(entry, dict):
                    continue
                slug = entry.get("file") or ""
                provider = by_slug.get(slug)
                if provider is None:
                    details.append({
                        "type": "model",
                        "name": f"{slug}/{entry.get('model_id')}",
                        "action": "skipped (unknown provider file)",
                    })
                    continue
                _, seen_key = _upsert_model_from_card_entry(
                    provider, card_meta, card_path.stem, entry, details
                )
                if seen_key is not None:
                    seen_models.add(seen_key)

    if disable_missing:
        stale_providers = ApiProvider.objects.exclude(slug__in=list(by_slug)).filter(enabled=True, is_local=False)
        for provider in stale_providers:
            provider.enabled = False
            provider.save(update_fields=["enabled"])
            details.append({"type": "provider", "name": provider.name, "action": "disabled (no file)"})
        seen_pairs = {(int(k.split(":")[0]), k.split(":", 1)[1]) for k in seen_models}
        stale_models = AiModel.objects.filter(enabled=True, is_cloud = True)
        for model in stale_models:
            if (model.api_provider_id, model.provider_model_id) not in seen_pairs:
                model.enabled = False
                model.save(update_fields=["enabled"])
                details.append({
                    "type": "model",
                    "name": f"{model.api_provider.name}/{model.provider_model_id}",
                    "action": "disabled (no card row)",
                })

    return count
