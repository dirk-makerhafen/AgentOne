from __future__ import annotations

import requests
from requests.exceptions import RequestException

from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


OLLAMA_CLOUD_PROVIDER_NAME = "Ollama Cloud"
"""Provider name for cloud-served models discovered on a local Ollama endpoint.

Cloud models enabled in a local Ollama install appear in ``GET /v1/models``
with a ``-cloud`` / ``:cloud`` tag (e.g. ``gpt-oss:120b-cloud``). They are
split out of the local provider and stored here instead.
"""


def _is_cloud_suffixed(name: str) -> bool:
    return name.endswith("-cloud") or name.endswith(":cloud")


def _strip_cloud_suffix(name: str) -> str:
    for suffix in (":cloud", "-cloud"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _get_cloud_provider() -> ApiProvider:
    """Get-or-create the provider that hosts Ollama cloud-served models."""
    cloud, _ = ApiProvider.objects.get_or_create(
        name=OLLAMA_CLOUD_PROVIDER_NAME,
        defaults={"url": "https://ollama.com/v1", "is_local": False},
    )
    return cloud


def _resolve_target(provider, cloud_provider, raw_name, model_defaults):
    """Decide which provider/model a raw endpoint entry maps to.

    Cloud-served models found on a local provider (e.g. Ollama) are split
    out and stored on the ``Ollama Cloud`` provider with the ``-cloud`` /
    ``:cloud`` tag stripped.  Returns ``(target, stored_name, flags)``.
    """
    if provider.is_local and _is_cloud_suffixed(raw_name):
        target = cloud_provider
        stored_name = _strip_cloud_suffix(raw_name)
        flags = {"self_hosted": False, "is_cloud": True}
    else:
        target = provider
        stored_name = raw_name
        flags = {"self_hosted": model_defaults["self_hosted"], "is_cloud": model_defaults["is_cloud"]}
    return target, stored_name, flags


def sync_provider_models(provider_id: int) -> dict:
    """Fetch models from a provider's API and upsert AiModel records.

    Supports OpenAI-compatible APIs (``GET /v1/models``) and Google's
    Generative Language API.  Falls back to an unauthenticated request
    if no API key is configured.  Returns a summary dict with ``created``,
    ``updated``, ``total``, and ``error`` (empty on success).
    """
    try:
        provider = ApiProvider.objects.get(pk=provider_id)
    except ApiProvider.DoesNotExist:
        return {"error": "Provider not found", "created": 0, "updated": 0, "total": 0}

    base_url = provider.url.rstrip("/")
    is_google = "generativelanguage.googleapis.com" in base_url
    models_url = f"{base_url}/models"

    # A local provider (e.g. Ollama) may still serve cloud models, so newly
    # discovered models default to the provider's locality but can be overridden
    # per-model via explicit ``is_cloud`` / ``self_hosted`` keys in the payload.
    local_defaults = {"self_hosted": True, "is_cloud": False}
    cloud_defaults = {"self_hosted": False, "is_cloud": True}
    model_defaults = local_defaults if provider.is_local else cloud_defaults

    api_key = provider.api_keys.filter(enabled=True).first()
    headers = {}
    if api_key is not None:
        if is_google:
            headers["x-goog-api-key"] = api_key.key
        else:
            headers["Authorization"] = f"Bearer {api_key.key}"

    try:
        resp = requests.get(models_url, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except RequestException as e:
        return {"error": str(e), "created": 0, "updated": 0, "total": 0}

    raw_models = payload.get(
        "data" if not is_google else "models",
        payload if isinstance(payload, list) else [],
    )
    if not isinstance(raw_models, list):
        raw_models = []

    created = 0
    updated = 0
    seen_names = set()
    seen_cloud = set()
    cloud_provider = None

    for m in raw_models:
        raw_name = m.get("id" if not is_google else "name", "")
        if not raw_name:
            continue
        name = raw_name
        if name.startswith("models/"):
            name = name.split("/", 1)[-1]

        # Split cloud-served models off a local endpoint into the cloud provider
        # (ids keep their ollama.com form — the ``-cloud`` tag is local-only).
        is_cloud_served = provider.is_local and _is_cloud_suffixed(name)
        if is_cloud_served and cloud_provider is None:
            cloud_provider = _get_cloud_provider()
        target, stored_name, flags = _resolve_target(
            provider, cloud_provider, name, model_defaults,
        )

        (seen_cloud if is_cloud_served else seen_names).add(stored_name)

        family = m.get("owned_by", "") if not is_google else m.get("displayName", "")
        description = m.get("description", "")

        model, is_new = AiModel.objects.get_or_create(
            api_provider=target,
            name=stored_name,
            defaults={
                "family": family,
                "description": description,
                "self_hosted": flags["self_hosted"],
                "is_cloud": flags["is_cloud"],
            },
        )
        if is_new:
            created += 1
            continue
        updated += 1

        # Existing models keep their manifest flags (is_cloud/self_hosted).
        # Refresh metadata and re-enable models the provider still serves.
        re_enabled = not model.enabled
        if re_enabled:
            model.enabled = True
        fields_changed = model.family != family or model.description != description
        if fields_changed or re_enabled:
            model.family = family
            model.description = description
            model.save(update_fields=["family", "description", "enabled"])

    # Disable models the providers no longer serve
    stale_count = AiModel.objects.filter(
        api_provider=provider, enabled=True,
    ).exclude(name__in=seen_names).update(enabled=False)
    if cloud_provider is not None:
        stale_count += AiModel.objects.filter(
            api_provider=cloud_provider, enabled=True,
        ).exclude(name__in=seen_cloud).update(enabled=False)

    return {"error": "", "created": created, "updated": updated, "stale": stale_count, "total": len(raw_models)}
