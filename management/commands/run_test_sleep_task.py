# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock, handle_schedule, add_qs_arguments

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

class Command(BaseCommand):
    help = 'Test Quicksilver task command with 5 second sleep.'

    @add_qs_arguments
    def add_arguments(self, parser):
        pass

    @handle_schedule
    @handle_lock
    def handle(self, *args, **options):
        logger.info('Start time: %s', timezone.now().isoformat())
        time.sleep(5)
        logger.info('End time: %s', timezone.now().isoformat())
