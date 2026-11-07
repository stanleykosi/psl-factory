from uuid import uuid4
from apps.core.services import add_evidence
from apps.policy.services import resolve
from apps.policy.signature_validators import COMPONENT, SCHEMA
from apps.pmo.signatures import capture_packet, latest
from .document_helpers import artifact
from .helpers import rev


def contract(actor, case, owner, reuse='unconfigured'):
    identity = case.evidence.filter(kind='client_identity').order_by('pk').first() or add_evidence(actor, case.pk, 'client_identity', 'Synthetic authorized client representative', 'synthetic:identity')
    return artifact(actor, case, COMPONENT, SCHEMA,
        {'parties': [{'party_ref': 'synthetic-client', 'display_name': 'Synthetic client representative',
                      'identity_evidence_id': identity.pk, 'documents': ['sow', 'prd']}],
         'methods': ['synthetic-reviewed-file'], 'assurance': 'human_verified_reference_only',
         'unchanged_prd_signature_reuse': reuse, 'applicability': 'client_project', 'signature_requirement': 'required', 'scope_evidence_id': None, 'allow_synthetic': case.synthetic}, owner)


def packet_for(actor, case, evidence, revision=None, *, signatures=None, configure=True):
    if configure and resolve(COMPONENT, case).status != 'ACTIVE':
        contract(actor, case, evidence['policy_decision'])
    prd = case.evidence.filter(kind='prd').order_by('-version').first()
    if not prd:
        prd = add_evidence(actor, case.pk, 'prd', 'Synthetic exact PRD content', 'synthetic:prd')
    if signatures is None:
        prd_signature = add_evidence(actor, case.pk, 'signature', 'Synthetic separate PRD signature', 'synthetic:prd-signature')
        signatures = {kind: {'evidence_id': source.pk, 'party_ref': 'synthetic-client',
                            'method': 'synthetic-reviewed-file', 'locator': kind + ':signature', 'human_verified': True}
                      for kind, source in [('sow', evidence['signature']), ('prd', prd_signature)]}
    return capture_packet(actor, case.pk, prd.pk, signatures, 'Synthetic human verified document-specific signature references',
                          str(uuid4()), rev(case), revision.pk if revision else None, getattr(latest(case), 'pk', None))


def reaffirm_for(actor, case):
    """Explicit synthetic human re-attestation after a positive fixture changes roles."""
    from apps.pmo.signatures import baseline_use, reaffirm_baseline
    _, use = baseline_use(case)
    original = use.packet
    captured = capture_packet(actor, case.pk, original.sources['prd']['id'], original.signatures,
        'Synthetic human rechecked original exact document signatures under the current fixture authority',
        str(uuid4()), rev(case), original.revision_id, getattr(latest(case), 'pk', None))
    return reaffirm_baseline(actor, case.pk, captured.pk, rev(case))
