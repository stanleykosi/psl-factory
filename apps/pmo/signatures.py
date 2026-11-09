"""P20 current two-document evidence, separate from planning and signature authenticity."""
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.policy.services import active_component, reference_values, role_policy, PolicyHold
from apps.policy.signature_validators import COMPONENT, SIGNATURES
from apps.documents.contracts import validate
from .models import Baseline, CommercialSignaturePacket, CommercialSignatureUse
from .services import subject


def pin(evidence):
    return {'id': evidence.pk, 'version': evidence.version, 'sha256': evidence.sha256}


def sources(case, prd_id, revision=None):
    # A proposed successor is not an adopted replacement. Reaffirm the exact
    # current adopted document facts even while another draft is being prepared.
    if Baseline.objects.filter(case=case,signed__isnull=False).exists():
        try:
            baseline, use = baseline_use(case)
        except ValidationError:
            use = None
        if use and use.packet.revision_id == (revision.pk if revision else None) and use.packet.sources['prd']['id'] == prd_id:
            current_baseline_documents(case, baseline, use)
            return use.packet.sources
    if revision is not None:
        from .commercial import current_revision, require_project_conversion
        require_project_conversion(case)
        from .models import BaselineAdoption
        if BaselineAdoption.objects.filter(revision=revision).exists():
            baseline, use = baseline_use(case)
            current_baseline_documents(case, baseline, use)
            if use.packet.revision_id != revision.pk:
                raise ValidationError('Select the exact current adopted revision')
        else:
            revision = current_revision(case, revision.pk)
        ids = {key: revision.sources[key] for key in ['plan', 'costing', 'sow']}
    else:
        from .services import commercial_guard
        commercial_guard(case)
        baseline = Baseline.objects.filter(case=case).first()
        if not baseline:
            raise ValidationError('Prepare the native baseline before capturing signatures')
        ids = {key: getattr(baseline, key + '_id') for key in ['plan', 'costing', 'sow']}
    # PRD has its own immutable document identity. Generic signature text and a
    # requirements wrapper cannot silently establish a signed PRD version.
    prd = subject(case, prd_id, 'prd')
    if case.evidence.filter(kind='prd').order_by('-version').first().pk != prd.pk:
        raise ValidationError('Select the current PRD version; historical signatures remain in history')
    return {**{key: pin(subject(case, value, key)) for key, value in ids.items()}, 'prd': pin(prd)}


def latest(case):
    return CommercialSignaturePacket.objects.filter(case=case).order_by('-pk').first()


def validate_signature_sources(case, signatures):
    validate(SIGNATURES, signatures)
    for value in signatures.values():
        subject(case, value['evidence_id'], 'signature')
        if value['human_verified'] and not all(value[key] for key in ['party_ref', 'method', 'locator']):
            raise ValidationError('Human verification requires actual party, method and document signature location')
    if set(signatures) == {'sow', 'prd'}:
        left, right = signatures['sow'], signatures['prd']
        if left['locator'] and right['locator'] and (left['evidence_id'], left['locator']) == (right['evidence_id'], right['locator']):
            raise ValidationError('One signature cannot stand for both documents; identify each separately, including within a bundle')


@transaction.atomic
def capture_packet(actor, case_id, prd_id, signatures, note, operation_key, expected, revision_id=None, predecessor_id=None):
    case = lock_case(actor, case_id, 'commercial.response', expected)
    require(actor, case, 'baseline.sign')
    authority = role_policy(actor, case, 'PM')
    from .commercial import note_required
    from .models import CommercialRevision
    note_required(note)
    if not isinstance(operation_key, str) or not operation_key.strip() or len(operation_key) > 100:
        raise ValidationError('A stable signature capture key of at most 100 characters is required')
    revision = None
    if revision_id is not None:
        revision = CommercialRevision.objects.filter(pk=revision_id, dossier__case=case).first()
        if not revision:
            raise ValidationError('Select this case commercial revision')
    pinned = sources(case, prd_id, revision)
    validate_signature_sources(case, signatures)
    # An immutable signature reference is attributable to one exact document,
    # even before adoption. A later human packet may not relabel old evidence.
    for historical in CommercialSignaturePacket.objects.filter(case=case):
        for kind, value in signatures.items():
            for prior_kind, prior in historical.signatures.items():
                if value['locator'] and prior['locator'] and (value['evidence_id'], value['locator']) == (prior['evidence_id'], prior['locator']) and (
                        prior_kind != kind or historical.sources[prior_kind] != pinned[kind]):
                    raise ValidationError('Signature reference already identifies another document/version; obtain current document evidence')
    try:
        policy = active_component(COMPONENT, case)
    except PolicyHold:
        policy = None  # Preparation is allowed; this is never an adoption grant.
    previous = latest(case)
    repeated = CommercialSignaturePacket.objects.filter(case=case, operation_key=operation_key).first()
    if repeated:
        if repeated != previous or (repeated.sources, repeated.signatures, repeated.note, repeated.revision_id,
                repeated.policy_id, repeated.authority_id, repeated.actor_id) != (pinned, signatures, note, revision_id,
                policy.pk if policy else None, authority.pk, actor.pk):
            raise ValidationError('Capture key already identifies another or historical signature packet')
        return repeated
    if (previous.pk if previous else None) != predecessor_id:
        raise ValidationError('Refresh and identify the current signature packet predecessor')
    packet = CommercialSignaturePacket.objects.create(case=case, revision=revision, predecessor=previous,
        sources=pinned, signatures=signatures, policy=policy, authority=authority, actor=actor,
        note=note, operation_key=operation_key)
    event(actor, case, 'commercial.signatures_captured', packet=packet.pk, predecessor=predecessor_id,
          documents=list(signatures), policy=packet.policy_id, assurance='human_reference_only')
    bump(case)
    return packet


