# pylint: skip-file
# Generated by Django 2.2.24 on 2021-09-21 16:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quicksilver', '0007_auto_20210616_1046'),
    ]

    operations = [
        migrations.AlterField(
            model_name='execution',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='task',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
