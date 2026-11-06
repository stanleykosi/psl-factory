from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import add_evidence,event,bump
from apps.finance import billing_evidence as d
from apps.finance.models import BillingEvidenceSource,BillingReleaseAssessment
from apps.policy.services import resolve
from apps.policy.d03_validators import SCHEMAS
from .models import AgentRun
@transaction.atomic
def investigate(a,case_id,expected=None):
 c=d.locked(a,case_id,'agent.billing_evidence',expected);questions=[]
 for s in BillingEvidenceSource.objects.filter(case=c).select_related('case').order_by('-pk')[:30]:
  try:d.confirmed(s);status='current_finance_confirmation'
  except (ValidationError,PermissionDenied):status='confirmation_required_or_stale'
  questions.append({'source':s.pk,'kind':s.kind,'version':s.version,'status':status,'question':'Resolve FIN P0023 prices versus VID U0079 sign with exact owner/source evidence. Do not infer a signature gate; inspect actual generation/posting/sending contracts separately.' if s.kind=='statement' else 'Confirm current flow/environment version and exact effect controls. A generated document is not evidence of posting, sending, deployment or debt waiver.'})
 for r in BillingReleaseAssessment.objects.filter(invoice__case=c).order_by('-pk')[:20]:
  try:d.current_assessment(r);status='evidence_current'
  except (ValidationError,PermissionDenied):status='reassessment_required'
  questions.append({'assessment':r.pk,'invoice':r.invoice_id,'effect':r.effect,'status':status,'question':'Reconcile missing/unknown/unavailable control evidence before binding; lookup any uncertain invoice effect before retry.'})
 e=add_evidence(a,c.pk,'agent_billing_evidence','Bounded source-version/release evidence investigation; no raw source read or financial effect','local:deterministic-billing-evidence-v1')
 r=AgentRun.objects.create(case=c,actor=a,evidence=e,process_id='F30',provider='deterministic-billing-evidence-v1',result={'questions':questions,'policy_status':{k:resolve(k,c).status for k in SCHEMAS},'coverage':'At most 30 source versions and 20 assessments in the granted case','source_body_read':False,'signature_gate_inferred':False,'financial_execution':False,'native_flow_verified':False})
 event(a,c,'agent.billing_evidence',run=r.pk);bump(c);return r
