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
    if any(r['kind']=='workflows.factory_planning_execution_bindings' for r in records):
        findings.append('Historical planning execution binding metadata only: not selected worker, current execution authority or permission to dispatch. No binding or worker action is performed.')
    if any(r['kind']=='workflows.factory_engagement_profiles' for r in records):
        findings.append('Engagement intake profile metadata only: not verified source currency, resolved identity, assigned PM, project registration, planning readiness or execution authority. Use the native engagement workspace; no worker or profile rebinding is performed.')
    if any(r['kind']=='workflows.factory_planning_profiles' for r in records):
        findings.append('Planning work profile metadata only: observed status is not verified output, source currency, dispatch permission or current execution authority. No worker or profile rebinding is performed.')
    if any(r['kind']=='pmo.baseline_signature_exemptions' for r in records):
        findings.append('Selected historical unsigned exemption validation only: not latest baseline assurance, source-owner policy inference, a signature, signing permission or newly granted authority.')
    if any(r['kind']=='pmo.signature_packets' for r in records):
        findings.append('Selected original packet policy observation only: not current sources, latest packet, baseline currency, signature authenticity, reuse eligibility or renewed signing authority.')
    if any(r['kind']=='pmo.emergency_recovery_requests' for r in records):
        findings.append('Emergency recovery request snapshot metadata grants no current authority and never repairs missing original preauthorization or changes original outcome times.')
    if any(r['kind']=='pmo.signed_adoption_recovery_requests' for r in records):
        findings.append('Signed-adoption recovery request metadata only: snapshot currentness does not recover authority, finalize recovery, or cover emergency targets.')
    if any(r['kind']=='pmo.delivery_prerequisites' for r in records):
        findings.append('Delivery prerequisite qualification is not universal closure validity. Preserve historical release and signed facts; this observation does not renew signatures, archive artifacts or authorize closure.')
    if any(r['kind']=='pmo.approval_routing_jobs' for r in records):
        findings.append('Routing receipt metadata is historical communication evidence, not department approval. Intent matching does not evaluate dispatch readiness or authorize reminders or retries.')
    if any(r['kind']=='finance.payment_assessments' for r in records):
        findings.append('Payment assessment metadata only: unchanged snapshot is not payment qualification, exception approval or release authority. Reassess in the native workspace; no cash movement, debt waiver or deployment is performed.')
    if any(r['kind']=='pmo.planning_readiness' for r in records):
        findings.append('Planning metadata only: reassess through the native planning workspace with current source-read grants. This does not renew readiness, verify source authenticity or grant owner approval.')
    if any(r['kind']=='documents.publication_effects' for r in records):
        findings.append('Historical recipient receipts do not authorize a new publication. Check current audience, recipient, review and retention controls in the document workspace')
    return {'capability':'A04 domain policy impact investigation','provider':'deterministic_internal_no_external_model',
        'observation':report,'uncertain_effects':[r for r in records if r['state']=='uncertain_effect'],
        'committed_effects':[r for r in records if r['state'] in ['committed_effect','committed_receipt_requires_reconciliation']],
        'receipt_conflicts':[r for r in records if r['state']=='receipt_conflict_requires_reconciliation'],
        'findings':findings,
        'next_work':['Reconcile uncertain effects by existing receipt-first domain recovery','Use domain services for new decisions and snapshots; old approvals are never copied'],
        'effect_tools':[],'business_approval':False,'owner_values_inferred':False}
