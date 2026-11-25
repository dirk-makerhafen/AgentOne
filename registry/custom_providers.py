"""UI-managed custom providers and their model offerings.

Providers created in Settings are not part of the generated catalog, so the
loader leaves them (and their offerings) alone.  This module owns the two ways
a custom provider gets its models: fetching an OpenAI-compatible ``/models``
endpoint, or entering a provider-side model id by hand.  Both paths end in an
:class:`~server.models.providers.ai_model_offering.AiModelOffering` row, which
is what the picker and rate limiter actually route on.
"""
from __future__ import annotations

from urllib.parse import urlparse

import requests
from django.db import transaction
from requests.exceptions import RequestException

from server.models.providers.ai_model import AiModel
from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider

REQUEST_TIMEOUT = 10
MAX_MODELS = 5000


def _clean_url(value: str) -> str:
    url = (value or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Base URL must be an http(s) URL, e.g. http://127.0.0.1:8000/v1")
    return url


def mark_custom(provider: ApiProvider) -> None:
    """Protect a provider and its offerings from stale-catalog disabling."""
    if not provider.is_custom:
        provider.is_custom = True
        provider.save(update_fields=["is_custom"])


@transaction.atomic
def create_custom_provider(
    *,
    name: str,
    url: str,
    is_local: bool = False,
    litellm_prefix: str = "",
    api_key: str = "",
    keyless: bool = False,
) -> ApiProvider:
    """Create a provider from the Settings form and make it immediately usable.

    A supplied API key becomes an enabled :class:`ApiKey`.  For keyless (typically
    local) endpoints ``default_api_key`` gets a placeholder token — the picker
    requires one of the two before it will route to the provider.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Provider name is required.")
    base_url = _clean_url(url)
    provider = ApiProvider.objects.create(
        name=name,
        url=base_url,
        is_local=bool(is_local),
        litellm_prefix=(litellm_prefix or "").strip(),
        is_custom=True,
        enabled=True,
    )
    if (api_key or "").strip():
        ApiKey.objects.create(
            api_provider=provider,
            key=api_key.strip(),
            comment="Added in settings",
            enabled=True,
        )
    elif keyless:
        provider.default_api_key = "local" if provider.is_local else "public"
        provider.save(update_fields=["default_api_key"])
    return provider


@transaction.atomic
def upsert_offering(
    provider: ApiProvider,
    provider_model_id: str,
    *,
    name: str = "",
    is_free: bool = False,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
) -> bool:
    """Ensure a routable offering exists; return True when one was created.

    Offerings are keyed by the exact provider-side model id.  An existing row
    is re-enabled but keeps its curated name/flags, so loading models never
    overwrites free-tier research or an operator's edits.
    """
    model_id = (provider_model_id or "").strip()
    if not model_id:
        raise ValueError("Model id is required.")
    if len(model_id) > 512:
        raise ValueError("Model id is too long (512 characters max).")
    display = (name or "").strip() or model_id

    existing = provider.offerings.filter(provider_model_id=model_id).first()
    if existing is not None:
        if not existing.enabled:
            existing.enabled = True
            existing.save(update_fields=["enabled"])
        return False

    raw, _ = AiModel.objects.get_or_create(name=display)
    AiModelOffering.objects.create(
        api_provider=provider,
        model=raw,
        name=display,
        provider_model_id=model_id,
        enabled=True,
        is_free=bool(is_free),
        is_cloud=not provider.is_local,
        context_window_override=context_window or None,
        max_output_tokens_override=max_output_tokens or None,
    )
    return True


def _model_urls(base_url: str) -> tuple[list[str], bool]:
    """Return candidate ``/models`` URLs and whether this is a Google endpoint."""
    is_google = "generativelanguage.googleapis.com" in base_url
    if is_google or base_url.rstrip("/").endswith("/v1"):
        return [f"{base_url}/models"], is_google
    return [f"{base_url}/models", f"{base_url}/v1/models"], is_google


def fetch_provider_model_ids(provider: ApiProvider) -> tuple[list[str], str]:
    """Fetch model ids from *provider*; return ``(ids, error)``."""
    base_url = (provider.url or "").rstrip("/")
    if not base_url:
        return [], "Provider has no base URL."
    urls, is_google = _model_urls(base_url)

    key = provider.api_keys.filter(enabled=True).values_list("key", flat=True).first()
    key = key or provider.default_api_key
    headers = {}
    if key and key not in ("local", "public"):
        if is_google:
            headers["x-goog-api-key"] = key
        else:
            headers["Authorization"] = f"Bearer {key}"

    payload = None
    last_error = ""
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 404 and len(urls) > 1:
                last_error = f"HTTP 404 from {url}"
                continue
            response.raise_for_status()
            payload = response.json()
            break
        except RequestException as exc:
            last_error = str(exc)
        except ValueError:
            last_error = "Endpoint did not return valid JSON."
    if payload is None:
        return [], last_error or "Could not fetch models."

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("data") or payload.get("models") or []
    else:
        return [], "Unexpected /models response."

    ids: list[str] = []
    for item in items:
        if isinstance(item, str):
            raw = item
        elif isinstance(item, dict):
            raw = item.get("id") or item.get("name") or ""
        else:
            continue
        raw = str(raw).strip()
        if raw.startswith("models/"):
            raw = raw.split("/", 1)[1]
        if not raw or raw in ids:
            continue
        ids.append(raw[:512])
        if len(ids) >= MAX_MODELS:
            break
    return ids, ""


@transaction.atomic
def sync_provider_models(provider: ApiProvider, model_ids: list[str]) -> dict:
    """Create offerings for *model_ids* and mark the provider as user-managed."""
    created = 0
    for model_id in model_ids:
        if upsert_offering(provider, model_id):
            created += 1
    mark_custom(provider)
    return {"created": created, "seen": len(model_ids)}
