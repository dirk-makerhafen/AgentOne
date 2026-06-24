"""Rename billion_parameters → total_parameters, add active_parameters & quantization."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0079_aimodel_open_weights_aimodel_self_hosted_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="aimodel",
            old_name="billion_parameters",
            new_name="total_parameters",
        ),
        migrations.AddField(
            model_name="aimodel",
            name="active_parameters",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="aimodel",
            name="quantization",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
