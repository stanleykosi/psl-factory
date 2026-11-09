"""Evidence-bound identity, independent of price, customer spelling and legacy keys."""
import json
import re
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction
from apps.core.models import Case
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.models import ScopeApplication
from apps.policy.services import active_component, reference_values, decision_authority
from apps.policy.scopes import source_health
from apps.pmo.services import subject
from .billing import digest, exact
from .models import (Invoice, InvoiceJob, InvoiceIssue, ObligationNamespace,
    ObligationClaim, ObligationLocalKey, ObligationAlias, ObligationBinding, ObligationEffect)

COMPONENT = 'D08.obligation_namespace'
KEY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$')
CONFLICT = 'Identity already claimed. Resolve through an authorised exact-identity reconciliation; no other case details are disclosed.'


def contract(case):
    config = active_component(COMPONENT, case)
    application = ScopeApplication.objects.filter(configuration=config).select_related('source__configuration__case').first()
    if not application or application.source.kind != 'organization' or application.source.ref != case.tenant:
        raise ValidationError('Apply an explicit organisation-scoped obligation namespace contract')
    source = application.source
    if source.configuration.case.synthetic != case.synthetic or source_health(source) != 'ACTIVE':
        raise ValidationError('Obligation namespace authority is not current')
    value = reference_values(config)[0]
    return config, source, value


def namespace_lock(case, name):
    if not connection.in_atomic_block:
        raise RuntimeError('Obligation identity mutations require an atomic transaction')
    key = int(digest([case.tenant, case.synthetic, name])[:15], 16)
    with connection.cursor() as cursor:
        cursor.execute('SHOW transaction_isolation')
        if cursor.fetchone()[0] != 'read committed':
            raise ValidationError('Identity writes require READ COMMITTED isolation; restart the transaction')
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [key])


def namespace(case, source, value):
    namespace_lock(case, value['namespace'])
    ns, _ = ObligationNamespace.objects.get_or_create(tenant=case.tenant, synthetic=case.synthetic,
        name=value['namespace'], defaults={'source':source, 'key_contract':value['key_contract']})
    if ns.key_contract != value['key_contract'] or ns.source.configuration.case_id != source.configuration.case_id:
        raise ValidationError('Namespace meaning or authoritative source changed; explicit reconciliation is required')
    return ns


def latest(invoice):
    return ObligationBinding.objects.filter(invoice=invoice).select_related('local_key__claim__namespace', 'evidence', 'actor', 'alias').order_by('-pk').first()


def declaration(invoice, namespace_name, key, predecessor=None):
    return {'invoice_id':invoice.pk, 'invoice_sha256':invoice.sha256,
        'preparation_id':invoice.preparation_id, 'legacy_key':invoice.obligation_key,
        'namespace':namespace_name, 'key':key, 'predecessor_binding_id':predecessor}


def evidence_value(case, evidence_id, kind):
    evidence = subject(case, evidence_id, kind)
    try:
        value = json.loads(evidence.body)
    except (ValueError, TypeError):
        raise ValidationError('Exact typed identity evidence is required')
    return evidence, value


@transaction.atomic
def bind(actor, case_id, invoice_id, key, evidence_id, expected, *, predecessor_id=None):
    case = lock_case(actor, case_id, 'finance.invoice.draft', expected)
    require(actor, case, 'case.read'); require(actor, case, 'finance.read')
    invoice = exact(case, Invoice, invoice_id)
    from .fixed_charge import preparation_access
    preparation_access(actor, invoice.preparation)
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValidationError('Supply the exact bounded key from the authoritative identity source')
    config, source, value = contract(case)
    evidence, supplied = evidence_value(case, evidence_id, 'invoice_identity')
    if supplied != declaration(invoice, value['namespace'], key, predecessor_id):
        raise ValidationError('Identity evidence must name the exact invoice, preparation, hash, namespace, key and predecessor')
    ns = namespace(case, source, value)
    alias = ObligationAlias.objects.filter(namespace=ns, key=key).order_by('-version').first()
    claim = alias.claim if alias else ObligationClaim.objects.filter(namespace=ns, key=key).first()
    # Claims are deliberately not transferable: an alias is identity resolution, not billing ownership.
    if claim and claim.case_id != case.pk:
        raise ValidationError(CONFLICT)
    predecessor = None
    if predecessor_id:
        predecessor = ObligationBinding.objects.filter(pk=predecessor_id, invoice__case=case).select_related('local_key__claim').first()
        if not predecessor or not claim or predecessor.local_key.claim_id != claim.pk:
            raise ValidationError('Exact same-case canonical predecessor binding is required')
    local = ObligationLocalKey.objects.filter(case=case, legacy_key=invoice.obligation_key).first()
    if local and (not claim or local.claim_id != claim.pk):
        raise ValidationError('A historical obligation identity cannot be reassigned')
    if claim and not local and not predecessor:
        raise ValidationError('An explicit predecessor binding is required for a changed local obligation key')
    if not claim:
        if predecessor:
            raise ValidationError('A successor must preserve its canonical claim')
        claim = ObligationClaim.objects.create(namespace=ns, key=key, case=case, evidence=evidence, actor=actor)
    if not local:
        local = ObligationLocalKey.objects.create(case=case, legacy_key=invoice.obligation_key, claim=claim)
    if alias:
        alias_current(alias)
    previous = latest(invoice)
    if previous and previous.local_key.claim_id != claim.pk:
        raise ValidationError('Invoice identity is immutable once bound')
    if previous and previous.policy_id == config.pk and previous.evidence_id == evidence.pk:
        return previous
    binding = ObligationBinding.objects.create(invoice=invoice, local_key=local, policy=config,
        evidence=evidence, alias=alias, predecessor=predecessor, actor=actor)
    event(actor, case, 'invoice.identity_bound', invoice=invoice.pk, binding=binding.pk)
    bump(case)
    return binding


