from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.finance.models import BillingCoverage,BillingUsage,BillingPreparation
from apps.finance.billing import exact,ensure_current,coverage_current,coverage_inventory
from apps.policy.models import Configuration
from apps.policy.services import reference_values
from .models import AgentRun

@transaction.atomic
def investigate(actor,case_id,coverage_id,preparation_id,expected):
    case=lock_case(actor,case_id,'agent.billing',expected);require(actor,case,'finance.read')
    cov=exact(case,BillingCoverage,coverage_id);prep=exact(case,BillingPreparation,preparation_id) if preparation_id else None
    if prep and prep.kind == 'fixed_contract':
        from .contract_coverage import investigate_charge
        return investigate_charge(actor, case_id, prep.fixed_charge_id, case.revision)
    if prep and prep.coverage_id!=cov.pk:raise ValidationError('Preparation belongs to another coverage')
    findings=[];citations={cov.evidence_id};current=coverage_current(cov)
    batches=BillingUsage.objects.filter(coverage=cov).order_by('-pk')[:20]
    for batch in batches:citations.add(batch.evidence_id);findings+=batch.findings
    if prep:
        findings+=prep.result['findings']
        try:ensure_current(prep)
        except (ValidationError,PermissionDenied) as exc:current=False;findings+=getattr(exc,'messages',[str(exc)])
        if prep.handoff_id:citations.add(prep.handoff.milestone.evidence_id)
        if prep.snapshot.get('signed_baseline'):citations.add(prep.snapshot['signed_baseline'])
        for entry in prep.snapshot['policies'].values():
            if not entry['id']:continue
            config=Configuration.objects.get(case=case,pk=entry['id'])
            citations.update(int(r.split(':')[-1]) for r in config.envelope['evidence_refs'])
            if entry['status']=='ACTIVE':
                for v in reference_values(config):
                    if 'oracle_evidence_id' in v:citations.add(v['oracle_evidence_id'])
    result={'capability':'A03/A05/A07 bounded billing coverage and pricing investigation','coverage':cov.pk,'preparation':prep.pk if prep else None,
        'current':current,'period_inventory':coverage_inventory(cov),'coverage_completeness':cov.completeness,'findings':list(dict.fromkeys(findings))[:100],
        'figures':prep.result if prep else None,'citations':list(case.evidence.filter(pk__in=citations).values('id','kind','sha256')),
        'next_work':'Resolve exact missing pricing/stage terms and investigate duplicate source identities. Review a current preparation before the separate invoice workflow.',
        'invoice_issued':False,'approval_granted':False,'policy_changed':False,'cash_recorded':False,'release_authorized':False,'external_authenticity_verified':False}
    from apps.finance.models import DraftGeneration
    from apps.finance.draft_generation import report as generation_report
    result['draft_generation']=[]
    for generation in DraftGeneration.objects.filter(case=case,preparation__coverage=cov).order_by('-pk')[:20]:
        try:result['draft_generation'].append(generation_report(actor,case_id,generation.pk))
        except PermissionDenied:pass
    run=AgentRun.objects.create(case=case,actor=actor,evidence=cov.evidence,provider='deterministic-billing-investigation-v1',process_id='F29',result=result)
    event(actor,case,'agent.billing_investigation',run=run.pk,coverage=cov.pk);return run

@transaction.atomic
def investigate_identity(actor, case_id, invoice_id, expected):
    """Read and explain only accessible exact identity pins; never infer or approve a key."""
    from apps.finance.models import Invoice
    from apps.finance.obligations import projection, latest
    from apps.finance.fixed_charge import preparation_access
    case = lock_case(actor, case_id, 'agent.billing', expected)
    require(actor, case, 'finance.read')
    invoice = exact(case, Invoice, invoice_id)
    preparation_access(actor, invoice.preparation)
    binding = latest(invoice)
    evidence = binding.evidence if binding else invoice.preparation.coverage.evidence
    result = {'invoice':invoice.pk, 'identity':projection(invoice),
        'coverage':'Explicit claims only; historical unbound invoices require evidenced reconciliation.',
        'next_work':'Supply the owner-backed namespace contract and exact invoice identity evidence. Resolve aliases only with configured resolver authority. Reconcile original attempted effects before any replacement.',
        'citations':[{'id':evidence.pk, 'kind':evidence.kind, 'sha256':evidence.sha256}],
        'invoice_issued':False, 'approval_granted':False, 'identity_inferred':False,
        'external_authenticity_verified':False}
    run = AgentRun.objects.create(case=case, actor=actor, evidence=evidence,
        provider='deterministic-invoice-identity-v1', process_id='F30', result=result)
    event(actor, case, 'agent.invoice_identity_investigation', run=run.pk, invoice=invoice.pk)
    return run
