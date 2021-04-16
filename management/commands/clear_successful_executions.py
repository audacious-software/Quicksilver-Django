from __future__ import print_function
# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import datetime
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock
from ...models import Execution

class Command(BaseCommand):
    help = 'Clears older Quicksilver successful task execution records.'

    def add_arguments(self, parser):
        parser.add_argument('--before_minutes', required=False, type=int, default=120, help='Removes successful task executions older than provided minutes.')

    @handle_lock
    def handle(self, *args, **options):
        before = timezone.now() - datetime.timedelta(seconds=(60 * options['before_minutes']))
        
        if int(options['verbosity']) > 1:
            print(before.isoformat() + ' -- ' + str(options['before_minutes']) + ' -- ' + str(options['verbosity']))

        deleted = Execution.objects.filter(ended__lte=before, status='success').delete()[0]
        
        if int(options['verbosity']) > 1:
            print('Cleared ' + str(deleted) + ' task execution record(s).')
