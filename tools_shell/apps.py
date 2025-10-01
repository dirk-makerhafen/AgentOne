from django.apps import AppConfig
import sys

class ToolsShellConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_shell'
    #THIS_IS_A_MARKER
    def ready(self):
        if 'manage.py' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_shell.prompts import DESCRIPTION, FUNCTIONS
            
            # The key in the FUNCTIONS dict is the function name.
            function_name = list(FUNCTIONS.keys())[0]
            function_definition = FUNCTIONS[function_name]
            
            function_shell_string = f"{generate_function_stub(function_name, function_definition)}\n"
            PromptString.objects.get_or_create(owner=None, source="Tools.Shell", key="Description", value= DESCRIPTION)
            PromptString.objects.get_or_create(owner=None, source="Tools.Shell", key="Functions", value= function_shell_string)
