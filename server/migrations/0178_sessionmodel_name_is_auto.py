from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('server', '0177_debuglogentry_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionmodel',
            name='name_is_auto',
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]
