from __future__ import annotations

import requests
from requests.exceptions import RequestException

from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


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

    for m in raw_models:
        raw_name = m.get("id" if not is_google else "name", "")
        if not raw_name:
            continue
        name = raw_name
        if name.startswith("models/"):
            name = name.split("/", 1)[-1]

        defaults = {
            "family": m.get("owned_by", "") if not is_google else m.get("displayName", ""),
            "description": m.get("description", ""),
        }

        _, is_new = AiModel.objects.update_or_create(
            api_provider=provider,
            name=name,
            defaults=defaults,
        )
        if is_new:
            created += 1
        else:
            updated += 1

    return {"error": "", "created": created, "updated": updated, "total": len(raw_models)}
