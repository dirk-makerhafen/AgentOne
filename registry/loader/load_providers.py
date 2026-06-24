from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


def load_providers_manifest(
    manifest_path: Path,
    details: List[Dict[str, str]],
) -> int:
    # pylint: disable=too-many-locals
    """Upsert providers and models from a YAML manifest.

    Expected format::

        providers:
          - name: Google
            url: "https://generativelanguage.googleapis.com/v1beta/"
            models:
              - name: gemini-2.5-flash
                family: gemini
                vision: true
                supports_reasoning: true
                supports_tool_call: true

    Returns the number of providers loaded.
    """
    if not manifest_path.exists():
        return 0

    with manifest_path.open(encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}

    providers_list: List[Dict[str, Any]] = data.get("providers") or []
    if not providers_list:
        return 0

    count = 0
    for provider_data in providers_list:
        name = provider_data["name"]
        provider, created = ApiProvider.objects.get_or_create(
            name=name,
            defaults={"url": provider_data.get("url", "")},
        )
        if not created:
            url = provider_data.get("url")
            if url is not None and provider.url != url:
                provider.url = url
                provider.save()
                action = "updated"
            else:
                action = "up to date"
        else:
            action = "created"
        details.append({
            "type": "provider",
            "name": name,
            "action": action,
        })

        for model_data in provider_data.get("models") or []:
            model_name: str = model_data["name"]
            defaults = {
                "family": model_data.get("family", ""),
                "self_hosted": model_data.get("self_hosted", False),
                "open_weights": model_data.get("open_weights", False),
                "supports_reasoning": model_data.get("supports_reasoning", False),
                "supports_tool_call": model_data.get("supports_tool_call", False),
                "vision": model_data.get("vision", False),
                "total_parameters": model_data.get("total_parameters", 0),
                "active_parameters": model_data.get("active_parameters", 0),
                "quantization": model_data.get("quantization", ""),
                "context_length": model_data.get("context_length", 1000000),
                "description": model_data.get("description", ""),
                "enabled": model_data.get("enabled", True),
                "max_prompt_tokens": model_data.get("max_prompt_tokens", 1000000),
                "max_response_tokens": model_data.get("max_response_tokens", 1000000),
            }

            model_obj, model_created = AiModel.objects.get_or_create(
                api_provider=provider,
                name=model_name,
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
                "name": f"{name}/{model_name}",
                "action": model_action,
            })

        count += 1

    return count
