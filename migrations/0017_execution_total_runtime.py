# pylint: skip-file
# Generated by Django 4.2.13 on 2024-07-19 18:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quicksilver', '0016_auto_20230411_1937'),
    ]

    operations = [
        migrations.AddField(
            model_name='execution',
            name='total_runtime',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
