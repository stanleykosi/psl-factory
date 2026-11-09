"""Useful scoped investigation; link suggestions never create source facts."""
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.pmo.delivery import dossier_for
from apps.pmo.progress import report, readable
from .models import AgentRun


@transaction.atomic
def investigate(actor,case_id,dossier_id,expected):
    case=lock_case(actor,case_id,'agent.delivery',expected);readable(actor,case)
    dossier=dossier_for(case,dossier_id,current=False)
    result=report(actor,dossier)
    from apps.pmo.models import DeliveryProgressObservation
    observation=DeliveryProgressObservation.objects.filter(source__dossier=dossier).order_by('-pk').first()
    if not observation:raise ValidationError('Capture a scoped source observation first')
    result['capability']='A03/P28 exact source, plan and issue correlation investigation'
    result['suggestions_are_decisions']=False
    run=AgentRun.objects.create(case=case,actor=actor,evidence=observation.evidence,
        provider='deterministic-delivery-progress-v1',process_id='P28',result=result)
    event(actor,case,'delivery.progress.investigated',run=run.pk,evidence=observation.evidence_id)
    return run
