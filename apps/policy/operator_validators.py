from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from adapters.forecast import obj,KEY
from apps.identity.models import Grant
from .document_validators import typed,ROLES
OPERATOR='OPS.operator_rules';PROTECTION='OPS.protection_rules'
ID={'type':'integer','minimum':1};NULL={'type':'null'}
KINDS=['export','backup','restore','verification']
FAMILIES=['handoff','publication','invoice','engineering','partner','approval','protection','supportresponse','supportchannel','ledgerdata','financefollowup']
PURPOSES=['recover','export','backup','restore','review']
SCHEMAS={
 OPERATOR:('schema:psl/operator-rules/v1',obj({'operators':{'type':'array','minItems':1,'maxItems':40,'items':obj({'user_id':ID,'role':{'enum':ROLES},'purposes':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':PURPOSES}}})},'routes':{'type':'array','maxItems':10,'items':obj({'family':{'enum':FAMILIES},'actions':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['cancel','retry','replace_intent']}}})},'reviewer_id':ID,'reviewer_role':{'enum':ROLES},'independent_review':{'type':'boolean'}})),
 PROTECTION:('schema:psl/protection-rules/v1',obj({'projection':{'const':'portable_case_metadata_v1'},'max_records':{'type':'integer','minimum':1,'maximum':5000},'required_proofs':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':{'enum':KINDS}},'freshness_seconds':{'type':'integer','minimum':1,'maximum':31536000},'rpo_seconds':{'anyOf':[{'type':'integer','minimum':0},NULL]},'rto_seconds':{'anyOf':[{'type':'integer','minimum':1},NULL]},'backup_adapter':{'const':'sealed_local_metadata_v1'},'restore_adapter':{'enum':['isolated_postgres_metadata_v1','reference_only']},'restore_target':{'const':'isolated_metadata_db_v1'},'lease_seconds':{'type':'integer','minimum':10,'maximum':300},'max_attempts':{'type':'integer','minimum':1,'maximum':20}}))}

ACCEPTED_PROTECTION='OPS.accepted_protection_rules'
SCHEMAS[ACCEPTED_PROTECTION]=('schema:psl/accepted-protection-operations/v1',obj({'private_protection_packet_ids':{'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},'private_disclosure':{'const':'accepted_metadata_only'}}))

import copy
PRIVATE_SCHEMA='schema:psl/protection-rules/v2'
PRIVATE_VALUE=copy.deepcopy(SCHEMAS[PROTECTION][1])
PRIVATE_VALUE['properties'].update(private_readiness_packet_ids={'type':'array','minItems':1,'maxItems':100,'uniqueItems':True,'items':ID},private_disclosure={'const':'accepted_metadata_only'})
PRIVATE_VALUE['required']+=['private_readiness_packet_ids','private_disclosure']

from .application_recovery_validators import COMPONENT as APPLICATION,SCHEMA as APPLICATION_SCHEMA,VALUE as APPLICATION_VALUE,validate_reference as validate_application
SCHEMAS[APPLICATION]=(APPLICATION_SCHEMA,APPLICATION_VALUE)
from .cold_recovery_validators import COMPONENT as COLD,SCHEMA as COLD_SCHEMA,VALUE as COLD_VALUE,validate_reference as validate_cold
SCHEMAS[COLD]=(COLD_SCHEMA,COLD_VALUE)
from .reconstitution_validators import COMPONENT as RECONSTITUTION,SCHEMA as RECONSTITUTION_SCHEMA,VALUE as RECONSTITUTION_VALUE,validate_reference as validate_reconstitution
SCHEMAS[RECONSTITUTION]=(RECONSTITUTION_SCHEMA,RECONSTITUTION_VALUE)
from .domain_contract_validators import COMPONENT as DOMAIN,SCHEMA as DOMAIN_SCHEMA,VALUE as DOMAIN_VALUE,validate_reference as validate_domain
SCHEMAS[DOMAIN]=(DOMAIN_SCHEMA,DOMAIN_VALUE)
from .native_finance_validators import COMPONENT as NATIVE_FINANCE,SCHEMA as NATIVE_FINANCE_SCHEMA,VALUE as NATIVE_FINANCE_VALUE,validate_reference as validate_native_finance
SCHEMAS[NATIVE_FINANCE]=(NATIVE_FINANCE_SCHEMA,NATIVE_FINANCE_VALUE)
from .invoice_receipt_validators import SCHEMAS as INVOICE_RECEIPTS,validate_reference as validate_invoice_receipts
SCHEMAS.update(INVOICE_RECEIPTS)
from .followup_readback_validators import COMPONENT as FINANCE_READBACK,SCHEMA as FINANCE_READBACK_SCHEMA,VALUE as FINANCE_READBACK_VALUE,validate_reference as validate_finance_readback
SCHEMAS[FINANCE_READBACK]=(FINANCE_READBACK_SCHEMA,FINANCE_READBACK_VALUE)
from .followup_successor_validators import COMPONENT as FINANCE_SUCCESSORS,SCHEMA as FINANCE_SUCCESSORS_SCHEMA,VALUE as FINANCE_SUCCESSORS_VALUE,validate_reference as validate_finance_successors
SCHEMAS[FINANCE_SUCCESSORS]=(FINANCE_SUCCESSORS_SCHEMA,FINANCE_SUCCESSORS_VALUE)
from .followup_transport_validators import SCHEMAS as FINANCE_TRANSPORT,validate_reference as validate_finance_transport
SCHEMAS.update(FINANCE_TRANSPORT)
from .engagement_validators import SCHEMAS as ENGAGEMENT,validate_reference as validate_engagement
SCHEMAS.update(ENGAGEMENT)
from .identity_resolution_validators import COMPONENT as IDENTITY_RESOLUTION,SCHEMA as IDENTITY_SCHEMA,VALUE as IDENTITY_VALUE,validate_reference as validate_identity_resolution
SCHEMAS[IDENTITY_RESOLUTION]=(IDENTITY_SCHEMA,IDENTITY_VALUE)
from .project_view_validators import COMPONENT as PROJECT_VIEW,SCHEMA as PROJECT_VIEW_SCHEMA,VALUE as PROJECT_VIEW_VALUE,validate_reference as validate_project_view
SCHEMAS[PROJECT_VIEW]=(PROJECT_VIEW_SCHEMA,PROJECT_VIEW_VALUE)
from .planning_validators import COMPONENT as PLANNING,SCHEMA as PLANNING_SCHEMA,VALUE as PLANNING_VALUE,validate_reference as validate_planning
SCHEMAS[PLANNING]=(PLANNING_SCHEMA,PLANNING_VALUE)
from .factory_validators import COMPONENT as FACTORY,SCHEMA as FACTORY_SCHEMA,VALUE as FACTORY_VALUE,validate_reference as validate_factory
SCHEMAS[FACTORY]=(FACTORY_SCHEMA,FACTORY_VALUE)
from .factory_validators import PLANNING_COMPONENT as FACTORY_PLANNING,PLANNING_SCHEMA as FACTORY_PLANNING_SCHEMA,PLANNING_VALUE as FACTORY_PLANNING_VALUE
SCHEMAS[FACTORY_PLANNING]=(FACTORY_PLANNING_SCHEMA,FACTORY_PLANNING_VALUE)
from .factory_validators import COMMERCIAL_COMPONENT as FACTORY_COMMERCIAL,COMMERCIAL_SCHEMA as FACTORY_COMMERCIAL_SCHEMA,COMMERCIAL_VALUE as FACTORY_COMMERCIAL_VALUE
from .factory_validators import DELIVERY_COMPONENT as FACTORY_DELIVERY,DELIVERY_SCHEMA as FACTORY_DELIVERY_SCHEMA,DELIVERY_VALUE as FACTORY_DELIVERY_VALUE
SCHEMAS[FACTORY_DELIVERY]=(FACTORY_DELIVERY_SCHEMA,FACTORY_DELIVERY_VALUE)
from .factory_validators import HYPERCARE_COMPONENT as FACTORY_HYPERCARE,HYPERCARE_SCHEMA as FACTORY_HYPERCARE_SCHEMA,HYPERCARE_VALUE as FACTORY_HYPERCARE_VALUE
SCHEMAS[FACTORY_HYPERCARE]=(FACTORY_HYPERCARE_SCHEMA,FACTORY_HYPERCARE_VALUE)
from .factory_validators import ARCHIVE_COMPONENT as FACTORY_ARCHIVE,ARCHIVE_SCHEMA as FACTORY_ARCHIVE_SCHEMA,ARCHIVE_VALUE as FACTORY_ARCHIVE_VALUE
SCHEMAS[FACTORY_ARCHIVE]=(FACTORY_ARCHIVE_SCHEMA,FACTORY_ARCHIVE_VALUE)
from .factory_validators import HANDOVER_COMPONENT as FACTORY_HANDOVER,HANDOVER_SCHEMA as FACTORY_HANDOVER_SCHEMA,HANDOVER_VALUE as FACTORY_HANDOVER_VALUE
SCHEMAS[FACTORY_HANDOVER]=(FACTORY_HANDOVER_SCHEMA,FACTORY_HANDOVER_VALUE)
from .factory_validators import CLOSURE_COMPONENT as FACTORY_CLOSURE,CLOSURE_SCHEMA as FACTORY_CLOSURE_SCHEMA,CLOSURE_VALUE as FACTORY_CLOSURE_VALUE
SCHEMAS[FACTORY_CLOSURE]=(FACTORY_CLOSURE_SCHEMA,FACTORY_CLOSURE_VALUE)
from .factory_validators import GO_LIVE_COMPONENT as FACTORY_GO_LIVE,GO_LIVE_SCHEMA as FACTORY_GO_LIVE_SCHEMA,GO_LIVE_VALUE as FACTORY_GO_LIVE_VALUE
SCHEMAS[FACTORY_GO_LIVE]=(FACTORY_GO_LIVE_SCHEMA,FACTORY_GO_LIVE_VALUE)
from .factory_validators import PAYROLL_COMPONENT as FACTORY_PAYROLL,PAYROLL_SCHEMA as FACTORY_PAYROLL_SCHEMA,PAYROLL_VALUE as FACTORY_PAYROLL_VALUE
SCHEMAS[FACTORY_PAYROLL]=(FACTORY_PAYROLL_SCHEMA,FACTORY_PAYROLL_VALUE)
from .factory_validators import CHANGE_COMPONENT as FACTORY_CHANGE,CHANGE_SCHEMA as FACTORY_CHANGE_SCHEMA,CHANGE_VALUE as FACTORY_CHANGE_VALUE
SCHEMAS[FACTORY_CHANGE]=(FACTORY_CHANGE_SCHEMA,FACTORY_CHANGE_VALUE)
from .factory_emergency_validators import COMPONENT as FACTORY_EMERGENCY,SCHEMA as FACTORY_EMERGENCY_SCHEMA,VALUE as FACTORY_EMERGENCY_VALUE,validate_reference as validate_emergency_factory
SCHEMAS[FACTORY_EMERGENCY]=(FACTORY_EMERGENCY_SCHEMA,FACTORY_EMERGENCY_VALUE)
SCHEMAS[FACTORY_COMMERCIAL]=(FACTORY_COMMERCIAL_SCHEMA,FACTORY_COMMERCIAL_VALUE)
from .factory_routing_validators import COMPONENT as FACTORY_RESPONSIBILITY,SCHEMA as FACTORY_RESPONSIBILITY_SCHEMA,VALUE as FACTORY_RESPONSIBILITY_VALUE,validate_reference as validate_factory_responsibility
SCHEMAS[FACTORY_RESPONSIBILITY]=(FACTORY_RESPONSIBILITY_SCHEMA,FACTORY_RESPONSIBILITY_VALUE)
from .reviewer_availability_validators import COMPONENT as REVIEW_AVAILABILITY,SCHEMA as REVIEW_AVAILABILITY_SCHEMA,VALUE as REVIEW_AVAILABILITY_VALUE,validate_reference as validate_review_availability
SCHEMAS[REVIEW_AVAILABILITY]=(REVIEW_AVAILABILITY_SCHEMA,REVIEW_AVAILABILITY_VALUE)
from .factory_accounting_validators import COMPONENT as FACTORY_ACCOUNTING,SCHEMA as FACTORY_ACCOUNTING_SCHEMA,ACCOUNTING_VALUE,validate_reference as validate_factory_accounting
SCHEMAS[FACTORY_ACCOUNTING]=(FACTORY_ACCOUNTING_SCHEMA,ACCOUNTING_VALUE)
from .factory_coordinator_validators import COMPONENT as FACTORY_COORDINATOR,SCHEMA as FACTORY_COORDINATOR_SCHEMA,VALUE as COORDINATOR_VALUE,validate_reference as validate_factory_coordinator
SCHEMAS[FACTORY_COORDINATOR]=(FACTORY_COORDINATOR_SCHEMA,COORDINATOR_VALUE)
from .factory_recovery_validators import COMPONENT as FACTORY_RECOVERY,SCHEMA as FACTORY_RECOVERY_SCHEMA,VALUE as FACTORY_RECOVERY_VALUE,validate_reference as validate_factory_recovery
SCHEMAS[FACTORY_RECOVERY]=(FACTORY_RECOVERY_SCHEMA,FACTORY_RECOVERY_VALUE)
from .factory_receipt_recovery_validators import COMPONENT as RECEIPT_RECOVERY,SCHEMA as RECEIPT_RECOVERY_SCHEMA,VALUE as RECEIPT_RECOVERY_VALUE,validate_reference as validate_receipt_recovery
SCHEMAS[RECEIPT_RECOVERY]=(RECEIPT_RECOVERY_SCHEMA,RECEIPT_RECOVERY_VALUE)
from .factory_rfp_validators import COMPONENT as FACTORY_RFP,SCHEMA as FACTORY_RFP_SCHEMA,RFP_VALUE,validate_reference as validate_factory_rfp
SCHEMAS[FACTORY_RFP]=(FACTORY_RFP_SCHEMA,RFP_VALUE)
from .rfp_outcome_validators import COMPONENT as RFP_OUTCOME,SCHEMA as RFP_OUTCOME_SCHEMA,VALUE as RFP_OUTCOME_VALUE,validate_reference as validate_rfp_outcome
SCHEMAS[RFP_OUTCOME]=(RFP_OUTCOME_SCHEMA,RFP_OUTCOME_VALUE)

from .factory_forecast_validators import COMPONENT as FACTORY_FORECAST,SCHEMA as FORECAST_SCHEMA,VALUE as FORECAST_VALUE,validate_reference as validate_forecast_factory
SCHEMAS[FACTORY_FORECAST]=(FORECAST_SCHEMA,FORECAST_VALUE)

def validate_reference(component,target,case,runtime=False):
    if component==FACTORY_FORECAST:return validate_forecast_factory(component,target,case,runtime)
    if component==RFP_OUTCOME:return validate_rfp_outcome(component,target,case,runtime)
    if component==FACTORY_RFP:return validate_factory_rfp(component,target,case,runtime)
    if component==RECEIPT_RECOVERY:return validate_receipt_recovery(component,target,case,runtime)
    if component==FACTORY_RECOVERY:return validate_factory_recovery(component,target,case,runtime)
    if component==FACTORY_COORDINATOR:return validate_factory_coordinator(component,target,case,runtime)
    if component==FACTORY_ACCOUNTING:return validate_factory_accounting(component,target,case,runtime)
    if component==REVIEW_AVAILABILITY:return validate_review_availability(component,target,case,runtime)
    if component==FACTORY_RESPONSIBILITY:return validate_factory_responsibility(component,target,case,runtime)
    if component==FACTORY_EMERGENCY:return validate_emergency_factory(component,target,case,runtime)
    if component in [FACTORY_PAYROLL,FACTORY,FACTORY_PLANNING,FACTORY_COMMERCIAL,FACTORY_DELIVERY,FACTORY_HYPERCARE,FACTORY_ARCHIVE,FACTORY_HANDOVER,FACTORY_CLOSURE,FACTORY_GO_LIVE,FACTORY_CHANGE]:return validate_factory(component,target,case,runtime)
    if component==PLANNING:return validate_planning(component,target,case,runtime)
    if component==PROJECT_VIEW:return validate_project_view(component,target,case,runtime)
    if component==IDENTITY_RESOLUTION:return validate_identity_resolution(component,target,case,runtime)
    if component in ENGAGEMENT:return validate_engagement(component,target,case,runtime)
    if component in FINANCE_TRANSPORT:return validate_finance_transport(component,target,case,runtime)
    if component==FINANCE_SUCCESSORS:return validate_finance_successors(component,target,case,runtime)
    if component==FINANCE_READBACK:return validate_finance_readback(component,target,case,runtime)
    if component in INVOICE_RECEIPTS:return validate_invoice_receipts(component,target,case,runtime)
    if component==NATIVE_FINANCE:return validate_native_finance(component,target,case,runtime)
    if component==DOMAIN:return validate_domain(component,target,case,runtime)
    if component==RECONSTITUTION:return validate_reconstitution(component,target,case,runtime)
    if component==COLD:return validate_cold(component,target,case,runtime)
    if component==APPLICATION:return validate_application(component,target,case,runtime)
    private=component==PROTECTION and target.schema_ref==PRIVATE_SCHEMA
    v=typed(target,PRIVATE_SCHEMA,PRIVATE_VALUE) if private else typed(target,*SCHEMAS[component])
    if private:
        from apps.workflows.private_readiness_operations import validate_policy
        validate_policy(case,v,runtime)
    if component==ACCEPTED_PROTECTION:
        from apps.workflows.accepted_protection_operations import validate_policy
        validate_policy(case,v,runtime)
    if component==OPERATOR:
        if any(r['family']=='financefollowup' and r['actions']!=['retry'] for r in v['routes']):raise ValidationError('Finance intake transport supports original-request retry only')
        if len({r['user_id'] for r in v['operators']})!=len(v['operators']) or len({r['family'] for r in v['routes']})!=len(v['routes']):raise ValidationError('Distinct scoped operators and routes required')
        if not any(r['user_id']==v['reviewer_id'] and r['role']==v['reviewer_role'] and 'review' in r['purposes'] for r in v['operators']):raise ValidationError('Explicit reviewer must have the configured review purpose/role')
        if any(r['family'] in ['handoff','publication','supportresponse','supportchannel','ledgerdata'] and 'replace_intent' in r['actions'] for r in v['routes']):raise ValidationError('Source workflow has no intent-replacement interface')
        if any(r['family']=='ledgerdata' and r['actions']!=['retry'] for r in v['routes']):raise ValidationError('Private Finance extraction supports original-intent retry only')
        # Runtime authority is checked only for the relevant operator/purpose, never globally revoked by an unrelated operator.
        if not runtime:
            for r in v['operators']:
                if not get_user_model().objects.filter(pk=r['user_id'],is_active=True).exists() or any(not Grant.objects.filter(case=case,user_id=r['user_id'],action='ops.'+p,active=True).exists() for p in r['purposes']):raise ValidationError('Actual scoped operator/purpose grants required')

    if component==OPERATOR and not runtime:
        from apps.workflows.operator_inventory import family_access,PRIVATE_FAMILIES,ROUTES,source_query,job_access
        from apps.identity.services import require
        for family in {r['family'] for r in v['routes']} & PRIVATE_FAMILIES:
            for row in v['operators']:
                if 'recover' in row['purposes']:
                    try:
                        actor=get_user_model().objects.get(pk=row['user_id']);family_access(actor,case,family);require(actor,case,ROUTES[family][3])
                        if family=='ledgerdata':
                            for job in source_query(case,family):job_access(actor,case,family,job)
                    except PermissionDenied:raise ValidationError('Private recovery requires native source/read/operate grants') from None
