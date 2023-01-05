# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import json

from django.http import HttpResponse
from django.utils import timezone

from .models import Task

def quicksilver_status(request): # pylint: disable=unused-argument
    issues = []

    now = timezone.now()

    for overdue in Task.objects.exclude(next_run=None, repeat_interval__lte=0).filter(next_run__lte=now).order_by('next_run'): # pylint: disable=too-many-nested-blocks
        if overdue.is_running() is False:
            latest_execution = overdue.executions.exclude(ended=None).order_by('-ended').first()

            if latest_execution is not None:
                delta_seconds = (now - latest_execution.ended).total_seconds()

                runtime_outlier_threshold = overdue.runtime_outlier_threshold()

                if runtime_outlier_threshold is not None:
                    outlier_threshold = (overdue.repeat_interval * 2) + overdue.runtime_outlier_threshold()

                    if delta_seconds > outlier_threshold:
                        other_tasks = Task.objects.filter(queue=overdue.queue).exclude(pk=overdue.pk)

                        others_running = False

                        for task in other_tasks:
                            if task.is_running():
                                others_running = True

                        if others_running is False:
                            issues.append({
                                'task': str(overdue),
                                'outlier_threshold': outlier_threshold,
                                'overdue': delta_seconds
                            })
        elif overdue.executions.all().count() < 2:
            issues.append({
                'task': str(overdue),
                'issue': 'Only %d runs recorded.' % overdue.executions.all().count()
            })

        if overdue.should_alert():
            overdue.alert()

    payload = {
        'issues': issues,
        'status': 'ok',
    }

    if len(issues) > 0: # pylint: disable=len-as-condition
        payload['status'] = 'error'

    return HttpResponse(json.dumps(payload, indent=2), content_type='application/json', status=200)
