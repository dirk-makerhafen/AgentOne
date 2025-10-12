from django.apps import AppConfig

class SystemsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'systems'

    def ready(self):
        # Import signals to ensure they are connected when the app is ready.
        from . import signals
