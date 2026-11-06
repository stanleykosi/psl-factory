"""Reviewed original planning-receipt transport. This service never sends a plan."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case,event
from apps.identity.models import Grant
from apps.identity.services import require
from apps.policy.factory_receipt_recovery_validators import COMPONENT,METHOD
from apps.policy.role_assignments import instant
from apps.policy.services import active_component,reference_values,decision_authority
from .models import FactoryWork,FactoryPlanningRecovery,FactoryPlanningReceipt,FactoryPlanningReceiptUse
from . import readiness
from .readiness_models import IntegrationAssessment


def requester_id(attempt):
    from .models import FactoryExecutionBinding
    # Historical identity, never the current policy's nominee or an inferred fallback.
    original=FactoryExecutionBinding.objects.filter(work=attempt.activity.work,created_at__lte=attempt.created_at).order_by('-sequence').first()
    return original.principal_id if original else attempt.activity.work.actor_id


def configured(work):
    config=active_component(COMPONENT,work.case);rule=reference_values(config)[0]
    if any(value is None for value in rule.values()):raise ValidationError('Configure the receipt recovery reviewer, responsibility, independence and validity window')
    if rule['method']!=METHOD or not instant(rule['valid_from'])<=timezone.now()<instant(rule['valid_until']):
        raise ValidationError('Current finite receipt recovery authority required')
    reviewer=get_user_model().objects.filter(pk=rule['reviewer_id'],is_active=True).first()
    if not reviewer:raise PermissionDenied('Current configured receipt reviewer required')
    from .factory import access
    access(reviewer,work.case,'factory.manage',work.definition)
    for action in ['integration.read','integration.source.read','integration.review']:require(reviewer,work.case,action)
    decision_authority(reviewer,work.case,rule['review_role'])
    return config,rule,reviewer


def destination(attempt,contract,actor):
    """Same original provider identity and reviewed successor; credentials alone may differ."""
    from adapters.readiness import binding
    from adapters.factory_planner_contracts import PROTOCOL
    work=attempt.activity.work;original=readiness.contract_for(work.case,attempt.result['contract'])
    readiness.readable(actor,work.case,True);readiness.contract_access(actor,original);readiness.contract_access(actor,contract)
    readiness.current_contract(contract)
    if contract.case_id!=work.case_id or contract.reference!=original.reference or contract.version<=original.version:
        raise ValidationError('Choose the reviewed successor of this original provider contract')
    for key in ['kind','family','implementation','principal_ref','contract_version','model_id','data_scope']:
        if contract.payload[key]!=original.payload[key]:raise ValidationError('Receipt recovery cannot change provider, principal, protocol, model or data scope')
    if contract.payload['contract_version']!=PROTOCOL or contract.payload['implementation']!='authenticated_json_v1' or 'receipt_lookup' not in contract.payload['capabilities']:
        raise ValidationError('Same authenticated planning receipt protocol required')
    public,private=binding(contract)
    for key in ['implementation','target','classification','auth_mode']:
        if public[key]!=attempt.result['binding'][key]:raise ValidationError('Receipt recovery cannot redirect the original destination')
    assessment=IntegrationAssessment.objects.filter(contract=contract).order_by('-pk').first()
    if not assessment or not assessment.result.get('capability_ready'):raise ValidationError('Current assessed and reviewed successor receipt destination required')
    review=readiness.review_current(assessment)
    return public,private,{'assessment':assessment.pk,'review':review.pk}


@transaction.atomic
def review(actor,work_id,expected,case_expected,attempt_id,contract_id,evidence_id,reason):
    from .factory import access
    from apps.agents.factory_coordinator import pending
    if any(type(n) is not int or n<1 for n in [expected,case_expected,attempt_id,contract_id,evidence_id]):raise ValidationError('Exact current work, project and receipt references required')
    work=FactoryWork.objects.select_for_update(of=('self',)).select_related('case','actor').get(pk=work_id)
    access(actor,work.case,'factory.manage',work.definition);work.case=lock_case(actor,work.case_id,'integration.review',case_expected)
    list(Grant.objects.select_for_update().filter(case=work.case).order_by('pk'))
    if work.revision!=expected:raise ValidationError('STALE_VERSION: refresh current receipt work')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: a worker owns the original request')
    attempt=pending(work)
    if attempt is None or attempt.pk!=attempt_id or FactoryPlanningReceipt.objects.filter(attempt=attempt).exists():raise ValidationError('Select the exact original unresolved planning request')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed credential recovery in at most2000 characters')
    config,rule,reviewer=configured(work)
    if actor.pk!=reviewer.pk:raise PermissionDenied('Only the configured receipt reviewer can authorise recovery')
    if rule['independent_of_requester'] and actor.pk==requester_id(attempt):raise PermissionDenied('Configured reviewer must be independent of the original requester')
    evidence=Evidence.objects.filter(pk=evidence_id,case=work.case,kind='policy_decision').first()
    if not evidence:raise ValidationError('Same-workspace human authority evidence required')
    contract=readiness.contract_for(work.case,contract_id)
    public,_,pins=destination(attempt,contract,actor)
    auth=readiness.authority(actor,contract,'review')
    previous=FactoryPlanningRecovery.objects.filter(attempt=attempt).order_by('-sequence').first()
    record=FactoryPlanningRecovery.objects.create(attempt=attempt,sequence=previous.sequence+1 if previous else 1,
        contract=contract,reviewer=actor,configuration=config,authority={'rule':rule,'readiness':auth,'pins':pins},
        binding=public,work_revision=work.revision,evidence=evidence,reason=reason)
    work.revision+=1;work.save(update_fields=['revision','updated_at'])
    event(actor,work.case,'factory.receipt_recovery_reviewed',work=work.pk,attempt=attempt.pk,recovery=record.pk,lookup_only=True)
    return record


def transport(attempt,actor):
    work=attempt.activity.work
    config,rule,reviewer=configured(work)
    record=FactoryPlanningRecovery.objects.filter(attempt=attempt).select_related('contract__case','reviewer').order_by('-sequence').first()
    if not record or record.configuration_id!=config.pk or record.reviewer_id!=reviewer.pk or record.authority['rule']!=rule:
        raise ValidationError('Original provider credentials changed; current per-request recovery review required')
    public,private,pins=destination(attempt,record.contract,actor)
    if public!=record.binding or pins!=record.authority['pins'] or readiness.authority(reviewer,record.contract,'review')!=record.authority['readiness']:
        raise ValidationError('Reviewed receipt destination or authority changed; review recovery again')
    return record,private


def attach(receipt,record):
    """Called in the receipt transaction; original receipt identity stays immutable."""
    use,created=FactoryPlanningReceiptUse.objects.get_or_create(receipt=receipt,defaults={'recovery':record})
    if not created and use.recovery_id!=record.pk:raise ValidationError('Conflicting original receipt transport provenance')
    return use
