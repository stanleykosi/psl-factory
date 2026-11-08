"""Receipt-first internal requests. Delivery never records a department approval."""
from datetime import timedelta
from django.db import transaction,IntegrityError
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest
from adapters.approvals import InternalApprovalRoutingAdapter
from . import approvals as d
from .models import ApprovalRouteJob,ApprovalRouteReceipt

def intent(a,r,purpose,factory_work_id=None):
 d.current_request(r);d.readable(a,r.case);require(a,r.case,'approval.route')
 p,q,route,contract,settings=d.rules(r.case,r.kind);accepted=d.approved_contract(r.case,r.kind)
 owner=__import__('django.contrib.auth',fromlist=['get_user_model']).get_user_model().objects.get(pk=route['owner_id'])
 authority=d.owner_authority(owner,r.case,route,'approval.receive')
 if route['route_mode']!='internal_inbox_v1':raise ValidationError('Remote routing adapter is not configured; internal inbox is the implemented channel')
 if route['gate_kind']!=r.gate_kind or any(r.subject[k] is None for k in contract['required_subject_fields']):raise ValidationError('Exact configured prerequisite subject required')
 if purpose not in ['request','reminder']:raise ValidationError('Choose request or reminder')
 if purpose=='reminder' and not contract['reminders_enabled']:raise ValidationError('Owner contract does not enable reminders')
 value={'policies':[p.pk,q.pk],'contract_review':accepted.pk,'recipient':owner.pk,'authority':authority,'lease_seconds':settings['lease_seconds'],'max_attempts':settings['max_attempts'],'public':{'request_id':r.pk,'reference':r.reference,'version':r.version,'kind':r.kind,'subject':r.subject,'source_owner':route['source_owner'],'purpose':purpose,'approval_granted':False}}
 if factory_work_id is not None:
  from apps.workflows.models import FactoryWork
  from apps.workflows import factory
  from apps.core.models import Audit
  w=FactoryWork.objects.select_related('case').filter(pk=factory_work_id,case=r.case,definition='planning/v1',actor=a).first()
  if not w:raise ValidationError('Exact factory planning execution principal required; recovery cannot impersonate the initiator')
  factory.access(a,r.case,'factory.execute',w.definition);profile,_=factory.profile(w)
  from apps.pmo import planning
  planning.packet(r.case,w.source_head_id)
  if w.cancel_requested or w.status in ['verified','cancelled','followup_needed']:raise ValidationError('Factory planning routing is stopped')
  marker=Audit.objects.filter(case=r.case,action='planning.requests_opened',data__packet_id=w.source_head_id).order_by('-pk').first()
  if not marker or r.pk not in marker.data['requests'].values():raise ValidationError('Exact current factory planning subject required')
  value['factory_execution']={'schema':'factory-planning-routing/v1','work':w.pk,'profile':profile.pk,'executor':a.pk}
 return value

def guard_reserve(a,c,request_id,purpose='request',factory_work_id=None):
 """Read-only native reservation prerequisites; observation grants no dispatch authority."""
 d.readable(a,c);require(a,c,'approval.route')
 if c.kind!='project':raise ValidationError('Project coordination case required')
 r=d.exact(c,request_id);value=intent(a,r,purpose,factory_work_id)
 jobs=ApprovalRouteJob.objects.filter(request=r).order_by('-generation');last=jobs.first()
 if purpose=='request' and last:
  original=jobs.filter(purpose='request').exclude(status__in=['cancelled','replaced']).order_by('-pk').first()
  if original and original.intent==value and original.status not in ['cancelled','replaced']:return r,value,original,last.generation+1
  raise ValidationError('Use explicit held-job intent replacement or a successor request')
 if last and (last.status in ['pending','unknown','leased','held']):raise ValidationError('Reconcile outstanding routing before another reminder')
 if purpose=='reminder':
  _,_,_,contract,_=d.rules(c,r.kind)
  receipts=ApprovalRouteReceipt.objects.filter(job__request=r).order_by('-created_at')
  latest=receipts.first()
  if not latest or (timezone.now()-latest.created_at).total_seconds()<contract['minimum_reminder_interval_seconds']:raise ValidationError('Confirmed receipt and configured reminder interval required')
  if receipts.filter(job__purpose='reminder').count()>=contract['maximum_reminders']:raise ValidationError('Configured reminder budget exhausted')
 generation=last.generation+1 if last else 1
 return r,value,None,generation

@transaction.atomic
def reserve(a,case_id,request_id,purpose='request',expected=None,factory_work_id=None):
 c=d.locked(a,case_id,'approval.route',expected)
 r,value,existing,generation=guard_reserve(a,c,request_id,purpose,factory_work_id)
 if existing:return existing
 j=ApprovalRouteJob.objects.create(request=r,actor=a,generation=generation,purpose=purpose,operation_key=digest({'tenant':c.tenant,'request':r.pk,'generation':generation,'purpose':purpose}),intent=value)
 event(a,c,'approval.route_reserved',job=j.pk,approval_granted=False);bump(c);return j

