# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock
from ...models import Execution

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

class Command(BaseCommand):
    help = 'Clears Quicksilver ongoing task execution records.'

    def add_arguments(self, parser):
        parser.add_argument('--before_minutes', required=False, type=int, default=120, help='Removes ongoing task executions older than provided minutes.')

    @handle_lock
    def handle(self, *args, **options):
        before = timezone.now() - datetime.timedelta(seconds=(60 * options['before_minutes'])) # pylint: disable=superfluous-parens

        deleted = Execution.objects.filter(ended__lte=before, status='ongoing').delete()[0]

        if int(options['verbosity']) > 1:
            logger.info('Cleared %s task execution record(s).', deleted)
