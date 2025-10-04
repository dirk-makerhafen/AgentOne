from django.apps import AppConfig
import sys

class ToolsShellConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_shell'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_shell.prompts import INSTRUCTIONS, FUNCTIONS
            from tools_shell.shelltool import ShellTool
            from tools_common.models  import ToolDefinition # Import ToolDefinition

            # Register the ToolDefinition for the Shell tool
            ToolDefinition.objects.get_or_create(
                name='shell',
                defaults={
                    'display_name': 'Shell Command Executor',
                    'description': ShellTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )
            
            # Register prompts
            # The key in the FUNCTIONS dict is the function name.
            function_name = list(FUNCTIONS.keys())[0]
            function_definition = FUNCTIONS[function_name]
            
            function_shell_string = f"{generate_function_stub(function_name, function_definition)}\n"
            PromptString.objects.get_or_create(owner=None, source="Tools.Shell", key="Instructions", value= INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.Shell", key="Functions", value= function_shell_string)
