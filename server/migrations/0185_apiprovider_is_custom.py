from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0184_apikey_budget"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiprovider",
            name="is_custom",
            field=models.BooleanField(default=False),
        ),
    ]
