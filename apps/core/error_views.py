"""Plain factory error pages with the framework's original status and access checks."""
from django.shortcuts import render
from django.views import defaults


def forbidden(request, exception):
    response = defaults.permission_denied(request, exception, template_name='403.html')
    response['Cache-Control'] = 'no-store'
    return response


def missing(request, exception):
    response = defaults.page_not_found(request, exception, template_name='404.html')
    response['Cache-Control'] = 'no-store'
    return response


def failed(request):
    response = defaults.server_error(request, template_name='500.html')
    response['Cache-Control'] = 'no-store'
    return response


def csrf_failure(request, reason=''):
    response = render(request, 'csrf_failure.html', status=403)
    response['Cache-Control'] = 'no-store'
    return response
