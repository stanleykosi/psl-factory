from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import add_evidence,event,bump
from apps.finance.bu import locked,current
from apps.finance.bu_models import BUWork
from apps.policy.bu_validators import SCHEMAS
from apps.policy.services import resolve
from .models import AgentRun
def inspect_work(w):
 codes=w.metadata['codes'];questions=[]
 if any('exception' in k or 'pool' in k for k in codes):questions.append('Ask actual Finance authority for the exact restricted subject/component/period ratio and standard-pool exclusion; do not reuse last month or infer from job title.')
 if any('event' in k for k in codes):questions.append('Investigate exact event identity, source tags, coverage and approved shared/direct treatment; never duplicate the event amount or write a ledger.')
 if any('historical' in k or 'closed_period' in k for k in codes):questions.append('Obtain separately authorised historical-reference review or retain the incumbent manual route; no silent restatement or period reopen.')
 try:current(w,check_comparison=False);state='current source/policy metadata; financial comparison checked on controlled use' if w.metadata.get('comparison') else 'current'
 except (ValidationError,PermissionDenied):state='reassessment required';questions.append('Current source, policy, role, access or retention has changed; preserve history and rebuild a reviewed successor.')
 latest=w.reviews.filter(purpose=w.kind).order_by('-pk').values('verdict','subject_sha256').first()
 if not latest or latest['verdict']!='approve' or latest['subject_sha256']!=w.sha256:questions.append('Exact human review is missing/returned/revoked; prepare the scoped evidence for the configured reviewer, never approve automatically.')
 return {'work_id':w.pk,'kind':w.kind,'version':w.version,'sha256':w.sha256,'state':state,'parent_ref':w.parent_id,'payroll_ref':w.payroll_id,'rule_refs':w.metadata.get('rule_ids',[]),'codes':codes,'owner_questions':questions}

@transaction.atomic
def investigate(actor,case_id,expected):
 c=locked(actor,case_id,'agent.bu',expected);findings=[]
 for w in BUWork.objects.defer('payload').filter(case=c).order_by('-pk')[:40]:
  findings.append(inspect_work(w))
 e=add_evidence(actor,c.pk,'agent_bu','Bounded metadata-only exception/allocation investigation; no staff ratios, payroll or transaction rows read','local:deterministic-bu-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='F21',provider='deterministic-bu-v1',result={'process_ids':['F21','F44'],'findings':findings,'policy_readiness':{k:resolve(k,c).status for k in SCHEMAS},'budget':{'work_versions':40},'private_payloads_read':False,'finance_comparison_values_read':False,'review_approved':False,'ledger_posted':False,'source_written':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.bu',run=r.pk);bump(c);return r
