from __future__ import print_function
# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import datetime
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock
from ...models import Task

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

class Command(BaseCommand):
    help = 'Starts Quicksilver execution process.'

    def add_arguments(self, parser):
        parser.add_argument('--task-queue', default='default')
        parser.add_argument('--sleep-duration', type=int, default=5)
        parser.add_argument('--restart-after', type=int, default=30)

    @handle_lock
    def handle(self, *args, **options):
        queue_started = timezone.now()

        try:
            for task in Task.objects.filter(queue=options.get('task_queue')):
                for execution in task.executions.filter(status='ongoing'):
                    execution.kill_if_stuck(queue_started)

            when_stop = timezone.now() + datetime.timedelta(seconds=(options.get('restart_after') * 60)) # pylint: disable=superfluous-parens

            cycle_sleep = 5

            try:
                cycle_sleep = settings.QUICKSILVER_MIN_CYCLE_SLEEP_SECONDS
            except AttributeError:
                pass

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

                if wake_next > cycle_sleep:
                    time.sleep(wake_next)
                else:
                    time.sleep(cycle_sleep)

        except KeyboardInterrupt:
            logger.info('Exiting queue "%s" due to keyboard interruption...', options.get('task_queue'))
