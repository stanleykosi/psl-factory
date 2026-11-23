"""Server-rendered factory screens based on native records and current grants."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.identity.factory_access import project_actions, project_cases
from apps.identity.intake import options as intake_authority
from apps.identity.services import active_case_grants, require, visible_cases
from apps.workflows.factory_definitions import DEFINITIONS
from apps.workflows.factory_views import visible

from . import project_journey
from .workbench import granted


def discoverable_work(actor, *, case_id=None):
    # Payroll and business-unit work require record-specific source or
    # aggregate-recipient checks. Their native workbenches own that discovery.
    return visible(actor,case_id=case_id).exclude(definition__in=['finance-payroll/v1', 'finance-bu/v1'])


class FactorySignInForm(AuthenticationForm):
    username = UsernameField(max_length=254, label='Work email or sign-in name',
                             widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}))
    remember = forms.BooleanField(required=False, label='Keep me signed in')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].max_length = 254
        self.fields['username'].widget.attrs['maxlength'] = 254

    def clean(self):
        identifier = self.cleaned_data.get('username', '')
        if '@' in identifier:
            users = get_user_model()._default_manager
            if not users.filter(username=identifier).exists():
                names = list(users.filter(email__iexact=identifier).order_by('pk').values_list('username', flat=True)[:2])
                if len(names) == 1:
                    self.cleaned_data['username'] = names[0]
        return super().clean()


class FactoryLogin(LoginView):
    authentication_form = FactorySignInForm

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(None if form.cleaned_data['remember'] else 0)
        return response

    def get_default_redirect_url(self):
        return factory_landing(self.request.user) or super().get_default_redirect_url()


def factory_landing(actor):
    from apps.identity.primary_roles import administered_projects
    from apps.identity.teams import memberships

    if memberships(actor).exists() or (
            not granted(actor, ['factory.read']).exists() and administered_projects(actor).exists()):
        return reverse('home')
    if not visible_cases(actor).exists():
        return reverse('getting_started')
    return None


@login_required
@require_safe
@never_cache
def getting_started(request):
    from apps.identity.teams import memberships

    if memberships(request.user).exists():
        return redirect('home')
    if visible_cases(request.user).exists():
        return redirect('home')
    return render(request, 'design/getting_started.html', {
        'can_create': bool(intake_authority(request.user)),
    })


@login_required
@require_safe
@never_cache
def overview(request):
    # Only the recorded state is projected here. Verification and the current
    # next action remain the responsibility of the native work item.
    inventory = discoverable_work(request.user).exclude(status__in=['verified', 'cancelled'])
    counts = list(inventory.order_by().values('definition').annotate(total=Count('pk')))
    lines = sorted(
        ({'key': row['definition'], 'title': DEFINITIONS[row['definition']]['title'], 'total': row['total']}
         for row in counts),
        key=lambda line: line['title'],
    )
    return render(request, 'design/overview.html', {
        'lines': lines,
        'total': sum(row['total'] for row in lines),
        'as_of': timezone.now(),
    })


@login_required
@require_safe
@never_cache
def agents(request):
    from apps.agents import assistant
    from apps.agents.assistant_views import owned_conversations

    departments = [(key, name, department) for key, (name, department, _) in assistant.PERSONAS.items()
                   if assistant.cases_for(request.user, key).exists()]
    return render(request, 'design/agents.html', {'departments': departments,
                                                  'conversations': owned_conversations(request.user).order_by('-updated_at')[:25]})


@login_required
@require_safe
@never_cache
def project(request, case_id, tab='journey'):
    case = get_object_or_404(project_cases(request.user), pk=case_id)
    actions = project_actions(request.user, case)
    navigation = project_journey.tabs(case, actions)
    if tab in ('hr', 'templates', 'month-end') and not any(item['key'] == tab for item in navigation):
        from django.http import Http404
        raise Http404
    if tab == 'templates':
        from apps.documents.template_catalog import show

        return show(request, case, navigation)
    if tab == 'month-end':
        from apps.finance.month_end import show

        return show(request, case, navigation)
    if tab == 'hr':
        from apps.finance.hr_workspace import destinations

        return render(request, 'design/project_hr.html', {'case': case, 'tab': tab, 'tabs': navigation,
                                                          'destinations': destinations(request.user, case)})
    if tab == 'money':
        from apps.finance.project_money import projection

        if 'finance.read' not in actions:
            return render(request, 'design/project_money.html', {'case': case, 'tab': tab, 'tabs': navigation,
                                                                 'access_required': True}, status=403)
        money = projection(request.user, case, request.GET.get('figure', '')[:80])
        return render(request, 'design/project_money.html', {'case': case, 'tab': tab, 'tabs': navigation, 'money': money})
    if tab != 'journey':
        query = request.GET.get('q', '').strip()[:120]
        filter_form=project_journey.filters(case,tab,actions,request.GET)
        sections = project_journey.sections(request.user, case, tab, actions, query, request.GET,
            selected=filter_form.cleaned_data) if filter_form.is_valid() else []
        stages = None
        if tab == 'milestones' and 'finance.read' in actions:
            from apps.finance.project_money import projection

            stages = projection(request.user, case, include_change_links='change.read' in actions)
            stages['rows'] = [row for row in stages['rows'] if row['contract_stage']]
        return render(request, 'design/project_tab.html', {
            'case': case, 'tab': tab, 'tabs': navigation, 'panels': sections, 'q': query, 'stages': stages,'filter_form':filter_form,
            'can_link_milestone_change': tab == 'milestones' and {'change.read', 'change.manage', 'finance.read'}.issubset(actions),
            'change_timeline': project_journey.change_timeline(case, query, request.GET.get('plan-page'))
                if tab == 'milestones' and 'change.read' in actions else None,
        })
    works = discoverable_work(request.user, case_id=case.pk)
    journey = project_journey.work_timeline(works, request.GET.get('page'))
    finance = project_journey.finance_facts(request.user, case) if 'finance.read' in actions else None
    engagement = project_journey.engagement_facts(request.user, case) if 'engagement.read' in actions else None
    from apps.agents.assistant import cases_for
    from apps.identity.factory_access import PERSONA_ROLES, department_cases
    can_ask = cases_for(request.user, 'tola').filter(pk=case.pk).exists()
    department_links = [(persona, assistant_name) for persona, assistant_name in (
        ('tola', 'PMO records'), ('chidi', 'Finance records'), ('zainab', 'HR records'))
        if department_cases(request.user, PERSONA_ROLES[persona]).filter(pk=case.pk).exists()]
    return render(request, 'design/project.html', {'case': case, 'actions': actions, 'journey': journey, 'finance': finance,
                                                   'engagement': engagement, 'tab': tab, 'tabs': navigation,
                                                   'department_links': department_links, 'can_ask_tola': can_ask})
