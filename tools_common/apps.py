from django.apps import AppConfig
import sys

class Tools_Common_Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_common'

    def ready(self):
        if not 'manage.py' in sys.argv:
            from common.models import PromptString
            from tools_common.prompts import INSTRUCTIONS, TOOL_RESULT_INJECTION
            PromptString.objects.get_or_create(owner=None, source="Tools.Common", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.Common", key="ResultInjection", value=TOOL_RESULT_INJECTION)
