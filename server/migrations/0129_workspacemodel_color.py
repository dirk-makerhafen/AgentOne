import random

import server.models.workspace
from django.db import migrations, models


def backfill_workspace_colors(apps, schema_editor):
    WorkspaceModel = apps.get_model("server", "WorkspaceModel")
    palette = server.models.workspace.WORKSPACE_COLOR_PALETTE
    for ws in WorkspaceModel.objects.all():
        if not ws.color:
            ws.color = random.choice(palette)
            ws.save(update_fields=["color"])


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0128_taskinstance_dedupe_hash_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspacemodel',
            name='color',
            field=models.CharField(default=server.models.workspace.random_workspace_color, help_text='Workspace accent color as a #rrggbb hex string.', max_length=7),
        ),
        migrations.RunPython(backfill_workspace_colors, migrations.RunPython.noop),
    ]
