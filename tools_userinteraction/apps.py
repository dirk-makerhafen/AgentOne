from django.apps import AppConfig
import sys

class Tools_Userintraction(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_userinteraction'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_userinteraction.prompts import INSTRUCTIONS, FUNCTIONS
            from tools_userinteraction.tool import UserInteractionTool
            from tools_common.models  import ToolDefinition # Import ToolDefinition

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
            PromptString.objects.get_or_create(owner=None, source="Tools.UserInteraction", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.UserInteraction", key="Functions", value=function_python_string)

