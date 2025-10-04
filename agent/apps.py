from django.apps import AppConfig
import sys

class Agent_Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agent'

    def ready(self):
        # Import signals to ensure they are registered
        import agent.signals 

        if not 'manage.py' in sys.argv:
            from common.models import PromptString
            from agent.prompts import INSTRUCTIONS, SYSTEM_PROMPT, OUTPUT_FORMAT_RULES, OUTPUT_FORMAT_RULES_REMINDER

            PromptString.objects.get_or_create(owner=None, source="Agent", key="System", value=SYSTEM_PROMPT)
            PromptString.objects.get_or_create(owner=None, source="Agent", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Agent", key="OutputFormat", value=OUTPUT_FORMAT_RULES)
            PromptString.objects.get_or_create(owner=None, source="Agent", key="OutputFormatReminder", value=OUTPUT_FORMAT_RULES_REMINDER)
