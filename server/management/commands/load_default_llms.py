from pathlib import Path

from django.core.management.base import BaseCommand

from registry.loader.load_providers import load_providers_manifest
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider


class Command(BaseCommand):
    def handle(self, *args, **options):
        default_providers = [
            {
                "name": "Google",
                "url": "https://generativelanguage.googleapis.com/v1beta/",
            },
            {
                "name": "Ollama",
                "url": "http://localhost:11434/v1/",
            }
        ]

        for provider_data in default_providers:
            provider, created = ApiProvider.objects.get_or_create(
                name=provider_data["name"],
                defaults={'url': provider_data["url"]}
            )
            if created:
                print(f"Created default API provider: {provider.name}")


        g=AiModel.objects.get_or_create
        
        ollama = ApiProvider.objects.get(name="ollama")
        g(api_provider = ollama, name = "deepseek-ocr:3b", family = "deepseek", is_cloud = False, vision = True, billion_parameters = 3)

        g(api_provider = ollama, name = "glm-ocr:q8_0", family = "glm", is_cloud = False, vision = True, billion_parameters = 0.8)

        g(api_provider = ollama, name = "ministral-3:3b" , family = "ministral-3", is_cloud = False, vision = True, billion_parameters = 3)
        g(api_provider = ollama, name = "ministral-3:8b" , family = "ministral-3", is_cloud = False, vision = True, billion_parameters = 8)
        g(api_provider = ollama, name = "ministral-3:14b", family = "ministral-3", is_cloud = False, vision = True, billion_parameters = 14)

        g(api_provider = ollama, name = "mistral-small3.2:24b", family = "mistral-small", is_cloud = False, vision = True, billion_parameters = 24)


        g(api_provider = ollama, name = "qwen3-vl:2b-instruct", family = "qwen3-vl", is_cloud = False, vision = True, billion_parameters = 2)
        g(api_provider = ollama, name = "qwen3-vl:4b-instruct", family = "qwen3-vl", is_cloud = False, vision = True, billion_parameters = 4)
        g(api_provider = ollama, name = "qwen3-vl:8b-instruct", family = "qwen3-vl", is_cloud = False, vision = True, billion_parameters = 8)

        g(api_provider = ollama, name = "qwen3.5:0.8b", family = "qwen3.5", is_cloud = False, vision = True, billion_parameters = 0.8)
        g(api_provider = ollama, name = "qwen3.5:2b"  , family = "qwen3.5", is_cloud = False, vision = True, billion_parameters = 2)
        g(api_provider = ollama, name = "qwen3.5:4b"  , family = "qwen3.5", is_cloud = False, vision = True, billion_parameters = 4)
        g(api_provider = ollama, name = "qwen3.5:9b"  , family = "qwen3.5", is_cloud = False, vision = True, billion_parameters = 9)

        g(api_provider = ollama, name = "gemma3:1b" , family = "gemma3", is_cloud = False, vision = True, billion_parameters = 1)
        g(api_provider = ollama, name = "gemma3:4b" , family = "gemma3", is_cloud = False, vision = True, billion_parameters = 4)
        g(api_provider = ollama, name = "gemma3:27b", family = "gemma3", is_cloud = False, vision = True, billion_parameters = 27)
        g(api_provider = ollama, name = "gemma4:26b", family = "gemma6", is_cloud = False, vision = True, billion_parameters = 27)


        google = ApiProvider.objects.get(name="google")
        g(api_provider = google, name = "gemini-3.1-flash-lite-preview", family = "gemini", is_cloud = True, vision = True, billion_parameters = 0)
        g(api_provider = google, name = "gemini-3-flash-preview"       , family = "gemini", is_cloud = True, vision = True, billion_parameters = 0)
        g(api_provider = google, name = "gemini-2.5-pro"               , family = "gemini", is_cloud = True, vision = True, billion_parameters = 0)
        g(api_provider = google, name = "gemini-2.5-flash"             , family = "gemini", is_cloud = True, vision = True, billion_parameters = 0)
        g(api_provider = google, name = "gemini-2.5-flash-lite"        , family = "gemini", is_cloud = True, vision = True, billion_parameters = 0)