@transaction.atomic
def claim(case_id=None,job_id=None):
 now=timezone.now();query=ApprovalRouteJob.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now))
 if case_id is not None:query=query.filter(request__case_id=case_id)
 if job_id is not None:query=query.filter(pk=job_id)
 j=query.order_by('pk').first()
 if not j:return None
 j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence

def check(j,fence):
 if j.status!='leased' or j.fence!=fence or j.lease_until<=timezone.now():raise ValidationError('Expired prerequisite routing worker fence')

@transaction.atomic
def finish(pk,fence,status,error=''):
 initial=ApprovalRouteJob.objects.select_related('request').get(pk=pk);Case.objects.select_for_update().get(pk=initial.request.case_id)
 j=ApprovalRouteJob.objects.select_for_update().get(pk=pk);check(j,fence);j.status=status;j.error=error[:400];j.save(update_fields=['status','error']);event(j.actor,j.request.case,'approval.route_'+status,job=j.pk)

@transaction.atomic
def deliver_local(pk,fence):
 initial=ApprovalRouteJob.objects.select_related('request').get(pk=pk);c=Case.objects.select_for_update().get(pk=initial.request.case_id)
 j=ApprovalRouteJob.objects.select_for_update().select_related('request__case','request__candidate__requirements').get(pk=pk);check(j,fence);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
 from apps.workflows.readiness import gate
 gate(c,'approval')
 if intent(j.actor,j.request,j.purpose,j.intent.get('factory_execution',{}).get('work'))!=j.intent:raise ValidationError('Current owner, subject, contract or authority differs from reserved routing intent')
 receipt=ApprovalRouteReceipt.objects.create(job=j,recipient_id=j.intent['recipient'],operation_key=j.operation_key,payload=j.intent['public'])
 event(j.actor,c,'approval.request_received',receipt=receipt.pk,approval_granted=False);return receipt.pk

def run_once(adapter=None,case_id=None,job_id=None,lookup_only=False):
 if type(lookup_only) is not bool:raise ValidationError('Choose an explicit receipt-only routing mode')
 adapter=adapter or InternalApprovalRoutingAdapter();lease=claim(case_id,job_id)
 if not lease:return False
 pk,fence=lease;j=ApprovalRouteJob.objects.select_related('request__case').get(pk=pk)
 if type(adapter) is not InternalApprovalRoutingAdapter and not j.request.case.synthetic:finish(pk,fence,'held','Fault adapters restricted to synthetic cases');return True
 try:
  if adapter.lookup(j):finish(pk,fence,'confirmed');return True
  if lookup_only:raise TimeoutError('Receipt-only reconciliation found no original routing receipt; no dispatch authorised')
  if j.attempts>j.intent['max_attempts']:finish(pk,fence,'held','Attempt budget exhausted; operator reconciliation required');return True
  adapter.deliver(pk,fence)
 except (TimeoutError,ConnectionError):finish(pk,fence,'unknown','Outcome unknown; lookup actual receipt before retry')
 except IntegrityError:finish(pk,fence,'held','Receipt conflict; reconcile the logical operation')
 except (ValidationError,PermissionDenied,ValueError) as exc:finish(pk,fence,'held',str(exc))
 else:finish(pk,fence,'confirmed')
 return True

@transaction.atomic
def operate(a,case_id,job_id,action,reason,expected=None):
 c=d.locked(a,case_id,'approval.operate',expected)
 if not isinstance(reason,str) or not 1<=len(reason.strip())<=400:raise ValidationError('Bounded operator reason required')
 j=ApprovalRouteJob.objects.select_for_update().select_related('request__case','request__candidate__requirements').filter(pk=job_id,request__case=c).first()
 if not j or action not in ['cancel','retry','replace_intent']:raise ValidationError('Exact case job and recovery action required')
 if j.status in ['confirmed','cancelled','replaced'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Terminal or actively leased routing cannot be changed')
 if InternalApprovalRoutingAdapter().lookup(j):raise ValidationError('Actual receipt exists; let the worker reconcile it')
 if j.status=='unknown':raise ValidationError('Unknown outcome requires worker receipt lookup before operator retry')
 if action=='cancel':j.status='cancelled'
 else:
  if j.status!='held':raise ValidationError('Only held work needs operator retry')
  value=intent(a,j.request,j.purpose,j.intent.get('factory_execution',{}).get('work'))
  if action=='retry':
   if value!=j.intent or a.pk!=j.actor_id:raise ValidationError('Intent changed; explicitly replace it')
   j.status='pending';j.attempts=0
  else:
   j.status='replaced';j.save(update_fields=['status'])
   generation=ApprovalRouteJob.objects.filter(request=j.request).order_by('-generation').first().generation+1
   ApprovalRouteJob.objects.create(request=j.request,actor=a,generation=generation,purpose=j.purpose,operation_key=digest({'tenant':c.tenant,'request':j.request_id,'generation':generation,'purpose':j.purpose}),intent=value)
 j.error=reason;j.save(update_fields=['status','attempts','error']);event(a,c,'approval.route_operator_'+action,job=j.pk,reason=reason);bump(c);return j
