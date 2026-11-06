"""Live source-authorised private guidance. No generic AgentRun persistence or recovery effect."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.identity.services import require
from apps.baas import support_release as d
from apps.workflows.operator_inventory import jobs
from apps.workflows import readiness

@transaction.atomic
def investigate(actor,case_id):
 c=d.native.locked(actor,case_id,'agent.operations');d.access(actor,c);require(actor,c,'ops.read');require(actor,c,'integration.read')
 rows,_,_=jobs(actor,c)
 findings=[]
 for row in rows:
  if row['family']!='supportresponse':continue
  question='Inspect original receipt before considering any operator recovery.'
  if row['status']=='unknown' or row['lease_expired']:question='Run the case-scoped response worker to reconcile the original receipt; never force retry or cancel an uncertain effect.'
  elif row['status']=='held':question='Review current source/draft approval, human release, recipient grants, readiness and original attempt budget; only the native recovery service can retry.'
  elif row['status']=='confirmed':question='Preserve the stored internal receipt; customer delivery and response time still require separate evidence.'
  findings.append({'job':row['id'],'status':row['status'],'question':question,'source_url':row['source_url']})
 try:gate=readiness.gate(c,'supportresponse');state='reviewed' if gate else 'not_enrolled'
 except (ValidationError,PermissionDenied,ConnectionError):state='held'
 return {'family':'supportresponse','jobs':findings,'readiness':state,'recovery_executed':False,'source_body_read':False,'customer_delivery_verified':False,'response_clock_attested':False,'persisted_in_generic_agent_run':False}
