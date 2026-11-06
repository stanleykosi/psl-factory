"""Live, source-authorised guidance; no persisted generic agent output or effects."""
from django.db import transaction
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.operator_validators import OPERATOR,PROTECTION
from apps.policy.readiness_validators import ADAPTER
from apps.finance import ledger_agents as d
from apps.workflows.operator_inventory import jobs

@transaction.atomic
def investigate(actor,case_id):
 c=d.locked(actor,case_id,'agent.operations');require(actor,c,'agent.operations')
 checks=[]
 for row in jobs(actor,c)[0]:
  if row['family']!='ledgerdata':continue
  question='Inspect original source/policy/authority, reviewed provider binding and remaining attempt budget before configured held-job retry.'
  if row['status']=='unknown' or row['lease_expired']:question='Reconcile the original operation with the scoped extraction worker; do not cancel, rekey or reset attempts.'
  elif row['status'] in ['confirmed','rejected']:question='Inspect the immutable receipt and human result review; a receipt does not establish native QuickBooks authenticity or authorise posting.'
  checks.append({'job':row['id'],'status':row['status'],'attempts':row['attempts'],'question':question})
 return {'operator_checks':checks,'policy_status':{k:resolve(k,c).status for k in [OPERATOR,PROTECTION,ADAPTER]},'private_input_read':False,'provider_called':False,'recovery_executed':False,'generic_agent_history_written':False,'accounting_posted':False}
