"""Supplemental AF13 owner/acceptance interfaces; no new consolidated D group."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from functools import lru_cache
from adapters.forecast import obj,KEY
from .document_validators import typed,ROLES

OWNER='AF13.owner_validation_rules'
ACCEPTANCE='AF13.acceptance_rules'
SOP='D09.support_sop_ref'
ID={'type':'integer','minimum':1}
PROCESS_IDS={'type':'array','minItems':1,'maxItems':122,'uniqueItems':True,'items':{'type':'string','pattern':'^[BFP][0-9]{2}$'}}
AUTH=obj({'user_id':ID,'role':{'enum':ROLES},'process_ids':PROCESS_IDS,'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['meaning','expectations','acceptance']}}})
SCHEMAS={
 OWNER:('schema:psl/validation-authority/v1',obj({'human_only':{'const':True},'assignments':{'type':'array','minItems':1,'maxItems':100,'items':AUTH},'allow_preparer_review':{'type':'boolean'}})),
 ACCEPTANCE:('schema:psl/validation-acceptance/v1',obj({'allowed_levels':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['definition','synthetic_implementation']}},'independent_tester':{'type':'boolean'},'independent_acceptor':{'type':'boolean'}})),
 SOP:('schema:psl/support-sop-evidence/v1',obj({'source_id':ID,'source_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'meaning_review_id':ID,'process_ids':PROCESS_IDS})),
}

# Versioned acceptance criteria reuse existing human owner authority.
import copy
PRIVATE_SCHEMA='schema:psl/validation-acceptance/v2'
PRIVATE_VALUE=copy.deepcopy(SCHEMAS[ACCEPTANCE][1])
PRIVATE_VALUE['properties']['private_readiness']=obj({
 'inventory':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':obj({'package_id':ID,'assessment_id':ID})},
 'freshness_seconds':{'type':'integer','minimum':1,'maximum':31536000},
 'receipt_requirement':{'enum':['observed','found']},
 'independent_transport_acceptor':{'const':True},
})
PRIVATE_VALUE['required'].append('private_readiness')

NATIVE_SCHEMA='schema:psl/validation-acceptance/v3'
NATIVE_VALUE=copy.deepcopy(SCHEMAS[ACCEPTANCE][1])
NATIVE_VALUE['properties']['allowed_levels']['items']['enum'].append('operational')
NATIVE_VALUE['properties']['native_execution']=obj({
 'families':{'type':'array','minItems':1,'maxItems':10,'uniqueItems':True,'items':{'enum':['handoff','publication','invoice','engineering','partner','approval','supportresponse','supportchannel','ledgerdata','financefollowup']}},
 'freshness_seconds':{'type':'integer','minimum':1,'maximum':31536000},
 'scope':{'const':'native_source_receipt_only'},'expectations_before_reservation':{'const':True}})
NATIVE_VALUE['required'].append('native_execution')

@lru_cache
def known_process_ids():
    import json
    from django.conf import settings
    return frozenset(r['id'] for r in json.loads((settings.BASE_DIR/'contracts/process-map.json').read_text(encoding='utf-8'))['rows'])

def process_ids(ids):
    from apps.documents.contracts import validate
    validate(PROCESS_IDS,ids)
    if set(ids)-known_process_ids():raise ValidationError('Unknown original process ID')
    return ids

def validate_reference(component,target,case,runtime=False):
    from .protection_acceptance_validators import COMPONENT,OWNER as PROTECTION_OWNER_COMPONENT,validate_reference as protection_validate
    if component in [COMPONENT,PROTECTION_OWNER_COMPONENT]:return protection_validate(component,target,case,runtime)
    private=component==ACCEPTANCE and target.schema_ref==PRIVATE_SCHEMA
    native=component==ACCEPTANCE and target.schema_ref==NATIVE_SCHEMA
    v=typed(target,NATIVE_SCHEMA,NATIVE_VALUE) if native else typed(target,PRIVATE_SCHEMA,PRIVATE_VALUE) if private else typed(target,*SCHEMAS[component])
    if private:
        from apps.finance.readiness_acceptance import validate_inventory
        validate_inventory(case,v,runtime)
    if component==OWNER:
        keys=[]
        for row in v['assignments']:
            process_ids(row['process_ids'])
            if not get_user_model().objects.filter(pk=row['user_id'],is_active=True).exists():raise ValidationError('Nominate an active actual human principal')
            keys.extend((row['user_id'],p,k) for p in row['process_ids'] for k in row['purposes'])
        if len(keys)!=len(set(keys)):raise ValidationError('Ambiguous duplicate owner responsibility')
    elif component==SOP:
        from apps.documents.validation_models import DiscoverySource,ValidationReview
        from apps.documents.validation import source_current,approved_review
        source=DiscoverySource.objects.filter(case=case,pk=v['source_id']).first()
        review=ValidationReview.objects.filter(package__case=case,pk=v['meaning_review_id'],kind='meaning').first()
        process_ids(v['process_ids'])
        if not source or not review or source.sha256!=v['source_sha256'] or source.metadata['classification']!='documented_policy' or source.metadata.get('document_kind')!='support_sop':raise ValidationError('SOP reference needs exact documented Support SOP source and meaning review')
        if SOP in review.package.payload['policy_components']:raise ValidationError('SOP validation cannot depend on its own configuration')
        source_current(source)
        if source.pk not in review.package.payload['source_ids'] or not set(v['process_ids'])<=set(review.package.payload['process_ids']) or not set(v['process_ids'])<=set(source.metadata['process_ids']):raise ValidationError('SOP reviewed source/scope mismatch')
        try:current=approved_review(review.package,'meaning')
        except PermissionDenied:raise ValidationError('SOP owner validation authority is no longer current')
        if current.pk!=review.pk:raise ValidationError('Current exact owner meaning review required')

PROTECTION_OWNER='AF13.protection_owner_rules'
PROTECTION_ACCEPTANCE='AF13.protection_acceptance_rules'
PROTECTION_OWNER_SCHEMA='schema:psl/protection-owner/v1'
PROTECTION_OWNER_VALUE=copy.deepcopy(SCHEMAS[OWNER][1])
PROTECTION_SCHEMA='schema:psl/protection-acceptance/v1'
PROTECTION_VALUE=copy.deepcopy(SCHEMAS[ACCEPTANCE][1])
PROTECTION_VALUE['properties']['private_protection']=obj({'inventory':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':obj({'package_id':ID,'assessment_id':ID})},'freshness_seconds':{'type':'integer','minimum':1,'maximum':31536000},'receipt_requirement':{'enum':['observed','found']},'independent_transport_acceptor':{'const':True}})
PROTECTION_VALUE['required'].append('private_protection')
SCHEMAS[PROTECTION_OWNER]=(PROTECTION_OWNER_SCHEMA,PROTECTION_OWNER_VALUE)
SCHEMAS[PROTECTION_ACCEPTANCE]=(PROTECTION_SCHEMA,PROTECTION_VALUE)

# Explicit native kind in v2; historical v1 inventories remain restore-only.
PROTECTION_FILE_SCHEMA='schema:psl/protection-acceptance/v2'
PROTECTION_FILE_VALUE=copy.deepcopy(PROTECTION_VALUE)
PROTECTION_FILE_VALUE['properties']['private_protection']['properties']['inventory']['items']=obj({'package_id':ID,'assessment_id':ID,'native_kind':{'enum':['restore','export','backup']}})
