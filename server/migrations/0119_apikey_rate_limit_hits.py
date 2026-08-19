from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0118_apikey_rate_limit_until"),
    ]

    operations = [
        migrations.AddField(
            model_name="apikey",
            name="rate_limit_hits",
            field=models.IntegerField(default=0),
        ),
    ]
