from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from apps.core.views import accessible_case
from apps.identity.services import require
from apps.agents import contract_coverage as agent
from apps.agents.models import AgentRun
from . import contract_coverage as service
from . import fixed_charge as fixed
from .coverage_forms import commands, sources, terms, allowed
from .models import CoverageAssessment, CoveragePreparationRequest, CoveragePreparationReceipt


@login_required
@require_http_methods(['GET', 'POST'])
def workbench(request, case_id):
    case = accessible_case(request.user, case_id)
    require(request.user, case, 'coverage.read')
    forms = commands(request.user, case, request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        try:
            command = next((x for x in forms if x['action'] == request.POST.get('action')), None)
            if not command or not command['form'].is_valid():
                raise ValidationError('Select an available action and valid authorised references')
            form = command['form']
            if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'}:
                raise ValidationError('Unexpected command fields')
            d = form.cleaned_data
            a, c, v, action = request.user, case.pk, d['revision'], d['action']
            if action == 'evidence':
                proof=service.supply_evidence(a,c,d['references'],d['purposes'],d['kind'],d['body'],d['source'],v)
                messages.success(request,f'Private evidence #{proof.pk} saved for the exact supplied references and purposes.')
            elif action == 'grant':
                service.grant_access(a, c, d['reference'], d['principal'].pk, d['permissions'], d['evidence'], v)
            elif action == 'capture':
                service.capture_source(a, c, d['reference'], d['kind'], d['payload'], d['evidence'], v)
            elif action == 'draft':
                for principal, permission in [(d['owner'], 'read'), (d['reviewer'], 'activate')]:
                    if principal:
                        for source in [d['register'], d['contract']]:
                            service.source_access(principal, source, permission, current=False)
                payload = {'implementation': d['implementation'], 'review_requirement': d['review_requirement'],
                    'reviewer_id': d['reviewer'].pk if d['reviewer'] else None, 'owner_id': d['owner'].pk if d['owner'] else None}
                if d['schedule_interpretation'] is not None:payload['schedule_interpretation']=d['schedule_interpretation']
                if d['invoice_verification'] is not None:payload['invoice_verification']=d['invoice_verification']
                service.draft_terms(a, c, d['coverage'].pk, d['register'].pk, d['contract'].pk, payload, d['evidence'], v)
            elif action in ['validate', 'activate', 'revoke']:
                service.transition(a, c, d['terms'].pk, {'validate': 'validated', 'activate': 'active', 'revoke': 'revoked'}[action], d['evidence'], v)
            elif action == 'verify':
                service.verify_invoice(a, c, d['source'].pk, d['evidence'], d['native_issue_id'], v, terms_id=d['terms'].pk)
            elif action == 'assess':
                service.assess(a, c, d['terms'].pk, d['as_of'], v)
            elif action == 'investigate':
                agent.investigate(a, c, d['terms'].pk, d['as_of'], d['process_id'], v)
            elif action == 'request':
                service.request_preparation(a, c, d['assessment'].pk, d['obligation_key'], d['recipient_id'], v)
            elif action == 'route':
                service.route_preparation(a, c, d['request'].pk, d['assessment'].pk,
                    d['recipient_id'], d['state'], d['evidence'], v)
            elif action == 'continue_preparation':
                from .preparation_continuation import assign
                record = assign(a,c,d['request'].pk,d['assessment'].pk,d['recipient_id'],d['evidence'],d['reason'],v)
                messages.success(request, f'Continuation #{record.pk} recorded. Original acknowledgement and any existing approval remain unchanged.')
            elif action == 'receive':
                service.receive_preparation(a, c, d['request'].pk, d['preparation_id'], v)
            elif action == 'fixed_charge':
                fixed.supply_charge(a, c, d['request'].pk, d['payload'], d['evidence'], v, assessment_id=d['assessment'].pk if d['assessment'] else None)
            elif action == 'fixed_investigate':
                agent.investigate_charge(a, c, d['charge'].pk, v)
            elif action == 'fixed_prepare':
                from adapters.factory_invoice_preparation import NativeFixedContractPreparationAdapter
                result = NativeFixedContractPreparationAdapter().prepare(a, c, d['charge'].pk, v)
                messages.success(request, f"Native preparation #{result['preparation_id']} is {result['status']}. Review and issuance remain separate.")
            elif action == 'fixed_recover':
                binding = fixed.recovered(a, d['preparation'])
                messages.success(request, f'Committed native preparation #{binding.preparation_id}, receipt #{binding.pk}. This lookup did not prepare or issue again.')
            elif action == 'question':
                agent.request_owner_question(a, c, d['run'].pk, v)
            messages.success(request, 'Coverage work recorded. No invoice or external communication was sent.')
            return redirect('finance_contract_coverage', case_id=c)
        except PermissionDenied:
            raise
        except (ValidationError, ValueError, ObjectDoesNotExist) as exc:
            messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'The exact reference is unavailable or invalid.')
            case.refresh_from_db()
            forms = commands(request.user, case)
    visible_terms = terms(request.user, case, current=False)
    for t in visible_terms:
        t.lifecycle = t.events.order_by('-pk').first()
        t.current_findings = service.active_findings(request.user, t)
    assessments = []
    for assessment in CoverageAssessment.objects.filter(terms__in=visible_terms).order_by('-pk'):
        try:
            snapshot, result = service.projection(request.user, assessment.terms, assessment.as_of)
            if snapshot != assessment.snapshot or result != assessment.result:
                continue
        except (PermissionDenied, ValidationError):
            continue
        assessments.append(assessment)
    runs = allowed(lambda r: agent.current_run(request.user, r),
        AgentRun.objects.filter(case=case, provider=agent.PROVIDER).order_by('-pk'))
    requests = []
    for preparation_request in CoveragePreparationRequest.objects.filter(assessment__terms__in=visible_terms).order_by('-pk'):
        try:
            route = service.preparation_route(preparation_request)
            service.terms_access(request.user, route['assessment'].terms, current=False)
        except (PermissionDenied, ValidationError):
            continue
        preparation_request.current_route = route
        preparation_request.route_history = allowed(
            lambda r: service.terms_access(request.user, r.assessment.terms, current=False),
            preparation_request.routes.select_related('assessment__terms').order_by('-pk'))
        requests.append(preparation_request)
    receipts = CoveragePreparationReceipt.objects.filter(request__in=requests).order_by('-pk')
    from .models import CoverageFixedCharge, CoverageNativePreparation
    fixed_charges = allowed(lambda r: fixed.charge_access(request.user, r, current=False),
        CoverageFixedCharge.objects.filter(assessment__terms__in=visible_terms).order_by('-pk'))
    bindings = allowed(lambda r: fixed.recovered(request.user, r.preparation),
        CoverageNativePreparation.objects.filter(preparation__fixed_charge__in=fixed_charges).order_by('-pk'))
    from . import preparation_continuation as continuation
    from .models import CoveragePreparationContinuation
    continuations = allowed(lambda r: continuation.access(request.user,r),
        CoveragePreparationContinuation.objects.filter(receipt__in=receipts).order_by('-pk'))
    for record in continuations:
        try:
            continuation.access(request.user,record,current=True); record.current_authority=True
        except (PermissionDenied,ValidationError): record.current_authority=False
    fixed_agents = []
    for run in AgentRun.objects.filter(case=case, provider='deterministic-fixed-charge-v1').order_by('-pk'):
        charge = next((r for r in fixed_charges if r.pk == run.result.get('charge')), None)
        if charge is None: continue
        try:
            fixed.charge_access(run.actor, charge, 'investigate')
            snapshot, result = fixed.inputs(request.user, charge)
            route = fixed.route_for(request.user,charge.request,assessment=charge.assessment)
            resumed = route.get('continuation')
            recorded = run.result.get('work_route')
            route_matches = recorded is None and resumed is None or recorded and recorded['recipient']==route['recipient'].pk and recorded['continuation']==(resumed.pk if resumed else None)
            if route_matches and snapshot == run.result['snapshot'] and result == run.result['preparation_preview']: fixed_agents.append(run)
        except (PermissionDenied, ValidationError): continue
    response = render(request, 'finance/contract_coverage.html', {'case': case, 'commands': forms,
        'sources': sources(request.user, case), 'terms': visible_terms, 'assessments': assessments,
        'agents': runs, 'fixed_agents': fixed_agents, 'fixed_charges': fixed_charges, 'native_bindings': bindings, 'preparation_requests': requests, 'receipts': receipts, 'continuations': continuations})
    response['Cache-Control'] = 'no-store'
    return response
