from django.db import transaction
from apps.finance.acceptance_evaluation import evaluated
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.pmo.services import subject
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.readiness_validators import ADAPTER,PROVIDER
from adapters.forecast import obj,KEY
from adapters.costing import read,ID
from adapters.readiness import binding,CAPS,VERSION
from .operator_inventory import ROUTES,family_access,can_private,PRIVATE_FAMILY,PRIVATE_FAMILIES,lock_scope
from .readiness_models import IntegrationContract,IntegrationProbe,IntegrationObservation,IntegrationAssessment,IntegrationReview,IntegrationSelection
NULLKEY={'anyOf':[VERSION,{'type':'null'}]}
CONTRACT=obj({'kind':{'enum':['adapter','provider']},'family':{'enum':list(ROUTES)+['provider']},'implementation':{'enum':['internal_postgres_session_v1','authenticated_json_v1','reference_only']},'target_key':{'anyOf':[{'type':'string','pattern':'^(internal:[a-z]+|endpoint:[a-z][a-z0-9_.-]{0,79})$'},{'type':'null'}]},'credential_ref':{'anyOf':[{'type':'string','pattern':'^(runtime:postgres|secret:[a-z][a-z0-9_.-]{0,79})$'},{'type':'null'}]},'credential_revision':NULLKEY,'principal_ref':{'anyOf':[{'type':'string','pattern':'^principal:[A-Za-z0-9_.@-]{1,80}$'},{'type':'null'}]},'contract_version':NULLKEY,'model_id':NULLKEY,'capabilities':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':CAPS}},'data_scope':{'const':'public_canary_and_scoped_receipt_metadata_only'}})
SUPPLIED=obj({'contract_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'kind':{'enum':['health','receipt','evaluation']},'outcome':{'enum':['passed','failed','unknown','unavailable']},'recorded_at':{'type':'string'},'source_ref':KEY})

def readable(a,c,private=False):
 if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Current active integration principal required')
 require(a,c,'case.read');require(a,c,'integration.read')
 if private:require(a,c,'integration.source.read')
def locked(a,case_id,action,expected=None):
 from .operator_inventory import lock_scope
 lock_scope(case_id)
 c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c);return c
def contract_for(c,pk):
 r=IntegrationContract.objects.select_related('case','actor').filter(case=c,pk=pk).first()
 if not r:raise ValidationError('Exact case contract required')
 return r
def current_contract(r):
 if IntegrationContract.objects.filter(case=r.case,reference=r.reference,version__gt=r.version).exists():raise ValidationError('Contract superseded')
def rules(r):
 from .accepted_protection_readiness import binding as accepted_binding,policy as accepted_policy
 from .private_protection_readiness import binding as private_binding
 from .private_file_readiness import binding as file_binding
 from apps.policy.readiness_validators import PRIVATE_COMPONENT,ACCEPTED_COMPONENT
 p=active_component(ACCEPTED_COMPONENT if accepted_binding(r) else PRIVATE_COMPONENT if private_binding(r) or file_binding(r) else ADAPTER if r.payload['kind']=='adapter' else PROVIDER,r.case);v=reference_values(p)[0]
 accepted_policy(r,v)
 from apps.finance.publication_readiness import policy
 policy(r,v)
 from .private_protection_readiness import policy as private_policy
 private_policy(r,v)
 from .private_file_readiness import policy as file_policy
 file_policy(r,v);return p,v
def authority(a,r,purpose):
 readable(a,r.case,True);require(a,r.case,'integration.'+purpose);contract_access(a,r)
 if r.payload['kind']=='adapter':require(a,r.case,ROUTES[r.payload['family']][2])
 p,v=rules(r);key='probe' if purpose=='probe' else 'reviewer';userkey='probe_user_id' if purpose=='probe' else 'reviewer_id';role=v['probe_role' if purpose=='probe' else 'reviewer_role']
 if a.pk!=v[userkey]:raise PermissionDenied('Exact configured integration principal required')
 return {'policy':p.pk,'role':role,'role_authority':decision_authority(a,r.case,role)}

@transaction.atomic
@evaluated
def capture(a,case_id,reference,payload,evidence_id,expected=None,predecessor=None,native_publication_job=None,native_protection_job=None,native_file_job=None,native_accepted_protection_job=None):
 c=locked(a,case_id,'integration.capture',expected);readable(a,c,True);validate(KEY,reference);validate(CONTRACT,payload);private_payload_access(a,c,payload);e=subject(c,evidence_id,'integration_contract')
 if (payload['kind']=='provider')!=(payload['family']=='provider') or payload['kind']=='provider' and payload['implementation']=='internal_postgres_session_v1':raise ValidationError('Exact adapter/provider family required')
 if 'health' not in payload['capabilities'] or payload['kind']=='adapter' and 'evaluation' in payload['capabilities']:raise ValidationError('Reviewed health/capability set required')
 from apps.finance import publication_readiness as native
 from . import private_protection_readiness as private
 from . import private_file_readiness as file
 from . import accepted_protection_readiness as accepted
 if sum(x is not None for x in [native_publication_job,native_protection_job,native_file_job,native_accepted_protection_job])>1:raise ValidationError('Choose one exact native source')
 context=native.prepare(a,c,native_publication_job,payload) if native_publication_job is not None else None
 private_context=private.prepare(a,c,native_protection_job,payload) if native_protection_job is not None else None
 file_context=file.prepare(a,c,native_file_job,payload) if native_file_job is not None else None
 accepted_context=accepted.prepare(a,c,native_accepted_protection_job,payload) if native_accepted_protection_job is not None else None
 old=IntegrationContract.objects.filter(case=c,reference=reference).order_by('-version').first()
 if old:contract_access(a,old)
 old_binding=native.binding(old) if old else None
 old_private=private.binding(old) if old else None
 old_file=file.binding(old) if old else None
 old_accepted=accepted.binding(old) if old else None
 if old_accepted and accepted_context is None:raise ValidationError('AF13 native history cannot become public or another native kind')
 if old_file and file_context is None:raise ValidationError('Private file history cannot become public or another native kind')
 if old_private and private_context is None:raise ValidationError('Private protection history cannot become public')
 if old_binding and context is None:raise ValidationError('Native contract history cannot become a public reference')
 if old and old.sha256==digest(payload) and (old_binding.job_id if old_binding else None)==native_publication_job and (old_private.job_id if old_private else None)==native_protection_job and (old_file.job_id if old_file else None)==native_file_job and (old_accepted.job_id if old_accepted else None)==native_accepted_protection_job:return old
 for historical in IntegrationContract.objects.filter(case=c,reference=reference):contract_access(a,historical)
 if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit predecessor required')
 row=IntegrationContract.objects.create(case=c,reference=reference,version=old.version+1 if old else 1,payload=payload,sha256=digest(payload),evidence=e,actor=a)
 if context:native.bind(a,row,context)
 if private_context:private.bind(a,row,private_context)
 if file_context:file.bind(a,row,file_context)
 if accepted_context:accepted.bind(a,row,accepted_context)
 audit(a,c,'integration.contract',row,contract=row.pk);bump(c);return row

def timestamp(value):
 from adapters.hrfinance import timestamp as parse
 return parse(value)
@transaction.atomic
def supplied(a,case_id,contract_id,key,evidence_id,expected=None):
 c=locked(a,case_id,'integration.capture',expected);readable(a,c,True);r=contract_for(c,contract_id);contract_access(a,r);validate(KEY,key)
 if key.startswith('native:'):raise ValidationError('Reserved native receipt namespace')
 e=subject(c,evidence_id,'integration_report');v=read(e.body,SUPPLIED)
 if v['contract_sha256']!=r.sha256 or timestamp(v['recorded_at'])>timezone.now():raise ValidationError('Exact contract and actual observation timestamp required')
 old=IntegrationObservation.objects.filter(contract=r,external_key=key).first();payload=dict(v,classification='supplied_report',authenticated_transport=False)
 if old:
  if old.sha256!=digest(payload):raise ValidationError('Conflicting report identity')
  return old
 o=IntegrationObservation.objects.create(contract=r,external_key=key,payload=payload,sha256=digest(payload),actor=a,evidence=e);audit(a,c,'integration.supplied',r,observation=o.pk);bump(c);return o

def source_job(a,c,family,pk,contract=None):
 from django.apps import apps
 if family not in ROUTES:raise ValidationError('Reviewed source family required')
 from .operator_inventory import source_query,job_access
 from .private_readiness_operations import has_private
 family_access(a,c,family);j=source_query(c,family).filter(pk=pk).first()
 if not j:raise ValidationError('Exact case source job required')
 job_access(a,c,family,j)
 if family=='protection' and has_private(j.plan):
  from .private_protection_readiness import check
  if j.kind in ['export','backup']:
   from .private_file_readiness import check
  if j.plan.payload.get('private_protection_packet_ids'):
   from .accepted_protection_readiness import check
  b=check(a,contract) if contract is not None else None
  if not b or b.job_id!=j.pk:raise ValidationError('Private protection receipts require an exact private readiness binding; use source-authorised operator receipt diagnostics')
 return j
def lookup_source(family,j):
 if family=='financefollowup':
  from adapters.finance_followup_transport import FinanceFollowupTransport
  return FinanceFollowupTransport().lookup(j)
 if family=='ledgerdata':
  from adapters.ledger_operations import FinanceReceiptAdapter
  return FinanceReceiptAdapter().lookup(j)
 if family=='supportchannel':
  from adapters.support_channel import SupportChannelAdapter
  return SupportChannelAdapter().lookup(j)
 if family==PRIVATE_FAMILY:
  from adapters.support_response import InternalSupportResponseAdapter
  return InternalSupportResponseAdapter().lookup(j)
 if family=='handoff':
  from adapters.finance import InternalFinanceAdapter
  return InternalFinanceAdapter().lookup(j.operation_key,j.payload)
 if family=='publication':
  from adapters.publications import InternalPublicationAdapter
  return InternalPublicationAdapter().lookup(j.publication)
 if family=='invoice':
  from adapters.invoices import InternalInvoiceAdapter
  return InternalInvoiceAdapter().lookup(j)
 if family=='engineering':
  from adapters.reconciliation import InternalEngineeringAdapter
  return InternalEngineeringAdapter().lookup(j)
 if family=='partner':
  from adapters.partner_operations import InternalPartnerFinanceAdapter
  return InternalPartnerFinanceAdapter().lookup(j)
 if family=='approval':
  from adapters.approvals import InternalApprovalRoutingAdapter
  return InternalApprovalRoutingAdapter().lookup(j)
 from adapters.operator_protection import restore_receipt
 if j.kind!='restore':raise ValidationError('Isolated target receipt probe requires a restore job')
 return restore_receipt(j)

@transaction.atomic
@evaluated
def snapshot(r):
 current_contract(r);p,v=rules(r);b,_=binding(r);required=['health']
 if r.payload['kind']=='provider':required.append('evaluation')
 elif v['require_receipt_probe']:required.append('receipt')
 findings=[];heads=[]
 if b['classification']=='synthetic_authenticated_http' and not v['allow_synthetic_target']:findings.append('Synthetic target is not permitted')
 for kind in required:
  head=IntegrationObservation.objects.filter(contract=r,payload__kind=kind).order_by('-pk').first();heads.append([kind,head.pk if head else None])
  latest=IntegrationProbe.objects.filter(contract=r,intent__kind=kind).order_by('-pk').first();heads.append(['probe:'+kind,latest.pk if latest else None,latest.status if latest else None])
  if latest and (latest.status!='confirmed' or not head or head.job_id!=latest.pk):findings.append('Latest '+kind+' probe is pending, failed or unavailable')
  if not head:findings.append('Missing '+kind+' observation');continue
  if head.job_id is None or head.payload['outcome']!='passed':findings.append('Current '+kind+' is supplied, failed or unknown');continue
  readable(head.actor,r.case,True);require(head.actor,r.case,'integration.probe')
  if authority(head.actor,r,'probe')!=head.job.intent['authority'] or head.job.intent['binding']!=b:findings.append('Probe authority/target/credential changed')
  if kind=='receipt':source_job(head.actor,r.case,r.payload['family'],head.job.intent['source_job'],r)
  from apps.finance.publication_readiness import findings as native_findings
  findings.extend(native_findings(r,head))
  from .private_protection_readiness import findings as private_findings
  findings.extend(private_findings(r,head))
  from .private_file_readiness import findings as file_findings
  findings.extend(file_findings(r,head))
  from .accepted_protection_readiness import findings as accepted_findings
  findings.extend(accepted_findings(r,head))
  if (timezone.now()-timestamp(head.payload['observed_at'])).total_seconds()>v['freshness_seconds']:findings.append('Current '+kind+' expired')
 native=r.payload['implementation']=='internal_postgres_session_v1' and r.payload['kind']=='adapter'
 provider=r.payload['implementation']=='authenticated_json_v1' and r.payload['kind']=='provider'
 if not (native or provider):findings.append('Matching native dispatch/provider implementation is not installed')
 result={'capability_ready':not findings,'findings':findings,'scope':'internal receipt readiness or public provider canary only','business_dispatch_verified':False,'real_model_evaluated':False,'operational_provider_canary_evaluated':provider and b['classification']=='authenticated_remote_claim' and not findings,'synthetic_provider_evaluated':provider and b['classification']=='synthetic_authenticated_http' and not findings,'operational_ready':False,'deployment_authorized':False}
 return {'contract':r.sha256,'policy':p.pk,'binding':b,'heads':heads},result
@transaction.atomic
@evaluated
def assess(a,case_id,contract_id,key,expected=None):
 c=locked(a,case_id,'integration.assess',expected);readable(a,c,True);r=contract_for(c,contract_id);contract_access(a,r);validate(KEY,key);pins,result=snapshot(r);old=IntegrationAssessment.objects.filter(contract=r,operation_key=key).first()
 if old:
  if old.snapshot!=pins or old.result!=result or old.actor_id!=a.pk:raise ValidationError('Assessment intent changed')
  return old
 row=IntegrationAssessment.objects.create(contract=r,operation_key=key,snapshot=pins,result=result,actor=a);audit(a,c,'integration.assessed',r,assessment=row.pk);bump(c);return row
def current_assessment(r):
 readable(r.actor,r.contract.case,True);require(r.actor,r.contract.case,'integration.assess');pins,result=snapshot(r.contract)
 if IntegrationAssessment.objects.filter(contract=r.contract,pk__gt=r.pk).exists() or r.snapshot!=pins or r.result!=result or not result['capability_ready']:raise ValidationError('Current readiness reassessment required')
def review_current(r):
 current_assessment(r);rr=IntegrationReview.objects.filter(assessment=r).select_related('actor').order_by('-pk').first()
 if not rr or rr.verdict!='confirm' or rr.authority!=authority(rr.actor,r.contract,'review'):raise ValidationError('Current configured human readiness review required')
 return rr
@transaction.atomic
@evaluated
def review(a,case_id,assessment_id,verdict,key,evidence_id,expected=None):
 c=locked(a,case_id,'integration.review',expected);r=IntegrationAssessment.objects.select_related('contract__case','actor').filter(contract__case=c,pk=assessment_id).first()
 if not r:raise ValidationError('Exact assessment required')
 auth=authority(a,r.contract,'review');_,v=rules(r.contract);validate(KEY,key);e=subject(c,evidence_id,'integration_review')
 if verdict not in ['confirm','return','withdraw']:raise ValidationError('Typed review disposition required')
 preparers={r.actor_id,r.contract.actor_id}|set(IntegrationObservation.objects.filter(contract=r.contract).values_list('actor_id',flat=True))
 from .accepted_protection_readiness import binding as accepted_binding
 accepted=accepted_binding(r.contract)
 if accepted:preparers.add(accepted.job.actor_id)
 if v['independent_review'] and a.pk in preparers:raise PermissionDenied('Independent configured reviewer required')
 old=IntegrationReview.objects.filter(assessment=r,operation_key=key).first()
 if old:
  if (old.actor_id,old.verdict,old.evidence_id)!=(a.pk,verdict,e.pk):raise ValidationError('Review intent conflicts')
  return old
 if verdict=='confirm':current_assessment(r)
 row=IntegrationReview.objects.create(assessment=r,operation_key=key,verdict=verdict,authority=auth,evidence=e,actor=a);audit(a,c,'integration.review',r.contract,review=row.pk);bump(c);return row
@transaction.atomic
@evaluated
def select(a,case_id,contract_id,evidence_id,expected=None):
 c=locked(a,case_id,'integration.select',expected);readable(a,c,True);r=contract_for(c,contract_id);contract_access(a,r);current_contract(r)
 from apps.finance.publication_readiness import binding as native_binding
 from .private_protection_readiness import binding as private_binding
 from .private_file_readiness import binding as file_binding
 from .accepted_protection_readiness import binding as accepted_binding
 if native_binding(r) or private_binding(r) or file_binding(r) or accepted_binding(r):rules(r)
 e=subject(c,evidence_id,'integration_selection');family=r.payload['family']
 if family!='provider':require(a,c,ROUTES[family][3])
 old=IntegrationSelection.objects.filter(case=c,family=family).order_by('-version').first()
 if old and old.contract_id==r.pk:return old
 row=IntegrationSelection.objects.create(case=c,family=family,version=old.version+1 if old else 1,contract=r,evidence=e,actor=a);audit(a,c,'integration.enrolled',r,selection=row.pk);bump(c);return row
def gate(c,family,source_job=None):
 s=IntegrationSelection.objects.select_related('contract__case').filter(case=c,family=family).order_by('-version').first()
 if family=='publication':
  from apps.finance.publication_readiness import selection
  s=selection(c,source_job)
 if family=='protection':
  from .private_protection_readiness import selection
  from .private_file_readiness import selection as file_selection
  from .accepted_protection_readiness import selection as accepted_selection
  s=accepted_selection(c,source_job) or file_selection(c,source_job) or selection(c,source_job)
 if not s:return None # Only explicitly enrolled effects acquire this dependency.
 from apps.finance.publication_readiness import binding as native_binding
 from .private_protection_readiness import binding as private_binding
 from .private_file_readiness import binding as file_binding
 from .accepted_protection_readiness import binding as accepted_binding
 if family in PRIVATE_FAMILIES or native_binding(s.contract) or private_binding(s.contract) or file_binding(s.contract) or accepted_binding(s.contract):
  contract_access(s.actor,s.contract);readable(s.actor,c,True);require(s.actor,c,'integration.select');require(s.actor,c,ROUTES[family][3])
 a=IntegrationAssessment.objects.select_related('contract__case','actor').filter(contract=s.contract).order_by('-pk').first()
 if not a:raise ValidationError('Enrolled integration needs assessment')
 rr=review_current(a);return {'selection':s.pk,'assessment':a.pk,'review':rr.pk}
@transaction.atomic
@evaluated
def report(a,case_id,pk):
 c=locked(a,case_id,'integration.read');r=IntegrationAssessment.objects.select_related('contract__case','actor').filter(contract__case=c,pk=pk).first()
 if not r:raise ValidationError('Exact assessment required')
 contract_access(a,r.contract)
 ready=reviewed=False
 try:current_assessment(r);ready=True;review_current(r);reviewed=True
 except (ValidationError,PermissionDenied,ConnectionError):pass
 value={'assessment':r.pk,'recorded_ready':r.result['capability_ready'],'current_ready':ready,'review_current':reviewed,'operational_ready':False,'deployment_authorized':False}
 if Grant.objects.filter(case=c,user=a,action='integration.source.read',active=True).exists():value['recorded_result']=r.result
 return value


def private_payload_access(a,c,payload):
 if payload['family'] in PRIVATE_FAMILIES:family_access(a,c,payload['family'])
 if payload['family']=='ledgerdata':
  from .operator_inventory import source_query,job_access
  for j in source_query(c,'ledgerdata'):job_access(a,c,'ledgerdata',j)
def contract_access(a,r):
 private_payload_access(a,r.case,r.payload)
 from apps.finance.publication_readiness import check
 check(a,r)
 from .private_protection_readiness import check as private_check
 private_check(a,r)
 from .private_file_readiness import check as file_check
 file_check(a,r)
 from .accepted_protection_readiness import check as accepted_check
 accepted_check(a,r)

def visible_contracts(a,c):
 q=IntegrationContract.objects.filter(case=c)
 hidden=[]
 for r in q:
  try:contract_access(a,r)
  except PermissionDenied:hidden.append(r.pk)
 return q.exclude(pk__in=hidden)
def audit(a,c,action,record,**data):
 from apps.finance.publication_readiness import binding as native_binding
 from .private_protection_readiness import binding as private_binding
 from .private_file_readiness import binding as file_binding
 from .accepted_protection_readiness import binding as accepted_binding
 prefix='agent.data.accepted_protection_' if accepted_binding(record) else 'agent.data.private_file_' if file_binding(record) else 'agent.data.private_protection_' if private_binding(record) else 'agent.data.finance_publication_' if native_binding(record) else 'agent.data.support_' if record.payload['family'] in PRIVATE_FAMILIES else ''
 event(a,c,prefix+action,**data)
