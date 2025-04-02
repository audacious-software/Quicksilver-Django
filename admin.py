# pylint: disable=no-member
# -*- coding: utf-8 -*-

from django.contrib import admin
from django.contrib.admin.filters import RelatedFieldListFilter
from django.utils.translation import gettext_lazy as _

from .models import Task, Execution

class DropdownFilter(RelatedFieldListFilter):
    template = 'admin/quicksilver_dropdown_filter.html'

class RuntimeFilter(admin.SimpleListFilter):
    title = _("total runtime")

    parameter_name = "runtime"

    def lookups(self, request, model_admin):
        for empty_items in Execution.objects.filter(ended=None):
            empty_items.runtime()

        for empty_items in Execution.objects.filter(total_runtime=None):
            empty_items.runtime()

        return [
            ('0_1', _('less than a minute')),
            ('1_5', _('one to five minutes')),
            ('5_15', _('five to fifteen minutes')),
            ('15_30', _('fifteen minutes to half hour')),
            ('30_60', _('half hour to full hour')),
            ('60_', _('more than a full hour')),
        ]

    def queryset(self, request, queryset):
        if self.value() == '0_1':
            return queryset.filter(total_runtime__lt=60)

        if self.value() == '1_5':
            return queryset.filter(total_runtime__gte=60, total_runtime__lt=300)

        if self.value() == '5_15':
            return queryset.filter(total_runtime__gte=300, total_runtime__lt=900)

        if self.value() == '15_30':
            return queryset.filter(total_runtime__gte=900, total_runtime__lt=1800)

        if self.value() == '30_60':
            return queryset.filter(total_runtime__gte=1800, total_runtime__lt=3600)

        if self.value() == '60_':
            return queryset.filter(total_runtime__gte=3600)

        return queryset

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('command', 'queue', 'repeat_interval', 'next_run',)
    list_filter = ('next_run', 'queue',)

@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ('task', 'total_runtime', 'started', 'ended', 'status',)
    list_filter = ('status', 'started', 'ended', ('task', DropdownFilter), RuntimeFilter)
