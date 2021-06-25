# -*- coding: utf-8 -*-


from django.contrib import admin

from .models import Task, Execution

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('command', 'queue', 'repeat_interval', 'next_run',)
    list_filter = ('next_run', 'queue',)

@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ('task', 'started', 'ended', 'status',)
    list_filter = ('status', 'started', 'ended', 'task',)
