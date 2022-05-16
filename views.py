# pylint: disable=no-member, line-too-long
# -*- coding: utf-8 -*-

import json

from django.http import HttpResponse
from django.utils import timezone

from .models import Task

def quicksilver_status(request): # pylint: disable=unused-argument
    overdue_tasks = []

    now = timezone.now()

    for overdue in Task.objects.exclude(next_run=None, repeat_interval__lte=0).filter(next_run__lte=now).order_by('next_run'):
        if overdue.is_running() is False:
            latest_execution = overdue.executions.exclude(ended=None).order_by('-ended').first()

            if latest_execution is not None:
                delta_seconds = (now - latest_execution.ended).total_seconds()

                runtime_outlier_threshold = overdue.runtime_outlier_threshold()

                if runtime_outlier_threshold is not None:
                    outlier_threshold = (overdue.repeat_interval * 2) + overdue.runtime_outlier_threshold()

                    if delta_seconds > outlier_threshold:
                        overdue_tasks.append({
                            'task': str(overdue),
                            'outlier_threshold': outlier_threshold,
                            'overdue': delta_seconds
                        })
        elif overdue.should_alert():
            overdue.alert()

    payload = {
        'overdue_tasks': overdue_tasks,
        'status': 'ok',
    }

    if len(overdue_tasks) > 0: # pylint: disable=len-as-condition
        payload['status'] = 'error'

    return HttpResponse(json.dumps(payload, indent=2), content_type='application/json', status=200)
