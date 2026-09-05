"""Session todo list fields on SettingsModel."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0121_delete_historylimitingrule"),
    ]

    operations = [
        migrations.AddField(
            model_name="settingsmodel",
            name="todo_auto_process",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
