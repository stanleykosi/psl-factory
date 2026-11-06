from django import forms
from .forms import CommandForm
from .models import PaymentAssessment,PaymentException,BillingCoverage,PaymentReleaseReservation
from apps.pmo.models import DeliveryDossier
from apps.policy.payment_validators import SCHEMAS

def commands(case,data=None):
    def select(model,path='case',required=True):return forms.ModelChoiceField(model.objects.filter(**{path:case}),required=required)
    def evidence():return forms.ModelChoiceField(case.evidence.all())
    def text():return forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))
    defs={
      'assess':('Assess captured payment position',{'dossier':select(DeliveryDossier),'coverage':select(BillingCoverage)}),
      'request':('Request a human exception',{'assessment':select(PaymentAssessment),'operation_key':forms.CharField(max_length=100),'reason':text(),'evidence':evidence(),'valid_from':forms.DateTimeField(),'valid_until':forms.DateTimeField()}),
      'decide':('Record human decision or own withdrawal',{'request':select(PaymentException,'assessment__case'),'verdict':forms.ChoiceField(choices=[(v,v) for v in ['approve','reject','return','revoke','withdraw']]),'reason':text(),'evidence':evidence()}),
      'reserve':('Reserve combined local release controls',{'assessment':select(PaymentAssessment),'request':select(PaymentException,'assessment__case',False),'operation_key':forms.CharField(max_length=100)}),
      'check':('Revalidate reservation for downstream use',{'reservation':select(PaymentReleaseReservation,'assessment__case')}),
      'investigate':('Investigate evidence and draft follow-up',{}),
      'policy':('Draft typed D13 configuration',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':forms.JSONField(widget=forms.Textarea(attrs={'rows':7})),'evidence':forms.ModelChoiceField(case.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()}),
    }
    result=[]
    for action,(title,fields) in defs.items():
        cls=type('Payment'+action,(CommandForm,),fields)
        f=cls(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='id_'+action+'_%s')
        result.append({'action':action,'title':title,'form':f})
    return result
