from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj
from adapters.costing import ID,HASH
from .document_validators import typed
import copy
COMPONENT='P14-Q01.commercial_costing_rule_oracle'
SCHEMAS={COMPONENT:('schema:psl/commercial-costing-oracle/v1',obj({'rule_id':ID,'rule_sha256':HASH,'rule_review_id':ID,'oracle_id':ID,'oracle_sha256':HASH,'oracle_review_id':ID}))}
STUDIO_SCHEMA = 'schema:psl/commercial-costing-oracle/v2'
STUDIO_VALUE = copy.deepcopy(SCHEMAS[COMPONENT][1])
STUDIO_VALUE['properties']['studio_source_id'] = ID
STUDIO_VALUE['required'].append('studio_source_id')

def validate_reference(component,target,case,runtime=False):
    studio = target.schema_ref == STUDIO_SCHEMA
    v=typed(target,STUDIO_SCHEMA,STUDIO_VALUE) if studio else typed(target,*SCHEMAS[component])
    from apps.pmo import costing as d
    source_case=case
    if studio:
        from apps.pmo.costing_studio import source_case as studio_case
        source_case=studio_case(None,case,v)
    r=d.rule_for(source_case,v['rule_id']);o=d.oracle_for(r,v['oracle_id'])
    try:rr=d.confirmed(r);review=d.confirmed(r,o)
    except PermissionDenied:raise ValidationError('Current costing owner/oracle authority and source access required')
    expected={'rule_id':r.pk,'rule_sha256':r.sha256,'rule_review_id':rr.pk,'oracle_id':o.pk,'oracle_sha256':o.sha256,'oracle_review_id':review.pk}
    if studio:expected['studio_source_id']=v['studio_source_id']
    if v!=expected:raise ValidationError('Exact current rule, independent oracle and reviews required')
    d.oracle_results(r,o,require_match=True)
