"""Closed planning capture protocol. Source IDs are references, never authority."""
from adapters.forecast import obj,KEY
from apps.policy.planning_validators import ID,NULL,TEAMS,STATES
REF={'anyOf':[ID,NULL]}
INPUT=obj({'prd_id':REF,'scope_id':REF,'engineering_estimate_id':REF,'security_estimate_id':REF,
 'stakeholders':{'type':'array','minItems':4,'maxItems':4,'items':obj({'team':{'enum':TEAMS},'contact_id':REF,'evidence_id':REF})},
 'questions':{'type':'array','maxItems':100,'items':obj({'key':KEY,'detail':{'type':'string','minLength':1,'maxLength':1000},'state':{'enum':STATES},'action_id':REF,'evidence_id':REF})}})
CORRELATION_FIELDS = ['scope_id', 'engineering_estimate_id', 'security_estimate_id']
TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 500, 'pattern': r'\S'}
CORRELATION_ROW = obj({'key': KEY, 'source_field': {'enum': CORRELATION_FIELDS}, 'source_id': {'type': 'integer', 'minimum': 1},
    'document_version': {'anyOf': [{'type': 'string', 'minLength': 1, 'maxLength': 100, 'pattern': r'\S'}, {'type': 'null'}]},
    'target_prd_id': REF, 'target_scope_id': REF, 'evidence_id': REF,
    'state': {'enum': ['current', 'conflicting', 'excluded']}, 'detail': TEXT, 'resolution_id': REF})
CORRELATIONS = {'type': 'array', 'maxItems': 50, 'items': CORRELATION_ROW}

# Optional at intake, never an implicit source binding or readiness exemption.
INPUT['properties']['source_correlations']=CORRELATIONS
SOURCE_KINDS={'prd_id':['prd','requirements'],'scope_id':['scope_baseline','requirements','plan'],
 'engineering_estimate_id':['engineering_estimate'],'security_estimate_id':['security_estimate']}
PURPOSES=['prd_walkthrough','scope_estimate_alignment']
KINDS={'packet':'planning_packet','prd_walkthrough':'planning_prd_alignment','scope_estimate_alignment':'planning_scope_alignment','comparison':'planning_contract_comparison','ready':'planning_readiness'}

class PlanningPacketAdapter:
    name='referenced-planning-packet-v2'
    @staticmethod
    def parse(evidence):
        import json
        from django.core.exceptions import ValidationError
        try:value=json.loads(evidence.body)
        except (ValueError,TypeError):raise ValidationError('Closed planning JSON record required') from None
        if not isinstance(value,dict):raise ValidationError('Planning record must be an object')
        return value
