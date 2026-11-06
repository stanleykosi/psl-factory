"""Exact AF13 protection inventory in shared portable metadata operations."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from apps.documents.contracts import digest
from apps.policy.services import active_component,reference_values
from adapters.accepted_protection_operations import AcceptedProtectionOperatorAdapter as Adapter

FIELD='private_protection_packet_ids'
ROWS='accepted_private_protection'
SCHEMA='accepted_private_protection_v1'
COMPONENT='OPS.accepted_protection_rules'

def ids(p):return p.payload.get(FIELD,[])

def plan_access(a,p):
 from .operator_models import RecoveryPlan
 for prior in RecoveryPlan.objects.filter(case=p.case,reference=p.reference):
  for pk in ids(prior):Adapter().access(a,Adapter().packet(p.case,pk))

def source_plans(c,selected):
 from .operator_models import RecoveryPlan
 seen=set();pending=list(selected)
 while pending:
  b=Adapter().packet(c,pending.pop());pk=b.snapshot['evidence']['plan']
  if pk in seen:continue
  seen.add(pk);p=RecoveryPlan.objects.get(case=c,pk=pk)
  pending.extend(ids(p))
 return RecoveryPlan.objects.filter(case=c,pk__in=seen)

def validate_plan(a,c,payload,reference):
 selected=payload.get(FIELD,[])
 if not selected:return
 if payload['scope']!='portable_case_metadata_v1':raise ValidationError('Protection acceptance permits portable metadata only')
 for pk in selected:
  b=Adapter().packet(c,pk);Adapter().access(a,b)
  if {COMPONENT,'INT.accepted_protection_readiness'} & set(b.package.payload['policy_components']):raise ValidationError('Protection source package cannot depend on its downstream operator inventory')
  if not set(b.package.payload['process_ids'])<=set(payload['process_ids']):raise ValidationError('Exact protection packet process scope required')
 if source_plans(c,selected).filter(reference=reference).exists():raise ValidationError('Protection metadata plan cannot supersede its own source closure')

def validate_policy(c,v,runtime=False):
 for pk in v[FIELD]:
  b=Adapter().packet(c,pk)
  if {COMPONENT,'INT.accepted_protection_readiness'} & set(b.package.payload['policy_components']):raise ValidationError('Protection source package cannot depend on its downstream operator inventory')
 if runtime:return
 from apps.policy.operator_validators import OPERATOR
 operators=reference_values(active_component(OPERATOR,c))[0]
 try:
  for row in operators['operators']:
   if set(row['purposes']) & {'export','backup','restore','review','recover'}:
    a=get_user_model().objects.get(pk=row['user_id'],is_active=True)
    for pk in v[FIELD]:Adapter().access(a,Adapter().packet(c,pk))
 except (PermissionDenied,get_user_model().DoesNotExist):raise ValidationError('Actual original protection source/export grants required for operators') from None

def rules(p):
 if not ids(p):return None
 policy=active_component(COMPONENT,p.case);v=reference_values(policy)[0]
 if not set(ids(p))<=set(v[FIELD]) or v['private_disclosure']!='accepted_metadata_only':raise ValidationError('Configure exact accepted protection inventory and disclosure')
 return policy.pk

def add(a,c,m,selected,max_records):
 if not selected:return m
 rows=[Adapter().capture(a,c,pk) for pk in selected]
 from .private_readiness_operations import count
 if len(rows)+len(m['evidence'])+len(m['jobs'])+count(m)>max_records:raise ValidationError('Accepted protection metadata exceeds record budget')
 return dict(m,protection_metadata_schema=SCHEMA,accepted_private_protection=rows,current_authority_restored=False)

def historical(a,c,m):
 if ROWS not in m:return
 allowed={'schema','case_id','evidence','jobs','source_grants','omitted_families','evidence_bodies_included','credentials_included','business_jobs_reenacted','private_metadata_schema','accepted_private_readiness','protection_metadata_schema',ROWS,'current_authority_restored'}
 if set(m)-allowed or any(m.get(k) is not False for k in ['evidence_bodies_included','credentials_included','business_jobs_reenacted']):raise ValidationError('Closed portable protection metadata manifest required')
 rows=m[ROWS]
 if m.get('protection_metadata_schema')!=SCHEMA or m.get('current_authority_restored') is not False or not isinstance(rows,list) or not rows:raise ValidationError('Explicit protection metadata extension required')
 if len({r['packet'] for r in rows})!=len(rows):raise ValidationError('Duplicate protection packet')
 for row in rows:Adapter().historical(a,c,row)

def current(a,p,m):
 rows=m.get(ROWS,[])
 if [r['packet'] for r in rows]!=ids(p):raise ValidationError('Exact selected protection inventory required')
 if not ids(p):return
 plan_access(a,p);historical(a,p.case,m)
 for row in rows:
  if Adapter().capture(a,p.case,row['packet'])!=row:raise ValidationError('Protection owner acceptance changed; preserve history and capture a new export')
