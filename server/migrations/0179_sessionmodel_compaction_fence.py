from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('server', '0178_sessionmodel_name_is_auto'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionmodel',
            name='is_compacting',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='sessionmodel',
            name='compacting_call_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='sessionmodel',
            name='compacting_root_task_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
