from django.apps import AppConfig
import sys

class ToolsBuiltinUserinteractionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.builtin_userinteraction'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt import Prompt
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .user_interaction_tool import UserInteractionTool
            from .prompts import TOOLS, PROMPTS

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
            for prompt in PROMPTS:
                Prompt.get_or_create_template(owner=None, source=self.name, key=prompt["name"], value=prompt["template"])
            
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in TOOLS.items()])
            Prompt.get_or_create_template(owner=None, source=self.name, key="functions", value=function_python_string)
