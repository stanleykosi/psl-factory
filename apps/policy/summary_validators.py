from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed
SCOPE='B14.summary_scope';REVIEW='B14.summary_review'
FIELDS=['meaning','reopened','source_references','metrics','unlinked_intake_count']
field_list={'type':'array','uniqueItems':True,'maxItems':len(FIELDS),'items':{'enum':FIELDS}}
ID={'type':'integer','minimum':1}
SCHEMAS={
 SCOPE:('schema:psl/complaint-summary-scope/v1',obj({'membership':{'enum':['linked_receipt_half_open_v1','event_activity_half_open_v1']},
    'max_cases':{'type':'integer','minimum':1,'maximum':100},'max_references':{'type':'integer','minimum':1,'maximum':1000},
    'missing_source_behavior':{'enum':['hold','omit_with_reason']},'merged_case_behavior':{'enum':['omit_with_reason','include_marked']},
    'allowed_fields':field_list,'allow_synthetic':{'type':'boolean'}})),
 REVIEW:('schema:psl/complaint-summary-review/v1',obj({'reviewer_id':ID,'reviewer_role':{'const':'Support'},'independent_review':{'type':'boolean'},
    'audiences':{'type':'array','minItems':1,'maxItems':30,'items':obj({'key':KEY,'recipient_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'fields':field_list})},
    'allow_synthetic':{'type':'boolean'}}))}

def validate_reference(component,target,case,runtime=False):
    v=typed(target,*SCHEMAS[component])
    if case.kind!='support' or v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact Support/classification summary criteria required')
    if component==REVIEW:
        if len({a['key'] for a in v['audiences']})!=len(v['audiences']):raise ValidationError('Distinct summary audience keys required')
        if not runtime:
            from apps.identity.services import require
            from .services import decision_authority
            try:
                reviewer=get_user_model().objects.get(pk=v['reviewer_id'],is_active=True)
                for action in ['case.read','support.read','support.summary.read','support.summary.draft_read','support.summary.review']:require(reviewer,case,action)
                decision_authority(reviewer,case,'Support')
                for audience in v['audiences']:
                    for pk in audience['recipient_ids']:
                        recipient=get_user_model().objects.get(pk=pk,is_active=True)
                        for action in ['case.read','support.read','support.summary.read']:require(recipient,case,action)
            except (get_user_model().DoesNotExist,PermissionDenied):raise ValidationError('Actual current summary reviewer/recipient records and grants required') from None
    return v
