from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0155_rename_project_workspace_manifest_dir_to_agentone_dir'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workspacemodel',
            name='agentone_dir',
            field=models.CharField(blank=False, default='', max_length=4096),
        ),
    ]