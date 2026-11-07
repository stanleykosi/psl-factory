from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .document_validators import typed,ROLES
from .finance_validators import obj,KEY

ROLE_LIST={'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':{'enum':ROLES}}
SCHEMAS={
'D08.obligation_namespace':('obligation-namespace',obj({
    'implementation':{'const':'explicit_obligation_identity_v1'}, 'namespace':KEY,
    'key_contract':obj({'reference':KEY,'version':{'type':'integer','minimum':1},'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}}),
    'history_scope':obj({'reference':KEY,'version':{'type':'integer','minimum':1},'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'coverage':{'enum':['unresolved','supplied_subset','declared_complete']}}),
    'resolver_role':{'enum':ROLES},
    'resolver_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':{'type':'integer','minimum':1}},
    'legacy_mode':{'const':'explicit_reconciliation_only'}})),
'D08.adapter_contract_ref':('invoice-adapter',obj({'implementation':{'const':'internal_invoice_register_v1'},'recipient_id':{'type':'integer','minimum':1},
    'require_due_date':{'type':'boolean'},'allow_partial_usage':{'type':'boolean'},'issuer_roles':ROLE_LIST,'payable_basis':{'const':'gross_including_tax'}})),
'D08.duplicate_correction_rules':('invoice-identity',obj({'implementation':{'const':'single_obligation_v1'},'on_unknown':{'const':'reconcile_first'},
    'max_attempts':{'type':'integer','minimum':1,'maximum':10},'lease_seconds':{'type':'integer','minimum':5,'maximum':120},'cancellation':{'const':'sticky_before_effect'}})),
'D14.receipt_verification_source_ref':('cash-source',obj({'source':KEY,'implementation':{'const':'supplied_statement_v1'},'currency':{'type':'string','pattern':'^[A-Z]{3}$'},
    'amount_basis':{'const':'gross_including_tax'},'decimal_places':{'type':'integer','minimum':0,'maximum':8},'require_independent_evidence':{'type':'boolean'}})),
'D14.recorder_authority_ref':('cash-recorder',obj({'roles':ROLE_LIST,'allow_reporter_verify':{'type':'boolean'}})),
'D14.allocation_rule_ref':('cash-matching',obj({'implementation':{'const':'explicit_human_v1'},'roles':ROLE_LIST,'allow_reassignment':{'type':'boolean'},'allow_verifier_allocation':{'type':'boolean'},'overdue_definition':{'const':'due_date_before_as_of'},'decimal_places':{'type':'integer','minimum':0,'maximum':8}})),
'D14.adjustment_correction_rule_refs':('cash-reversal',obj({'target':{'enum':['lot','allocation']},'implementation':{'const':'full_once_v1'},'roles':ROLE_LIST,'require_distinct_verifier':{'type':'boolean'}})),
'D14.legal_document_requirements':('cash-legal-evidence',obj({'target':{'enum':['lot','allocation']},'evidence_kind':{'const':'cash_correction'},'reason_required':{'const':True}}))}
SUPPORTED=set(SCHEMAS)
ARRAYS={'D14.adjustment_correction_rule_refs','D14.legal_document_requirements'}
STRINGS=SUPPORTED-ARRAYS-{'D08.duplicate_correction_rules','D08.obligation_namespace'}

def validate_reference(component,target,case,runtime=False):
    if target.schema_ref in ['schema:psl/invoice-identity/v2','schema:psl/financial-correction/v1','schema:psl/financial-legal-evidence/v1']:
        from .correction_validators import validate_reference as validate_correction
        validate_correction(component,target,case);return
    name,schema=SCHEMAS[component];v=typed(target,'schema:psl/'+name+'/v1',schema)
    if component=='D08.adapter_contract_ref':
        from apps.identity.models import Grant
        if not get_user_model().objects.filter(pk=v['recipient_id'],is_active=True).exists():raise ValidationError('Invoice recipient must be an active configured principal')
        if not runtime and not Grant.objects.filter(case=case,user_id=v['recipient_id'],action='finance.invoice.receive',active=True).exists():raise ValidationError('Invoice recipient requires explicit case receive grant')

def validate_collection(component,values):
    if component in ARRAYS and len({v['target'] for v in values})!=len(values):raise ValidationError('Duplicate cash correction target policy')
