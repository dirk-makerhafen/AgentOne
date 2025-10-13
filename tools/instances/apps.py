from django.apps import AppConfig


class ToolsInstancesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tools.instances"

    def ready(self):
        # Import signals to ensure they are connected when the app is ready.
        from . import signals
