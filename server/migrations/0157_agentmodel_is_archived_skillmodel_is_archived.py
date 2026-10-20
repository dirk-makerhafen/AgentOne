from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0156_alter_workspacemodel_agentone_dir_blank'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentmodel',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='skillmodel',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
    ]
