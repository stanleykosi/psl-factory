from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.pmo.delivery import dossier_for,planning_inputs,readiness_inputs
from apps.pmo.delivery_closure import hypercare_inputs,current_archive,closure_inputs
from adapters.delivery import LocalDeliveryAdapter
from .models import AgentRun


@transaction.atomic
def investigate_delivery(actor,case_id,dossier_id,expected,closure_data=None):
    case=lock_case(actor,case_id,'agent.delivery',expected);require(actor,case,'delivery.read')
    d=dossier_for(case,dossier_id,current=False);result=LocalDeliveryAdapter().read_current(d);checks={}
    def closure_check(dossier):
        from apps.pmo.models import DeliveryDocumentBinding
        binding=DeliveryDocumentBinding.objects.filter(dossier=dossier,purpose='closure').order_by('-pk').first()
        if not binding:raise ValidationError('Prepare the PM closure report after current archive, Support/Operations receipts, retrospective and Finance coverage')
        return closure_inputs(dossier,binding.data)
    for name,fn in [('planning',planning_inputs),('release_evidence',readiness_inputs),('hypercare',hypercare_inputs),
            ('archive',lambda x:{'archive_id':current_archive(x).pk}),('closure',closure_check)]:
        try:dossier_for(case,d.pk);checks[name]={'inputs':fn(d),'findings':[]}
        except (ValidationError,PermissionDenied) as exc:checks[name]={'findings':str(exc)}
    closed=d.records.filter(kind='closure').order_by('-pk').first()
    if closure_data is None:
        from apps.pmo.models import DeliveryDocumentBinding
        binding=DeliveryDocumentBinding.objects.filter(dossier=d,purpose='closure').order_by('-pk').first()
        if binding:closure_data=binding.data
    result.update(checks=checks,closure_requirements=LocalDeliveryAdapter().read_closure(d,closure_data),recorded_closure_id=closed.pk if closed else None,capability='A03/A04/A07 delivery chronology and prerequisite investigation',approval_granted=False,
        deployment_dispatched=False,external_authenticity_verified=False,
        next_work='Preserve recorded closure and archive; assess further work in a new candidate dossier. No release or payment authority is granted.' if closed else
        'Resolve the cited owner/source gaps, record actual outcomes truthfully and obtain only the prescribed current human decisions. Hypercare, archive, Support receipts, retrospective and Finance notification coverage stay separate from debt and release authority.')
    run=AgentRun.objects.create(case=case,actor=actor,evidence=d.evidence,provider='deterministic-delivery-investigation-v1',process_id='P39',result=result)
    event(actor,case,'agent.delivery_investigation',run=run.pk,dossier=d.pk);return run


def investigate_phases(actor, case_id, dossier_id):
    """Read-only tool: no AgentRun, task, approval or factory mutation."""
    from apps.core.models import Case
    from apps.pmo.phase_evidence import projection
    case = Case.objects.get(pk=case_id)
    require(actor, case, 'agent.delivery')
    return projection(actor, case_id, dossier_id)
