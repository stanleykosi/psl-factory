from apps.policy.impact import inspect


def investigate(actor,case_id,assessment_id):
    report=inspect(actor,case_id,assessment_id)
    records=[record for values in report['domains'].values() for record in values]
    findings=['Observed heads changed; capture a successor assessment'] if not report['current'] else ['Observed heads match this bounded assessment']
    if report['review_authority_current'] is False:findings.append('Recorded reviewer authority is no longer current')
    if any(r['kind']=='finance.correction_effects' for r in records):
        findings.append('Correction application and note delivery receipts are separate; preserve canonical debt and reconcile the exact reservation before further work')
    if any(r.get('metadata_only') and r['kind'].startswith('finance.') for r in records):
        findings.append('Private metadata only: use the native Finance workspace to rebuild and review current evidence. This reassessment does not renew HR consent, extend retention or grant private payload access')
    if any(r['kind']=='documents.publication_effects' for r in records):
        findings.append('Historical recipient receipts do not authorize a new publication. Check current audience, recipient, review and retention controls in the document workspace')
    return {'capability':'A04 domain policy impact investigation','provider':'deterministic_internal_no_external_model',
        'observation':report,'uncertain_effects':[r for r in records if r['state']=='uncertain_effect'],
        'committed_effects':[r for r in records if r['state'] in ['committed_effect','committed_receipt_requires_reconciliation']],
        'receipt_conflicts':[r for r in records if r['state']=='receipt_conflict_requires_reconciliation'],
        'findings':findings,
        'next_work':['Reconcile uncertain effects by existing receipt-first domain recovery','Use domain services for new decisions and snapshots; old approvals are never copied'],
        'effect_tools':[],'business_approval':False,'owner_values_inferred':False}
