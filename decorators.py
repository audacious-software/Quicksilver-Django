from __future__ import print_function
# pylint: disable=pointless-string-statement, line-too-long

import logging
import os
import tempfile
import time
import traceback

from lockfile import FileLock, AlreadyLocked, LockTimeout

import arrow

from django.conf import settings
from django.utils.text import slugify

"""
Decorators for wrapping existing Django management commands for use within the
Quicksilver task execution system.
"""

def add_qs_arguments(handle):
    def wrapper(self, parser):
        parser.add_argument('--qs-context', dest='_qs_context', default=True, required=False)
        parser.add_argument('--qs-next-interval', dest='_qs_next_interval', type=int, default=5, required=False)

        handle(self, parser)

    return wrapper


def handle_schedule(handle):
    def wrapper(self, *args, **options):
        invoked_by_qs = False

        if '_qs_context' in options:
            invoked_by_qs = options['_qs_context']

            del options['_qs_context']

        next_interval = None

        if '_qs_next_interval' in options:
            next_interval = options['_qs_next_interval']

            del options['_qs_next_interval']

        handle(self, *args, **options)

        if invoked_by_qs:
            if next_interval is not None:
                print('_qs_next_run: ' + arrow.get().shift(seconds=next_interval).isoformat())

    return wrapper

# Lock timeout value - how long to wait for the lock to become available.
# Default behavior is to never wait for the lock to be available (fail fast)
LOCK_WAIT_TIMEOUT = getattr(settings, "DEFAULT_LOCK_WAIT_TIMEOUT", -1)

def handle_lock(handle): # pylint: disable=too-many-statements
    """
    Decorate the handle method with a file lock to ensure there is only ever
    one process running at any one time.
    """
    def wrapper(self, *args, **options): # pylint: disable=too-many-statements
        lock_prefix = ''

        try:
            lock_prefix = settings.SITE_URL.split('//')[1].replace('/', '').replace('.', '-')
        except AttributeError:
            try:
                lock_prefix = settings.ALLOWED_HOSTS[0].replace('.', '-')
            except IndexError:
                lock_prefix = 'qs_lock'

        lock_suffix = ''

        if 'task_queue' in options:
            lock_suffix = '_' + options.get('task_queue')

        lock_prefix = slugify(lock_prefix)

        lock_suffix = slugify(lock_suffix)

        start_time = time.time()
        verbosity = options.get('verbosity', 0)
        if verbosity == 0:
            level = logging.ERROR
        elif verbosity == 1:
            level = logging.WARN
        elif verbosity == 2:
            level = logging.INFO
        else:
            level = logging.DEBUG

        logging.basicConfig(level=level, format="%(message)s")
        logging.debug("-" * 72)

        lock_name = self.__module__.split('.').pop()

        lock_filename = '%s/%s__%s__%s' % (tempfile.gettempdir(), lock_prefix, lock_name, lock_suffix) # pylint: disable=consider-using-f-string

        while lock_filename.endswith('_'):
            lock_filename = lock_filename[:-1]

        lock = FileLock(lock_filename)

        logging.debug("%s - acquiring lock...", lock_name)

        try:
            lock.acquire(LOCK_WAIT_TIMEOUT)
        except AlreadyLocked:
            logging.debug("Lock already in place. Quitting.")
            return
        except LockTimeout:
            logging.debug("Waiting for the lock timed out. Quitting.")
            return

        logging.debug("Acquired.")

        options['__qs_lock_filename'] = lock_filename

        try:
            handle(self, *args, **options)
        except: # pylint: disable=bare-except
            logging.error("Command Failed")
            logging.error('==' * 72)
            logging.error(traceback.format_exc())
            logging.error('==' * 72)

        logging.debug("Releasing lock...")
        lock.release()
        logging.debug("Released.")

        logging.debug("Done in %.2f seconds", (time.time() - start_time))

        return

    return wrapper

def touch_lock(options):
    lock_filename = options['__qs_lock_filename']

    if os.path.exists(lock_filename):
        os.utime(lock_filename, None)
