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

    if any(type(value) is not int or value < 1 for value in [base_id, latest_revision, expected]):
        raise ValidationError('Use exact current disclosure and workspace revisions.')
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


def disclosure_field_review(actor, case_id, configuration_id):
    """Read the exact proposal and its original reviewed terms under current access."""
    from apps.core.models import Audit
    from .hrfinance_validators import DISCLOSURE
    from .impact import configuration
    from .models import Configuration
    from .services import active_component, reference_values, validate_envelope

    draft = configuration(actor, case_id, configuration_id)
    recorded = Audit.objects.filter(case_id=case_id, action='policy.disclosure_fields_proposed',
                                     data__configuration=draft.pk).first()
    if draft.component != DISCLOSURE or recorded is None:
        raise ValidationError('Choose a saved visibility proposal from this workspace.')
    base = configuration(actor, case_id, recorded.data['base'])
    original = reference_values(base)[0]
    proposed = reference_values(draft)[0]
    if (base.component != DISCLOSURE or
        {key: value for key, value in original.items() if key != 'allowed_fields'} !=
        {key: value for key, value in proposed.items() if key != 'allowed_fields'}):
        raise ValidationError('Review the complete disclosure terms through its configuration history.')
    validate_envelope(draft.case, draft.envelope)
    state = draft.states.order_by('-pk').first().state
    current = active_component(DISCLOSURE, draft.case)
    latest = Configuration.objects.filter(case_id=case_id, component=DISCLOSURE).order_by('-revision').first()
    return {'configuration': draft, 'base': base, 'original': original, 'proposed': proposed,
            'reason': recorded.data['reason'], 'state': state,
            'current': latest.pk == draft.pk and current.pk == base.pk}


@transaction.atomic
def review_disclosure_fields(actor, case_id, configuration_id, expected_state, action, expected):
    from apps.core.services import bump
    from .services import transition

    if any(type(value) is not int or value < 1 for value in [configuration_id, expected]):
        raise ValidationError('Use exact current disclosure and workspace revisions.')
    if action not in {'validate', 'activate'}:
        raise ValidationError('Choose an available visibility review action.')
    case = lock_case(actor, case_id, 'policy.configure' if action == 'validate' else 'policy.activate', expected)
    review = disclosure_field_review(actor, case.pk, configuration_id)
    if (not review['current'] or review['state'] != expected_state or
        review['state'] != ('draft' if action == 'validate' else 'validated')):
        raise ValidationError('The proposal changed. Refresh its current review before continuing.')
    result = transition(actor, configuration_id, 'validated' if action == 'validate' else 'active')
    bump(case)
    return result

@transaction.atomic
def draft_hrfinance_policy(actor,case_id,component,content,evidence_id,effective_from):
    case=lock_case(actor,case_id,'policy.configure')
    if component not in SCHEMAS:raise ValidationError('Choose an HR/Finance interface')
    r=register_reference(actor,case.pk,'hrfinance:'+str(uuid4()),SCHEMAS[component][0],content,evidence_id)
    value={'artifact_ref':r.ref,'artifact_version':r.version,'sha256':r.sha256,'schema_ref':r.schema_ref}
    return save_draft(actor,case.pk,{'slot_id':components()[component]['parent_decision_id'],'component_id':component,'component_schema_ref':components()[component]['schema_ref'],'schema_version':'1','policy_revision':1,'lifecycle':'draft','subject_scope':{'kind':'project' if case.kind=='project' else 'service','ref':str(case.pk)},'effective_from':aware(effective_from).isoformat(),'effective_until':None,'evidence_refs':['evidence:'+str(evidence_id)],'human_decision_ref':'evidence:'+str(evidence_id),'implementation_id':'psl.reference-validation','implementation_version':'1','reviewed_implementation_ref':'code:apps/policy/services.py#reference-validation-v1','fixture_scope':'synthetic_test' if case.synthetic else 'operational','value':value})
