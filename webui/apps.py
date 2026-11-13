from django.apps import AppConfig


class WebuiConfig(AppConfig):
    """Server-rendered htmx UI (parallel to the legacy pyHtmlGui UI)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "webui"
    verbose_name = "htmx UI"
