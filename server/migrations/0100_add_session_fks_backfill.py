"""
Add ``session`` FKs to Query/Response/AgentTaskRun and ``parent_session`` to
SessionVersionModel, backfilling existing rows from ``session_version.session``.

The new FK columns are non-nullable in the models, but adding a non-nullable
column to populated tables requires a one-off default.  We therefore add each
column as nullable, backfill it from the corresponding ``session_version``
relationship, then alter the column to non-nullable.
"""

from django.db import migrations, models
import django.db.models.deletion


def backfill_session_from_session_version(apps, schema_editor):
    """Set ``<model>.session = <model>.session_version.session`` for existing rows."""
    for model_name in ("Query", "Response", "AgentTaskRun"):
        model = apps.get_model("server", model_name)
        for instance in model.objects.filter(session__isnull=True).select_related(
            "session_version__session"
        ).iterator():
            session = instance.session_version.session
            if session is not None:
                model.objects.filter(pk=instance.pk).update(session=session)


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0099_rename_agenttaskcall_old_subtask_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="session",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_queries",
                to="server.sessionmodel",
            ),
        ),
        migrations.AddField(
            model_name="response",
            name="session",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_response",
                to="server.sessionmodel",
            ),
        ),
        migrations.AddField(
            model_name="agenttaskrun",
            name="session",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_task_runs",
                to="server.sessionmodel",
            ),
        ),
        migrations.AddField(
            model_name="sessionversionmodel",
            name="parent_session",
            field=models.ForeignKey(
                default=None,
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_child_session_versions",
                to="server.sessionmodel",
            ),
        ),
        migrations.RunPython(
            backfill_session_from_session_version,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="query",
            name="session",
            field=models.ForeignKey(
                null=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_queries",
                to="server.sessionmodel",
            ),
        ),
        migrations.AlterField(
            model_name="response",
            name="session",
            field=models.ForeignKey(
                null=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_response",
                to="server.sessionmodel",
            ),
        ),
        migrations.AlterField(
            model_name="agenttaskrun",
            name="session",
            field=models.ForeignKey(
                null=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_task_runs",
                to="server.sessionmodel",
            ),
        ),
    ]
