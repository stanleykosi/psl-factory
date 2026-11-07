from django.db import transaction
from apps.core.services import lock_case, event
from apps.documents.controlled import baseline_manifest
from apps.pmo.commercial import current_revision, latest_decisions
from apps.pmo.models import ChangeAuthorization
from apps.pmo.models import CommercialRevision
from django.core.exceptions import ValidationError
from .models import AgentRun


@transaction.atomic
def investigate_proposal(actor,case_id,revision_id,expected):
    case=lock_case(actor,case_id,'agent.commercial',expected)
    from apps.identity.services import require
    require(actor,case,'commercial.read')
    revision=CommercialRevision.objects.select_related('dossier__case').filter(pk=revision_id,dossier__case=case).first()
    if not revision:raise ValidationError('Select a commercial proposal within this case')
    previous=revision.previous
    changes=[{'kind':kind,'before_id':previous.sources.get(kind) if previous else None,'after_id':pk}
        for kind,pk in revision.sources.items() if not previous or previous.sources.get(kind)!=pk]
    latest=latest_decisions(revision)
    from apps.pmo.signatures import latest as latest_packet, packet_status
    signature_packet = latest_packet(case)
    signature_state = packet_status(signature_packet) if signature_packet else {'sow': 'missing', 'prd': 'missing', 'contract': 'not captured', 'authenticity': 'Not verified by a signature provider'}
    result={'document_signature_status': signature_state, 'signature_packet_id': signature_packet.pk if signature_packet else None, 'capability':'A02/A06/A08 commercial revision and authority investigation','revision_id':revision.pk,
        'changed_sources':changes,'source_evidence_ids':list(revision.sources.values()),
        'decision_status':{role:d.verdict for role,d in latest.items()},
        'missing_decision_roles':[r for r in ['PM','Head of PMO','CEO','PMO Lead'] if r not in latest or latest[r].verdict!='approve'],
        'signed_baseline_change':bool(baseline_manifest(case).get('signed_id')),
        'linked_change_authorization':ChangeAuthorization.objects.filter(commercial=revision).values_list('pk',flat=True).first(),
        'cost_calculated':False,'approval_granted':False,'signature_authenticity_verified':False,
        'next_work':'Human owners review exact changed sources; captured signatures are evidence, not provider verification.'}
    run=AgentRun.objects.create(case=case,actor=actor,evidence=revision.context,provider='deterministic-commercial-investigation-v1',process_id='P19',result=result)
    event(actor,case,'agent.commercial_investigation',run=run.pk,revision=revision.pk)
    return run
