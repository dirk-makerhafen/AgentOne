from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0154_alter_agentversionmodel_visibility'),
    ]

    operations = [
        migrations.RenameField(
            model_name='project',
            old_name='manifest_dir',
            new_name='agentone_dir',
        ),
        migrations.RenameField(
            model_name='workspacemodel',
            old_name='manifest_dir',
            new_name='agentone_dir',
        ),
    ]