# pylint: skip-file
# Generated by Django 2.2.24 on 2021-09-21 17:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quicksilver', '0009_execution_postpone_alert_until'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='execution',
            name='postpone_alert_until',
        ),
        migrations.AddField(
            model_name='task',
            name='postpone_alert_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
