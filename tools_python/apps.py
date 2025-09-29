from django.apps import AppConfig
import sys

class Tools_Python(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools_python'

    def ready(self):
        if not 'manage.py' in sys.argv:
            from common.models import PromptString
            from tools_common.tool_parser import generate_function_stub
            from tools_python.prompts import DESCRIPTION, FUNCTIONS, LIST_OF_SHARED_VARS
            function_python_string =  "\n".join([f"{generate_function_stub(fname, fdef)}\n" for fname, fdef in FUNCTIONS.items()])
            PromptString.objects.get_or_create(owner=None, source="Tools.Python", key="Description", value=DESCRIPTION)
            PromptString.objects.get_or_create(owner=None, source="Tools.Python", key="Functions", value=function_python_string)
            PromptString.objects.get_or_create(owner=None, source="Tools.Python", key="SharedVarsInjection", value=LIST_OF_SHARED_VARS)

