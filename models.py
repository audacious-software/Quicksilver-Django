# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
import importlib
import io
import logging
import signal
import sys
import traceback

import arrow
import numpy

from six import python_2_unicode_compatible

from django.conf import settings
from django.core.checks import Warning, register # pylint: disable=redefined-builtin
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.db import models
from django.db.utils import ProgrammingError, OperationalError
from django.template.loader import render_to_string
from django.utils import timezone

RUN_STATUSES = (
    ('success', 'Successful',),
    ('error', 'Error',),
    ('killed', 'Killed (Stuck)',),
    ('pending', 'Pending',),
    ('ongoing', 'Ongoing',),
)

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

class ExecutionTimeoutError(Exception):
    pass

class ExecutionTimeout: # pylint: disable=old-style-class
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame): # pylint: disable=unused-argument
        raise ExecutionTimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback): # pylint: disable=redefined-builtin, redefined-outer-name
        signal.alarm(0)

@register()
def check_all_quicksilver_tasks_installed(app_configs, **kwargs): # pylint: disable=unused-argument, invalid-name
    errors = []

    try: # pylint: disable=too-many-nested-blocks
        if 'quicksilver.W001' in settings.SILENCED_SYSTEM_CHECKS:
            return errors

        for app in settings.INSTALLED_APPS:
            try:
                app_module = importlib.import_module('.quicksilver_api', package=app)

                custom_tasks = app_module.quicksilver_tasks()

                for task in custom_tasks:
                    if Task.objects.filter(command=task[0]).count() == 0:
                        warning_id = 'quicksilver.%s.%s.W001' % (app, task[0])

                        if (warning_id in settings.SILENCED_SYSTEM_CHECKS) is False:
                            warning = Warning('Quicksilver task "%s.%s" is not installed' % (app, task[0]), hint='Run "install_quicksilver_tasks" command to install or add "%s" to SILENCED_SYSTEM_CHECKS.' % warning_id, obj=None, id=warning_id) # pylint: disable=consider-using-f-string

                            errors.append(warning)
            except ImportError:
                pass
            except AttributeError:
                pass

    except ProgrammingError: # Tables not yet created
        pass
    except OperationalError: # Tables not yet created
        pass

    return errors

@register()
def check_quicksilver_lock_dir_defined(app_configs, **kwargs): # pylint: disable=unused-argument, invalid-name
    errors = []

    if hasattr(settings, 'QUICKSILVER_LOCK_DIR') is False:
        warning = Warning('QUICKSILVER_LOCK_DIR is not set.', hint='Define QUICKSILVER_LOCK_DIR (e.g. "QUICKSILVER_LOCK_DIR = tempfile.gettempdir()") in the settings to set the lock directory or add "quicksilver.W002" to SILENCED_SYSTEM_CHECKS.', obj=None, id='quicksilver.W002')

        errors.append(warning)

    return errors

class QuicksilverIO(io.BytesIO, object): # pylint: disable=too-few-public-methods, useless-object-inheritance
    def __init__(self): # pylint: disable=useless-super-delegation
        super(QuicksilverIO, self).__init__() # pylint: disable=super-with-arguments

    def write(self, value): # pylint: disable=useless-super-delegation, arguments-differ
        super(QuicksilverIO, self).write(value.encode()) # pylint: disable=super-with-arguments

