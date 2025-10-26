from django.apps import AppConfig
import sys

class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents'

    def ready(self):
        if 'manage.py' not in sys.argv and 'migrate' not in sys.argv:
            # Import signals here so they are registered at app startup.
            import agents.signals

            from core.models.prompt_string import Prompt
            from .prompts import SYSTEM_PROMPT, INSTRUCTIONS, OUTPUT_FORMAT_RULES_REMINDER
            
            Prompt.get_or_create_template(owner=None, source=self.name, key="system", value=SYSTEM_PROMPT)
            Prompt.get_or_create_template(owner=None, source=self.name, key="instructions", value=INSTRUCTIONS)
            Prompt.get_or_create_template(owner=None, source=self.name, key="OutputFormatReminder", value=OUTPUT_FORMAT_RULES_REMINDER)
