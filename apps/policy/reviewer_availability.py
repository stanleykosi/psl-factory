"""Independent immutable availability versions and protected record-preserving drafts."""
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from .reviewer_availability_validators import COMPONENT,validate_value

def source(actor,case):
    from .impact import context,configuration
    from .role_assignments import authorize_header
    from .services import resolve,reference_values
    context(actor,case.pk);authorize_header(actor,case,COMPONENT)
    result=resolve(COMPONENT,case)
    if result.status=='ACTIVE':
        config=configuration(actor,case.pk,result.configuration.pk)
        return config,reference_values(config)[0]
    if result.status in ['CONFLICT','AMBIGUOUS']:raise ValidationError('Resolve conflicting availability sources before editing')
    return None,{'purpose':'finance.invoice.review','records':[]}

@transaction.atomic
def draft_record(actor,case_id,record,evidence_id,effective_from,expected_source,replacement=None):
    from .operator_drafts import draft_operator_policy
    from apps.finance.billing import digest
    case=lock_case(actor,case_id,'policy.configure');config,value=source(actor,case)
    if expected_source!=(config.pk if config else None):raise ValidationError('STALE_VERSION: reload current availability before drafting')
    records=value['records']
    if replacement is not None:
        if sum(digest(r)==replacement for r in records)!=1:raise ValidationError('STALE_VERSION: exact current availability record required')
        records=[r for r in records if digest(r)!=replacement]
    value={'purpose':'finance.invoice.review','records':records+[record]}
    validate_value(case,value)
    return draft_operator_policy(actor,case.pk,COMPONENT,value,evidence_id,effective_from)
