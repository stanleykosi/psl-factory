"""Separate F43 disclosure boundary; deliberately does not compute group balances."""
import json
import hashlib
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, add_evidence, event, bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values, decision_authority
from apps.policy.group_forecast_validators import validate_group
from apps.documents.contracts import digest
from apps.documents.models import Template, ControlledReview, PublicationReceipt, Publication
from apps.documents.controlled import _create_version, project_payload
from apps.pmo.services import subject
from .models import ForecastRun, ForecastBinding
from . import forecast

IMPLEMENTATION='forecast-group/selected-items-v1'
TITLE='Selected group cash forecast'
SUMMARY='Owner-selected cash assumptions only. No group opening, closing or aggregate balance is calculated. No payment authority is granted.'
SCOPE='No BU allocation, entity consolidation or full-business accounting oracle is inferred.'


def project(result, policy):
    """Allowlist construction, never remove rows from precomputed internal totals."""
    validate_group(policy)
    if policy['implementation']!='native_selected_items_v1':
        raise ValidationError('owner_needed: Group aggregate method and independent owner financial oracle remain unresolved')
    rows={row['key']:row for row in result['items']}
    if set(policy['rows'])-rows.keys():
        raise ValidationError('Disclosure policy selects an absent native forecast row')
    projected={'implementation':IMPLEMENTATION,
            'metadata':{k:result[k] for k in policy['metadata']},
            'rows':[{k:rows[key][k] for k in policy['fields']} for key in policy['rows']],
            'scope':'selected_assumptions_only_no_group_balances', 'execution_authorized':False}
    summary=forecast.continuation_summary([rows[key] for key in policy['rows']])
    if summary:projected['continuation']=summary
    return projected


def inputs(run):
    review=forecast.approved(run)
    c=active_component('D10.audience_projection_rules',run.case)
    policy=reference_values(c)[0].get('group')
    if policy is None:raise ValidationError('owner_needed: Configure exact group disclosure rows, fields, recipients and review authority')
    validate_group(policy)
    if policy['run_id']!=run.pk or policy['run_hash']!=run.sha256:
        raise ValidationError('Group disclosure policy must select the exact reviewed native calculation')
    projected=project(run.result,policy)
    oracle=subject(run.case,policy['oracle_evidence_id'],'forecast_group_oracle')
    try:expected=json.loads(oracle.body)
    except (ValueError,TypeError):raise ValidationError('Supply an exact independent selected-projection oracle') from None
    if oracle.sha256!=hashlib.sha256(oracle.body.encode()).hexdigest():raise ValidationError('Disclosure oracle evidence hash differs')
    if expected!=projected:raise ValidationError('Group projection differs from the supplied disclosure oracle')
    return {'projection_implementation':IMPLEMENTATION,'run':run.pk,'run_hash':run.sha256,
            'output_review':review.pk,'forecast_authority':review.authority,'method_config':review.snapshot['method'],'projection_config':c.pk,'projection':policy,
            'audience':'group','oracle_hash':oracle.sha256,'projection_hash':digest(projected)}


def fields(projected,evidence_id):
    return {key:{'text':value,'evidence_ids':[evidence_id]} for key,value in
            [('executive_summary',SUMMARY),('financial_metrics',json.dumps(projected,sort_keys=True)),('bu_totals',SCOPE)]}


@transaction.atomic
def draft(actor,case_id,run_id,template_id,expected):
    case=lock_case(actor,case_id,'finance.publish',expected);require(actor,case,'finance.read')
    run=forecast.exact(case,ForecastRun,run_id);snapshot=inputs(run)
    template=Template.objects.filter(pk=template_id,case=case,definition__document_type='finance_group_report').first()
    if not template:raise ValidationError('Select this case separate group disclosure template')
    from apps.documents.contracts import validate_template
    validate_template(template.definition)
    projected=project(run.result,snapshot['projection'])
    e=add_evidence(actor,case.pk,'finance_group_snapshot',json.dumps(projected,sort_keys=True),'derived:group-forecast',case.revision)
    case.refresh_from_db()
    version=_create_version(actor,case.pk,template.pk,TITLE,'group',fields(projected,e.pk),case.revision,authorized_restricted_source_ids=[e.pk])
    binding=ForecastBinding.objects.create(version=version,run=run,snapshot=snapshot)
    check_content(binding)
    from .documents import sender
    sender(actor,version)
    return version


def check_content(binding):
    v=binding.version
    if v.audience!='group' or v.template.definition['document_type']!='finance_group_report':raise ValidationError('Separate group document boundary required')
    projected=project(binding.run.result,binding.snapshot['projection'])
    if not isinstance(v.fields,dict) or set(v.fields)!={'executive_summary','financial_metrics','bu_totals'} or any(not isinstance(f,dict) or set(f)!={'text','evidence_ids'} or not isinstance(f['evidence_ids'],list) for f in v.fields.values()):
        raise ValidationError('Group fields must contain only exact projected sections and evidence')
    ids={pk for f in v.fields.values() for pk in f.get('evidence_ids',[])}
    if len(ids)!=1:raise ValidationError('Group output must cite only its separate projected evidence')
    e=subject(binding.run.case,ids.pop(),'finance_group_snapshot')
    if e.sha256!=hashlib.sha256(e.body.encode()).hexdigest() or e.body!=json.dumps(projected,sort_keys=True):raise ValidationError('Group evidence contains unapproved or hidden content')
    expected_fields=fields(projected,e.pk)
    manifest=[{'id':e.pk,'version':e.version,'sha256':e.sha256}]
    expected=project_payload(TITLE,v.template.definition,'group',expected_fields)
    if v.baseline_manifest!={} or v.fields!=expected_fields or v.payload!=expected or v.payload_sha256!=digest(expected) or v.source_manifest!=manifest:
        raise ValidationError('Group payload, fields or metadata differ from the exact allowlisted projection')
    return projected


