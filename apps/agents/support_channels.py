"""Source-protected live investigation; no automatic reviews, clocks, dispatch or shared history."""
from django.db import transaction
from apps.identity.services import require
from apps.policy.services import resolve
from apps.policy.support_channel_validators import RECEIPTS,CLOCK,CORRECTIONS
from apps.baas import support_channel as d,support_clock_corrections as corrections
@transaction.atomic
def investigate(actor,case_id):
 c=d.locked(actor,case_id,'read');require(actor,c,'agent.operations');rows=[]
 for r in d.Claim.objects.filter(case=c).order_by('-pk')[:30]:
  report=d.inspect(actor,c.pk,r.pk);latest=report['checks'][0] if report['checks'] else None
  question='Reserve a scoped read-only receipt check; a supplied identity alone does not prove delivery.'
  if latest:
   if latest['status']=='unknown':question='Reconcile the original read-only check with the scoped worker; never dispatch a message or force an unknown outcome.'
   elif latest['status']=='held':question='Inspect exact source identity, current grants/policy/credential binding and original attempt budget; changed context needs a new check key.'
   elif latest['currently_reviewed_delivery']:question='A configured human may attest the exact delivery time through original Support controls; late times need correction and duplicate message clocks are forbidden.'
   else:question='Inspect delivered/human status, release window and independent review history. Withdrawn, retracted or expired proof cannot support a current clock.'
  rows.append({'claim':r.pk,'status':latest['status'] if latest else 'unchecked','reviewed_delivery':bool(latest and latest['currently_reviewed_delivery']),'question':question})
 clock=corrections.projection(c)
 from apps.workflows.operator_inventory import jobs
 checks=[{'job':r['id'],'status':r['status'],'question':'Reconcile unknown reads with the scoped worker; retry/cancel only through configured native recovery and original budget.'} for r in jobs(actor,c)[0] if r['family']=='supportchannel']
 return {'current_clock':clock,'correction_question':'Prepare an explicit source revision/new verification and human correction successor when review, source or policy changes; never rewrite ordered events or attest automatically.','operator_checks':checks,'claims':rows,'policy_status':{k:resolve(k,c).status for k in [RECEIPTS,CLOCK,CORRECTIONS]},'clock_applied':False,'message_sent':False,'generic_agent_history_written':False}
