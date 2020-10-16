# -*- coding: utf-8 -*-


from django.contrib import admin

from .models import Task, Execution

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('command', 'next_run',)

@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ('task', 'started', 'ended', 'status',)