def resolver(actor, case, config, value):
    require(actor, case, 'finance.invoice.review')
    if actor.pk not in value['resolver_ids']:
        raise PermissionDenied('Configured identity resolver authority required')
    return decision_authority(actor, case, value['resolver_role'])


def alias_current(alias):
    config, source, value = contract(alias.case)
    if ObligationAlias.objects.filter(namespace=alias.namespace, key=alias.key, version__gt=alias.version).exists():
        raise ValidationError('Alias resolution has a newer explicit attestation')
    if config.pk != alias.policy_id or resolver(alias.actor, alias.case, config, value) != alias.authority:
        raise ValidationError('Alias authority changed; exact reconciliation is required')
    require(alias.actor, alias.claim.case, 'case.read')
    require(alias.actor, alias.claim.case, 'finance.read')


@transaction.atomic
def resolve_alias(actor, case_id, claim_id, key, evidence_id, expected):
    # Lock cases in stable order before policy/namespace locks.
    claim = ObligationClaim.objects.select_related('case', 'namespace').filter(pk=claim_id).first()
    if not claim:
        raise ValidationError('Select an accessible canonical claim')
    cases = list(Case.objects.select_for_update().filter(pk__in=[case_id, claim.case_id]).order_by('pk'))
    case = next((c for c in cases if str(c.pk) == str(case_id)), None)
    if not case:
        raise ValidationError('Select an accessible case')
    require(actor, claim.case, 'case.read'); require(actor, claim.case, 'finance.read')
    case = lock_case(actor, case_id, 'finance.invoice.review', expected)
    require(actor, case, 'case.read'); require(actor, case, 'finance.read')
    config, source, value = contract(case)
    authority = resolver(actor, case, config, value)
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValidationError('Supply an exact bounded alias key')
    ns = namespace(case, source, value)
    if claim.namespace_id != ns.pk:
        raise ValidationError('Alias must remain within the exact tenant, test scope and namespace')
    evidence, supplied = evidence_value(case, evidence_id, 'invoice_identity_alias')
    if supplied != {'namespace':ns.name, 'key':key, 'canonical_claim_id':claim.pk,
                    'canonical_key':claim.key, 'canonical_case_id':str(claim.case_id)}:
        raise ValidationError('Exact canonical identity and alias evidence required')
    previous = ObligationAlias.objects.filter(namespace=ns, key=key).order_by('-version').first()
    if ObligationClaim.objects.filter(namespace=ns, key=key).exists() or previous and previous.claim_id != claim.pk:
        raise ValidationError('A claimed identity cannot be merged, freed or reassigned')
    alias = ObligationAlias.objects.create(namespace=ns, key=key, claim=claim, case=case, version=previous.version+1 if previous else 1,
        policy=config, evidence=evidence, actor=actor, authority=authority)
    event(actor, case, 'invoice.identity_alias_resolved', alias=alias.pk)
    bump(case)
    return alias


def current(invoice):
    binding = latest(invoice)
    if not binding:
        raise ValidationError('Explicit obligation identity binding required before issuance; historical unbound invoices remain unverified')
    config, source, value = contract(invoice.case)
    claim = binding.local_key.claim
    if (binding.policy_id != config.pk or claim.namespace.name != value['namespace']
            or claim.namespace.key_contract != value['key_contract']
            or claim.namespace.source.configuration.case_id != source.configuration.case_id):
        raise ValidationError('Identity contract changed; explicitly reaffirm the exact binding')
    require(binding.actor, invoice.case, 'case.read')
    require(binding.actor, invoice.case, 'finance.invoice.draft')
    require(binding.actor, invoice.case, 'finance.read')
    if binding.alias_id:
        alias_current(binding.alias)
    key = binding.alias.key if binding.alias_id else claim.key
    if json.loads(binding.evidence.body) != declaration(invoice, value['namespace'], key, binding.predecessor_id):
        raise ValidationError('Invoice identity evidence differs from immutable source pins')
    return binding


def projection(invoice):
    binding = latest(invoice)
    if not binding:
        return {'status':'legacy_unverified' if InvoiceIssue.objects.filter(invoice=invoice).exists() else 'binding_required', 'binding':None}
    try:
        current(invoice)
    except (ValidationError, PermissionDenied) as exc:
        return {'status':'held', 'binding':binding.pk, 'findings':getattr(exc, 'messages', [str(exc)])}
    config,source,value=contract(invoice.case)
    return {'status':'bound', 'binding':binding.pk, 'namespace':binding.local_key.claim.namespace.name,
        'history_scope':value['history_scope'], 'historical_coverage_verified':False,
        'coverage':'Exact evidenced claims only; scope declaration is not independently verified history'}


