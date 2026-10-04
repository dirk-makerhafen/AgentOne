from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0133_settingsmodel_guidance_files'),
    ]

    operations = [
        migrations.RenameField(
            model_name='settingsmodel',
            old_name='compact_size_limit',
            new_name='auto_compact_keep_percent',
        ),
    ]
