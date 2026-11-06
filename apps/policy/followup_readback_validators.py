from django.db import transaction
from adapters.forecast import obj
from .document_validators import typed
COMPONENT='OPS.native_finance_readback'
SCHEMA='schema:psl/native-finance-readback/v1'
VALUE=obj({'implementation':{'const':'source_finance_authority_v1'},
 'max_records':{'type':'integer','minimum':10,'maximum':1000},'max_queries':{'type':'integer','minimum':10,'maximum':1000},
 'max_payload_bytes':{'type':'integer','minimum':256,'maximum':1048576},'max_seconds':{'type':'integer','minimum':1,'maximum':60},
 'observation_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},'review_valid_seconds':{'type':'integer','minimum':1,'maximum':31536000},
 'allow_synthetic':{'type':'boolean'},'disclosure':{'const':'acknowledgement_metadata_only'}})

@transaction.atomic
def validate_reference(component,target,case,runtime=False):
    from django.core.exceptions import ValidationError
    v=typed(target,SCHEMA,VALUE)
    if v['allow_synthetic']!=case.synthetic:raise ValidationError('Exact source readback fixture classification required')
    return v
