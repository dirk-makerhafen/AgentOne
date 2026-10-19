from django.db import migrations, models


def _backfill_message_type(apps, schema_editor):
    """Classify existing messages from their role + parts.

    ``source`` was never populated (always ``default``), so the mapping is
    inferred: a ``COMPACTION`` part marks a compaction boundary; then role
    drives info / assistant / tool; every remaining row is user chat.
    Bootstrap / system_notice / reflection are indistinguishable
    retroactively and land on ``user_chat``.
    """
    Message = apps.get_model("server", "Message")
    MessagePart = apps.get_model("server", "MessagePart")
    db = schema_editor.connection.alias

    compaction_ids = (
        MessagePart.objects.using(db)
        .filter(type="COMPACTION")
        .values_list("message_id", flat=True)
        .distinct()
    )
    Message.objects.using(db).filter(pk__in=list(compaction_ids)).update(
        message_type="compaction"
    )
    Message.objects.using(db).filter(role="info").update(message_type="info")
    Message.objects.using(db).filter(role="assistant").update(
        message_type="assistant_message"
    )
    Message.objects.using(db).filter(role="tool").update(
        message_type="tool_response"
    )
    Message.objects.using(db).filter(message_type="default").update(
        message_type="user_chat"
    )


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0150_remove_project_path'),
    ]

    operations = [
        migrations.RenameField(
            model_name='message',
            old_name='source',
            new_name='message_type',
        ),
        migrations.AlterField(
            model_name='message',
            name='message_type',
            field=models.CharField(choices=[('default', 'Default'), ('user_chat', 'User Chat'), ('assistant_message', 'Assistant Message'), ('tool_response', 'Tool Response'), ('system_notice', 'System Notice'), ('compaction', 'Compaction'), ('reflection', 'Reflection'), ('info', 'Info'), ('bootstrap', 'Bootstrap')], default='default', max_length=61),
        ),
        migrations.RunPython(_backfill_message_type, _noop),
    ]
