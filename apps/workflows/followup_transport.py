"""Durable publication-to-current-source metadata handoff, never financial execution."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.identity.services import require
from apps.documents.contracts import validate,digest
from apps.policy.services import active_component,reference_values,resolve
from apps.policy.followup_transport_validators import OUTBOUND
from adapters.forecast import KEY
from adapters import finance_followup_protocol as wire,finance_followup_transport as adapter
from . import native_finance as d,finance_readback as readback
from .followup_transport_models import FinanceFollowupDispatch as Job

@transaction.atomic
def access(actor,p,purpose='operate'):
    m=d.get(actor,p.mapping.plan.case_id,p.mapping_id,purpose);d.principal(actor,m,purpose,d.rules(m)[1])
    require(actor,m.plan.case,'reconstitution.native_finance.transport')

def controls(actor,p):
    access(actor,p);cfg=active_component(OUTBOUND,p.mapping.plan.case);v=reference_values(cfg)[0]
    # Sending inert investigation metadata requires the exact historical published
    # request, not permission to re-publish a financial companion or a readback policy.
    pin,projection=readback.published_context(actor,p)
    binding,_=adapter.binding(p.mapping.plan.case,v)
    return {**pin,'transport_policy':cfg.pk},v,projection,binding

@transaction.atomic
def reserve(actor,case_id,packet_id,operation_key):
    p=readback.packet(actor,case_id,packet_id,'operate');validate(KEY,operation_key)
    from apps.core.models import Case
    Case.objects.select_for_update().get(pk=case_id)
    pin,v,projection,binding=controls(actor,p);key=digest({'transport':wire.FORMAT,'packet':p.pk,'key':operation_key})
    envelope={'format':wire.FORMAT,'operation_key':key,'sender_ref':v['sender_ref'],'destination_ref':v['destination_ref'],
        'projection':projection,'publication_receipt_sha256':pin['publication_sha256']}
    validate(wire.ENVELOPE,envelope)
    intent={'format':wire.FORMAT,'pin':pin,'rules':v,'binding':binding,'envelope':envelope}
    old=Job.objects.filter(operation_key=key).first()
    if old:
        if old.intent!=intent or old.actor_id!=actor.pk:raise ValidationError('Transport key binds another immutable request')
        return old
    return Job.objects.create(packet=p,operation_key=key,intent=intent,actor=actor)

@transaction.atomic
def retry(actor,case_id,job_id,operation='retry',reason='',expected=None):
    j=Job.objects.select_for_update().select_related('packet__mapping__plan__case').get(pk=job_id,packet__mapping__plan__case_id=case_id)
    access(actor,j.packet)
    if operation!='retry' or j.status not in ['held','unknown']:raise ValidationError('Reconcile only original held/unknown intake; no cancellation or replacement')
    j.status='pending';j.save(update_fields=['status']);return j

def run_once(transport=None):
    d.d.cold.control();transport=transport or adapter.FinanceFollowupTransport()
    with transaction.atomic():
        j=Job.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lt=timezone.now())).order_by('pk').first()
        if not j:return False
        j.status,j.fence,j.attempts='leased',j.fence+1,j.attempts+1;j.lease_until=timezone.now()+timedelta(seconds=j.intent['rules']['lease_seconds'])
        j.save(update_fields=['status','fence','attempts','lease_until']);pk,fence=j.pk,j.fence
    with transaction.atomic():
        j=Job.objects.select_for_update().select_related('packet__mapping__plan__case','packet__mapping__plan__recovery__plan__case','packet__observation','actor').get(pk=pk)
        if j.status!='leased' or j.fence!=fence:return True
        try:
            if type(transport) is not adapter.FinanceFollowupTransport and not j.packet.mapping.plan.case.synthetic:raise PermissionDenied('Fault adapters are synthetic only')
            receipt=transport.lookup(j)
            if receipt is None:
                pin,v,projection,binding=controls(j.actor,j.packet)
                if pin!=j.intent['pin'] or v!=j.intent['rules'] or projection!=j.intent['envelope']['projection'] or binding!=j.intent['binding'] or j.attempts>v['max_attempts']:raise ValidationError('Current transport controls/budget changed')
                receipt=transport.deliver(j)
            if j.lease_until<=timezone.now():raise ConnectionError('Transport fence expired; reconcile original acknowledgement')
            wire.result(receipt,j.intent['envelope'])
            j.status,j.receipt,j.error='confirmed',receipt,''
        except (ConnectionError,TimeoutError,OSError):j.status,j.error='unknown','source_intake_outcome_unresolved'
        except (ValidationError,PermissionDenied,ValueError):j.status,j.error='held','source_intake_controls_held'
        j.save(update_fields=['status','receipt','error'])
    return True

@transaction.atomic
def report(actor,case_id,job_id):
    j=Job.objects.select_related('packet__mapping__plan__case').get(pk=job_id,packet__mapping__plan__case_id=case_id);access(actor,j.packet,'read')
    return {'job':j.pk,'status':j.status,'attempts':j.attempts,'policy_status':resolve(OUTBOUND,j.packet.mapping.plan.case).status,
        'recorded_acknowledgement':j.receipt,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False,
        'next_steps':['Reconcile the original signed source receipt before any retry.','Source intake and Finance owner disposition are separate.','Use native readback and independent review for current source evidence.'],'effect_tools':[]}
