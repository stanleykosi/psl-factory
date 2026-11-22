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
from apps.core.workbench import granted
from apps.identity.services import visible_cases
from .native_station_access import project_scope
from .process_directory import trigger_guide
from .process_triggers import SCREENS, TRIGGERS


def source_projects(actor, trigger):
    _, read = SCREENS[trigger.screen]
    # The linked workbenches require admission to the project record as well
    # as their own read permission. They independently check all actions.
    return granted(actor, [read]).filter(kind='project', pk__in=visible_cases(actor).values('pk')).distinct()


@login_required
@require_safe
@never_cache
def destination(request, process, target):
    if process not in TRIGGERS or target not in ('source', 'track'):
        raise Http404
    trigger = TRIGGERS[process]
    tracking = target == 'track'
    projects = project_scope(request.user, process=process) if tracking else source_projects(request.user, trigger)

    def link(case_id):
        if tracking:
            return reverse('project_handoffs', args=[case_id]) + '?' + urlencode({'process': process})
        return reverse(trigger.screen, args=[case_id]) + '#' + trigger.section

    if 'project' in request.GET:
        try:
            case_id = UUID(request.GET['project'])
        except ValueError:
            raise Http404 from None
        case = get_object_or_404(projects, pk=case_id)
        return redirect(link(case.pk))
    search = request.GET.get('q', '').strip()[:100]
    query = projects.order_by('title', 'pk')
    if not search and 'page' not in request.GET:
        first = list(query.values_list('pk', flat=True)[:2])
        if len(first) == 1:
            return redirect(link(first[0]))
    if search:
        query = query.filter(title__icontains=search)
    page = Paginator(query, 24).get_page(request.GET.get('page'))
    return render(request, 'factory/process_destination.html', {
        'process': process, 'title': routes()[process]['original_title'],
        'guide': trigger_guide(process), 'tracking': tracking, 'page': page,
        'projects': [(case, link(case.pk)) for case in page], 'search': search,
    })
