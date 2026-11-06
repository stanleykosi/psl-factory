from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.finance.ledger import locked
from apps.finance.models import LedgerLineage
from apps.policy.ledger_validators import SCHEMAS
from apps.policy.services import resolve
from .models import AgentRun
@transaction.atomic
def investigate(actor,case_id,expected=None):
 c=locked(actor,case_id,'agent.ledger',expected)
 rows=list(LedgerLineage.objects.filter(case=c).order_by('-pk').values('id','identity','predecessor_id','payload__outcome')[:40])
 for row in rows:
  row['same_identity_count']=LedgerLineage.objects.filter(case=c,identity=row['identity']).count()
  row['questions']=['Obtain incumbent read evidence for an uncertain outcome before any manual retry.','Confirm source identity, entity, realm, treatment and target version with authorised Finance.','Review an explicit claim-disposition packet with fresh found target/version evidence; unresolved or inaccessible cross-case claims cannot be waived.','After independent resolution review, obtain a new incumbent read and the original Finance verification review; no posting or retry tool is available.']
 e=add_evidence(actor,c.pk,'agent_ledger','Bounded F01 reference investigation; no posting authority','local:deterministic-ledger-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='F01',provider='deterministic-ledger-v1',result={'references':rows,'policy_readiness':{k:resolve(k,c).status for k in SCHEMAS},'resolution_decision_executed':False,'cross_case_source_details_read':False,'budget':40,'posting_performed':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.ledger',run=r.pk);bump(c);return r
