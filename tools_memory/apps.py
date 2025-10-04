from django.apps import AppConfig
import sys

class Tools_Memory(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_memory'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_memory.prompts import INSTRUCTIONS, FUNCTIONS, STALLED_WARNING, CONTENT_HEADER, CONTENT, TRACKS
            from tools_memory.memory import SMLMemoryTool
            from tools_common.models  import ToolDefinition # Import ToolDefinition

            # Register the ToolDefinition for the Memory tool
            ToolDefinition.objects.get_or_create(
                name='memory',
                defaults={
                    'display_name': 'Memory Management',
                    'description': SMLMemoryTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            # Register prompts
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key="StalledWarning", value=STALLED_WARNING)
            PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key="ContentHeader", value=CONTENT_HEADER)
            PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key="Content", value=CONTENT)
            PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key="Functions", value=function_python_string)

            for trackname, trackitem in TRACKS.items():
                header = f'## {trackname} - {trackitem["description"]}\n'
                PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key=f"ContentHeader.{trackname}", value=header)

                for layername, layerdescription in trackitem['layers'].items():
                    header = f'### {trackname} {layername} - {layerdescription}\n'
                    PromptString.objects.get_or_create(owner=None, source="Tools.Memory", key=f"ContentHeader.{trackname}.{layername}", value=header)


