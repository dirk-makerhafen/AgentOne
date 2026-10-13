# Generated for soft session pause on 2026-10-13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0146_project_git_ref_project_git_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionmodel',
            name='is_paused',
            field=models.BooleanField(default=False),
        ),
    ]
