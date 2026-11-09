"""One exact source read using native visibility within a PostgreSQL snapshot."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.db.models import Func, IntegerField

from apps.core.models import Evidence
from apps.identity.services import require, visible_cases
from .template_access import visible_sources


# Engineering limits for an interactive source read. The byte cap also admits
# the worst-case UTF-8 representation of the normal 100,000-character capture.
MAX_QUERIES = 40
MAX_BODY_BYTES = 1024 * 1024
STATEMENT_TIMEOUT_MS = 2500


class SourceReadUnavailable(Exception):
    """The read could not complete within its transaction or resource limits."""


def read_source(actor, case_id, source_id):
    if not actor.is_authenticated or actor.pk is None:
        raise PermissionDenied
    if type(source_id) is not int or not 0 < source_id < 2**63:
        return None
    if connection.vendor != 'postgresql' or connection.in_atomic_block or not connection.get_autocommit():
        raise SourceReadUnavailable

    remaining = MAX_QUERIES

    def charge(execute, sql, params, many, context):
        nonlocal remaining
        if remaining == 0:
            raise SourceReadUnavailable
        remaining -= 1
        return execute(sql, params, many, context)

    try:
        with transaction.atomic(durable=True):
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(STATEMENT_TIMEOUT_MS)])
            with connection.execute_wrapper(charge):
                fresh = get_user_model().objects.filter(pk=actor.pk, is_active=True).only('id', 'is_active').first()
                if fresh is None:
                    raise PermissionDenied
                case = visible_cases(fresh).filter(pk=case_id).first()
                if case is None:
                    return None
                require(fresh, case, 'document.read')

                size = Func('body', function='OCTET_LENGTH', output_field=IntegerField())
                source = visible_sources(fresh, case, source_id=source_id).annotate(body_bytes=size).values(
                    'id', 'kind', 'version', 'source', 'sha256', 'body_bytes',
                ).first()
                if source is None:
                    return None
                if source.pop('body_bytes') > MAX_BODY_BYTES:
                    raise SourceReadUnavailable
                # Exact admitted row, on the same read-only snapshot. No
                # alternate query or partial projection is returned on failure.
                source['body'] = Evidence.objects.values_list('body', flat=True).get(pk=source['id'])
                return case, source
    except DatabaseError as exc:
        if getattr(exc.__cause__, 'sqlstate', None) == '57014':
            raise SourceReadUnavailable from exc
        raise
