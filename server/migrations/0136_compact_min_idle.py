from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0135_agentversionmodel_visibility'),
    ]

    operations = [
        migrations.RenameField(
            model_name='settingsmodel',
            old_name='auto_compact_limit',
            new_name='auto_compact_max_tokens',
        ),
        migrations.AddField(
            model_name='settingsmodel',
            name='auto_compact_min_tokens',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='settingsmodel',
            name='auto_compact_idle_seconds',
            field=models.IntegerField(blank=True, default=None, null=True),
        ),
    ]