def recipient_requirements(binding,recipients):
    if recipients!=sorted(binding.snapshot['projection']['recipient_ids']):
        raise ValidationError('Group recipients differ from exact owner disclosure policy')
    from django.contrib.auth import get_user_model
    users=list(get_user_model().objects.filter(pk__in=recipients))
    if len(users)!=len(recipients):raise ValidationError('Group recipient is absent')
    for user in users:require(user,binding.run.case,'document.receive:group')
    roles=active_component('D05.role_principal_assignments',binding.run.case)
    matrix=active_component('D05.decision_action_matrix',binding.run.case)
    method=active_component('D10.forecast_inclusion_rule_id',binding.run.case)
    return {'D10.audience_projection_rules':binding.snapshot['projection_config'],roles.component:roles.pk,matrix.component:matrix.pk,method.component:method.pk}


def review_context(version,actor,role,verdict):
    binding=ForecastBinding.objects.get(version=version)
    if binding.snapshot!=inputs(binding.run):raise ValidationError('Group source, policy or forecast review changed')
    check_content(binding)
    policy=binding.snapshot['projection']
    if role not in policy['reviewer_roles']:raise PermissionDenied('Select explicitly configured group disclosure reviewer role')
    if actor.pk==version.created_by_id and not policy['allow_preparer_review']:raise PermissionDenied('Separate group disclosure reviewer required')
    from apps.documents.controlled import publication_requirements
    policies,recipients,retention=publication_requirements(binding.run.case,version)
    return {'group':IMPLEMENTATION,'role':role,'authority':decision_authority(actor,binding.run.case,role,verdict),
            'policies':policies,'recipients':recipients,'retention_days':retention,'binding_hash':digest(binding.snapshot)}


@transaction.atomic
def review(actor,case_id,version_id,role,verdict,note,expected):
    case=lock_case(actor,case_id,'document.review_controlled',expected);require(actor,case,'finance.read')
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    binding=ForecastBinding.objects.filter(version_id=version_id,run__case=case,version__audience='group').select_related('version').first()
    if not binding or verdict not in ['approve','return','reject'] or not note.strip() or len(note)>4000:
        raise ValidationError('Select exact group projection, decision and rationale')
    version=binding.version
    if version.document.current_id!=version.pk:raise ValidationError('A newer group document exists')
    previous=version.reviews.order_by('-pk').first()
    if previous and previous.verdict in ['return','reject']:
        raise ValidationError('Prepare a fresh group artifact after return or rejection')
    if Publication.objects.filter(version=version).exists():raise ValidationError('Reserved output cannot be re-reviewed; reconcile original delivery first')
    context=review_context(version,actor,role,verdict)
    r=ControlledReview.objects.create(version=version,actor=actor,verdict=verdict,note=note,authority=context,delegated=False,payload_sha256=version.payload_sha256)
    event(actor,case,'forecast.group_reviewed',version=version.pk,review=r.pk,verdict=verdict);bump(case)
    return r


def approved(version):
    r=version.reviews.order_by('-pk').first()
    if not r or r.verdict!='approve' or r.payload_sha256!=version.payload_sha256:
        raise ValidationError('Exact group disclosure and recipient approval required')
    case=version.document.case
    require(r.actor,case,'document.review_controlled');require(r.actor,case,'finance.read')
    if r.authority!=review_context(version,r.actor,r.authority.get('role'),'approve'):
        raise ValidationError('Group approval authority, source or destination changed')
    return r


def recipient_access(actor,receipt):
    p=receipt.publication;v=p.version
    require(actor,v.document.case,'document.receive:group')
    c=active_component('D10.audience_projection_rules',v.document.case)
    policy=reference_values(c)[0].get('group')
    binding=ForecastBinding.objects.get(version=v)
    if c.pk!=binding.snapshot['projection_config'] or c.pk!=p.policies.get('D10.audience_projection_rules') or policy!=binding.snapshot['projection']:
        raise PermissionDenied('Current exact disclosure policy required; historical receipt retained privately')
    recipients=active_component('D11.recipient_grant_refs',v.document.case)
    if recipients.pk!=p.policies.get(recipients.component) or not any(row['audience']=='group' and row['user_id']==actor.pk for row in reference_values(recipients)):
        raise PermissionDenied('Current exact group recipient policy required')
    check_content(binding)
    if not policy or actor.pk not in policy['recipient_ids'] or actor.pk not in p.recipient_ids or receipt.recipient_id!=actor.pk:
        raise PermissionDenied('Current exact group membership required')
    if receipt.payload!=v.payload or receipt.payload_sha256!=v.payload_sha256:raise ValidationError('Group receipt differs from reviewed output')


def verified(version):
    from apps.documents.controlled import current_version
    current_version(version.document.case,version.pk)
    approved(version)
    binding=ForecastBinding.objects.get(version=version);check_content(binding)
    p=Publication.objects.filter(version=version).first()
    if not p:raise ValidationError('Await controlled group publication')
    if p.job.status!='confirmed':raise ValidationError('Reconcile the original group delivery before final verification')
    from apps.documents.controlled import publication_requirements
    policies,recipients,_=publication_requirements(binding.run.case,version)
    if policies!=p.policies or recipients!=p.recipient_ids:raise ValidationError('Group destination policy changed')
    receipts=list(PublicationReceipt.objects.filter(publication=p))
    if sorted(r.recipient_id for r in receipts)!=recipients:raise ValidationError('Await every exact group recipient receipt')
    for receipt in receipts:recipient_access(receipt.recipient,receipt)
    return {'version':version.pk,'publication':p.pk,'recipient_count':len(receipts),'payload_sha256':version.payload_sha256}
