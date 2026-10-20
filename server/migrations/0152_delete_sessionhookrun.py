from django.db import migrations


class Migration(migrations.Migration):
    """Drop the lifecycle session-hook run table.

    Lifecycle hooks (``on: stop|pre_compact|post_compact|session_end``) were
    replaced by per-call intercept hooks; session end is now the
    ``session_end`` task. ``SessionHookRun`` (audit rows for the old detached
    forks) has no remaining references.
    """

    dependencies = [
        ("server", "0151_message_type"),
    ]

    operations = [
        migrations.DeleteModel(name="SessionHookRun"),
    ]
