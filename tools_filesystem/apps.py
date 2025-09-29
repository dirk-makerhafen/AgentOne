from django.apps import AppConfig
import sys

class Tools_Filesystem_Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_filesystem'

    def ready(self):
        if not 'manage.py' in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_filesystem.prompts import DESCRIPTION, FUNCTIONS, CONTENT_INJECTION
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source="Tools.Filesystem", key="Description", value=DESCRIPTION)
            PromptString.objects.get_or_create(owner=None, source="Tools.Filesystem", key="ContentInjection", value=CONTENT_INJECTION)
            PromptString.objects.get_or_create(owner=None, source="Tools.Filesystem", key="Functions", value=function_python_string)

