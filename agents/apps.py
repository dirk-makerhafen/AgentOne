from django.apps import AppConfig
import sys

class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents'

    def ready(self):
        if 'manage.py' not in sys.argv and 'migrate' not in sys.argv:
            from core.models.prompt_string import PromptString
            from .prompts import SYSTEM_PROMPT, INSTRUCTIONS, OUTPUT_FORMAT_RULES, OUTPUT_FORMAT_RULES_REMINDER
            
            PromptString.objects.get_or_create(owner=None, source=self.name, key="System", value=SYSTEM_PROMPT)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="OutputFormat", value=OUTPUT_FORMAT_RULES)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="OutputFormatReminder", value=OUTPUT_FORMAT_RULES_REMINDER)
