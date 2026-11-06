"""Explicit private packet inventory for shared metadata protection; no business replay."""
from django.db import transaction
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.documents.contracts import digest
from apps.policy.services import active_component,reference_values
from apps.policy.operator_validators import OPERATOR
from adapters.private_readiness_operations import AcceptedReadinessOperatorAdapter as Adapter

from . import accepted_protection_operations as protection
from apps.finance.acceptance_evaluation import evaluated

FIELD='private_readiness_packet_ids'
EXTENSION='accepted_private_readiness_v1'

def ids(p):return p.payload.get(FIELD,[])

def has_private(p):return bool(ids(p) or protection.ids(p))

def plan_access(a,p):
 protection.plan_access(a,p)
 from .operator_models import RecoveryPlan
 for old in RecoveryPlan.objects.filter(case=p.case,reference=p.reference):
  for pk in ids(old):Adapter().access(a,Adapter().packet(p.case,pk))

def validate_plan(a,c,payload):
 values=payload.get(FIELD,[])
 if not values:return
 if payload['scope']!='portable_case_metadata_v1':raise ValidationError('Private packet scope is portable metadata only')
 for pk in values:
  b=Adapter().packet(c,pk);Adapter().access(a,b)
  if not set(b.package.payload['process_ids'])<=set(payload['process_ids']):raise ValidationError('Recovery plan must include the exact selected packet process scope')

def rules(p,value):
 protection.rules(p)
 selected=ids(p)
 if selected and (not set(selected)<=set(value.get(FIELD,[])) or value.get('private_disclosure')!='accepted_metadata_only'):raise ValidationError('Configure v2 private packet protection inventory/disclosure')

def validate_policy(c,v,runtime=False):
 for pk in v[FIELD]:Adapter().packet(c,pk)
 if not runtime:
  from django.contrib.auth import get_user_model
  operators=reference_values(active_component(OPERATOR,c))[0]
  try:
   for row in operators['operators']:
    if set(row['purposes']) & {'export','backup','restore','review','recover'}:
     a=get_user_model().objects.get(pk=row['user_id'])
     for pk in v[FIELD]:Adapter().access(a,Adapter().packet(c,pk))
  except PermissionDenied:raise ValidationError('Actual original private source/export grants required for protection operators') from None

def add(a,c,manifest,selected,max_records):
 if not selected:return manifest
 rows=[Adapter().capture(a,c,pk) for pk in selected]
 if len(rows)+len(manifest['evidence'])+len(manifest['jobs'])>max_records:raise ValidationError('Private metadata export exceeds configured record budget')
 return dict(manifest,private_metadata_schema=EXTENSION,accepted_private_readiness=rows,current_authority_restored=False)

def historical(a,c,m):
 protection.historical(a,c,m)
 rows=m.get('accepted_private_readiness',[])
 if not rows:return
 if m.get('private_metadata_schema')!=EXTENSION or m.get('current_authority_restored') is not False:raise ValidationError('Explicit historical metadata extension required')
 if len({r['packet'] for r in rows})!=len(rows):raise ValidationError('Duplicate private metadata packet')
 for row in rows:Adapter().historical(a,c,row)

def current(a,p,m):
 protection.current(a,p,m)
 plan_access(a,p);rows=m.get('accepted_private_readiness',[])
 if [r['packet'] for r in rows]!=ids(p):raise ValidationError('Exact selected private packet inventory required')
 historical(a,p.case,m)
 for row in rows:
  if Adapter().capture(a,p.case,row['packet'])!=row:raise ValidationError('Private acceptance changed; preserve sealed history and prepare a new export')

def count(m):return len(m.get('accepted_private_readiness',[]))+len(m.get(protection.ROWS,[]))

def private_job(c,pk):
 from .operator_models import RecoveryJob
 from django.db.models import Q
 return RecoveryJob.objects.filter(Q(plan__payload__has_key=FIELD)|Q(plan__payload__has_key=protection.FIELD),plan__case=c,pk=pk).exists()

def audit(a,c,p,action,**data):
 from apps.core.services import event
 event(a,c,('agent.data.private_readiness_ops.' if has_private(p) else 'ops.')+action,**data)

@transaction.atomic
@evaluated
def investigate(a,case_id):
 from .operator_recovery import locked,config
 from .operator_models import RecoveryPlan,RecoveryJob
 from apps.policy.operator_validators import PROTECTION
 c=locked(a,case_id,'agent.operations');rows=[]
 from django.db.models import Q
 for p in RecoveryPlan.objects.filter(Q(payload__has_key=FIELD)|Q(payload__has_key=protection.FIELD),case=c).order_by('-pk')[:30]:
  try:plan_access(a,p)
  except PermissionDenied:continue
  try:
   from .protection import current_plan
   current_plan(p)
   _,v=config(c,PROTECTION);rules(p,v)
   for pk in ids(p):Adapter().capture(a,c,pk)
   for pk in protection.ids(p):protection.Adapter().capture(a,c,pk)
   ready=True
  except (ValidationError,PermissionDenied,ConnectionError):ready=False
  jobs=list(RecoveryJob.objects.filter(plan=p).values('id','kind','status','attempts')[:30])
  inventory='OPS.accepted_protection_rules'+(' and Finance v2 inventory' if ids(p) else '') if protection.ids(p) else 'Finance v2 inventory'
  question='Use separate human protection review after verified metadata receipts; effect authority and target controls remain separate.' if ready else 'Recheck current plan, exact source grants, packet successor/owner review and '+inventory+' before a new effect.'
  if any(j['status']=='unknown' for j in jobs):question='Reconcile the original committed receipt before retry; do not reset uncertain work.'
  rows.append({'plan':p.pk,'packets':ids(p),'protection_packets':protection.ids(p),'new_effect_ready':ready,'readiness_scope':'current_plan_and_selected_metadata_only','jobs':jobs,'question':question,'current_authority_restored':False})
 return {'findings':rows,'effect_tools':[],'persisted_agent_run':False}
