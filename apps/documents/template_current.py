"""Optional owner-approved currentness. Explicit historical pins remain independent."""
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Max
from apps.core.models import Evidence
from apps.core.services import lock_case, bump, event
from apps.identity.services import require
from apps.policy.services import active_component, reference_values
from .contracts import digest, AUDIENCES, TEMPLATE_SCHEMA
from .models import Template, TemplateScope, TemplateClaim, TemplateClaimRetraction, TemplateResolution

COMPONENT = 'D11.template_storage_retention_rules'
SOURCE_KIND = 'template_current_source'


def text(value, label, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f'{label} is required and limited to {limit} characters')
    return value.strip()


def source(case, pk, actor=None):
    evidence = Evidence.objects.filter(case=case, pk=pk, kind__in=[SOURCE_KIND, 'policy_decision']).first()
    if not evidence:
        raise ValidationError('Select exact same-case template owner source evidence')
    if actor is not None:
        from .template_access import visible_sources
        if not visible_sources(actor,case).filter(pk=pk).exists():
            raise PermissionDenied('Template source needs its owning document-domain access')
    return evidence


def scope_for(case, pk):
    scope = TemplateScope.objects.filter(case=case, pk=pk).select_related('case').first()
    if not scope:
        raise ValidationError('Select an exact template applicability scope on this case')
    return scope


def owner_policy(actor, scope):
    require(actor, scope.case, 'case.read')
    require(actor, scope.case, 'document.read')
    require(actor, scope.case, 'document.template')
    if scope.document_type in ['finance_report','finance_group_report']:
        require(actor,scope.case,'finance.read')
    policy = active_component(COMPONENT, scope.case)
    rules = reference_values(policy)[0].get('template_owners', [])
    if not any(r['scope_id'] == scope.pk and r['user_id'] == actor.pk for r in rules):
        raise PermissionDenied('Document owner is unconfigured for this exact scope or is a different principal')
    return policy


def owner_current(record):
    if record.owner_policy_id is None:
        return False
    try:
        return owner_policy(record.actor, record.scope).pk == record.owner_policy_id
    except (ValidationError, PermissionDenied):
        return False


@transaction.atomic
def capture_source(actor, case_id, body, locator, expected):
    case = lock_case(actor, case_id, 'document.template', expected)
    require(actor, case, 'document.read')
    body, locator = text(body, 'Source content', 100000), text(locator, 'Source reference', 500)
    import hashlib
    evidence = Evidence.objects.create(case=case, kind=SOURCE_KIND,
        version=(case.evidence.filter(kind=SOURCE_KIND).aggregate(n=Max('version'))['n'] or 0)+1,
        body=body, source=locator, sha256=hashlib.sha256(body.encode()).hexdigest(), created_by=actor)
    event(actor, case, 'document.template_current.source', evidence=evidence.pk)
    bump(case)
    return evidence


@transaction.atomic
def register_scope(actor, case_id, document_type, audience, purpose, context, source_owner, evidence_id, expected):
    case = lock_case(actor, case_id, 'document.template', expected)
    require(actor, case, 'document.read')
    if document_type not in TEMPLATE_SCHEMA['properties']['document_type']['enum'] or document_type == 'accepted_finance_metadata' or audience not in AUDIENCES:
        raise ValidationError('Supported controlled document type and audience required')
    if document_type in ['finance_report','finance_group_report']:
        require(actor,case,'finance.read')
    values = dict(document_type=document_type, audience=audience,
        purpose=text(purpose, 'Purpose', 160), context=text(context, 'Applicability context', 160),
        source_owner=text(source_owner, 'Source-owner reference', 160))
    if TemplateScope.objects.filter(case=case, **values).exists():
        raise ValidationError('This exact applicability scope already exists; reuse it instead of splitting competing claims')
    result = TemplateScope.objects.create(case=case, **values, evidence=source(case, evidence_id, actor), actor=actor)
    event(actor, case, 'document.template_current.scope', scope=result.pk)
    bump(case)
    return result


@transaction.atomic
def claim_current(actor, case_id, scope_id, template_id, evidence_id, note, expected, *, confirm_owner=False):
    case = lock_case(actor, case_id, 'document.template', expected)
    require(actor, case, 'document.read')
    scope = scope_for(case, scope_id)
    from .template_access import require_scope, visible_templates
    require_scope(actor,scope)
    if not visible_templates(actor,case).filter(pk=template_id).exists():
        raise PermissionDenied('Template requires its owning document-domain access')
    template = Template.objects.filter(case=case, pk=template_id, definition__document_type=scope.document_type).first()
    if not template or scope.audience not in template.definition['audience_fields']:
        raise ValidationError('Template must match this exact case, document type and audience')
    if type(confirm_owner) is not bool:
        raise ValidationError('Explicit owner confirmation must be boolean')
    policy = owner_policy(actor, scope) if confirm_owner else None
    if policy and template.pk not in reference_values(policy)[0]['template_ids']:
        raise ValidationError('Owner-approved current template must be enabled by current storage policy')
    result = TemplateClaim.objects.create(scope=scope, template=template, evidence=source(case, evidence_id, actor),
        note=text(note, 'Claim rationale'), actor=actor, owner_policy=policy)
    event(actor, case, 'document.template_current.claim', claim=result.pk)
    bump(case)
    return result


def active_claims(scope):
    return list(scope.claims.filter(retraction__isnull=True).select_related('template', 'evidence', 'actor', 'scope__case').order_by('pk'))


