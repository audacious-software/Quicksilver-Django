# pylint: disable=line-too-long

from django.urls import re_path

from .views import quicksilver_status

urlpatterns = [
    re_path(r'^status$', quicksilver_status, name='quicksilver_status'),
]
