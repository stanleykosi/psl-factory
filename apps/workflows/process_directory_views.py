from urllib.parse import urlencode
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.agents.specialists import routes
from apps.core.workbench import source_workspaces
from apps.identity.factory_access import management_cases
from apps.identity.services import visible_cases
from .native_station_access import project_scope
from .process_directory import trigger_guide
from .process_triggers import SCREENS, TRIGGERS


def source_projects(actor, trigger):
    _, read = SCREENS[trigger.screen]
    return (visible_cases(actor) if trigger.screen == 'case' else source_workspaces(actor, read)).filter(kind='project')


@login_required
@require_safe
@never_cache
def destination(request, process, target):
    if process not in TRIGGERS or target not in ('source', 'track'):
        raise Http404
    trigger = TRIGGERS[process]
    tracking = target == 'track'
    direct = project_scope(request.user, process=process) if tracking else source_projects(request.user, trigger)
    projects = direct if tracking else direct | management_cases(request.user)
    guide = trigger_guide(process)
    context = {'title': routes()[process]['original_title'], 'guide': guide, 'tracking': tracking}

    def tracking_link(case_id):
        return reverse('project_handoffs', args=[case_id]) + '?' + urlencode({'process': process})

    def source_link(case_id):
        return reverse(trigger.screen, args=[case_id]) + '#' + trigger.section

    def open_project(case):
        if tracking:
            return redirect(tracking_link(case.pk))
        if direct.filter(pk=case.pk).exists():
            return redirect(source_link(case.pk))
        return render(request, 'factory/process_destination.html', {
            **context, 'case': case, 'tracking_link': tracking_link(case.pk),
        })

    if 'project' in request.GET:
        try:
            case_id = UUID(request.GET['project'])
        except ValueError:
            raise Http404 from None
        return open_project(get_object_or_404(projects, pk=case_id))
    search = request.GET.get('q', '').strip()[:100]
    query = projects.order_by('title', 'pk')
    if not search and 'page' not in request.GET:
        first = list(query[:2])
        if len(first) == 1:
            return open_project(first[0])
    if search:
        query = query.filter(title__icontains=search)
    page = Paginator(query, 24).get_page(request.GET.get('page'))
    direct_ids = set(direct.filter(pk__in=[case.pk for case in page]).values_list('pk', flat=True)) if not tracking else set()
    links = [
        (case, tracking_link(case.pk) if tracking else source_link(case.pk) if case.pk in direct_ids
         else guide['source_url'] + '?' + urlencode({'project': case.pk}))
        for case in page
    ]
    return render(request, 'factory/process_destination.html', {
        **context, 'page': page, 'projects': links, 'search': search,
    })
