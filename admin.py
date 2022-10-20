# -*- coding: utf-8 -*-

from django.contrib import admin
from django.contrib.admin.filters import RelatedFieldListFilter

from .models import Task, Execution

class DropdownFilter(RelatedFieldListFilter):
    template = 'admin/quicksilver_dropdown_filter.html'

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('command', 'queue', 'repeat_interval', 'next_run',)
    list_filter = ('next_run', 'queue',)

@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ('task', 'started', 'ended', 'status',)
    list_filter = ('status', 'started', 'ended', ('task', DropdownFilter),)
