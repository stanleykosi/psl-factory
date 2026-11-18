from uuid import uuid4
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case
from apps.pmo.clocks import aware
from .registry import components
from .services import register_reference,save_draft
from .hrfinance_validators import SCHEMAS


@transaction.atomic
def draft_disclosure_fields(actor, case_id, base_id, latest_revision, fields, evidence_id,
                            effective_from, expected, *, reason):
    """Propose fields against one current disclosure without changing its other terms."""
    from apps.core.services import bump, event
    from apps.documents.contracts import validate
    from apps.identity.services import require
    from .hrfinance_validators import DISCLOSURE, FIELD_LIST
    from .models import Configuration
    from .impact import configuration
    from .services import active_component, reference_values, validate_envelope

    case = lock_case(actor, case_id, 'policy.configure', expected)
    require(actor, case, 'case.read')
    require(actor, case, 'policy.read')
    current = active_component(DISCLOSURE, case)
    configuration(actor, case.pk, current.pk)
    latest = Configuration.objects.filter(case=case, component=DISCLOSURE).order_by('-revision').first()
    if current.pk != base_id or latest.revision != latest_revision:
        raise ValidationError('The disclosure changed. Refresh before proposing its fields.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError('Provide a concise reason for the visibility change.')
    validate(FIELD_LIST, fields)
    content = dict(reference_values(current)[0], allowed_fields=fields)
    draft = draft_hrfinance_policy(actor, case.pk, DISCLOSURE, content, evidence_id, effective_from)
    validate_envelope(case, draft.envelope)
    event(actor, case, 'policy.disclosure_fields_proposed', configuration=draft.pk,
          base=current.pk, reason=reason.strip())
    bump(case)
    return draft

@transaction.atomic
def draft_hrfinance_policy(actor,case_id,component,content,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    if component not in SCHEMAS:raise ValidationError('Choose an HR/Finance interface')
    r=register_reference(actor,case.pk,'hrfinance:'+str(uuid4()),SCHEMAS[component][0],content,evidence_id)
    value={'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
    return save_draft(actor,case.pk,{'slot_id':components()[component]['parent_decision_id'],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
