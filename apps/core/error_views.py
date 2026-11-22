"""Plain factory error pages with the framework's original status and access checks."""
from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.shortcuts import render
from django.views import defaults


def _json_errors(request):
    return not settings.PSL_DJANGO_UI or request.path_info.startswith('/api/v1/')


def bad_request(request, exception):
    if _json_errors(request):
        from .factory_api.http import error

        if isinstance(exception, RequestDataTooBig):
            return error(413, 'request_too_large', 'The request exceeds the application size limit.')
        return error(400, 'bad_request', 'Check the request and try again.')
    return defaults.bad_request(request, exception)


def forbidden(request, exception):
    if _json_errors(request):
        from .factory_api.http import error

        return error(403, 'forbidden', 'You do not have permission for this action.')
    response = defaults.permission_denied(request, exception, template_name='403.html')
    response['Cache-Control'] = 'no-store'
    return response


def missing(request, exception):
    if _json_errors(request):
        from .factory_api.http import missing as missing_record

        return missing_record()
    response = defaults.page_not_found(request, exception, template_name='404.html')
    response['Cache-Control'] = 'no-store'
    return response


def failed(request):
    if _json_errors(request):
        from .factory_api.http import error

        return error(500, 'internal_error', 'The request could not be completed. Check the current work before retrying.')
    response = defaults.server_error(request, template_name='500.html')
    response['Cache-Control'] = 'no-store'
    return response


def csrf_failure(request, reason=''):
    if _json_errors(request):
        from .factory_api.http import error

        return error(403, 'csrf_failed', 'Refresh your session and try again.')
    response = render(request, 'csrf_failure.html', status=403)
    response['Cache-Control'] = 'no-store'
    return response
