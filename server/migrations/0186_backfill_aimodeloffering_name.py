"""Backfill ``AiModelOffering.name`` from the linked raw model.

0181 split the old AiModel table into a raw model plus a provider-specific
offering and removed the offering's ``name`` column.  0183 re-added the column
with an empty default but never populated it, so offerings created before the
split (typically local/custom providers) have a blank name.  The model picker
and the fallback helper group by that name, which leaves those rows invisible.

The raw model still carries the canonical name, so copy it across.
"""
from django.db import migrations


def backfill_name(apps, schema_editor):
    Offering = apps.get_model("server", "AiModelOffering")
    rows = []
    for offering in Offering.objects.filter(name="", model__isnull=False).iterator():
        offering.name = offering.model.name
        rows.append(offering)
        if len(rows) >= 500:
            Offering.objects.bulk_update(rows, ["name"])
            rows = []
    if rows:
        Offering.objects.bulk_update(rows, ["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0185_apiprovider_is_custom"),
    ]

    operations = [
        migrations.RunPython(backfill_name, migrations.RunPython.noop),
    ]
