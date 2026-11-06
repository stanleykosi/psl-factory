"""Bounded A03/A05/A07 comparison and request drafting; no financial execution tools."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import event,bump
from apps.agents.models import AgentRun
from apps.baas import reconciliation as recon
from apps.baas.models import ReconciliationRun,ReconciliationBatch,CorrectiveRequest,CorrectiveDecision,CorrectiveDelivery,EngineeringOutcome,OutcomeVerification

@transaction.atomic
def investigate(actor,case_id,run_id,expected):
    case=recon.locked(actor,case_id,'agent.reconciliation',expected);run=recon.exact(case,ReconciliationRun,run_id);findings=list(run.result['findings'])
    try:recon.ensure_current(run);current=True
    except (ValidationError,PermissionDenied) as exc:current=False;findings.append(str(exc))
    batches=list(ReconciliationBatch.objects.filter(case=case,pk__in=[v for v in run.selections.values() if v]));sources=[b.evidence for b in batches]
    from apps.baas.models import ReconciliationAttestation
    sources += [a.evidence for a in ReconciliationAttestation.objects.filter(batch__in=batches)]
    requests=list(CorrectiveRequest.objects.filter(case=case));sources += [r.evidence for r in requests]
    sources += [d.evidence for d in CorrectiveDecision.objects.filter(request__case=case)]
    sources += [d.evidence for d in EngineeringOutcome.objects.filter(delivery__request__case=case)]
    sources += [d.evidence for d in OutcomeVerification.objects.filter(delivery__request__case=case)]
    for d in CorrectiveDelivery.objects.filter(request__case=case):
        verified=OutcomeVerification.objects.filter(delivery=d).first()
        if not verified:findings.append(f'Request receipt {d.pk} proves delivery only; terminal execution remains unverified')
        elif EngineeringOutcome.objects.filter(delivery=d).exclude(payload__status=verified.outcome.payload['status']).exclude(payload__status='unknown').exists():findings.append(f'Conflicting terminal Engineering reports for receipt {d.pk}; preserve verified history and investigate')
    result={'capabilities':['A03','A05','A07'],'current':current,'findings':findings,'scope':run.result['scope'],
        'transactions':[{'partner':r['partner'],'transaction':r['transaction'],'finding':r['finding'],'issues':r['issues'],'queue_state':r['queue']['queue_state'] if r['queue'] else None,'aged_queue':r['queue_age_threshold_exceeded']} for r in run.result['rows']],
        'investigation_plan':[{'partner':r['partner'],'transaction':r['transaction'],'amount_difference':r['amount_difference'],'source_refresh_required':not current or r['finding']=='ambiguous',
            'next_step':'Compare exact customer/currency/source hashes and obtain missing or unambiguous current settlement evidence' if r['finding']=='ambiguous' else 'Review configured pending/failed interpretation and obtain an authorised request decision; no credit or fund action inferred' if r['finding']=='not_confirmed' else 'Retain settlement evidence; any corrective request still requires separate configured human authority'} for r in run.result['rows']],
        'request_draft_advice':[{'request':r.pk,'command':r.payload['command'],'operation_key':r.operation_key,'next_step':'Confirm exact current configured human decision, recipient and source before handoff; reconcile existing receipts/outcomes first.'} for r in requests],
        'citations':[{'id':e.pk,'kind':e.kind,'sha256':e.sha256} for e in {e.pk:e for e in sources}.values()],
        'next_steps':['Resolve duplicate/missing/conflicting or stale source evidence.','Distinguish request delivery from terminal Engineering outcome verification.','Refresh source batches after externally reported execution; do not overwrite the business queue.'],
        'tools':['case_evidence_read','reconciliation_compare','restricted_request_draft'],'approval_granted':False,'funds_mutated':False,'business_queue_mutated':False,'execution_authorized':False}
    if not batches:raise ValidationError('Select at least one captured source for a cited investigation')
    log=AgentRun.objects.create(case=case,actor=actor,evidence=batches[0].evidence,provider='deterministic-reconciliation-v1',process_id='B04',result=result)
    event(actor,case,'agent.reconciliation_investigated',run=run.pk,agent_run=log.pk);bump(case);return log
