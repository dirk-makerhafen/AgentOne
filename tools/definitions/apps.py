from django.apps import AppConfig

class DefinitionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools.definitions'

    def ready(self):
        from . import signals
