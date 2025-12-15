from django.apps import AppConfig
import sys

class ProvidersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'providers'

    def ready(self):
        """
        This method is called when the application is ready.
        We use it to create default API providers if they don't exist.
        """
        from .models.api_provider import ApiProvider
        if 'manage.py'  not in sys.argv and 'migrate' not in sys.argv:
            # Default providers to ensure are present on startup
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