@transaction.atomic
def retract_claim(actor, case_id, claim_id, evidence_id, note, expected):
    case = lock_case(actor, case_id, 'document.template', expected)
    require(actor, case, 'document.read')
    claim = TemplateClaim.objects.select_related('scope__case').filter(scope__case=case, pk=claim_id, retraction__isnull=True).first()
    if not claim:
        raise ValidationError('Select an unretracted claim on this case')
    from .template_access import require_scope
    require_scope(actor,claim.scope)
    policy = None if claim.actor_id == actor.pk else owner_policy(actor, claim.scope)
    result = TemplateClaimRetraction.objects.create(claim=claim, evidence=source(case, evidence_id, actor),
        note=text(note, 'Retraction rationale'), actor=actor, owner_policy=policy)
    event(actor, case, 'document.template_current.retract', retraction=result.pk)
    bump(case)
    return result


@transaction.atomic
def resolve_claims(actor, case_id, scope_id, selected_claim_id, claim_ids, evidence_id, note, expected):
    case = lock_case(actor, case_id, 'document.template', expected)
    scope = scope_for(case, scope_id)
    from .template_access import require_scope
    require_scope(actor,scope)
    policy = owner_policy(actor, scope)
    claims = active_claims(scope)
    if not claims or not isinstance(claim_ids, list) or any(type(i) is not int for i in claim_ids) or claim_ids != [c.pk for c in claims]:
        raise ValidationError('Current claims changed; review every exact active claim before resolving')
    chosen = next((c for c in claims if c.pk == selected_claim_id), None)
    if not chosen or chosen.template_id not in reference_values(policy)[0]['template_ids']:
        raise ValidationError('Select one active claim whose template is enabled by current policy')
    result = TemplateResolution.objects.create(scope=scope, selected_claim=chosen, claim_ids=claim_ids,
        evidence=source(case, evidence_id, actor), note=text(note, 'Owner decision rationale'), actor=actor, owner_policy=policy)
    event(actor, case, 'document.template_current.resolved', resolution=result.pk)
    bump(case)
    return result


def status(scope):
    claims = active_claims(scope)
    ids = [c.pk for c in claims]
    result = {'status': 'MISSING', 'claims': claims, 'claim_ids': ids, 'manifest': {},
        'question': 'Which owner-approved template applies to this purpose, context and audience? Capture the exact source; do not infer a current template.'}
    if not claims:
        return result
    resolution = scope.resolutions.select_related('actor', 'scope__case', 'selected_claim').order_by('-pk').first()
    chosen = None
    if resolution and resolution.claim_ids == ids and owner_current(resolution):
        chosen = next((c for c in claims if c.pk == resolution.selected_claim_id), None)
    if not chosen:
        resolution = None
        if len({c.template_id for c in claims}) > 1:
            result.update(status='OWNER_CONFLICT', question='Multiple templates claim current for this exact scope. The configured document owner must select a claim with evidence, or retract an incorrect claim. Both sources remain retained.')
            return result
        # This order selects only equivalent attestations of the SAME immutable
        # template, never a newer competing template or a registration timestamp.
        chosen = next((c for c in claims if owner_current(c)), None)
    if chosen:
        policy = owner_policy(resolution.actor if resolution else chosen.actor, scope)
        if chosen.template_id in reference_values(policy)[0]['template_ids']:
            result.update(status='CURRENT', question='Exact owner-approved current template is pinned; registration of a newer draft alone does not change it.',
                manifest={'scope_id': scope.pk, 'template_id': chosen.template_id, 'claim_ids': ids,
                    'configuration_id': policy.pk, 'resolution_id': resolution.pk if resolution else None,
                    'owner_claim_id': None if resolution else chosen.pk})
            return result
    result.update(status='OWNER_CONFIRMATION_REQUIRED', question='Record the actual scoped owner assignment and owner confirmation. Reported source text, document registration and administrator status grant no authority.')
    return result


def selection(case, template, audience, scope_id):
    scope = scope_for(case, scope_id)
    if scope.document_type != template.definition['document_type'] or scope.audience != audience:
        raise ValidationError('Current assertion must match the document type and intended audience')
    result = status(scope)
    if result['status'] != 'CURRENT':
        raise ValidationError('Template currentness: '+result['status']+'. '+result['question'])
    if result['manifest']['template_id'] != template.pk:
        raise ValidationError('Explicit selected template is not the owner-approved current template for this scope')
    return result['manifest']


def findings(version):
    if not version.template_current_manifest:
        return []
    try:
        actual = selection(version.document.case, version.template, version.audience, version.template_current_manifest['scope_id'])
        if actual != version.template_current_manifest:
            raise ValidationError('Current template evidence or owner authority changed; prepare a new explicit assertion')
    except (ValidationError, PermissionDenied, KeyError) as exc:
        # Generic agent preflight may report this bounded result, never owner
        # source text, names, exact private claim references or source metadata.
        return ['Owner-approved current template assertion requires rechecking in the document workbench']
    return []


@transaction.atomic
def draft_owner_policy(actor, case_id, value, evidence_id, effective_from, expected):
    from types import SimpleNamespace
    from apps.policy.document_validators import validate_reference
    from apps.policy.change_drafts import draft_standard_policy
    case = lock_case(actor, case_id, 'policy.configure', expected)
    require(actor, case, 'document.read')
    validate_reference(COMPONENT, SimpleNamespace(schema_ref='schema:psl/document-storage/v3', content=value), case)
    result = draft_standard_policy(actor, case_id, COMPONENT, value, evidence_id, effective_from)
    bump(case)
    return result
