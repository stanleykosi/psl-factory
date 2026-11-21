"""Entry points to the native HR handoff and payroll follow-up services."""
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.agents.assistant import cases_for
from apps.identity.services import require

from .payroll_correction_views import reviewer


def destinations(actor, case):
    require(actor, case, 'case.read')
    require(actor, case, 'hrfinance.read')

    result = [
        {'key': 'handoffs', 'title': 'HR handoffs',
         'description': 'Review what Finance requested, what HR authorised and what Finance received.',
         'django_url': reverse('hrfinance', args=[case.pk])},
        {'key': 'questions', 'title': 'Staff-cost questions',
         'description': 'Open questions you raised or questions assigned to you about reviewed reports.',
         'django_url': reverse('payroll_questions', args=[case.pk])},
    ]
    try:
        reviewer(actor, case)
    except PermissionDenied:
        pass
    else:
        result.insert(1, {'key': 'corrections', 'title': 'Staff matching corrections',
                          'description': 'Review payroll matching requests and provide a corrected HR export.',
                          'django_url': reverse('design_hr_payroll_corrections', args=[case.pk])})
    if cases_for(actor, 'zainab').filter(pk=case.pk).exists():
        result.append({'key': 'assistant', 'title': 'Zainab, HR assistant',
                       'description': 'Ask a question about the HR records available to you in this project.',
                       'django_url': f"{reverse('assistant_start', args=['zainab'])}?workspace={case.pk}"})
    return result
