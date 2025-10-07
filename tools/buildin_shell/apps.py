from django.apps import AppConfig
import sys

class ToolsBuildinShellConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.buildin_shell'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt_string import PromptString
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .shell_tool import ShellTool
            from .prompts import FUNCTIONS, INSTRUCTIONS

            ToolDefinition.objects.get_or_create(
                name='shell',
                defaults={
                    'display_name': 'Shell Command Executor',
                    'description': ShellTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Functions", value=function_python_string)