def binding_pin(binding):
    claim = binding.local_key.claim
    return {'claim':claim.pk, 'binding':binding.pk, 'policy':binding.policy_id,
        'namespace':claim.namespace_id, 'evidence':binding.evidence_id, 'evidence_sha256':binding.evidence.sha256}


def review_pin(invoice):
    # Issue-time lineage is immutable. Later namespace revocation/reconciliation must not
    # add an unrelated gate to delivery/correction of a proven original invoice.
    issued = InvoiceIssue.objects.filter(invoice=invoice).select_related('job').first()
    if issued:
        return issued.job.intent.get('obligation_identity')
    binding = latest(invoice)
    return binding_pin(binding) if binding else None


def issue_pin(invoice):
    binding = current(invoice)
    claim = binding.local_key.claim
    namespace_lock(invoice.case, claim.namespace.name)
    ObligationNamespace.objects.select_for_update().get(pk=claim.namespace_id)
    effect = ObligationEffect.objects.filter(claim=claim).first()
    if effect and effect.invoice_id != invoice.pk:
        raise ValidationError(CONFLICT)
    from .models import ObligationLegacyAttempt
    keys = ObligationLocalKey.objects.filter(claim=claim).values('legacy_key')
    if ObligationLegacyAttempt.objects.filter(job__invoice__case=invoice.case,
            job__invoice__obligation_key__in=keys).exclude(job__invoice__invoiceissue__isnull=False).exists():
        raise ValidationError('A frozen original attempted effect remains unreconciled; no new send is permitted')
    others = InvoiceJob.objects.filter(kind='issue', intent__obligation_identity__claim=claim.pk).exclude(invoice=invoice)
    if others.exclude(status__in=['cancelled','replaced']).exists() or others.filter(attempts__gt=0).exists():
        raise ValidationError('Canonical obligation has reserved or attempted work; reconcile its original operation first')
    if InvoiceIssue.objects.filter(invoice__obligationbinding__local_key__claim=claim).exclude(invoice=invoice).exists():
        raise ValidationError(CONFLICT)
    return {'claim':claim.pk, 'binding':binding.pk, 'policy':binding.policy_id,
        'namespace':claim.namespace_id, 'evidence':binding.evidence_id, 'evidence_sha256':binding.evidence.sha256}


def retain_effect(job):
    """Pin a first attempted effect, or reconcile the exact reserved identity after revocation."""
    pin = job.intent.get('obligation_identity')
    if not isinstance(pin, dict):
        raise ValidationError('Unbound historical effect requires explicit original-proof reconciliation')
    binding = ObligationBinding.objects.select_related('local_key__claim__namespace', 'invoice__case', 'evidence').filter(pk=pin.get('binding'), invoice=job.invoice).first()
    if not binding:
        raise ValidationError('Reserved identity binding is missing')
    claim = binding.local_key.claim
    expected = {'claim':claim.pk, 'binding':binding.pk, 'policy':binding.policy_id,
        'namespace':claim.namespace_id, 'evidence':binding.evidence_id, 'evidence_sha256':binding.evidence.sha256}
    if pin != expected:
        raise ValidationError('Reserved canonical identity changed')
    namespace_lock(job.invoice.case, claim.namespace.name)
    ObligationNamespace.objects.select_for_update().get(pk=claim.namespace_id)
    effect, created = ObligationEffect.objects.get_or_create(claim=claim,
        defaults={'invoice':job.invoice, 'binding':binding, 'job':job})
    if effect.invoice_id != job.invoice_id or effect.job_id != job.pk:
        raise ValidationError('Canonical effect belongs to its original operation; reconcile that operation before any replacement')
    return effect


def observe_original_attempt(job, observed):
    """Called only after the existing synthetic provider proof verifier has succeeded."""
    if job.intent.get('obligation_identity'):
        return retain_effect(job)
    from .models import ObligationLegacyAttempt, ObligationLegacyObservation
    marker = ObligationLegacyAttempt.objects.filter(job=job).first()
    if not marker or not job.invoice.case.synthetic:
        raise ValidationError('No frozen pre-migration attempted operation exists for this proof')
    snapshot = marker.snapshot
    if (job.operation_key != snapshot['operation_key'] or job.intent != snapshot['intent']
            or job.invoice_id != snapshot['invoice'] or job.invoice.payload != snapshot['payload']
            or job.invoice.sha256 != snapshot['sha256'] or job.actor_id != snapshot['actor']
            or job.attempts < snapshot['attempts']):
        raise ValidationError('Original attempted operation differs from its frozen migration identity')
    observation, _ = ObligationLegacyObservation.objects.get_or_create(attempt=marker,
        defaults={'proof':observed, 'fence':job.fence})
    if observation.proof != observed:
        raise ValidationError('Conflicting original-effect proof')
    return observation
