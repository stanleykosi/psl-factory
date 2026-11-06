from django import forms
from apps.identity.models import Grant
from apps.policy.ledger_validators import SCHEMAS
from .forms import CommandForm
from .models import LedgerLineage,LedgerCheck
def commands(a,c,data=None):
 from . import ledger_resolution as r
 def ev(kinds=None):return forms.ModelChoiceField(c.evidence.filter(kind__in=kinds) if kinds else c.evidence.all())
 defs={'capture':('Capture incumbent source/reference','ledger.capture',{'evidence':ev(['ledger_source']),'predecessor':forms.ModelChoiceField(LedgerLineage.objects.filter(case=c),required=False)}),'verify':('Record read-only incumbent verification','ledger.verify',{'lineage':forms.ModelChoiceField(LedgerLineage.objects.filter(case=c)),'evidence':ev(['quickbooks_verification'])}),'review':('Finance verification decision','ledger.review',{'verification':forms.ModelChoiceField(LedgerCheck.objects.filter(lineage__case=c)),'evidence':ev(),'verdict':forms.ChoiceField(choices=[('approve','approve'),('reject','reject')])}),'policy':('Draft typed incumbent policy','policy.configure',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea),'evidence':ev(['policy_decision']),'effective_from':forms.DateTimeField()}),'investigate':('Investigate duplicate/uncertain references','agent.ledger',{})}
 claims=r.visible_claims(a,c)
 defs.update({
 'resolution_evidence':('Capture restricted resolution evidence','ledger.capture',{'kind':forms.ChoiceField(choices=[(x,x) for x in ['ledger_resolution','ledger_resolution_review']]),'body':forms.CharField(max_length=12000,widget=forms.Textarea)}),
 'resolve':('Propose scoped duplicate or reference-correction resolution','ledger.resolve',{'selected':forms.ModelChoiceField(claims.filter(case=c)),'members':forms.ModelMultipleChoiceField(claims),'retired':forms.ModelMultipleChoiceField(claims),'mode':forms.ChoiceField(choices=[(x,x) for x in ['duplicate_alias','reference_correction']]),'reference':forms.CharField(max_length=100),'predecessor':forms.ModelChoiceField(r.Resolution.objects.filter(case=c),required=False),'evidence':ev(['ledger_resolution']),'reason':forms.CharField(max_length=400)}),
 'resolve_review':('Independently review exact claim resolution','ledger.resolve_review',{'resolution':forms.ModelChoiceField(r.Resolution.objects.filter(pk__in=[p['row'].pk for p in r.visible_packets(a,c)],case=c)),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['confirm','return','withdraw']]),'evidence':ev(['ledger_resolution_review'])})})
 grants=set(Grant.objects.filter(case=c,user=a,active=True).values_list('action',flat=True));out=[]
 for action,(title,permission,fields) in defs.items():
  if permission in grants:out.append({'title':title,'form':type('Ledger'+action,(CommandForm,),fields)(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':c.revision},auto_id='id_'+action+'_%s')})
 return out
