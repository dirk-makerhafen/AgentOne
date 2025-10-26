from django.apps import AppConfig
import sys

class ToolsBuiltinKvStorageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.builtin_kv_storage'

    def ready(self):
        # We only want to run this code outside of migration operations
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt_string import Prompt
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .kv_storage_tool import KVStorageTool # Corrected class name here
            from .prompts import TOOLS, PROMPTS

            # Register the kv_storage tool
            ToolDefinition.objects.get_or_create(
                name='kv_storage',
                defaults={
                    'display_name': 'Key-Value Storage',
                    'description': KVStorageTool.DESCRIPTION, # Use the DESCRIPTION from the class
                    'is_builtin': True,
                    'is_active': True,
                }
            )

            # Register specific prompts for kv_storage (PROMPTS is empty, so this loop won't run but is kept for consistency)
            # Register specific prompts for kv_storage (PROMPTS now includes "Instructions")
            for prompt in PROMPTS:
                Prompt.get_or_create_template(owner=None, source=self.name, key=prompt["name"], value=prompt["template"])
            
            # Generate and register function stubs for kv_storage
            function_python_string = "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in TOOLS.items()])
            Prompt.get_or_create_template(owner=None, source=self.name, key="functions", value=function_python_string)
