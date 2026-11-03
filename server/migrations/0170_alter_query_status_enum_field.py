# Align Query.status with its model definition.
#
# 0168 was written by hand and left the column as a plain CharField; the model
# uses django_enum's EnumCharField.  No data change is involved (the longest
# choice, RATE_LIMITED, is 12 characters).

import django_enum.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0169_model_health_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='query',
            name='status',
            field=django_enum.fields.EnumCharField(choices=[('ACTIVE', 'Active'), ('WAITING', 'Waiting (System Blocked)'), ('SUCCESS', 'Success (Terminal)'), ('FAILURE', 'Failure (Terminal)'), ('RATE_LIMITED', 'Rate Limited (Terminal)')], db_index=True, default='WAITING', max_length=12),
        ),
    ]
