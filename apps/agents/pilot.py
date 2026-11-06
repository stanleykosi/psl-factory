"""Bounded A04 investigator using only the native authorized preflight projection."""
from apps.identity.services import require
from apps.policy import pilot


def investigate(actor,case_id,pk):
    case=pilot.context(actor,case_id);require(actor,case,'agent.pilot')
    report=pilot.inspect(actor,case_id,pk);s=report['snapshot'];findings=[]
    if not report['current']:findings.append('Refresh stale evidence before supervised use')
    for p in s['participants']:
        if p['missing']:findings.append(f"Participant #{p['user_id']} lacks selected current grants; no access was installed")
    for p in s['policies']:
        variants=[g for g in s.get('bindings',{}).get('native_guards',[]) if g['operation']==p['operation']]
        required=set().union(*(set(g['native_required_components']) for g in variants)) if variants and all('native_required_components' in g for g in variants) else None
        missing=[r['component'] for r in p['dependencies'] if r['status']!='ACTIVE' and (required is None or r['component'] in required)]
        if missing:findings.append(p['operation']+': dependent runtime policy hold: '+', '.join(missing))
        unused=[r['component'] for r in p['dependencies'] if r['status']!='ACTIVE' and required is not None and r['component'] not in required]
        if unused:findings.append(p['operation']+': other declared variants remain unevaluated; these components are not needed by the selected native variants: '+', '.join(unused))
    for r in s['integrations']:
        if not r['current_ready'] or not r['review_current']:findings.append(f"Integration #{r['contract']} requires current authenticated evidence and human review")
    for j in s['jobs']:
        if j['status'] in ['unknown','uncertain','leased']:findings.append(f"{j['family']} #{j['id']}: receipt-first source investigation; never replay from this pack")
        if j['family'] in ['application','cold']:
            findings.append(f"{j['family']} #{j['id']}: native physical receipt current: {j['receipt_verified']}; isolated recovery only, live authority remains disabled")
    if not s['technical'].get('process_build_identity'):
        findings.append('Startup source identity is unavailable in this recorded pack; capture fresh native evidence')
    elif s['technical']['source_identity']!=s['technical']['process_build_identity']:
        findings.append('Source changed since process startup; restart the reviewed deployment before fresh attestation')
    binding=s.get('bindings',{})
    if binding.get('unbound_operations'):findings.append('Native guard not bound for selected operations: '+', '.join(binding['unbound_operations']))
    for g in binding.get('native_guards',[]):
        if g['state']!='READY_AT_OBSERVATION':findings.append(g['operation']+': shared native guard holds; no transition performed')
        if g['operation']=='role.decision.evaluate':findings.append('Role/action qualification only; actual business action grants and independent human controls remain separate')
        if g['operation']=='workflow.clock.evaluate':findings.append('Base due reassessment only; stored commitments, pause history and action permissions remain unchanged. Use the native human deadline review for adoption')
        if g['operation']=='payment.assess':
            findings.append('Payment assessment preview only: '+g.get('evaluation',{}).get('status','unavailable')+'; unknown values remain unknown. No exception approval, debt waiver or deployment authority is granted')
        if g['operation']=='hypercare.evaluate':
            findings.append('Hypercare evaluation preview only; unknown or failed qualification cannot close delivery. No deployment or closure is authorized')
        if g['operation'] in ['receipt.verify','receipt.allocate']:
            findings.append('Native cash preconditions only; no cash lot or allocation was created. Preserve exact source verification, separation, current cash/invoice capacity and receipt-first idempotent history')
    if not binding.get('worker_deployment_ready'):findings.append('Current independent web/worker deployment identity evidence is unavailable')
    human=s.get('human_acceptance',{})
    for r in human.get('references',[]):
        if not r['current']:findings.append(f"AF13 review #{r['review']} is historical or requires source-owned reassessment")
    if human.get('uncovered_process_ids'):findings.append('Selected process scope lacks current source-owned acceptance: '+', '.join(human['uncovered_process_ids']))
    findings.append('Physical storage/retention/monitoring, independent business oracle and full supervised pilot acceptance remain separate evidence')
    return {'agent':'A04 native read-only pilot investigator/v1','report':report,'findings':findings,
        'effect_tools':[],'model_provider':'none','operational_acceptance':False}
