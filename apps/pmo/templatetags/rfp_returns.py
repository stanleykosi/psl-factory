from django import template
from django.core.exceptions import PermissionDenied

from apps.workflows.factory_rfp_returns import project


register = template.Library()


@register.inclusion_tag('factory/rfp_returns.html', takes_context=True)
def rfp_return_handoff(context, work, can_correct):
    try:
        returned = project(context['user'], work)
    except PermissionDenied:
        return {}
    return {'returned': returned, 'work': work, 'can_correct': can_correct,
            'queue': context['queue'], 'q': context['q']}
