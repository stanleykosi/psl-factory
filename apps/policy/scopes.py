"""Explicit scoped sources and target-local policy applications, without precedence."""
from datetime import datetime
import uuid
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import connection, transaction
from django.utils import timezone
from apps.core.models import Case, Evidence
from apps.core.services import event
from apps.identity.services import require
from .models import Configuration, ScopeVersion, ScopeState, ScopeApplication
from adapters.policy_scope import bind


def state(source):
    return source.states.order_by('-pk').values_list('state', flat=True).first()


def family(source):
    return ScopeVersion.objects.filter(configuration__case=source.configuration.case,
        configuration__component=source.configuration.component, kind=source.kind, ref=source.ref)


def mutex(source):
    # Local workflow transactions retain this lock until their effect reservation commits.
    # Source transitions take the same lock, so revocation cannot interleave that boundary.
    if connection.in_atomic_block:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [74123, source.pk])


def authorized(actor, case, action):
    require(actor, case, 'case.read')
    require(actor, case, action)


def descriptor(config, kind, ref):
    case = config.case
    if kind == 'organization' and ref == case.tenant:
        return
    if kind == 'project' and case.kind == 'project' and ref == str(case.pk):
        return
    if kind == 'service' and case.kind == 'support' and ref == str(case.pk):
        return
    if kind == 'contract' and ref.startswith('evidence:'):
        # A recorded draft SOW is usable before signature; this never signs it.
        if Evidence.objects.filter(case=case, pk=ref[9:] if ref[9:].isdigit() else None, kind='sow').exists():
            return
    raise ValidationError('Scope must identify this tenant, project, service or recorded SOW')


def values(config):
    from .services import reference_values
    return [config.envelope['value']] if config.component == 'D04.iana_timezone' else reference_values(config)


def source_health(source, at=None):
    from .services import validate_envelope
    mutex(source)
    at = at or timezone.now()
    current = state(source)
    if current == 'revoked':
        return 'REVOKED'
    if current != 'active':
        return 'INVALID'
    if family(source).filter(states__state__in=['active', 'revoked']).order_by('-revision').first().pk != source.pk:
        return 'INVALID'
    try:
        activated = source.states.filter(state='active').latest('pk')
        authorized(activated.actor, source.configuration.case, 'policy.activate')
        descriptor(source.configuration, source.kind, source.ref)
        validate_envelope(source.configuration.case, source.configuration.envelope, runtime=True)
        if source.configuration.states.order_by('-pk').first().state != 'validated':
            return 'INVALID'
    except (PermissionDenied, ValidationError, ValueError, KeyError):
        return 'INVALID'
    start = datetime.fromisoformat(source.configuration.envelope['effective_from'])
    end = source.configuration.envelope.get('effective_until')
    if at < start:
        return 'MISSING'
    if end and at >= datetime.fromisoformat(end):
        return 'EXPIRED'
    return 'ACTIVE'


@transaction.atomic
def create(actor, configuration_id, kind, ref, binding_paths):
    from .services import validate_envelope
    config = Configuration.objects.select_related('case').get(pk=configuration_id)
    case = Case.objects.select_for_update().get(pk=config.case_id)
    authorized(actor, case, 'policy.configure')
    if config.states.order_by('-pk').first().state != 'validated' or ScopeApplication.objects.filter(configuration=config).exists():
        raise ValidationError('Sources require an independently validated, unapplied configuration')
    descriptor(config, kind, ref)
    validate_envelope(case, config.envelope)
    bind(values(config), binding_paths, [])
    versions = ScopeVersion.objects.filter(configuration__case=case, configuration__component=config.component, kind=kind, ref=ref)
    revision = (versions.order_by('-revision').values_list('revision', flat=True).first() or 0) + 1
    source = ScopeVersion.objects.create(configuration=config, kind=kind, ref=ref, revision=revision,
        binding_paths=binding_paths, created_by=actor)
    ScopeState.objects.create(source=source, state='draft', actor=actor)
    event(actor, case, 'policy.scope.drafted', source=source.pk, kind=kind, ref=ref, revision=revision)
    return source


