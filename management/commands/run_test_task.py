# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import six

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...decorators import handle_lock, handle_schedule, add_qs_arguments

class Command(BaseCommand):
    help = 'Test Quicksilver task command.'

    @add_qs_arguments
    def add_arguments(self, parser):
        pass

    @handle_schedule
    @handle_lock
    def handle(self, *args, **options):
        six.print_('Current time: ' + timezone.now().isoformat())
