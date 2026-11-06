from apps.core.evidence_access import public_evidence,restricted,public_timeline,public_agent_runs
import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import render, redirect
from apps.identity.services import visible_cases, require
from apps.policy.registry import components
from apps.policy.services import resolve, save_draft, transition, register_reference
from apps.policy.models import Configuration, RegisteredReference
from apps.agents.models import AgentRun
from apps.agents.services import extract_evidence
from apps.finance.models import Handoff, FinancialImport, InvoicePreparation, SignedBaselineIntake
from apps.finance.services import capture_import, validate_import, begin_invoice_preparation
from apps.pmo.models import Baseline, Decision
from apps.pmo.services import prepare_baseline, decide, sign_baseline, complete_milestone
from apps.baas.services import support_action
from apps.documents.services import review_document
from .forms import EvidenceForm, PolicyForm, ReferenceForm
from .services import add_evidence


def accessible_case(actor, case_id):
    try:
        return visible_cases(actor).get(pk=case_id)
    except Exception as exc:
        from .models import Case
        if isinstance(exc, Case.DoesNotExist):
            raise Http404
        raise

@login_required
def home(request):
    from apps.workflows.factory_views import index
    return index(request)

@login_required
def coverage(request):
    plan = json.loads((settings.BASE_DIR / 'contracts/implementation-coverage.json').read_text(encoding='utf-8'))
    return render(request, 'coverage.html', {'coverage': plan['rows']})

@login_required
def case_detail(request, case_id):
    case = accessible_case(request.user, case_id)
    evidence_form = EvidenceForm()
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            expected = int(request.POST['revision'])
            if action == 'evidence':
                evidence_form = EvidenceForm(request.POST)
                if not evidence_form.is_valid():
                    raise ValidationError(evidence_form.errors.as_text())
                add_evidence(request.user, case.pk, **evidence_form.cleaned_data, expected=expected)
            elif action == 'prepare':
                prepare_baseline(request.user, case.pk, int(request.POST['plan']), int(request.POST['costing']), int(request.POST['sow']), expected)
            elif action == 'decide':
                decide(request.user, case.pk, request.POST['role'], expected)
            elif action == 'sign':
                sign_baseline(request.user, case.pk, int(request.POST['evidence']), expected)
            elif action == 'complete':
                complete_milestone(request.user, case.pk, request.POST['name'], int(request.POST['evidence']), expected)
            elif action == 'extract':
                extract_evidence(request.user, case.pk, int(request.POST['evidence']), request.POST['process'])
            elif action == 'import':
                capture_import(request.user,case.pk,int(request.POST['evidence']),expected)
            elif action == 'validate_import':
                validate_import(request.user,case.pk,int(request.POST['batch']),expected)
            elif action == 'prepare_invoice':
                begin_invoice_preparation(request.user,case.pk,int(request.POST['handoff']),expected)
            elif action == 'review':
                review_document(request.user, case.pk, int(request.POST['evidence']), request.POST['verdict'], request.POST['note'], expected)
            elif action in ['respond', 'resolve', 'reopen']:
                support_action(request.user, case.pk, action, int(request.POST['evidence']), expected)
            else:
                raise ValidationError('Unknown operation')
            messages.success(request, 'Recorded. The timeline contains the result.')
            return redirect('case', case_id=case.pk)
        except (ValidationError, ValueError, KeyError, IntegrityError, Baseline.DoesNotExist, FinancialImport.DoesNotExist, Handoff.DoesNotExist) as exc:
            messages.error(request, str(exc))
            case.refresh_from_db()
    from apps.identity.models import Grant
    actions = set(Grant.objects.filter(case=case, user=request.user, active=True).values_list('action', flat=True))
    from apps.identity.intake import current as technical_authority
    from django.core.exceptions import PermissionDenied
    try:
        technical=technical_authority(request.user,case.tenant,'manage_access')
        can_manage_access=case.synthetic==(technical.value['classification']=='synthetic')
    except PermissionDenied:can_manage_access=False
    return render(request, 'case.html', {'case': case, 'actions': actions, 'can_manage_access':can_manage_access, 'evidence_form': evidence_form,
        'evidence': public_evidence(case.evidence.all()).order_by('-pk'), 'timeline': public_timeline(case).exclude(action__startswith='approval.').exclude(action__startswith='migration.').exclude(action__startswith='d03.').order_by('-pk')[:100],
        'baseline': Baseline.objects.filter(case=case).first(), 'decisions': Decision.objects.filter(case=case),
        'handoffs': Handoff.objects.filter(case=case) if 'finance.read' in actions else [],
        'baseline_intakes': SignedBaselineIntake.objects.filter(case=case) if 'finance.read' in actions else [],
        'imports': FinancialImport.objects.filter(case=case) if 'finance.read' in actions else [],
        'preparations': InvoicePreparation.objects.filter(handoff__case=case) if 'finance.read' in actions else [],
        'jobs': case.outbox_set.all() if 'workflow.read' in actions else [],
        'runs': public_agent_runs(AgentRun.objects.filter(case=case)) if 'agent.extract' in actions else []})