@transaction.atomic
def transition(actor, source_id, target):
    from .services import validate_envelope
    source = ScopeVersion.objects.select_related('configuration__case').get(pk=source_id)
    case = Case.objects.select_for_update().get(pk=source.configuration.case_id)
    authorized(actor, case, 'policy.activate' if target in ['active', 'revoked'] else 'policy.configure')
    # Lock every existing version before supersession (canonical order).
    for item in family(source).order_by('pk'):
        mutex(item)
    if (state(source), target) not in [('draft', 'validated'), ('validated', 'active'), ('active', 'revoked')]:
        raise ValidationError('Invalid scoped policy lifecycle transition')
    if target != 'revoked':
        descriptor(source.configuration, source.kind, source.ref)
        validate_envelope(case, source.configuration.envelope)
        if source.configuration.states.order_by('-pk').first().state != 'validated':
            raise ValidationError('Source configuration must remain validated')
    if target == 'active':
        if family(source).order_by('-revision').first().pk != source.pk:
            raise ValidationError('Stale scope draft')
        for other in family(source).exclude(pk=source.pk):
            if state(other) == 'active':
                ScopeState.objects.create(source=other, state='superseded', actor=actor)
    ScopeState.objects.create(source=source, state=target, actor=actor)
    event(actor, case, 'policy.scope.' + target, source=source.pk,
        impact_reassessment_required=target in ['active', 'revoked'])
    return source


@transaction.atomic
def apply(actor, source_id, case_id, decision_id, bindings):
    from .services import register_reference, save_draft, validate_envelope
    source = ScopeVersion.objects.select_related('configuration__case').get(pk=source_id)
    # One order for cross-case writes; never grant source rights from a target grant.
    cases = {c.pk: c for c in Case.objects.select_for_update().filter(pk__in=[source.configuration.case_id, case_id]).order_by('pk')}
    case = cases[uuid.UUID(str(case_id))]
    authorized(actor, source.configuration.case, 'policy.read')
    authorized(actor, case, 'policy.configure')
    if case.tenant != source.configuration.case.tenant or case.synthetic != source.configuration.case.synthetic:
        raise PermissionDenied('Policy scopes cannot cross tenant or classification boundaries')
    if source.kind != 'organization' and case.pk != source.configuration.case_id:
        raise ValidationError('Project, contract and service scopes require their exact case; no implicit rebinding')
    if source_health(source) != 'ACTIVE':
        raise ValidationError('Selected source version is not currently ACTIVE')
    decision = Evidence.objects.filter(case=case, pk=decision_id, kind='policy_decision').first()
    if not decision:
        raise ValidationError('Target owner decision evidence is required')
    bound = bind(values(source.configuration), source.binding_paths, bindings,
        cross_case=case.pk != source.configuration.case_id)
    envelope = dict(source.configuration.envelope, subject_scope={'kind':'project' if case.kind == 'project' else 'service', 'ref':str(case.pk)},
        evidence_refs=[f'evidence:{decision.pk}'], human_decision_ref=f'evidence:{decision.pk}')
    if source.configuration.component == 'D04.iana_timezone':
        envelope['value'] = bound[0]
    else:
        from .models import RegisteredReference
        original = source.configuration.envelope['value']
        refs = [original] if isinstance(original, (dict, str)) else original
        local = []
        for item, content in zip(refs, bound):
            ref, version = (item['artifact_ref'], item['artifact_version']) if isinstance(item, dict) else (item, 1)
            record = RegisteredReference.objects.get(case=source.configuration.case, ref=ref, version=version)
            local.append(register_reference(actor, case.pk, f'scope:{uuid.uuid4()}', record.schema_ref, content, decision.pk))
        if isinstance(original, dict):
            record = local[0]
            envelope['value'] = dict(original, artifact_ref=record.ref, artifact_version=record.version, sha256=record.sha256)
        else:
            envelope['value'] = [r.ref for r in local] if isinstance(original, list) else local[0].ref
    validate_envelope(case, envelope)
    config = save_draft(actor, case.pk, envelope)
    ScopeApplication.objects.create(configuration=config, source=source, bindings=bindings, actor=actor)
    event(actor, case, 'policy.scope.applied', source=source.pk, configuration=config.pk,
        source_configuration=source.configuration_id, source_revision=source.revision)
    return config


