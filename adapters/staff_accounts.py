"""Closed, source-free command shape for a human-reviewed account departure."""
import re
from django.core.exceptions import ValidationError


def checked_review(person_id,fingerprint):
    positive=lambda v:type(v) is int and v>0
    if not positive(person_id) or not isinstance(fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',fingerprint):
        raise ValidationError('An exact current staff account review is required.')


def checked(person_id,fingerprint,replacements,evidence):
    checked_review(person_id,fingerprint)
    positive=lambda v:type(v) is int and v>0
    if (type(replacements) is not dict or len(replacements)>10000 or
            any(not positive(k) or v is not None and not positive(v) for k,v in replacements.items())):
        raise ValidationError('Use exact action and successor references, or an explicit unassigned owner.')
    if (type(evidence) is not dict or len(evidence)>100 or
            any(not isinstance(k,str) or not positive(v) for k,v in evidence.items())):
        raise ValidationError('Use each workspace’s own handover evidence.')


def restoration_packet(prepared):
    """A bounded, source-free agent read; contains no credentials or old grants."""
    from adapters.forecast import obj
    from apps.documents.contracts import validate
    shape=obj({'format':{'const':'psl.staff-restoration-check/v1'},'person':{'type':'integer','minimum':1},
        'scopes':{'type':'array','minItems':1,'maxItems':100,'items':obj({
            'case':{'type':'string','format':'uuid'},'role_source':{'type':['integer','null'],'minimum':1}})},
        'findings':{'type':'array','maxItems':100,'items':{'type':'string','maxLength':1000}},
        'old_access_restored':{'const':False},'human_review_required':{'const':True},
        'effect_tools':{'type':'array','maxItems':0}})
    value={'format':'psl.staff-restoration-check/v1','person':prepared['person'].pk,
        'scopes':[{'case':str(s['case'].pk),'role_source':s['role_source']} for s in prepared['scopes']],
        'findings':prepared['blocked'],'old_access_restored':False,'human_review_required':True,'effect_tools':[]}
    validate(shape,value)
    return value
