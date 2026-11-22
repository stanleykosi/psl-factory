"""Replaceable human proof rules, with unresolved values kept explicitly nullable."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from adapters.forecast import obj
from .document_validators import typed,ROLES

COMPONENT='P02.client_response_rules'
SCHEMA_REF='schema:psl/client-uat-rules/v1'
TRI={'enum':[None,False,True]}
SCHEMA=obj({'format':{'const':'psl.client-uat-rules/v1'},'human_only':{'const':True},
    'qualification_mode':{'enum':[None,'reviewed_human_attestation_v1']},
    'reviewer_ids':{'type':'array','maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
    'reviewer_role':{'enum':[None,*ROLES]},'independent_review':TRI,'agent_review_required':TRI,
    'exact_mentions_required':TRI,
    'proof_formats':{'type':'array','maxItems':4,'uniqueItems':True,'items':{'enum':['pdf','docx','xlsx','txt']}},
    'workaround_mode':{'enum':[None,'explicit_client_approved_scope_v1']},
    'assurance':{'const':'human_witnessed_not_external_authentication'},
    'financial_controls':{'const':'independent'}})


def validate_reference(component,target,case,runtime=False):
    value=typed(target,SCHEMA_REF,SCHEMA)
    if value['reviewer_ids'] and value['reviewer_role'] is None:
        raise ValidationError('Choose the actual reviewer responsibility before nominating reviewers')
    if value['reviewer_ids'] and not runtime:
        from apps.identity.services import require
        from .services import decision_authority
        people=list(get_user_model().objects.filter(pk__in=value['reviewer_ids'],is_active=True))
        if len(people)!=len(value['reviewer_ids']):raise ValidationError('Current actual human reviewers required')
        for person in people:
            for action in ['case.read','delivery.read','engagement.read','client_uat.review','client_uat.proof.read']:
                require(person,case,action)
            decision_authority(person,case,value['reviewer_role'])
    return value
