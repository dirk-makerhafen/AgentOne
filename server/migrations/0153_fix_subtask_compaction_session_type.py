from django.db import migrations, models


def _fix_compaction_type(apps, schema_editor):
    """Rewrite the typo'd ``subtask_compaczt`` session type to ``subtask_compaction``."""
    SessionModel = apps.get_model("server", "SessionModel")
    SessionModel.objects.using(schema_editor.connection.alias).filter(
        session_type="subtask_compaczt"
    ).update(session_type="subtask_compaction")


def _revert_compaction_type(apps, schema_editor):
    """Reverse of :func:`_fix_compaction_type`."""
    SessionModel = apps.get_model("server", "SessionModel")
    SessionModel.objects.using(schema_editor.connection.alias).filter(
        session_type="subtask_compaction"
    ).update(session_type="subtask_compaczt")


class Migration(migrations.Migration):
    """Fix the ``SUBTASK_COMPACT`` ``SessionType`` value typo.

    The enum shipped as ``subtask_compaczt``; the choices label is corrected
    here and existing session rows are rewritten.
    """

    dependencies = [
        ("server", "0152_delete_sessionhookrun"),
    ]

    operations = [
        migrations.RunPython(_fix_compaction_type, _revert_compaction_type),
        migrations.AlterField(
            model_name="sessionmodel",
            name="session_type",
            field=models.CharField(
                choices=[
                    ("session", "Session"),
                    ("subsession", "Subsession"),
                    ("subtask_delegate", "Subtask (delegate)"),
                    ("subtask_fork", "Subtask (fork)"),
                    ("subtask_compaction", "Subtask (session compaction)"),
                    ("subtask_hook", "Subtask (hook)"),
                ],
                default="session",
                max_length=30,
            ),
        ),
    ]