@python_2_unicode_compatible
class Task(models.Model):
    class Meta: # pylint: disable=too-few-public-methods, old-style-class, no-init
        permissions = (
            ('access_module', 'Access Quicksilver components'),
        )

    command = models.CharField(max_length=4096, db_index=True)
    arguments = models.TextField(max_length=1048576, help_text='One argument per line', null=True, blank=True)
    queue = models.CharField(max_length=128, default='default')

    repeat_interval = models.IntegerField(default=0)
    max_duration = models.IntegerField(null=True, blank=True)

    next_run = models.DateTimeField(null=True, blank=True)

    postpone_alert_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        description = '%s[%s]' % (self.command, self.queue)

        if self.arguments.splitlines:
            description = '%s %s' % (description, ' '.join(self.arguments.splitlines()))

        return description

    def run(self):
        execution = Execution.objects.create(task=self, started=timezone.now())

        execution.run()

    def is_running(self):
        return self.executions.filter(status='ongoing').count() > 0

    def runtime_outlier_threshold(self, stddevs=2):
        runtimes = []

        for execution in self.executions.exclude(ended=None):
            runtimes.append(execution.runtime())

        if len(runtimes) > 5:
            runtime_std = numpy.std(runtimes)
            runtime_mean = numpy.mean(runtimes)

            return runtime_mean + (stddevs * runtime_std)

        return None

    def should_alert(self): # pylint: disable=too-many-return-statements,too-many-branches
        now = timezone.now()

        if self.postpone_alert_until is not None and now < self.postpone_alert_until:
            return False

        open_execution = self.executions.filter(ended=None).order_by('started').first()
        outlier_threshold = self.runtime_outlier_threshold()

        if open_execution is not None:
            runtime = open_execution.runtime()

            if outlier_threshold is not None:
                if open_execution.runtime() > outlier_threshold:
                    return True

                if self.executions.exclude(ended=None).count() < 2:
                    return True

            alert_seconds = 60

            try:
                alert_seconds = settings.QUICKSILVER_MIN_TASK_ALERT_RUNTIME_SECONDS
            except AttributeError:
                pass

            if runtime < alert_seconds:
                return False

            try:
                if runtime > settings.QUICKSILVER_MAX_TASK_RUNTIME_SECONDS:
                    return True
            except AttributeError:
                pass
        elif self.next_run is not None:
            extra_overdue_seconds = 120

            try:
                extra_overdue_seconds = settings.QUICKSILVER_MIN_TASK_ALERT_OVERDUE_SECONDS
            except AttributeError:
                pass

            if (self.next_run + datetime.timedelta(seconds=extra_overdue_seconds)) < now:
                other_tasks = Task.objects.filter(queue=self.queue).exclude(pk=self.pk)

                others_running = False

                for task in other_tasks:
                    if task.is_running():
                        others_running = True

                if others_running is False:
                    return True

        return False

    def alert(self): # pylint: disable=too-many-locals
        now = timezone.now()

        alerted = False

        runtimes = []

        for execution in self.executions.exclude(ended=None):
            runtimes.append(execution.runtime())

        runtime_std = -1
        runtime_mean = -1

        if runtimes:
            runtime_std = numpy.std(runtimes)
            runtime_mean = numpy.mean(runtimes)

        host = settings.ALLOWED_HOSTS[0]

        admins = [admin[1] for admin in settings.ADMINS]

        open_execution = self.executions.filter(ended=None).order_by('started').first()

        if open_execution is not None:
            if open_execution.runtime() > 10:
                context = {
                    'task': self,
                    'execution': open_execution,
                    'runtime_mean': runtime_mean,
                    'runtime_std': runtime_std,
                    'host': host,
                    'completed': self.executions.exclude(ended=None).count()
                }

                message = render_to_string('quicksilver_task_alert_message.txt', context)
                subject = render_to_string('quicksilver_task_alert_subject.txt', context)

                from_addr = 'quicksilver@' + host

                email = EmailMessage(subject, message, from_addr, admins, headers={'Reply-To': admins[0]})
                email.send()

                alerted = True
        elif self.next_run is not None and self.next_run < now:
            context = {
                'task': self,
                'host': host,
                'scheduled': self.next_run,
            }

            message = render_to_string('quicksilver_task_overdue_alert_message.txt', context)
            subject = render_to_string('quicksilver_task_overdue_alert_subject.txt', context)

            from_addr = 'quicksilver@' + host

            email = EmailMessage(subject, message, from_addr, admins, headers={'Reply-To': admins[0]})
            email.send()

            alerted = True

        if alerted:
            postpone_interval = 15 * 60

            try:
                postpone_interval = settings.QUICKSILVER_ALERT_INTERVAL
            except AttributeError:
                pass

            self.postpone_alert_until = now + datetime.timedelta(seconds=postpone_interval)
            self.save()

    def get_max_duration(self):
        max_duration = self.max_duration

        if max_duration is None:
            try:
                max_duration = settings.QUICKSILVER_MAX_TASK_DURATION_SECONDS
            except AttributeError:
                pass

        return max_duration

