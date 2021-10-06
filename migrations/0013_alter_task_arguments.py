# pylint: skip-file
# Generated by Django 3.2.7 on 2021-10-06 15:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quicksilver', '0012_merge_20210930_2209'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='arguments',
            field=models.TextField(default='--no-color', help_text='One argument per line', max_length=1048576),
        ),
    ]