@login_required
def policy_workbench(request, case_id):
    from apps.policy.role_forms import RoleAssignmentsForm,DelegationsForm
    from apps.policy.role_assignments import draft as draft_roles,draft_delegations,SCHEMAS as ROLE_SCHEMAS
    from apps.policy.delegation_validators import SCHEMAS as DELEGATION_SCHEMAS
    case = accessible_case(request.user, case_id)
    require(request.user, case, 'policy.read')
    form = PolicyForm()
    role_form=RoleAssignmentsForm(case,request.POST if request.method=='POST' and request.POST.get('action')=='roles_draft' else None)
    delegation_form=DelegationsForm(case,request.POST if request.method=='POST' and request.POST.get('action')=='delegations_draft' else None)
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'reference':
                reference_form = ReferenceForm(request.POST)
                if not reference_form.is_valid():
                    raise ValidationError(reference_form.errors.as_text())
                register_reference(request.user,case.pk,**reference_form.cleaned_data)
            elif request.POST.get('action')=='delegations_draft':
                if not delegation_form.is_valid():raise ValidationError(delegation_form.errors.as_text())
                data=delegation_form.cleaned_data
                draft_delegations(request.user,case.pk,data['delegations'],data['evidence'].pk,data['effective_from'])
            elif request.POST.get('action')=='roles_draft':
                if not role_form.is_valid():raise ValidationError(role_form.errors.as_text())
                data=role_form.cleaned_data
                draft_roles(request.user,case.pk,data['assignments'],data['evidence'].pk,data['effective_from'])
            elif request.POST.get('action') == 'draft':
                form = PolicyForm(request.POST)
                if not form.is_valid():
                    raise ValidationError(form.errors.as_text())
                save_draft(request.user, case.pk, form.cleaned_data['envelope'])
            else:
                config = Configuration.objects.get(case=case, pk=request.POST['configuration'])
                transition(request.user, config.pk, request.POST['action'])
            messages.success(request, 'Policy history updated')
            return redirect('policy', case_id=case.pk)
        except (ValidationError, ValueError, KeyError, Configuration.DoesNotExist) as exc:
            messages.error(request, str(exc))
    statuses = []
    for key, component in components().items():
        r = resolve(key, case)
        statuses.append({'id': key, 'status': r.status, 'reason': r.reason, 'schema': json.dumps(component['value_schema'], indent=2)})
    configs = list(Configuration.objects.filter(case=case).order_by('-pk'))
    for config in configs:
        config.current_state = config.states.order_by('-pk').first().state
    response=render(request, 'policy.html', {'case': case, 'form': form, 'role_form':role_form,'role_schemas':json.dumps(ROLE_SCHEMAS,indent=2),'delegation_form':delegation_form,'delegation_schemas':json.dumps(DELEGATION_SCHEMAS,indent=2),'components': statuses, 'configs': configs, 'reference_form': ReferenceForm(), 'references': RegisteredReference.objects.filter(case=case).order_by('-pk')})
    response['Cache-Control']='no-store';return response