def validate_packet_policy(packet):
    case = packet.case
    require(packet.actor, case, 'commercial.response')
    require(packet.actor, case, 'baseline.sign')
    if role_policy(packet.actor, case, 'PM').pk != packet.authority_id:
        raise ValidationError('Signature recorder authority changed; a current human attestation is required')
    validate_signature_sources(case, packet.signatures)
    if set(packet.signatures) != {'sow', 'prd'} or not all(x['human_verified'] for x in packet.signatures.values()):
        raise ValidationError('Separately human-verified current SOW and PRD signatures are both required')
    policy = active_component(COMPONENT, case)
    if packet.policy_id != policy.pk:
        raise ValidationError('Signature contract changed or was unknown; capture a current human packet')
    rules = reference_values(policy)[0]
    if rules['signature_requirement'] == 'unresolved' or rules['applicability'] == 'unresolved':
        from apps.policy.services import Resolution
        raise PolicyHold([Resolution('MISSING', COMPONENT, policy, 'Owner signature requirement or project classification remains unresolved')])
    if rules['signature_requirement'] != 'required':
        raise ValidationError('Use the explicit authorized internal exemption path; not-applicable signatures are not signed facts')
    if rules['applicability'] == 'internal_project':
        from .signature_exemptions import no_external_client_facts
        no_external_client_facts(case)
    for kind, value in packet.signatures.items():
        if value['method'] not in rules['methods'] or not any(
                p['party_ref'] == value['party_ref'] and kind in p['documents'] for p in rules['parties']):
            raise ValidationError('Signature party/method is not authorized by the current owner-supplied contract: ' + kind)
    return rules


def current_packet(case, signature_id, revision=None):
    packet = latest(case)
    if not packet or packet.revision_id != (revision.pk if revision else None):
        raise ValidationError('Capture a current separate SOW and PRD signature packet')
    if packet.sources != sources(case, packet.sources['prd']['id'], revision):
        raise ValidationError('Signature packet sources changed; capture a successor with current document evidence')
    rules = validate_packet_policy(packet)
    if packet.signatures['sow']['evidence_id'] != signature_id:
        raise ValidationError('Signed response must match this packet exact SOW signature evidence')
    for used in CommercialSignatureUse.objects.select_related('packet').filter(packet__case=case):
        for kind, item in packet.signatures.items():
            for prior_kind, prior in used.packet.signatures.items():
                if (item['evidence_id'], item['locator']) != (prior['evidence_id'], prior['locator']):
                    continue
                allowed = kind == prior_kind == 'prd' and packet.sources['prd'] == used.packet.sources['prd'] and rules['unchanged_prd_signature_reuse'] == 'same_document_reference_allowed'
                if not allowed:
                    raise ValidationError('Owner re-sign rule is unresolved or does not permit this consumed signature reference; SOW reuse cannot authorize another baseline')
    return packet


def record_use(actor, packet, adoption=None):
    return CommercialSignatureUse.objects.create(packet=packet, adoption=adoption, actor=actor)


def packet_status(packet):
    return {'sow': 'human reference captured' if packet.signatures.get('sow', {}).get('human_verified') else 'missing or unverified',
            'prd': 'human reference captured' if packet.signatures.get('prd', {}).get('human_verified') else 'missing or unverified',
            'contract': 'pinned' if packet.policy_id else 'unknown: owner input required',
            'authenticity': 'Not verified by a signature provider'}


