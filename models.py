# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import sys
import traceback

import io

import arrow

from django.core.management import call_command
from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

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
    arguments = models.TextField(max_length=1048576)
    queue = models.CharField(max_length=128, default='default')

    repeat_interval = models.IntegerField(default=0)

    next_run = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.command + '[' + self.queue + '] ' + ' '.join(self.arguments.splitlines())

    def run(self):
        execution = Execution(task=self, started=timezone.now())
        execution.save()

        self.save()

        execution.run()

    def is_running(self):
        return self.executions.filter(status='ongoing').count() > 0

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
                interval = None

            call_command(self.task.command, *args, _qs_context=True, _qs_next_interval=interval)

            sys.stdout = orig_stdout

            self.status = 'success'
        except: # pylint: disable=bare-except
            traceback.print_exc(None, qs_out)
            self.status = 'error'

        self.ended = timezone.now()
        self.output = qs_out.getvalue().decode('utf-8')

        output_lines = self.output.splitlines()

        last_line = output_lines[-1]

        if last_line.startswith('_qs_next_run:'):
            self.task.next_run = arrow.get(last_line.replace('_qs_next_run:', '').strip()).datetime

            self.task.save()

        self.save()
