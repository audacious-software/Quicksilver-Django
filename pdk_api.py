from __future__ import print_function

import bz2
import gc
import io
import logging
import os
import sys
import tempfile

from django.conf import settings
from django.core import management
from django.utils.text import slugify

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

def load_backup(filename, content):
    prefix = 'quicksilver_backup_' + settings.ALLOWED_HOSTS[0]

    if filename.startswith(prefix) is False:
        return

    if 'json-dumpdata' in filename:
        filename = filename.replace('.json-dumpdata.bz2.encrypted', '.json')

        path = os.path.join(tempfile.gettempdir(), filename)

        with open(path, 'wb') as fixture_file:
            fixture_file.write(content)

        management.call_command('loaddata', path)

        os.remove(path)
    else:
        logger.error('[quicksilver.pdk_api.load_backup] Unknown file type: %s', filename)

def incremental_backup(parameters): # pylint: disable=too-many-locals, too-many-statements
    to_transmit = []
    to_clear = []

    # Dump full content of these models. No incremental backup here.

    dumpdata_apps = (
        'quicksilver.Execution',
        'quicksilver.Task',
    )

    if parameters['skip_apps']:
        dumpdata_apps = ()

    prefix = 'quicksilver_backup_' + settings.ALLOWED_HOSTS[0]

    if 'start_date' in parameters:
        prefix += '_' + parameters['start_date'].isoformat()

    if 'end_date' in parameters:
        prefix += '_' + parameters['end_date'].isoformat()

    backup_staging = tempfile.gettempdir()

    try:
        backup_staging = settings.PDK_BACKUP_STAGING_DESTINATION
    except AttributeError:
        pass

    for app in dumpdata_apps:
        logger.info('[quicksilver] Backing up %s...', app)
        sys.stdout.flush()

        buf = io.StringIO()
        management.call_command('dumpdata', app, stdout=buf)
        buf.seek(0)

        database_dump = buf.read()

        buf = None

        gc.collect()

        compressed_str = bz2.compress(database_dump.encode('utf-8'))

        database_dump = None

        gc.collect()

        filename = prefix + '_' + slugify(app) + '.json-dumpdata.bz2'

        path = os.path.join(backup_staging, filename)

        with open(path, 'wb') as fixture_file:
            fixture_file.write(compressed_str)

        to_transmit.append(path)

    return to_transmit, to_clear

def clear_points(to_clear): # pylint: disable=unused-argument
    pass # No data points to clear
