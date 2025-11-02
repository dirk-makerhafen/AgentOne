from django.apps import AppConfig
import sys

class ToolsBuiltinA2aConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.builtin_a2a'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt import Prompt
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .a2a_tool import A2ATool
            from .prompts import TOOLS, PROMPTS

            ToolDefinition.objects.get_or_create(
                name='a2a',
                defaults={
                    'display_name': 'Agent-to-Agent Communication',
                    'description': A2ATool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )
            for prompt in PROMPTS:
                Prompt.get_or_create_template(owner=None, source=self.name, key=prompt["name"], value=prompt["template"])
            
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in TOOLS.items()])
            Prompt.get_or_create_template(owner=None, source=self.name, key="functions", value=function_python_string)
