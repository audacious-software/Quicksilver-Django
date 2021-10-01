from __future__ import print_function
# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import datetime
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock
from ...models import Task

class Command(BaseCommand):
    help = 'Starts Quicksilver execution process.'

    def add_arguments(self, parser):
        parser.add_argument('--task-queue', default='default')
        parser.add_argument('--sleep-duration', type=int, default=5)
        parser.add_argument('--restart-after', type=int, default=30)

    @handle_lock
    def handle(self, *args, **options):
        try:
            when_stop = timezone.now() + datetime.timedelta(seconds=(options.get('restart_after') * 60))

            while timezone.now() < when_stop:
                loop_start = timezone.now()

                overdue_tasks = []

                for overdue in Task.objects.exclude(next_run=None).filter(next_run__lte=timezone.now(), queue=options.get('task_queue')).order_by('next_run'):
                    if overdue.is_running() is False:
                        overdue_tasks.append(overdue)
                    elif overdue.should_alert():
                        overdue.alert()

                for task in overdue_tasks:
                    task.run()

                elapsed = (timezone.now() - loop_start).total_seconds()

                wake_next = options.get('sleep_duration') - elapsed

                if wake_next > 0:
                    time.sleep(wake_next)

        except KeyboardInterrupt:
            print('Exiting queue "' + options.get('task_queue') + '" due to keyboard interruption...')
