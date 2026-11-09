"""Exact-reference filtered choices. Evidence IDs never enumerate private evidence."""
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from apps.identity.services import require
from .forms import CommandForm
from . import contract_coverage as s
from .models import (CoverageSource, CoverageTerms, CoverageAssessment, CoveragePreparationRequest,
                     BillingCoverage)


def allowed(check, rows):
    result = []
    for row in rows:
        try:
            check(row)
        except (PermissionDenied, ValidationError):
            continue
        result.append(row)
    return result


def sources(actor, case, permission='read', current=True):
    return allowed(lambda r: s.source_access(actor, r, permission, current=current),
                   CoverageSource.objects.filter(case=case).select_related('case', 'evidence'))


def terms(actor, case, permission='read', current=True):
    return allowed(lambda r: s.terms_access(actor, r, permission, current=current),
                   CoverageTerms.objects.filter(case=case).select_related('case', 'register', 'contract', 'coverage'))


def commands(actor, case, data=None):
    def choice(values): return forms.ChoiceField(choices=[(x, x) for x in values])
    def select(model, rows, optional=False):
        return forms.ModelChoiceField(model.objects.filter(pk__in=[r.pk for r in rows]), required=not optional)
    def proof(): return forms.IntegerField(min_value=1, label='Exact private evidence ID')
    def ident(): return forms.IntegerField(min_value=1)
    configurable = sources(actor, case, 'configure', current=False)
    matching = lambda cov: any(all(getattr(cov, k) == src.payload[k] for k in ['customer', 'service', 'contract']) for src in configurable if src.kind != 'invoice')
    coverages = [r for r in BillingCoverage.objects.filter(case=case) if matching(r)]
    users = allowed(lambda u: require(u, case, 'case.read'), get_user_model().objects.filter(is_active=True))
    def eligible_user(user, permission):
        # Only display principals already authorised for at least one selectable
        # register/contract pair; exact selected pair is checked on submission.
        kinds = set()
        for src in configurable:
            try: s.source_access(user, src, permission, current=False)
            except (PermissionDenied, ValidationError): continue
            kinds.add(src.kind)
        if not {'register', 'contract'} <= kinds:
            raise PermissionDenied('Exact source access is required')
    owners = allowed(lambda u: eligible_user(u, 'read'), users)
    reviewers = allowed(lambda u: eligible_user(u, 'activate'), users)
    definitions = {
        'evidence': ('evidence.add', 'Supply purpose-scoped private coverage evidence', {
            'references': forms.JSONField(help_text='Exact source-reference list; no wildcard'),
            'purposes': forms.MultipleChoiceField(choices=[(p,p) for p in s.EVIDENCE_PURPOSES]),
            'kind': choice(sorted({kind for kinds in s.EVIDENCE_PURPOSES.values() for kind in kinds})),
            'body': forms.CharField(max_length=100000,widget=forms.Textarea),
            'source': forms.CharField(max_length=500)}),
        'grant': ('coverage.access', 'Grant or revoke exact source access', {
            'reference': forms.CharField(max_length=100), 'principal': select(get_user_model(), users),
            'permissions': forms.MultipleChoiceField(choices=[(p, p) for p in s.PERMISSIONS], required=False), 'evidence': proof()}),
        'capture': ('coverage.capture', 'Capture supplied source version', {
            'reference': forms.CharField(max_length=100), 'kind': choice(['register', 'contract', 'invoice']),
            'payload': forms.JSONField(widget=forms.Textarea), 'evidence': proof()}),
        'draft': ('coverage.configure', 'Draft evidenced contract terms', {
            'coverage': select(BillingCoverage, coverages),
            'register': select(CoverageSource, [r for r in configurable if r.kind == 'register']),
            'contract': select(CoverageSource, [r for r in configurable if r.kind == 'contract']),
            'implementation': choice(['explicit-contract-schedule/v1']),
            'review_requirement': choice(['unknown', 'none', 'required']),
            'schedule_interpretation': forms.JSONField(required=False, widget=forms.Textarea, help_text='Exact mode, attestation and private evidence_id for cadence/schedule interpretation'),
            'invoice_verification': forms.JSONField(required=False, widget=forms.Textarea, help_text='Optional exact method, verifier_id and distinct_capture_actor rule; missing holds only verification'),
            'reviewer': select(get_user_model(), reviewers, True), 'owner': select(get_user_model(), owners, True), 'evidence': proof()}),
        'verify': ('coverage.invoice.verify', 'Verify exact issued invoice reference', {
            'source': select(CoverageSource, [r for r in sources(actor, case, 'verify') if r.kind == 'invoice']),
            'terms': select(CoverageTerms, terms(actor, case, 'verify')),
            'native_issue_id': forms.IntegerField(min_value=1, required=False), 'evidence': proof()}),
        'assess': ('coverage.assess', 'Assess coverage as of a date', {
            'terms': select(CoverageTerms, terms(actor, case, current=False)), 'as_of': forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))}),
        'investigate': ('agent.coverage', 'Investigate exceptions and draft owner questions', {
            'terms': select(CoverageTerms, terms(actor, case, 'investigate', current=False)),
            'as_of': forms.DateField(widget=forms.DateInput(attrs={'type': 'date'})), 'process_id': choice(['F31', 'F45'])}),
    }
    for action, state, permission in [('validate', 'validated', 'configure'), ('activate', 'active', 'activate'), ('revoke', 'revoked', 'activate')]:
        definitions[action] = (s.ACTIONS[permission], action.capitalize() + ' exact terms version', {
            'terms': select(CoverageTerms, terms(actor, case, permission, current=action != 'revoke')), 'evidence': proof()})
    readable_terms = terms(actor, case, current=False)
    assessments = allowed(lambda r: s.current_assessment(actor, r),
        CoverageAssessment.objects.filter(terms__in=readable_terms))
    preparable = allowed(lambda r: s.terms_access(actor, r.terms, 'prepare'), assessments)
    all_requests = list(CoveragePreparationRequest.objects.filter(assessment__terms__in=readable_terms))
    def receivable(request):
        route = s.preparation_route(request)
        s.terms_access(actor, route['assessment'].terms, 'receive', current=False)
        if route['recipient'].pk != actor.pk or route['state'] != 'ready':
            raise PermissionDenied('Only the current ready route recipient may receive')
    requests = allowed(receivable, all_requests)
    def routable(request):
        s.terms_access(actor, request.assessment.terms, 'prepare', current=False)
        s.terms_access(actor, s.preparation_route(request)['assessment'].terms, current=False)
    route_requests = allowed(routable, all_requests)
    # Cancellation must remain possible when the route assessment becomes stale.
    # Ready revalidation is checked against current_assessment by the service.
    route_assessments = list(preparable)
    for request in route_requests:
        assessment = s.preparation_route(request)['assessment']
        if assessment.pk not in {r.pk for r in route_assessments}:
            route_assessments.append(assessment)
    definitions['route'] = ('coverage.prepare', 'Revalidate, reassign or cancel preparation request', {
        'request': select(CoveragePreparationRequest, route_requests),
        'assessment': select(CoverageAssessment, route_assessments),
        'recipient_id': ident(), 'state': choice(['ready', 'cancelled']), 'evidence': proof()})
    from .models import CoveragePreparationReceipt
    received_ids = CoveragePreparationReceipt.objects.filter(request__in=route_requests, preparation__isnull=True).values_list('request_id', flat=True)
    definitions['continue_preparation'] = ('coverage.prepare', 'Continue acknowledged work with a current Finance recipient', {
        'request': select(CoveragePreparationRequest, [r for r in route_requests if r.pk in received_ids]),
        'assessment': select(CoverageAssessment, preparable), 'recipient_id': ident(),
        'reason': forms.CharField(max_length=1000), 'evidence': proof()})
    definitions['request'] = ('coverage.prepare', 'Request internal Finance preparation', {
        'assessment': select(CoverageAssessment, preparable), 'obligation_key': forms.CharField(max_length=64),
        'recipient_id': ident()})
    definitions['receive'] = ('coverage.receive', 'Acknowledge internal preparation receipt', {
        'request': select(CoveragePreparationRequest, requests), 'preparation_id': forms.IntegerField(min_value=1, required=False)})
    from .fixed_charge import charge_access
    from .models import CoverageFixedCharge, BillingPreparation
    charges = allowed(lambda r: charge_access(actor, r, current=False),
        CoverageFixedCharge.objects.filter(assessment__terms__in=readable_terms))
    definitions['fixed_charge'] = ('coverage.configure', 'Supply exact fixed-contract amount and due terms', {
        'request': select(CoveragePreparationRequest, all_requests),
        'assessment': select(CoverageAssessment, assessments, True),
        'payload': forms.JSONField(widget=forms.Textarea, help_text='Exact fixed-charge/v1 declaration; unknown amount or date stays null. Gross includes tax and is never taxed again.'),
        'evidence': proof()})
    definitions['fixed_investigate'] = ('agent.coverage', 'Investigate exact fixed-contract pricing for review', {
        'charge': select(CoverageFixedCharge, charges)})
    definitions['fixed_prepare'] = ('finance.billing.prepare', 'Prepare fixed-contract invoice for human review', {
        'charge': select(CoverageFixedCharge, charges)})
    definitions['fixed_recover'] = ('finance.read', 'Look up committed native preparation receipt', {
        'preparation': select(BillingPreparation, BillingPreparation.objects.filter(fixed_charge__in=charges))})
    from apps.agents.contract_coverage import PROVIDER, current_run
    from apps.agents.models import AgentRun
    runs = allowed(lambda r: current_run(actor, r), AgentRun.objects.filter(case=case, provider=PROVIDER))
    definitions['question'] = ('agent.coverage', 'Request configured owner clarification internally', {'run': select(AgentRun, runs)})
    result = []
    for action, (permission, label, fields) in definitions.items():
        try: require(actor, case, permission)
        except PermissionDenied: continue
        form = CommandForm(data if data and data.get('action') == action else None,
            initial={'action': action, 'revision': case.revision}, auto_id='coverage_' + action + '_%s')
        form.fields.update(fields)
        result.append({'label': label, 'action': action, 'form': form})
    return result
