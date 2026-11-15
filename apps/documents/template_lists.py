"""Bounded template workbench windows. Native actions still validate exact records."""
import json
from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.db.models.query import prefetch_related_objects
from django.http import Http404
from django.utils.crypto import salted_hmac

from apps.core.read_budget import ReadBudget, ReadLimit, limit_queries
from . import template_current as current
from .models import Template, TemplateClaim, TemplateResolution, TemplateScope
from .template_access import visible_scopes, visible_sources, visible_templates


SCOPE_PAGE = 8
LIST_PAGE = 25
HISTORY_PREVIEW = 4
ACTIVE_PREVIEW = 12
LIST_QUERY_LIMIT = 250


def _window(query, request, case, name, limit, *, scope_id=None):
    # The anchor can be a denied candidate, so keep it opaque. It conveys
    # position only. The native visibility queries run again for every page.
    key = urlsafe_b64encode(salted_hmac('psl.template-lists.v1', 'cursor', algorithm='sha256').digest())
    cipher = Fernet(key)
    context = [str(request.user.pk), str(case.pk), name, scope_id]
    cursor = request.GET.get(name)
    if cursor:
        try:
            if len(cursor) > 512:
                raise ValueError
            token = json.loads(cipher.decrypt(cursor.encode('ascii'), ttl=3600))
            if token[:-1] != context or type(token[-1]) is not int:
                raise ValueError
        except (InvalidToken, ValueError, TypeError, IndexError):
            raise ValidationError('This page link has expired or is invalid. Return to template claims.') from None
        query = query.filter(pk__lt=token[-1])
    ids = list(query.order_by('-pk').values_list('pk', flat=True)[:limit])
    next_url = None
    if len(ids) == limit:
        params = request.GET.copy()
        params.pop('review', None)
        params[name] = cipher.encrypt(json.dumps([*context, ids[-1]]).encode()).decode()
        next_url = f'?{params.urlencode()}'
    return ids, next_url


def _selected_scope(value):
    if not value:
        return None
    try:
        pk = int(value)
        if str(pk) != value or not 0 < pk < 2**63:
            raise ValueError
    except ValueError:
        raise Http404 from None
    return pk


def _claims():
    return TemplateClaim.objects.select_related('actor', 'template', 'retraction').only(
        'scope_id', 'evidence_id', 'note', 'created_at', 'owner_policy_id',
        'actor__username', 'actor__is_active', 'template__name', 'template__version',
        'retraction__evidence_id', 'retraction__note',
    )


def read_workbench(request, case):
    focus = _selected_scope(request.GET.get('scope'))
    if focus and request.GET.get('review') == '1':
        return _read_workbench(request, case, focus, full_review=True)
    with limit_queries(LIST_QUERY_LIMIT):
        return _read_workbench(request, case, focus, full_review=False)


def _read_workbench(request, case, focus, *, full_review):
    actor = request.user
    budget = ReadBudget()
    scopes = TemplateScope.objects.filter(case=case)
    scope_ids, more_scopes = ([focus], None) if focus else _window(scopes, request, case, 'scopes', SCOPE_PAGE)
    shown_scopes = list(visible_scopes(actor, case, scopes=scopes.filter(pk__in=scope_ids), budget=budget).order_by('-pk'))
    if focus and not shown_scopes:
        raise Http404
    for scope in shown_scopes:
        scope.case = case

    claims = _claims()
    decisions = TemplateResolution.objects.defer('claim_ids')
    more_claims = more_decisions = None
    if focus:
        claim_ids, more_claims = _window(claims.filter(scope_id=focus), request, case, 'claims', LIST_PAGE, scope_id=focus)
        decision_ids, more_decisions = _window(decisions.filter(scope_id=focus), request, case, 'decisions', LIST_PAGE, scope_id=focus)
        shown_scopes[0].shown_claims = list(claims.filter(pk__in=claim_ids).order_by('-pk'))
        shown_scopes[0].shown_decisions = list(decisions.filter(pk__in=decision_ids).order_by('-pk'))
    else:
        prefetch_related_objects(
            shown_scopes,
            Prefetch('claims', claims.order_by('-pk')[:HISTORY_PREVIEW], to_attr='shown_claims'),
            Prefetch('resolutions', decisions.order_by('-pk')[:HISTORY_PREVIEW], to_attr='shown_decisions'),
        )
    prefetch_related_objects(shown_scopes, Prefetch(
        'claims', claims.filter(retraction__isnull=True).order_by('pk')[:ACTIVE_PREVIEW + 1], to_attr='active_preview',
    ))

    sources = case.evidence.filter(kind__in=[current.SOURCE_KIND, 'policy_decision'])
    source_ids, more_sources = _window(sources, request, case, 'sources', LIST_PAGE)
    linked_ids = {claim.evidence_id for scope in shown_scopes for claim in scope.shown_claims}
    linked_ids.update(claim.retraction.evidence_id for scope in shown_scopes for claim in scope.shown_claims if hasattr(claim, 'retraction'))
    visible_source_ids = set(visible_sources(
        actor, case, source_ids=linked_ids.union(source_ids), budget=budget,
    ).values_list('pk', flat=True))
    shown_sources = list(sources.filter(pk__in=set(source_ids) & visible_source_ids).only(
        'case_id', 'kind', 'version', 'source',
    ).order_by('-pk'))

    templates = Template.objects.filter(case=case)
    template_ids, more_templates = _window(templates, request, case, 'templates', LIST_PAGE)
    shown_templates = list(visible_templates(actor, case, candidate_ids=template_ids, budget=budget).only(
        'name', 'version',
    ).order_by('-pk'))

    rows = []
    for scope in shown_scopes:
        for claim in scope.active_preview:
            claim.scope = scope
        if full_review:
            # An operator explicitly opened the native exact inventory. Never
            # submit a page of claims as the complete resolution inventory.
            state = current.status(scope)
        elif len(scope.active_preview) > ACTIVE_PREVIEW:
            state = {'status': 'REVIEW REQUIRED', 'question': 'Open the complete current claim set to review this scope.'}
        else:
            try:
                state = current.status(scope, claims=scope.active_preview, budget=budget)
            except ReadLimit:
                state = {'status': 'REVIEW REQUIRED', 'question': 'Open the complete current claim set to review this scope.'}
        if state.get('claims'):
            state['claim_ids_json'] = json.dumps(state['claim_ids'])
        rows.append((scope, state))
    return {
        'rows': rows, 'sources': shown_sources, 'source_ids': visible_source_ids,
        'templates': shown_templates, 'scopes': shown_scopes, 'focus': focus,
        'more_scopes': more_scopes, 'more_sources': more_sources, 'more_templates': more_templates,
        'more_claims': more_claims, 'more_decisions': more_decisions,
    }
