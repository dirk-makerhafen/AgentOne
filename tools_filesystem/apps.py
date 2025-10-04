from django.apps import AppConfig
import sys

class Tools_Filesystem_Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_filesystem'

    def ready(self):
        # Only run this code if not during a migration or initial Django setup
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_filesystem.prompts import INSTRUCTIONS, FUNCTIONS, CONTENT_INJECTION
            from tools_filesystem.filesystem import FilesystemTool
            from tools_common.models  import ToolDefinition # Import ToolDefinition

            # Register the ToolDefinition for the filesystem tool
            ToolDefinition.objects.get_or_create(
                name='filesystem',
                defaults={
                    'display_name': 'Filesystem',
                    'description': FilesystemTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            # Register prompts
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source="Tools.Filesystem", key="Instructions", value=INSTRUCTIONS)
            PromptString.objects.get_or_create(owner=None, source="Tools.Filesystem", key="ContentInjection", value=CONTENT_INJECTION)
            PromptString.objects.get_or_create(owner=None, source="Tools.Filesystem", key="Functions", value=function_python_string)


