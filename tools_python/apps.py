from django.apps import AppConfig
import sys

class Tools_Python(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_python'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_python.prompts import INSTRUCTIONS, FUNCTIONS, LIST_OF_SHARED_VARS
            from tools_python.pythontool import PythonTool
            from tools_common.models  import ToolDefinition # Import ToolDefinition

            # Register the ToolDefinition for the Python tool
            ToolDefinition.objects.get_or_create(
                name='python',
                defaults={
                    'display_name': 'Python Interpreter',
                    'description': PythonTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            # Register prompts
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source="Tools.Python", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.Python", key="Functions", value=function_python_string)
            PromptString.objects.get_or_create(owner=None, source="Tools.Python", key="SharedVarsInjection", value=LIST_OF_SHARED_VARS)


