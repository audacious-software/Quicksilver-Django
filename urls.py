# pylint: disable=line-too-long, no-name-in-module

import sys

if sys.version_info[0] > 2:
    from django.urls import re_path

    from .views import quicksilver_status

    urlpatterns = [
        re_path(r'^status$', quicksilver_status, name='quicksilver_status'),
    ]
else:
    from django.conf.urls import url

    from .views import quicksilver_status

    urlpatterns = [
        url(r'^status$', quicksilver_status, name='quicksilver_status'),
    ]
