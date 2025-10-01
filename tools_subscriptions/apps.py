from django.apps import AppConfig
import sys

class ToolsSubscriptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_subscriptions'

    def ready(self):
        if 'manage.py' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from .prompts import INSTRUCTIONS, FUNCTIONS, SUBSCRIPTION_RESULT_INJECTION
            
            function_name = list(FUNCTIONS.keys())[0]
            function_definition = FUNCTIONS[function_name]
            function_string = f"{generate_function_stub(function_name, function_definition)}\n"

            PromptString.objects.get_or_create(owner=None, source="Tools.Subscriptions", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.Subscriptions", key="Functions", value=function_string)
            PromptString.objects.get_or_create(owner=None, source="Tools.Subscriptions", key="SubscriptionResultInjection", value=SUBSCRIPTION_RESULT_INJECTION)
