from django.core.exceptions import ValidationError,PermissionDenied
from adapters.forecast import obj
from adapters.costing import ID,HASH
from .document_validators import typed
COMPONENT='P14-Q01.commercial_costing_rule_oracle'
SCHEMAS={COMPONENT:('schema:psl/commercial-costing-oracle/v1',obj({'rule_id':ID,'rule_sha256':HASH,'rule_review_id':ID,'oracle_id':ID,'oracle_sha256':HASH,'oracle_review_id':ID}))}

def validate_reference(component,target,case,runtime=False):
    v=typed(target,*SCHEMAS[component])
    from apps.pmo import costing as d
    r=d.rule_for(case,v['rule_id']);o=d.oracle_for(r,v['oracle_id'])
    try:rr=d.confirmed(r);review=d.confirmed(r,o)
    except PermissionDenied:raise ValidationError('Current costing owner/oracle authority and source access required')
    if v!={'rule_id':r.pk,'rule_sha256':r.sha256,'rule_review_id':rr.pk,'oracle_id':o.pk,'oracle_sha256':o.sha256,'oracle_review_id':review.pk}:raise ValidationError('Exact current rule, independent oracle and reviews required')
    d.oracle_results(r,o,require_match=True)