@python_2_unicode_compatible
class Execution(models.Model):
    task = models.ForeignKey(Task, related_name='executions', on_delete=models.CASCADE)

    started = models.DateTimeField()
    ended = models.DateTimeField(null=True, blank=True)
    output = models.TextField(max_length=1048576, null=True, blank=True)
    status = models.CharField(max_length=64, choices=RUN_STATUSES, default='pending')

    total_runtime = models.FloatField(null=True, blank=True, verbose_name='runtime')

    def __str__(self):
        return str(self.task)

    def run(self):
        qs_out = QuicksilverIO()

        args = []

        if self.task.arguments is not None and self.task.arguments.strip() != '':
            args = self.task.arguments.split()

        try:
            self.status = 'ongoing'

            self.save()

            orig_stdout = sys.stdout
            sys.stdout = qs_out

            interval = self.task.repeat_interval

            if interval < 1:
                interval = 5

            max_duration = self.task.get_max_duration()

            if max_duration is not None:
                with ExecutionTimeout(seconds=max_duration):
                    call_command(self.task.command, *args, _qs_context=True, _qs_next_interval=interval)
            else:
                call_command(self.task.command, *args, _qs_context=True, _qs_next_interval=interval)

            sys.stdout = orig_stdout

            if self.status == 'ongoing':
                self.status = 'success'

            self.ended = timezone.now()
            self.output = qs_out.getvalue().decode('utf-8')

            output_lines = self.output.splitlines()

            if output_lines:
                last_line = output_lines[-1]

                if last_line.startswith('_qs_next_run:'):
                    self.task.next_run = arrow.get(last_line.replace('_qs_next_run:', '').strip()).datetime

                    self.task.save()
            else:
                logger.error('Task not Quicksilver-enabled: %s', self.task)

            self.save()
        except: # pylint: disable=bare-except
            self.output = 'Task exception %s:\n\n%s' % (self.task, traceback.format_exc())

            logger.error(self.output)

            self.status = 'error'
            self.ended = timezone.now()
            self.save()

            self.task.next_run = timezone.now() + datetime.timedelta(seconds=self.task.repeat_interval)

            self.task.save()

    def runtime(self):
        if self.ended is None:
            self.total_runtime = None

        if self.total_runtime is None:
            if self.started is None:
                return None

            if self.ended is not None:
                self.total_runtime = (self.ended - self.started).total_seconds()
                self.save()

                return (self.ended - self.started).total_seconds()

            self.total_runtime = (timezone.now() - self.started).total_seconds()
            self.save()

            return (timezone.now() - self.started).total_seconds()

        return self.total_runtime

    def kill_if_stuck(self, task_queue_start=None):
        if self.ended is not None:
            return False

        if task_queue_start is not None and self.started < task_queue_start:
            self.status = 'killed'
            self.ended = timezone.now()
            self.save()

            host = settings.ALLOWED_HOSTS[0]

            context = {
                'execution': self,
                'host': host,
                'task_queue_start': task_queue_start,
            }

            message = render_to_string('quicksilver_execution_stale_message.txt', context)
            subject = render_to_string('quicksilver_execution_stale_subject.txt', context)

            from_addr = 'quicksilver@' + host
            admins = [admin[1] for admin in settings.ADMINS]

            email = EmailMessage(subject, message, from_addr, admins, headers={'Reply-To': admins[0]})
            email.send()

            return True

        max_duration = self.task.get_max_duration()
        run_duration = self.runtime()

        if max_duration is not None and run_duration is not None:
            if run_duration > max_duration:
                self.status = 'killed'
                self.ended = timezone.now()
                self.save()

                context = {
                    'execution': self,
                    'max_duration': max_duration,
                    'run_duration': run_duration
                }

                message = render_to_string('quicksilver_execution_killed_message.txt', context)
                subject = render_to_string('quicksilver_execution_killed_subject.txt', context)

                host = settings.ALLOWED_HOSTS[0]
                from_addr = 'quicksilver@' + host
                admins = [admin[1] for admin in settings.ADMINS]

                email = EmailMessage(subject, message, from_addr, admins, headers={'Reply-To': admins[0]})
                email.send()

                return True

        return False
