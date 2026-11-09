"""Routing metadata only: intent match is neither dispatch readiness nor approval."""
from django.core.exceptions import PermissionDenied,ValidationError
from django.db.models import Q
from apps.pmo import approvals
from apps.pmo.models import ApprovalRouteJob
from apps.policy.approval_validators import ROUTES,CONTRACTS

KEY='pmo.approval_routing_jobs'

def query(actor,config):
    if actor is None:raise PermissionDenied('Current approval observer required')
    approvals.readable(actor,config.case)
    clause=Q(**{'intent__authority__'+config.component:config.pk})
    if config.component==ROUTES:clause |= Q(intent__policies__0=config.pk)
    elif config.component==CONTRACTS:clause |= Q(intent__policies__1=config.pk)
    return ApprovalRouteJob.objects.filter(request__case=config.case).filter(clause).order_by('pk')

def authorize_row(actor,case,row):
    approvals.readable(actor,case)
    if row.request.case_id!=case.pk:raise PermissionDenied('Select this case routing metadata')

def project(row):
    from apps.pmo.approval_routing import intent
    from adapters.approvals import InternalApprovalRoutingAdapter
    from apps.documents.contracts import digest
    from adapters.policy_impact import effect
    try:
        current=intent(row.actor,row.request,row.purpose,row.intent.get('factory_execution',{}).get('work'))==row.intent
    except (PermissionDenied,ValidationError):current=False
    receipt=None;conflict=False
    try:receipt=InternalApprovalRoutingAdapter().lookup(row)
    except ValidationError:conflict=True
    if conflict:state='receipt_conflict_requires_reconciliation'
    elif receipt:state=effect(row.status,receipt)
    elif row.status in ('cancelled','replaced'):state='historical_terminal_routing'
    else:state=effect(row.status,None)
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'approvals',
        'request':row.request_id,'generation':row.generation,'purpose':row.purpose,
        'status':row.status,'intent_sha256':digest(row.intent),
        'receipt':receipt.pk if receipt else None,'receipt_conflict':conflict,
        'native_intent_current':current,'state':state,
        'dispatch_readiness_evaluated':False,'dispatch_authorized':False,
        'approval_granted':False,'effects_performed':False}
