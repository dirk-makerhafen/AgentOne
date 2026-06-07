"""Remove NamedPipe and NamedPipeSubscription models (superseded by DataCollection)."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0074_datacollection_collectionitem"),
    ]

    operations = [
        migrations.DeleteModel(
            name="NamedPipeSubscription",
        ),
        migrations.DeleteModel(
            name="NamedPipe",
        ),
    ]
