"""Strict call-time tool allowlist on SettingsModel (execution gate, not advertisement)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0123_alter_sessionmodel_session_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='settingsmodel',
            name='tool_call_allowlist',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
