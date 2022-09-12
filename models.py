# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
import io
import sys
import traceback

import arrow
import numpy

from six import python_2_unicode_compatible

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

RUN_STATUSES = (
    ('success', 'Successful',),
    ('error', 'Error',),
    ('pending', 'Pending',),
    ('ongoing', 'Ongoing',),
)

class PermissionsSupport(models.Model): # pylint: disable=old-style-class, no-init, too-few-public-methods
    class Meta: # pylint: disable=too-few-public-methods, old-style-class, no-init
        managed = False
        default_permissions = ()

        permissions = (
            ('access_module', 'Access Quicksilver components'),
        )

class QuicksilverIO(io.BytesIO, object): # pylint: disable=too-few-public-methods, useless-object-inheritance
    def __init__(self): # pylint: disable=useless-super-delegation
        super(QuicksilverIO, self).__init__() # pylint: disable=super-with-arguments

    def write(self, value): # pylint: disable=useless-super-delegation, arguments-differ
        super(QuicksilverIO, self).write(value.encode()) # pylint: disable=super-with-arguments

@python_2_unicode_compatible
class Task(models.Model):
    command = models.CharField(max_length=4096, db_index=True)
    arguments = models.TextField(max_length=1048576, default='--no-color', help_text='One argument per line')
    queue = models.CharField(max_length=128, default='default')

    repeat_interval = models.IntegerField(default=0)

    next_run = models.DateTimeField(null=True, blank=True)

    postpone_alert_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.command + '[' + self.queue + '] ' + ' '.join(self.arguments.splitlines())

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

    def should_alert(self):
        if self.postpone_alert_until is not None and timezone.now() < self.postpone_alert_until:
            return False

        open_execution = self.executions.filter(ended=None).order_by('started').first()
        outlier_threshold = self.runtime_outlier_threshold()


        if open_execution is not None:
            runtime = open_execution.runtime()

            if outlier_threshold is not None:
                if open_execution.runtime() > outlier_threshold:
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

        return False

    def alert(self):
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

        context = {
            'task': self,
            'execution': open_execution,
            'runtime_mean': runtime_mean,
            'runtime_std': runtime_std,
            'host': host
        }

        message = render_to_string('quicksilver_task_alert_message.txt', context)
        subject = render_to_string('quicksilver_task_alert_subject.txt', context)

        from_addr = 'quicksilver@' + host

        email = EmailMessage(subject, message, from_addr, admins, headers={'Reply-To': admins[0]})
        email.send()

        postpone_interval = 15 * 60

        try:
            postpone_interval = settings.QUICKSILVER_ALERT_INTERVAL
        except AttributeError:
            pass

        self.postpone_alert_until = timezone.now() + datetime.timedelta(seconds=postpone_interval)
        self.save()

@python_2_unicode_compatible
class Execution(models.Model):
    task = models.ForeignKey(Task, related_name='executions', on_delete=models.CASCADE)

    started = models.DateTimeField()
    ended = models.DateTimeField(null=True, blank=True)
    output = models.TextField(max_length=1048576, null=True, blank=True)
    status = models.CharField(max_length=64, choices=RUN_STATUSES, default='pending')

    def __str__(self):
        return str(self.task)

    def run(self):
        qs_out = QuicksilverIO()

        args = self.task.arguments.splitlines()

        try:
            self.status = 'ongoing'

            self.save()

            orig_stdout = sys.stdout
            sys.stdout = qs_out

            interval = self.task.repeat_interval

            if interval < 1:
                interval = 5

            call_command(self.task.command, *args, _qs_context=True, _qs_next_interval=interval)

            sys.stdout = orig_stdout

            self.status = 'success'
        except: # pylint: disable=bare-except
            traceback.print_exc(None, qs_out)
            self.status = 'error'

        self.ended = timezone.now()
        self.output = qs_out.getvalue().decode('utf-8')

        output_lines = self.output.splitlines()

        if output_lines:
            last_line = output_lines[-1]

            if last_line.startswith('_qs_next_run:'):
                self.task.next_run = arrow.get(last_line.replace('_qs_next_run:', '').strip()).datetime

                self.task.save()

            self.save()
        else:
            print('Task not Quicksilver-enabled: ' + str(self.task))

    def runtime(self):
        if self.started is None:
            return None

        if self.ended is not None:
            return (self.ended - self.started).total_seconds()

        return (timezone.now() - self.started).total_seconds()
