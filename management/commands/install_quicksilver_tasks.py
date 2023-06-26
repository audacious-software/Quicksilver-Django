# pylint: disable=no-member, line-too-long

from __future__ import print_function

import importlib

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from quicksilver.models import Task

class Command(BaseCommand):
    help = 'Installs necessary Quicksilver tasks for dialogs to function properly.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        tasks = []

        for app in settings.INSTALLED_APPS:
            try:
                app_module = importlib.import_module('.quicksilver_api', package=app)

                custom_tasks = app_module.quicksilver_tasks()

                tasks.extend(custom_tasks)
            except ImportError:
                pass
            except AttributeError:
                pass

        for task in tasks:
            if Task.objects.filter(command=task[0]).count() == 0:
                task_obj = Task.objects.create(command=task[0], arguments=task[1], repeat_interval=task[2], next_run=timezone.now())

                if len(task) > 3:
                    task_obj.queue = task[3]
                    task_obj.save()

                print('Installed ' + str(task) + '...')
