from apps.core.evidence_access import public_evidence,restricted
import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event
from apps.pmo.services import subject
from .models import AgentRun

@transaction.atomic
def extract_evidence(actor, case_id, evidence_id, process_id, provider=None):
    from adapters.models import SyntheticEvidenceProvider
    case = lock_case(actor, case_id, 'agent.extract')
    evidence = subject(case, evidence_id)
    if any(restricted(e) for e in [evidence]):raise ValidationError('Restricted source evidence requires its authorized domain interface')
    rows = json.loads((settings.BASE_DIR / 'contracts/process-map.json').read_text(encoding='utf-8'))['rows']
    process = next((r for r in rows if r['id'] == process_id), None)
    if not process or (case.kind == 'support' and process['workflow_family_id'] != 'AF01'):
        raise ValidationError('Process is outside task scope')
    if provider is None:
        if not case.synthetic:
            raise ValidationError('Configure an approved real provider before operational agent work')
        provider = SyntheticEvidenceProvider()
    if len(evidence.body) > 16000:
        raise ValidationError('Agent input budget exceeded')
    result = provider.extract(evidence.body)
    if set(result) != {'facts', 'uncertainties', 'proposed_actions'} or result['proposed_actions'] != []:
        raise ValidationError('This extraction tool cannot propose or execute state changes')
    if not isinstance(result['facts'], list) or len(result['facts']) > 8 or not isinstance(result['uncertainties'], list):
        raise ValidationError('Malformed or over-budget provider output')
    if len(result['uncertainties']) > 16 or any(not isinstance(v,str) or len(v) > 2000 for v in result['uncertainties']):
        raise ValidationError('Uncertainty output is malformed or over budget')
    for fact in result['facts']:
        if not isinstance(fact, dict) or set(fact) != {'quote'} or not isinstance(fact['quote'], str) or not fact['quote'] or fact['quote'] not in evidence.body:
            raise ValidationError('Provider fact lacks an exact source citation')
        fact.update(evidence_id=evidence.pk, sha256=evidence.sha256, version=evidence.version)
    if len(json.dumps(result)) > 24000:
        raise ValidationError('Agent output budget exceeded')
    run = AgentRun.objects.create(case=case, actor=actor, evidence=evidence, provider=provider.name, process_id=process_id, result=result)
    event(actor, case, 'agent.extracted', run=run.pk, provider=provider.name, evidence=evidence.pk, process=process_id)
    return run
