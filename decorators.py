# pylint: disable=line-too-long, no-member

from __future__ import print_function

import logging
import os
import tempfile
import time

from lockfile import FileLock, AlreadyLocked, LockTimeout

import arrow
import psutil

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from .models import Execution

# Decorators for wrapping existing Django management commands for use within the
# Quicksilver task execution system.

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

        exception = None

        try:
            handle(self, *args, **options)
        except Exception as exc: # pylint: disable=broad-exception-caught
            exception = exc

        if invoked_by_qs:
            if next_interval is not None:
                print('_qs_next_run: ' + arrow.get().shift(seconds=next_interval).isoformat())

        if exception is not None:
            raise exception

    return wrapper

# Lock timeout value - how long to wait for the lock to become available.
# Default behavior is to never wait for the lock to be available (fail fast)

LOCK_WAIT_TIMEOUT = getattr(settings, 'DEFAULT_LOCK_WAIT_TIMEOUT', -1)

def handle_lock(handle): # pylint: disable=too-many-statements
    '''
    Decorate the handle method with a file lock to ensure there is only ever
    one process running at any one time.
    '''
    def wrapper(self, *args, **options): # pylint: disable=too-many-statements, too-many-branches, too-many-locals
        wrapper_time = time.time()

        lock_prefix = ''

        try:
            lock_prefix = settings.SITE_URL.split('//')[1].replace('/', '').replace('.', '-')
        except AttributeError:
            try:
                lock_prefix = settings.ALLOWED_HOSTS[0].replace('.', '-')
            except IndexError:
                lock_prefix = 'qs_lock'

        # Create a local temp file on first run to use as a proxy for system bootup. Needed
        # in container contexts...

        lockdir = tempfile.gettempdir()

        if hasattr(settings, 'QUICKSILVER_LOCK_DIR'):
            lockdir = settings.QUICKSILVER_LOCK_DIR

        startup_filename = '%s/%s__startup__.lock' % (lockdir, lock_prefix) # pylint: disable=consider-using-f-string

        if os.path.exists(startup_filename):
            # Check to see if startup file is older than the system runtime (not a container).

            boot_time = arrow.get(psutil.boot_time()).datetime

            start_time = arrow.get(os.path.getctime(startup_filename)).datetime

            if boot_time > start_time:
                os.remove(startup_filename)

        if os.path.exists(startup_filename) is False:
            startup_file = os.open(startup_filename, os.O_CREAT | os.O_RDWR)
            os.write(startup_file, timezone.now().isoformat().encode('utf8'))
            os.close(startup_file)

        start_time = arrow.get(os.path.getctime(startup_filename)).datetime

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

        logging.basicConfig(level=level, format='%(message)s')
        logging.debug('-' * 72)

        lock_name = self.__module__.split('.').pop()

        lock_filename = '%s/%s__%s__%s' % (tempfile.gettempdir(), lock_prefix, lock_name, lock_suffix) # pylint: disable=consider-using-f-string

        while lock_filename.endswith('_'):
            lock_filename = lock_filename[:-1]

        lock = FileLock(lock_filename)

        logging.debug('%s - acquiring lock...', lock_name)

        try:
            lock.acquire(LOCK_WAIT_TIMEOUT)
        except AlreadyLocked:
            start_time = arrow.get(os.path.getctime(startup_filename)).datetime

            lock_created = arrow.get(os.path.getctime('%s.lock' % lock_filename)).datetime

            logging.debug('Checking lock age: %s <? %s.', lock_created.isoformat(), start_time.isoformat())

            if lock_created < start_time: # Stale lock left over from reboot.
                logging.debug('Removing stale lock and jobs from before latest system boot.')

                task_queue = options.get('task_queue', 'default')

                deleted = Execution.objects.filter(task__queue=task_queue, status='ongoing', started__lte=start_time).delete()

                logging.debug('Deleted %s stale ongoing executions in the "%s" task queue.', deleted, task_queue)

                os.remove('%s.lock' % lock_filename)

                logging.debug('Removed lock file %s.', ('%s.lock' % lock_filename))

                try:
                    logging.debug('Attempting to acquire new lock...')

                    lock.acquire(LOCK_WAIT_TIMEOUT)
                except AlreadyLocked:
                    logging.debug('Lock already in place. Quitting.')
                    return
            else:
                logging.debug('Lock already in place. Quitting.')
                return
        except LockTimeout:
            logging.debug('Waiting for the lock timed out. Quitting.')
            return

        logging.debug('Acquired.')

        options['__qs_lock_filename'] = lock_filename

        exception = None

        try:
            handle(self, *args, **options)
        except Exception as exc: # pylint: disable=broad-exception-caught
            exception = exc

        logging.debug('Releasing lock...')
        lock.release()
        logging.debug('Released.')

        logging.debug('Done in %.2f seconds', (time.time() - wrapper_time))

        if exception is not None:
            raise exception

        return

    return wrapper

def touch_lock(options):
    lock_filename = options['__qs_lock_filename']

    if os.path.exists(lock_filename):
        os.utime(lock_filename, None)
