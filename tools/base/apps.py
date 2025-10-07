from django.apps import AppConfig
import sys

class ToolsBuildinUserinteractionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt_string import PromptString
            from .prompts import INSTRUCTIONS, TOOL_RESULT_INJECTION

            # Register prompts
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="ResultInjection", value=TOOL_RESULT_INJECTION)
