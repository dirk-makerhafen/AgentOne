from django.db import migrations, models
import dirtyfields.dirtyfields
import django.db.models.deletion


def backfill_existing_global_task_definitions(apps, schema_editor):
    ScriptsGeneration = apps.get_model("server", "ScriptsGeneration")
    TaskDefinition = apps.get_model("server", "TaskDefinition")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # Find global TaskDefinitions (no parent agent/skill/project)
    global_tds = list(
        TaskDefinition.objects.filter(
            parent_agent__isnull=True,
            parent_project__isnull=True,
            parent_skill__isnull=True,
            parent_generation__isnull=True,
        )
    )
    if not global_tds:
        return

    # Create a single ScriptsGeneration for all pre-existing global tasks
    gen = ScriptsGeneration.objects.create(commit="pre-migration")
    TaskDefinition.objects.filter(
        pk__in=[td.pk for td in global_tds]
    ).update(parent_generation=gen)


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0084_alter_workspacemodel_name_alter_workspacemodel_path'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScriptsGeneration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raw_data', models.TextField(blank=True, default='', max_length=104857600)),
                ('commit', models.CharField(default='', max_length=1024)),
                ('fork_of', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forks', to='server.scriptsgeneration')),
                ('raw_data_reference', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data_references', to='server.scriptsgeneration')),
            ],
            options={
                'verbose_name': 'Scripts Generation',
                'verbose_name_plural': 'Scripts Generations',
                'ordering': ['-created_at'],
            },
            bases=(dirtyfields.dirtyfields.DirtyFieldsMixin, models.Model),
        ),
        migrations.AddField(
            model_name='taskdefinition',
            name='parent_generation',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='related_task_definitions', to='server.scriptsgeneration'),
        ),
        migrations.RunPython(
            backfill_existing_global_task_definitions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
