"""
Add ``session`` FK to Message, backfilling existing rows from
``session_version.session``.

Same pattern as 0100: add the column as nullable, backfill it from the
corresponding ``session_version`` relationship, then alter to non-nullable.
"""

from django.db import migrations, models
import django.db.models.deletion


def backfill_session_from_session_version(apps, schema_editor):
    """Set ``Message.session = Message.session_version.session`` for existing rows."""
    Message = apps.get_model("server", "Message")
    for instance in Message.objects.filter(session__isnull=True).select_related(
        "session_version__session"
    ).iterator():
        session = instance.session_version.session
        if session is not None:
            Message.objects.filter(pk=instance.pk).update(session=session)


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0100_add_session_fks_backfill"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="session",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_messages",
                to="server.sessionmodel",
            ),
        ),
        migrations.RunPython(
            backfill_session_from_session_version,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="message",
            name="session",
            field=models.ForeignKey(
                null=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="related_messages",
                to="server.sessionmodel",
            ),
        ),
    ]
