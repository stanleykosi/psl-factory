from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .document_validators import typed,ROLES

SUPPORTED={'D11.adapter_configuration_refs'}
ROLE_LIST={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}}


def validate_reference(component,target,case,runtime=False):
    c=typed(target,'schema:psl/rfp-submission-route/v1',{'type':'object','properties':{
        'kind':{'const':'rfp_submission'},'key':{'type':'string','pattern':'^[a-z][a-z0-9_-]{0,39}$'},
        'method':{'const':'internal_recipient_inbox'},'destination_ref':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'},
        'recipient_ids':{'type':'array','minItems':1,'maxItems':50,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
        'sender_roles':ROLE_LIST},'required':['kind','key','method','destination_ref','recipient_ids','sender_roles'],'additionalProperties':False})
    from apps.identity.models import Grant
    if not runtime:
        for pk in c['recipient_ids']:
            if not get_user_model().objects.filter(pk=pk,is_active=True).exists() or not Grant.objects.filter(case=case,user_id=pk,action='document.receive:client',active=True).exists():
                raise ValidationError('RFP route recipient must have active exact-case client receive access')
