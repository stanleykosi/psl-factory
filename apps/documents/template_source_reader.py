"""Exact template reads using native visibility within a PostgreSQL snapshot."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.db.models import Func, IntegerField, Q

from apps.core.models import Evidence
from apps.core.read_budget import ReadBudget, ReadLimit
from apps.identity.services import require, visible_cases
from .models import TemplateClaim, TemplateClaimRetraction, TemplateResolution, TemplateScope
from .template_access import visible_scopes, visible_sources


# Engineering limits for an interactive source read. The byte cap also admits
# the worst-case UTF-8 representation of the normal 100,000-character capture.
MAX_QUERIES = 100
MAX_BODY_BYTES = 1024 * 1024
STATEMENT_TIMEOUT_MS = 2500
MAX_OWNER_RECORDS = 100
OWNER_RECORDS = {
    'claim': (TemplateClaim, 'scope'),
    'decision': (TemplateResolution, 'scope'),
    'retraction': (TemplateClaimRetraction, 'claim__scope'),
}


SourceReadUnavailable = ReadLimit


class InvalidOwnerSelection(ValueError):
    """Malformed or out-of-budget selection before any record reads."""


def read_source(actor, case_id, source_id):
    if not _valid_id(source_id):
        return None
    return _snapshot(actor, case_id, lambda fresh, case, budget: _source(fresh, case, budget, source_id))


def _valid_id(pk):
    return type(pk) is int and 0 < pk < 2**63


def _source(actor, case, budget, source_id):
    size = Func('body', function='OCTET_LENGTH', output_field=IntegerField())
    source = visible_sources(actor, case, source_id=source_id, budget=budget).annotate(body_bytes=size).values(
        'id', 'kind', 'version', 'source', 'sha256', 'body_bytes',
    ).first()
    if source is None:
        return None
    if source.pop('body_bytes') > MAX_BODY_BYTES:
        raise ReadLimit
    source['body'] = Evidence.objects.values_list('body', flat=True).get(pk=source['id'])
    return case, source


def read_owner_pin(actor, case_id, kind, pk):
    from .template_current import owner_current

    model = {'claim': TemplateClaim, 'decision': TemplateResolution}.get(kind)
    if model is None or not _valid_id(pk):
        return None

    def read(fresh, case, budget):
        record = model.objects.filter(pk=pk, scope__case=case).select_related('scope', 'actor').only(
            'id', 'owner_policy_id', 'scope__case_id', 'scope__document_type', 'actor__id', 'actor__is_active',
        ).first()
        if record is None:
            return None
        scopes = TemplateScope.objects.filter(pk=record.scope_id)
        if not visible_scopes(fresh, case, scopes=scopes, budget=budget).exists():
            return None
        record.scope.case = case
        return case, {'current': owner_current(record, budget=budget), 'pinned': record.owner_policy_id is not None}

    return _snapshot(actor, case_id, read)


def read_owner_metadata(actor, case_id, selection):
    """Return only selected historical pointers, all within the same scope check."""
    if type(selection) is not list or not 1 <= len(selection) <= MAX_OWNER_RECORDS:
        raise InvalidOwnerSelection
    keys = []
    grouped = {}
    for token in selection:
        if type(token) is not str or len(token) > 30:
            raise InvalidOwnerSelection
        kind, _, identifier = token.partition(':')
        if kind not in OWNER_RECORDS or not identifier.isascii() or not identifier.isdecimal():
            raise InvalidOwnerSelection
        pk = int(identifier)
        if not _valid_id(pk) or identifier != str(pk):
            raise InvalidOwnerSelection
        keys.append((kind, pk))
        grouped.setdefault(kind, []).append(pk)
    if len(set(keys)) != len(keys):
        raise InvalidOwnerSelection

    def read(fresh, case, budget):
        from .template_current import COMPONENT

        records = {}
        scope_ids = set()
        for kind, ids in grouped.items():
            model, scope = OWNER_RECORDS[kind]
            rows = model.objects.filter(pk__in=ids, **{f'{scope}__case': case}).filter(
                Q(owner_policy__isnull=True) | Q(owner_policy__case=case, owner_policy__component=COMPONENT),
            ).values_list('pk', f'{scope}_id', 'owner_policy_id')
            for pk, scope_id, policy_id in rows:
                scope_ids.add(scope_id)
                records[(kind, pk)] = {'kind': kind, 'id': pk, 'scope_id': scope_id, 'policy_id': policy_id}
        if len(records) != len(keys):
            return None
        selected_scopes = TemplateScope.objects.filter(pk__in=scope_ids)
        visible = visible_scopes(fresh, case, scopes=selected_scopes, budget=budget).values_list('pk', flat=True)
        if set(visible) != scope_ids:
            return None
        return case, [records[key] for key in keys]

    return _snapshot(actor, case_id, read)


def _snapshot(actor, case_id, read):
    if not actor.is_authenticated or actor.pk is None:
        raise PermissionDenied
    if connection.vendor != 'postgresql' or connection.in_atomic_block or not connection.get_autocommit():
        raise ReadLimit

    remaining = MAX_QUERIES

    def charge(execute, sql, params, many, context):
        nonlocal remaining
        if remaining == 0:
            raise ReadLimit
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

                return read(fresh, case, ReadBudget())
    except DatabaseError as exc:
        if getattr(exc.__cause__, 'sqlstate', None) == '57014':
            raise ReadLimit from exc
        raise
