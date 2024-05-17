# pylint: disable=line-too-long, no-name-in-module, wrong-import-position

import sys

if sys.version_info[0] > 2:
    from django.urls import re_path as url # pylint: disable=no-name-in-module
else:
    from django.conf.urls import url

from .views import quicksilver_status

urlpatterns = [
    url(r'^status$', quicksilver_status, name='quicksilver_status'),
]
