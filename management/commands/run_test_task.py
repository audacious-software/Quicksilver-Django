# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock, handle_schedule
from ...models import Task

class Command(BaseCommand):
    help = 'Test Quicksilver task command.'

    def add_arguments(self, parser):
        pass

    @handle_lock
    @handle_schedule
    def handle(self, *args, **options):
        print 'Current time: ' + timezone.now().isoformat()
