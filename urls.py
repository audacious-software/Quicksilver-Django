# pylint: disable=line-too-long

from django.conf.urls import url

from .views import quicksilver_status

urlpatterns = [
    url(r'^status$', quicksilver_status, name='quicksilver_status'),
]
