# pylint: skip-file
# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-05-14 22:10


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quicksilver', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='next_run',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
