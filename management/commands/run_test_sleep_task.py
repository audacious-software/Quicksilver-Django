from __future__ import print_function
# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock, handle_schedule, add_qs_arguments

class Command(BaseCommand):
    help = 'Test Quicksilver task command with 5 second sleep.'

    @add_qs_arguments
    def add_arguments(self, parser):
        pass

    @handle_lock
    @handle_schedule
    def handle(self, *args, **options):
        print('Start time: ' + timezone.now().isoformat())
        time.sleep(5)
        print('End time: ' + timezone.now().isoformat())
