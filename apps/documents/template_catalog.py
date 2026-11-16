"""Template version list with the same protected reads as owner review."""
from django.core.exceptions import ValidationError
from django.shortcuts import render

from apps.core.read_budget import ReadLimit, limit_queries
from apps.identity.services import require

from .template_lists import LIST_QUERY_LIMIT, template_page


def show(request, case, tabs):
    require(request.user, case, 'document.read')
    context = {'case': case, 'tab': 'templates', 'tabs': tabs}
    status = 200
    try:
        with limit_queries(LIST_QUERY_LIMIT):
            context['versions'], context['next_url'] = template_page(request, case)
    except ValidationError:
        context['error'] = 'This page link has expired. Return to the first page to continue.'
        status = 400
    except ReadLimit:
        context['error'] = 'The template history needs a closer review. Open its owner records to continue.'
        status = 503
    return render(request, 'design/template_catalog.html', context, status=status)
