from django.apps import AppConfig
import sys

class ToolsBuildinUserinteractionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.buildin_userinteraction'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt_string import PromptString
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .user_interaction_tool import UserInteractionTool
            from .prompts import INSTRUCTIONS, FUNCTIONS

            # Register the ToolDefinition for the User Interaction tool
            ToolDefinition.objects.get_or_create(
                name='userinteraction',
                defaults={
                    'display_name': 'User Interaction',
                    'description': UserInteractionTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            # Register prompts
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Functions", value=function_python_string)
