from apps.core.evidence_access import public_evidence,restricted
from django import forms
from apps.finance.forms import CommandForm
from apps.policy.validation_validators import SCHEMAS
from apps.pmo.models import ActionItem
from django.contrib.auth import get_user_model
from adapters.validation_evidence import pack_sources
from .validation_models import ValidationPackage

def commands(case,data=None,actor=None):
    def ev():return forms.ModelChoiceField(public_evidence(case.evidence.all()))
    def ref():return forms.CharField(max_length=100)
    def js():return forms.JSONField(widget=forms.Textarea(attrs={'rows':7}))
    from apps.finance.acceptance import visible_packages
    def package():return forms.ModelChoiceField(visible_packages(actor,case) if actor else ValidationPackage.objects.filter(case=case,finance_handoffs__isnull=True,private_readiness_packet__isnull=True,private_protection_packet__isnull=True))
    defs={
      'source':('Capture procedure or clarification',{'reference':ref(),'evidence':ev(),'metadata':js()}),
      'pack':('Import an allowlisted frozen source copy',{'path':forms.ChoiceField(choices=[(p,p) for p in pack_sources()]),'reference':ref(),'metadata':js()}),
      'example':('Record normal or exception expectations',{'reference':ref(),'process_ids':js(),'scenario':forms.ChoiceField(choices=[('normal','normal'),('exception','exception')]),'expected_output':js(),'evidence':ev()}),
      'package':('Prepare selected validation scope or revision',{'reference':ref(),'payload':js(),'evidence':ev()}),
      'review':('Record owner review or acceptance decision',{'package':package(),'kind':forms.ChoiceField(choices=[(x,x) for x in ['meaning','expectations','acceptance']]),'verdict':forms.ChoiceField(choices=[(x,x) for x in ['approve','return','disputed','reject','revoke']]),'operation_key':ref(),'evidence':ev(),'reason':forms.CharField(max_length=4000,widget=forms.Textarea(attrs={'rows':2}))}),
      'replay':('Compare a supplied result to approved expectations',{'package':package(),'evidence':ev(),'operation_key':ref()}),
      'native_subject':('Prepare an independent native source fingerprint',{'family':forms.ChoiceField(choices=native_choices(actor,case)),'source_id':forms.IntegerField(min_value=1),'reference':forms.CharField(required=False,max_length=200,label='Planned milestone name or Engineering request reference'),'operation':forms.ChoiceField(required=False,choices=[('', 'Invoice effect only')]+[(k,k) for k in ['issue','deliver','adjust','adjust_deliver']]),'related_id':forms.IntegerField(required=False,min_value=1,label='Engineering reconciliation run only'),'effect_key':forms.CharField(required=False,max_length=100,label='Engineering operation key only')}),
      'native_replay':('Evaluate an actual native workflow reservation and receipt',{'package':package(),'example_id':forms.IntegerField(min_value=1),'family':forms.ChoiceField(choices=native_choices(actor,case)),'job_id':forms.IntegerField(min_value=1),'evidence':ev(),'operation_key':ref()}),
      'followup':('Assign an open evidence gap',{'package':package(),'gap_key':ref(),'owner':forms.ModelChoiceField(get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='action.own').distinct()),'due_at':forms.DateTimeField(),'evidence':ev(),'reason':forms.CharField(max_length=4000)}),
      'investigate':('Investigate sources and acceptance gaps',{}),
      'policy':('Draft typed owner, acceptance or SOP policy',{'component':forms.ChoiceField(choices=[(k,k) for k in SCHEMAS]),'content':js(),'evidence':forms.ModelChoiceField(case.evidence.filter(kind='policy_decision')),'effective_from':forms.DateTimeField()})
    }
    result=[]
    for action,(title,fields) in defs.items():
        cls=type('Validation'+action,(CommandForm,),fields)
        result.append({'action':action,'title':title,'form':cls(data if data is not None and data.get('action')==action else None,initial={'action':action,'revision':case.revision},auto_id='id_'+action+'_%s')})
    return result


def native_choices(actor,case):
    from adapters.validation_native import FAMILIES
    from apps.workflows.operator_inventory import family_access
    from django.core.exceptions import PermissionDenied
    rows=[]
    if actor:
        for family in FAMILIES:
            try:family_access(actor,case,family)
            except PermissionDenied:continue
            rows.append((family,family))
    return rows
