from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.policy.services import resolve
from apps.policy.hrfinance_validators import AUTHORITY,DISCLOSURE,REQUIRED
from apps.finance.hrfinance import locked,current_contract,current_snapshot
from apps.finance.hrfinance_models import HRFinanceNeed,HRDisclosure
from django.core.exceptions import ValidationError,PermissionDenied
from .models import AgentRun
@transaction.atomic
def investigate(actor,case_id,expected):
 c=locked(actor,case_id,'agent.hrfinance',expected);findings=[]
 for n in HRFinanceNeed.objects.filter(case=c).order_by('-pk')[:20]:
  questions=[];extra=set(n.payload['fields'])-set(REQUIRED)
  if n.payload['purpose']=='bu_attribution' and extra:questions.append('Staff/BU attribution may not need these extra fields: '+', '.join(sorted(extra))+'. Ask HR to confirm minimum scope; no disclosure is changed.')
  policy={k:resolve(k,c).status for k in [AUTHORITY,DISCLOSURE]}
  questions += [k+': '+status for k,status in policy.items() if status!='ACTIVE']
  contracts=[]
  for d in HRDisclosure.objects.filter(need=n).order_by('-pk')[:5]:
   try:current_contract(d);status='current contract; HR approval still required for capture'
   except (ValidationError,PermissionDenied):status='contract reassessment required'
   snapshots=[]
   for s in d.snapshots.defer('payload').order_by('-pk')[:10]:
    try:current_snapshot(s);state='current'
    except (ValidationError,PermissionDenied):state='held or historical'
    observation={'snapshot_id':s.pk,'status':s.status,'current_use':state,'exception_codes':s.manifest['findings']}
    # Proposed engineering safeguard, not disclosure authority or a dispatch route.
    # Rejected values remain discarded; free-text correction routes nominate nobody.
    if s.status=='rejected' and 'out_of_contract_fields' in s.manifest['findings']:
     observation['scope_exception']={'status':'held','reason':'scope_exception_owner_unconfigured'}
     question='Ask HR to confirm the minimum permitted scope and an authorized scope-exception owner/action route. No typed owner route is configured; no notification was sent. Forbidden fields remain rejected and discarded, not eligible for acceptance through this question.'
     if question not in questions:questions.append(question)
    snapshots.append(observation)
   contracts.append({'contract_id':d.pk,'sha256':d.sha256,'status':status,'snapshots':snapshots})
  if not contracts:questions.append('Request HR confirmation of the exact supported source view, fields, recipients, freshness, retention and correction route.')
  findings.append({'need_id':n.pk,'need_evidence_id':n.evidence_id,'purpose':n.payload['purpose'],'requested_fields':n.payload['fields'],'questions':questions,'policy_readiness':policy,'contracts':contracts})
 e=add_evidence(actor,c.pk,'agent_hrfinance','Metadata-only F35 scope/freshness investigation; no staff or payroll rows','local:deterministic-hrfinance-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='F35',provider='deterministic-hrfinance-v1',result={'findings':findings,'need_limit':20,'private_rows_read':False,'disclosure_approved':False,'hr_source_written':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.hrfinance',run=r.pk);bump(c);return r
