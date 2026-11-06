"""Typed preparation and live private investigation; no human decision tools."""
def prepare(actor,case_id,draft_id,package_id,reference,predecessor=None,expected=None):
 from apps.finance.acceptance import prepare as command
 return command(actor,case_id,draft_id,package_id,reference,predecessor,expected)

def investigate(actor,case_id):
 from django.db import transaction
 from apps.finance import acceptance as d
 from apps.identity.services import require
 from django.core.exceptions import PermissionDenied
 with transaction.atomic():
  c=d.locked(actor,case_id,'finance.handoff.read');require(actor,c,'agent.validation');rows=[]
  for h in d.Handoff.objects.filter(case=c).order_by('-pk')[:30]:
   try:d.access(actor,h)
   except PermissionDenied:continue
   value=d.report(actor,c.pk,h.pk)
   question='Inspect exact source/package/policy revisions and obtain explicit recipient receipt and validation before separate AF13 reviews and acceptance.'
   if value['states']['validate']['current']:question='Recipient validation is current. Complete separate AF13 meaning, expectations and acceptance reviews before the configured independent acceptor confirms the handoff.'
   if value['scoped_acceptance_current']:question='This exact selected scope is accepted. Recheck source/review/authority/package freshness before later use; accounting, publication and deployment remain separate.'
   rows.append({'handoff':h.pk,'states':value['states'],'question':question})
  return {'findings':rows,'human_decisions_executed':False,'body_returned':False,'accounting_posted':False,'generic_agent_history_written':False}
