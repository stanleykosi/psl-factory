"""Exact native Finance publication enrollment; shared readiness remains the execution engine."""
from django.core.exceptions import PermissionDenied,ValidationError
from django.contrib.auth import get_user_model
from apps.identity.services import require
from apps.documents.contracts import digest
from adapters.finance_publication_readiness import FinancePublicationReadinessAdapter as Adapter
from .acceptance_models import FinancePublicationReadiness as Binding
from . import accepted_documents as publication


def binding(contract):return Binding.objects.select_related('contract__case','job__publication__version__document__case','job__publication__version__template').filter(contract=contract).first()

def access(actor,b):
 # A reference cannot wash away an earlier native source participant.
 for old in Binding.objects.filter(contract__case=b.contract.case,contract__reference=b.contract.reference).select_related('job__publication__version__document__case','job__publication__version__template'):
  Adapter().access(actor,old.job)

def validate_policy(c,v,runtime=False):
 ids=v['native_publication_job_ids']
 for pk in ids:Adapter().job(c,pk)
 if not v['independent_review'] or not v['require_receipt_probe'] or v['probe_user_id']==v['reviewer_id']:raise ValidationError('Native publication readiness requires independent humans and receipt probes')
 if not runtime:
  try:
   for key in ['probe_user_id','reviewer_id']:
    a=get_user_model().objects.filter(pk=v[key],is_active=True).first()
    if not a:raise ValidationError('Actual active native readiness principal required')
    for pk in ids:Adapter().access(a,Adapter().job(c,pk))
    require(a,c,'integration.read');require(a,c,'integration.source.read')
  except PermissionDenied:raise ValidationError('Actual original private Finance source grants required') from None

def prepare(actor,c,pk,payload):
 j=Adapter().job(c,pk);value=Adapter().describe(actor,j)
 if payload['kind']!='adapter' or payload['family']!='publication' or payload['implementation']!='internal_postgres_session_v1' or set(payload['capabilities'])!={'health','receipt_lookup'} or payload['target_key']!='internal:publication':raise ValidationError('Native publication requires the reviewed internal health/receipt adapter contract')
 return j,value

def bind(actor,contract,context):
 j,value=context
 return Binding.objects.create(contract=contract,job=j,actor=actor,snapshot=value,sha256=digest(value))

def check(actor,contract):
 b=binding(contract)
 if not b:return None
 access(actor,b)
 if b.snapshot!=Adapter().describe(actor,b.job) or b.sha256!=digest(b.snapshot):raise ValidationError('Exact native publication provenance changed')
 return b

def policy(contract,v):
 b=binding(contract)
 if b and (b.job_id not in v.get('native_publication_job_ids',[]) or not v['require_receipt_probe'] or not v['independent_review'] or v['probe_user_id']==v['reviewer_id']):raise ValidationError('Configure v2 native publication inventory, independent review and receipt probes')
 return b

def intent(actor,contract,kind,source_id):
 b=check(actor,contract)
 if not b:return None
 if kind=='evaluation' or kind=='receipt' and source_id!=b.job_id:raise ValidationError('Probe must use the exact enrolled native publication source')
 return {'binding':b.pk,'sha256':b.sha256,'source':b.snapshot}

def observation(contract,job,base):
 b=check(job.actor,contract)
 if not b:return None
 value=dict(base,native_publication={'binding':b.pk,'sha256':b.sha256,'source':b.snapshot})
 if job.intent['kind']=='receipt':value['receipt_provenance']=Adapter().receipts(b.job)
 return value

def findings(contract,head):
 b=binding(contract)
 if not b:return []
 check(head.actor,contract)
 if head.job.intent.get('native_publication')!={'binding':b.pk,'sha256':b.sha256,'source':b.snapshot} or head.payload.get('native_publication')!=head.job.intent.get('native_publication'):return ['Native publication observation provenance changed']
 if head.payload['kind']=='receipt' and head.payload.get('receipt_provenance')!=Adapter().receipts(b.job):return ['Native publication receipt provenance changed; fresh probe/review required']
 return []

def visible_jobs(actor,c):
 ids=[]
 for j in publication.PublicationJob.objects.filter(publication__version__document__case=c,publication__version__accepted_finance_binding__isnull=False):
  try:Adapter().access(actor,j)
  except PermissionDenied:continue
  ids.append(j.pk)
 return publication.PublicationJob.objects.filter(pk__in=ids)

def selection(c,source_job=None):
 from apps.workflows.readiness_models import IntegrationSelection
 q=IntegrationSelection.objects.select_related('contract__case').filter(case=c,family='publication')
 if source_job is None:return q.filter(contract__finance_publication_readiness__isnull=True).order_by('-version').first()
 return q.filter(contract__finance_publication_readiness__job_id=source_job).order_by('-version').first()

def investigate(actor,c):
 from apps.workflows import readiness as d
 require(actor,c,'agent.integrations');publication.h.readable(actor,c);rows=[]
 for b in Binding.objects.filter(contract__case=c).order_by('-pk')[:30]:
  try:
   access(actor,b);assessment=d.IntegrationAssessment.objects.filter(contract=b.contract).order_by('-pk').first();value=d.report(actor,c.pk,assessment.pk) if assessment else None
  except PermissionDenied:continue
  rows.append({'contract':b.contract_id,'publication_job':b.job_id,'current_ready':bool(value and value['review_current']),'question':'Reconcile original receipts before retry; obtain fresh exact native health/receipt evidence and independent review when held.'})
 return {'findings':rows,'business_effect_tools':[],'persisted_agent_run':False}