def application_health(config, at=None):
    application = ScopeApplication.objects.select_related('source__configuration__case', 'actor').filter(configuration=config).first()
    if not application:
        return 'ACTIVE'
    try:
        authorized(application.actor, config.case, 'policy.configure')
        authorized(application.actor, application.source.configuration.case, 'policy.read')
        source = application.source
        if config.case.tenant != source.configuration.case.tenant or config.case.synthetic != source.configuration.case.synthetic:
            return 'INVALID'
        if config.component != source.configuration.component or (source.kind != 'organization' and config.case_id != source.configuration.case_id):
            return 'INVALID'
        bound = bind(values(source.configuration), source.binding_paths, application.bindings,
            cross_case=config.case_id != source.configuration.case_id)
        if bound != values(config):
            return 'INVALID'
        for key in ['effective_from','effective_until','implementation_id','implementation_version','reviewed_implementation_ref','component_schema_ref','schema_version','fixture_scope']:
            if config.envelope.get(key) != source.configuration.envelope.get(key):
                return 'INVALID'
    except (PermissionDenied, ValidationError, ValueError, KeyError, ObjectDoesNotExist):
        return 'INVALID'
    return source_health(application.source, at)


def report(actor, case_id):
    from apps.identity.models import Grant
    case = Case.objects.get(pk=case_id)
    authorized(actor, case, 'policy.read')
    sources = []
    readable = Case.objects.filter(grant__user=actor, grant__active=True, grant__action='case.read').filter(
        pk__in=Grant.objects.filter(user=actor, active=True, action='policy.read').values('case_id'))
    for source in ScopeVersion.objects.filter(configuration__case=case).select_related('configuration__case').order_by('-pk')[:100]:
        sources.append({'id':source.pk, 'kind':source.kind, 'ref':source.ref, 'revision':source.revision,
            'component':source.configuration.component, 'state':state(source), 'health':source_health(source),
            'binding_paths':source.binding_paths, 'applications':list(source.applications.filter(configuration__case__in=readable).order_by('pk').values_list('configuration_id', flat=True)[:100])})
    applications = [{'configuration':a.configuration_id, 'source':a.source_id, 'status':application_health(a.configuration)}
        for a in ScopeApplication.objects.filter(configuration__case=case).select_related('configuration__case', 'source')[:100]]
    return {'sources':sources, 'applications':applications, 'limit':100, 'automatic_precedence':False}


def resolve_source(actor, authority_case_id, component, kind, ref, at=None, expected_revision=None):
    """Typed exact-source lookup; no precedence, inheritance or hidden source enumeration."""
    from .services import Resolution
    case = Case.objects.get(pk=authority_case_id)
    authorized(actor, case, 'policy.read')
    source = ScopeVersion.objects.filter(configuration__case=case, configuration__component=component,
        kind=kind, ref=ref, states__state__in=['active','revoked']).order_by('-revision').first()
    if not source:
        return Resolution('MISSING', component, reason='No published version at the explicit source scope')
    if expected_revision is not None and expected_revision != source.revision:
        return Resolution('INVALID', component, reason='Stale scoped source revision')
    status = source_health(source, at)
    return Resolution(status, component, source if status == 'ACTIVE' else None,
        reason='' if status == 'ACTIVE' else 'Selected scoped source unavailable; no fallback')
