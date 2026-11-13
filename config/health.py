from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
                ['finance', '0077_forecast_evidence_reference'],
            )
            ready = cursor.fetchone() is not None
    except DatabaseError:
        ready = False
    return HttpResponse('ok' if ready else 'unavailable', status=200 if ready else 503, content_type='text/plain')
