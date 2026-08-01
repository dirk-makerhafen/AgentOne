# Data migration: rename WAITING_SUBTASK -> WAITING_SUBTASKS_OR_HOOKS
# in existing AgentTaskCall.status_detail rows.

from django.db import migrations


def rename_old_subtask_status(apps, schema_editor):
    AgentTaskCall = apps.get_model("server", "AgentTaskCall")
    updated = AgentTaskCall.objects.filter(
        status_detail="WAITING_SUBTASK"
    ).update(status_detail="WAITING_SUBTASKS_OR_HOOKS")
    if updated:
        print(f"[migration 0099] renamed {updated} AgentTaskCall(s) "
              f"status_detail WAITING_SUBTASK -> WAITING_SUBTASKS_OR_HOOKS")


def revert(apps, schema_editor):
    AgentTaskCall = apps.get_model("server", "AgentTaskCall")
    AgentTaskCall.objects.filter(
        status_detail="WAITING_SUBTASKS_OR_HOOKS"
    ).update(status_detail="WAITING_SUBTASK")


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0098_alter_agenttaskcall_status_detail"),
    ]

    operations = [
        migrations.RunPython(rename_old_subtask_status, revert),
    ]
