# Backfill ApiProvider.is_local for providers pointing at a loopback address.
# Local providers (e.g. Ollama, OMLX) are classified here so the settings
# page can split providers into "Local providers" and "Cloud" sections.

from urllib.parse import urlparse

from django.db import migrations


def _is_loopback_url(url):
    try:
        host = urlparse(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    host = host.lower().rstrip(".")
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.startswith("127.")


def backfill_is_local(apps, schema_editor):
    ApiProvider = apps.get_model("server", "ApiProvider")
    for provider in ApiProvider.objects.all():
        if _is_loopback_url(provider.url):
            provider.is_local = True
            provider.save(update_fields=["is_local"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0110_apiprovider_is_local"),
    ]

    operations = [
        migrations.RunPython(backfill_is_local, noop),
    ]
