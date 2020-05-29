# pylint: disable=pointless-string-statement, line-too-long

import datetime
import functools
import logging
import tempfile
import time
import traceback

from lockfile import FileLock, AlreadyLocked, LockTimeout

import arrow

from django.conf import settings
from django.utils import timezone
from django.utils.decorators import available_attrs
from django.utils.text import slugify

"""
Decorators for wrapping existing Django management commands for use within the
Quicksilver task execution system.
"""

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

def handle_lock(handle):
    """
    Decorate the handle method with a file lock to ensure there is only ever
    one process running at any one time.
    """
    def wrapper(self, *args, **options):
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

        lock_filename = '%s/%s__%s__%s' % (tempfile.gettempdir(), lock_prefix, lock_name, lock_suffix)

        while lock_filename.endswith('_'):
            lock_filename = lock_filename[:-1]

        lock = FileLock(lock_filename)

        logging.debug("%s - acquiring lock...", lock_name)

        try:
            lock.acquire(LOCK_WAIT_TIMEOUT)
        except AlreadyLocked:
            logging.debug("lock already in place. quitting.")
            return
        except LockTimeout:
            logging.debug("waiting for the lock timed out. quitting.")
            return

        logging.debug("acquired.")

        try:
            handle(self, *args, **options)
        except: # pylint: disable=bare-except
            logging.error("Command Failed")
            logging.error('==' * 72)
            logging.error(traceback.format_exc())
            logging.error('==' * 72)

        logging.debug("releasing lock...")
        lock.release()
        logging.debug("released.")

        logging.info("done in %.2f seconds", (time.time() - start_time))
        return

    return wrapper
