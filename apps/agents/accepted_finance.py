"""Bounded live investigation and typed drafting. No human decision or release tools."""
from django.core.exceptions import PermissionDenied
from apps.identity.services import require
from apps.finance import accepted_documents as d

def prepare(actor,case_id,handoff_id,template_id,audience,expected=None,document_id=None):
 from apps.core.models import Case
 require(actor,Case.objects.get(pk=case_id),'agent.document')
 return d.draft(actor,case_id,handoff_id,template_id,audience,expected,document_id)

def investigate(actor,case_id):
 from apps.core.models import Case
 c=Case.objects.get(pk=case_id);d.h.readable(actor,c);require(actor,c,'agent.document');rows=[]
 for b in d.Binding.objects.filter(handoff__case=c).order_by('-pk')[:30]:
  try:value=d.report(actor,c.pk,b.version_id)
  except PermissionDenied:continue
  rows.append({'version':b.version_id,'question':'Resolve held source/acceptance/audience/review controls before human release' if value['findings'] else 'Separate configured human publisher may reserve this exact projection'})
 return {'findings':rows,'decision_tools':[],'publication_tools':[],'posted':False}
