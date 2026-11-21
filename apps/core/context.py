"""Presentation boundaries do not add routes or authority to the recovery plane."""
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

def interface(request):
    control_plane = settings.ROOT_URLCONF == 'config.cold_urls'
    nav = {'control_plane': control_plane}
    if control_plane or not request.user.is_authenticated:
        return nav
    from apps.core.workbench import granted
    from apps.identity.models import Grant
    from apps.identity.primary_roles import administered_projects
    from apps.identity.role_work import APPROVAL_DESKS
    from apps.identity.teams import memberships
    from apps.workflows.factory_views import QUEUES

    has_staff_home = memberships(request.user).exists() or administered_projects(request.user).exists()
    approval_actions = {actions[-1] for _,_,actions in APPROVAL_DESKS}
    nav['role_dashboard_available'] = (has_staff_home or granted(request.user,['factory.read']).exists()
        or Grant.objects.filter(user=request.user,active=True,action__in=approval_actions).exists())
    url = reverse('factory_intake')
    context = {}
    if request.resolver_match and request.resolver_match.url_name == 'home':
        if request.GET.get('queue') in QUEUES:
            context['queue'] = request.GET['queue']
        if request.GET.get('q', '').strip():
            context['q'] = request.GET['q'].strip()[:120]
    nav['start_work_url'] = url + '?' + urlencode({'entry': 'default', **context})
    nav['choose_work_url'] = url + ('?' + urlencode(context) if context else '')
    return nav
