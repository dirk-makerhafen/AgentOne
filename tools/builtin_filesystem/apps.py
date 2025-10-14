from django.apps import AppConfig
import sys

class ToolsBuiltinFilesystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.builtin_filesystem'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt_string import PromptString
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .filesystem_tool import FilesystemTool
            from .prompts import TOOLS, PROMPTS

            ToolDefinition.objects.get_or_create(
                name='filesystem',
                defaults={
                    'display_name': 'Filesystem',
                    'description': FilesystemTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )
            for prompt in PROMPTS:
                PromptString.objects.get_or_create(owner=None, source=self.name, key=prompt["name"], value=prompt["template"])
            
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in TOOLS.items()])
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Functions", value=function_python_string)
