# pylint: skip-file
# Generated by Django 3.2.18 on 2023-04-12 00:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quicksilver', '0015_alter_task_arguments'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='max_duration',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='execution',
            name='status',
            field=models.CharField(choices=[('success', 'Successful'), ('error', 'Error'), ('killed', 'Killed (Stuck)'), ('pending', 'Pending'), ('ongoing', 'Ongoing')], default='pending', max_length=64),
        ),
    ]
