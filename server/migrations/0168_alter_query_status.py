# Generated manually to add RATE_LIMITED to QueryStatus choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0167_alter_sessionmodel_session_type'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='query',
            name='server_Query_status_QueryStatus',
        ),
        migrations.AlterField(
            model_name='query',
            name='status',
            field=models.CharField(
                choices=[
                    ('ACTIVE', 'Active'),
                    ('WAITING', 'Waiting (System Blocked)'),
                    ('SUCCESS', 'Success (Terminal)'),
                    ('FAILURE', 'Failure (Terminal)'),
                    ('RATE_LIMITED', 'Rate Limited (Terminal)'),
                ],
                db_index=True,
                max_length=14,
            ),
        ),
        migrations.AddConstraint(
            model_name='query',
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=['ACTIVE', 'WAITING', 'SUCCESS', 'FAILURE', 'RATE_LIMITED']),
                name='server_Query_status_QueryStatus',
            ),
        ),
    ]
