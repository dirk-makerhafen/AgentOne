from django.apps import AppConfig
import sys

class ToolsBuiltinSubagentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.builtin_subagents'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            from core.models.prompt import Prompt
            from tools.base.utils import generate_function_stub
            from tools.definitions.models.tool_definition import ToolDefinition
            from .subagents_tool import SubAgentTool # Corrected import
            from .prompts import TOOLS, PROMPTS

            ToolDefinition.objects.get_or_create(
                name='subagent_tool', # Name should match BUILTIN_TOOL_CLASS_MAP key
                defaults={
                    'display_name': 'Sub-agent Management Tool',
                    'description': SubAgentTool.DESCRIPTION,
                    'is_builtin': True,
                    'is_active': True,
                }
            )
            for prompt_dict in PROMPTS: # Corrected iteration
                Prompt.get_or_create_template(owner=None, source=self.name, key=prompt_dict["name"], value=prompt_dict["template"])
            
            # Generate and save the functions prompt
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in TOOLS.items()])
            Prompt.get_or_create_template(owner=None, source=self.name, key="functions", value=function_python_string)
