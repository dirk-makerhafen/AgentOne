from django.apps import AppConfig
import sys

class ToolsBuildinMemoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.buildin_memory'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt_string import PromptString
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .memory_tool import MemoryTool
            from .prompts import INSTRUCTIONS, CONTENT, CONTENT_HEADER, FUNCTIONS, STALLED_WARNING, TRACKS

            ToolDefinition.objects.get_or_create(
                name='memory',
                defaults={
                    'display_name': 'Memory Management',
                    'description': MemoryTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="StalledWarning", value=STALLED_WARNING)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="ContentHeader", value=CONTENT_HEADER)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Content", value=CONTENT)
            PromptString.objects.get_or_create(owner=None, source=self.name, key="Functions", value=function_python_string)

            for trackname, trackitem in TRACKS.items():
                header = f'## {trackname} - {trackitem["description"]}\n'
                PromptString.objects.get_or_create(owner=None, source=self.name, key=f"ContentHeader.{trackname}", value=header)

                for layername, layerdescription in trackitem['layers'].items():
                    header = f'### {trackname} {layername} - {layerdescription}\n'
                    PromptString.objects.get_or_create(owner=None, source=self.name, key=f"ContentHeader.{trackname}.{layername}", value=header)