@transaction.atomic
def draft_contract(actor, case_id, value, evidence_id, effective_from, expected):
    """Typed draft only. Activation stays in the native owner policy workflow."""
    from types import SimpleNamespace
    from apps.policy.signature_validators import SCHEMA, validate_reference
    from apps.policy.change_drafts import draft_standard_policy
    case = lock_case(actor, case_id, 'policy.configure', expected)
    validate_reference(COMPONENT, SimpleNamespace(schema_ref=SCHEMA, content=value), case)
    result = draft_standard_policy(actor, case_id, COMPONENT, value, evidence_id, effective_from)
    bump(case)
    return result


def baseline_use(case):
    """Find original dual proof, never manufacture it for historical one-sign data."""
    baseline = Baseline.objects.filter(case=case, signed__isnull=False).first()
    if not baseline:
        raise ValidationError('Current signed planning baseline required')
    for use in CommercialSignatureUse.objects.filter(packet__case=case).select_related('packet', 'adoption__revision__dossier').order_by('-pk'):
        packet = use.packet
        if all(packet.sources[key]['id'] == getattr(baseline, key + '_id') for key in ['plan', 'costing', 'sow']) and packet.signatures['sow']['evidence_id'] == baseline.signed_id:
            return baseline, use
    raise ValidationError('Historical signed baseline has no original two-document proof; prepare the controlled current baseline, preserving history')


def current_baseline_documents(case, baseline, use):
    for kind, value in use.packet.sources.items():
        if pin(subject(case, value['id'], kind)) != value:
            raise ValidationError('Adopted document evidence changed or was withdrawn')
    from .models import BaselineAdoption
    current_adoption = BaselineAdoption.objects.filter(revision__dossier__case=case).order_by('-pk').values_list('pk', flat=True).first()
    if use.adoption_id != current_adoption:
        raise ValidationError('A later actual adoption supersedes this historical signed baseline')
    if use.adoption_id and use.adoption.after != {
            key: getattr(baseline, key) for key in ['plan_id', 'costing_id', 'sow_id', 'signed_id']}:
        raise ValidationError('Current adopted source changed; preserve historical signature proof')


def assert_current_signed_baseline(case):
    """Current PMO claim only. Does not erase history or gate Finance obligations."""
    baseline, use = baseline_use(case)
    current_baseline_documents(case, baseline, use)
    reaffirmation = use.reaffirmations.select_related('packet', 'actor').order_by('-pk').first()
    packet = reaffirmation.packet if reaffirmation else use.packet
    validate_packet_policy(packet)
    current_actor = reaffirmation.actor if reaffirmation else use.actor
    require(current_actor, case, 'baseline.sign')
    role_policy(current_actor, case, 'PM')
    return packet


@transaction.atomic
def reaffirm_baseline(actor, case_id, packet_id, expected):
    """Human current-authority reaffirmation of the same immutable document facts."""
    from .models import CommercialSignatureReaffirmation
    case = lock_case(actor, case_id, 'baseline.sign', expected)
    role_policy(actor, case, 'PM')
    baseline, use = baseline_use(case)
    current_baseline_documents(case, baseline, use)
    packet = latest(case)
    if not packet or packet.pk != packet_id or packet.sources != use.packet.sources or packet.revision_id != use.packet.revision_id:
        raise ValidationError('Reaffirm only the latest exact same-document packet for the existing baseline')
    rules = validate_packet_policy(packet)
    original_rules = reference_values(use.packet.policy)[0]
    for kind in ['sow', 'prd']:
        party = use.packet.signatures[kind]['party_ref']
        before = next(p['identity_evidence_id'] for p in original_rules['parties'] if p['party_ref'] == party and kind in p['documents'])
        after = next(p['identity_evidence_id'] for p in rules['parties'] if p['party_ref'] == party and kind in p['documents'])
        if before != after:
            raise ValidationError('Reaffirmation cannot relabel the original client identity')
    if packet.actor_id != actor.pk:
        raise ValidationError('Current human recorder must reaffirm their own current attestation')
    for kind in ['sow', 'prd']:
        if any(packet.signatures[kind][key] != use.packet.signatures[kind][key] for key in ['evidence_id', 'locator', 'party_ref', 'method']):
            raise ValidationError('Reaffirmation preserves original signature identities; changed documents/proof use controlled revision')
    previous = use.reaffirmations.order_by('-pk').first()
    if packet.pk == (previous.packet_id if previous else use.packet_id):
        assert_current_signed_baseline(case)
        return previous or use
    row = CommercialSignatureReaffirmation.objects.create(use=use, packet=packet, previous=previous, actor=actor)
    event(actor, case, 'commercial.signatures_reaffirmed', reaffirmation=row.pk, original_use=use.pk,
          packet=packet.pk, previous=previous.pk if previous else None, historical_receipts_rewritten=False)
    bump(case)
    return row
