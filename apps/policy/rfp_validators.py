from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .document_validators import typed,ROLES

SUPPORTED={'D11.adapter_configuration_refs'}
ROLE_LIST={'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':ROLES}}


def validate_reference(component,target,case,runtime=False):
    if target.schema_ref == 'schema:psl/go-live-client-replies/v1':
        from .go_live_reply_validators import validate_reference as validate_go_live_replies
        return validate_go_live_replies(target,case)
    if target.schema_ref == 'schema:psl/rfp-followup-route/v1':
        return validate_followup(target,case,runtime)
    c=typed(target,'schema:psl/rfp-submission-route/v1',{'type':'object','properties':{
        'kind':{'const':'rfp_submission'},'key':{'type':'string','pattern':'^[a-z][a-z0-9_-]{0,39}$'},
        'method':{'enum':['internal_recipient_inbox','manual_client_portal']},'destination_ref':{'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'},
        'recipient_ids':{'type':'array','maxItems':50,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
        'sender_roles':ROLE_LIST},'required':['kind','key','method','destination_ref','recipient_ids','sender_roles'],'additionalProperties':False})
    from apps.identity.models import Grant
    if bool(c['recipient_ids']) != (c['method']=='internal_recipient_inbox'):
        raise ValidationError('Choose recipient accounts for an internal inbox only. A manual client portal uses its exact destination reference.')
    if not runtime:
        for pk in c['recipient_ids']:
            if not get_user_model().objects.filter(pk=pk,is_active=True).exists() or not Grant.objects.filter(case=case,user_id=pk,action='document.receive:client',active=True).exists():
                raise ValidationError('RFP route recipient must have active exact-case client receive access')


def validate_followup(target,case,runtime):
    from apps.core.models import ClientContactRevision
    c=typed(target,'schema:psl/rfp-followup-route/v1',{'type':'object','properties':{
        'kind':{'const':'rfp_followup'},'key':{'type':'string','pattern':'^[a-z][a-z0-9_-]{0,39}$'},
        'mode':{'enum':['manual_evidence','synthetic_mailbox']},
        'contact_id':{'type':'integer','minimum':1},'sender_roles':ROLE_LIST},
        'required':['kind','key','mode','contact_id','sender_roles'],'additionalProperties':False})
    contact=ClientContactRevision.objects.filter(case=case,purpose='project',customer='',pk=c['contact_id']).exclude(email='').first()
    if contact is None:
        raise ValidationError('Select an evidenced project contact for bid follow-up.')
    if c['mode']=='synthetic_mailbox' and (not case.synthetic or not contact.email.casefold().endswith('.invalid')):
        raise ValidationError('The test mailbox requires a synthetic workspace and a reserved test address.')
