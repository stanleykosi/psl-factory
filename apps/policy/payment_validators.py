"""Finite D13 interfaces. No installed operational authority or payment basis."""
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from .document_validators import typed,ROLES

PREFIX='D13.'
ROLE=PREFIX+'human_authority_role_ref'
PEOPLE=PREFIX+'human_principal_refs'
DELEGATION=PREFIX+'delegation_evidence_refs'
VALIDITY=PREFIX+'validity_revocation_reassessment_rules'
DENOMINATOR=PREFIX+'payment_denominator_rule_ref'
FUNDS=PREFIX+'qualifying_funds_rule_ref'
ID={'type':'integer','minimum':1}
INSTANT={'type':'string','format':'date-time'}
SCHEMAS={
 ROLE:('schema:psl/payment-authority/v1',obj({'role':{'enum':ROLES},'human_only':{'const':True}})),
 PEOPLE:('schema:psl/payment-human/v1',obj({'user_id':ID,'kind':{'const':'human'}})),
 DELEGATION:('schema:psl/payment-delegation/v1',obj({'mode':{'enum':['disabled','explicit']},'delegations':{'type':'array','maxItems':100,'items':obj({'principal_id':ID,'delegate_id':ID,'valid_from':INSTANT,'valid_until':INSTANT,'evidence_id':ID})}})),
 VALIDITY:('schema:psl/payment-validity/v1',obj({'max_validity_seconds':{'type':'integer','minimum':1,'maximum':31536000},'allow_self_approval':{'type':'boolean'},'revocation':{'const':'current_authority'},'reassessment':{'const':'any_bound_change'}})),
 DENOMINATOR:('schema:psl/payment-denominator/v1',obj({'method':{'const':'adjusted_issued_invoices'},'coverage_id':ID,'scope':{'const':'complete_selected_coverage'},'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount_basis':KEY})),
 FUNDS:('schema:psl/payment-funds/v1',obj({'method':{'enum':['allocated_to_selected_invoices','verified_assigned_to_selected_coverage']},'coverage_id':ID,'currency':{'type':'string','pattern':'^[A-Z]{3}$'},'amount_basis':KEY})),
}

def validate_reference(component,target,case,runtime=False):
    from apps.core.models import Evidence
    from apps.finance.models import BillingCoverage
    from apps.pmo.clocks import aware
    v=typed(target,*SCHEMAS[component])
    if component==PEOPLE:
        if not get_user_model().objects.filter(pk=v['user_id'],is_active=True).exists():raise ValidationError('D13 human principal must be active')
    if component in [DENOMINATOR,FUNDS]:
        c=BillingCoverage.objects.filter(case=case,pk=v['coverage_id']).first()
        if not c or c.currency!=v['currency']:raise ValidationError('Payment basis needs exact case coverage and currency; invoice/funds amount basis is explicit')
    if component==DELEGATION:
        if (v['mode']=='disabled')!= (not v['delegations']):raise ValidationError('Disabled delegation must be empty; explicit delegation needs records')
        for d in v['delegations']:
            if d['delegate_id']==d['principal_id'] or aware(d['valid_from'])>=aware(d['valid_until']):raise ValidationError('Delegation needs distinct people and an increasing aware window')
            if get_user_model().objects.filter(pk__in=[d['delegate_id'],d['principal_id']],is_active=True).count()!=2 or not Evidence.objects.filter(case=case,pk=d['evidence_id']).exists():raise ValidationError('Delegation needs active people and scoped evidence')

def validate_collection(component,values):
    if component==PEOPLE and len({v['user_id'] for v in values})!=len(values):raise ValidationError('Duplicate D13 human principal')
    if component==DELEGATION and len(values)!=1:raise ValidationError('Configure one explicit D13 delegation catalogue')

