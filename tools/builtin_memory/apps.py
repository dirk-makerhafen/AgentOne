from django.apps import AppConfig
import sys

class ToolsBuiltinMemoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.builtin_memory'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt import Prompt
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .memory_tool import MemoryTool
            from .prompts import PROMPTS, TOOLS, TRACKS

            ToolDefinition.objects.get_or_create(
                name='memory',
                defaults={
                    'display_name': 'Memory Management',
                    'description': MemoryTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )
            for prompt in PROMPTS:
                Prompt.get_or_create_template(owner=None, source=self.name, key=prompt["name"], value=prompt["template"])
            
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in TOOLS.items()])
            Prompt.get_or_create_template(owner=None, source=self.name, key="functions", value=function_python_string)

            for trackname, trackitem in TRACKS.items():
                header = f'## {trackname} - {trackitem["description"]}\n'
                Prompt.get_or_create_template(owner=None, source=self.name, key=f"content_header.{trackname}", value=header)

                for layername, layerdescription in trackitem['layers'].items():
                    header = f'### {trackname} {layername} - {layerdescription}\n'
                    Prompt.get_or_create_template(owner=None, source=self.name, key=f"content_header.{trackname}.{layername}", value=header)
