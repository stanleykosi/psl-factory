"""Typed, live recovery investigation. No SQL, paths, credentials, approval or effect tools."""
from django.db import transaction
from apps.core.models import Case
from apps.identity.services import require
from apps.workflows import application_recovery as domain


@transaction.atomic
def prepare(actor, case_id, reference, source_ref, target_ref, key_ref):
    case = Case.objects.get(pk=case_id)
    require(actor, case, 'recovery.agent')
    return domain.capture(actor, case_id, reference, dict(source_ref=source_ref, target_ref=target_ref, key_ref=key_ref))


@transaction.atomic
def investigate(actor, case_id, plan_id):
    case = Case.objects.get(pk=case_id)
    require(actor, case, 'recovery.agent')
    result = domain.report(actor, case_id, plan_id)
    findings = []
    for job in result['jobs']:
        if job['status'] == 'confirmed' and not job['physical_receipt_current']:
            findings.append({'job': job['id'], 'finding': 'Recorded completion lacks current verified physical evidence', 'next': 'Investigate original archive/target; never reset or overwrite it'})
        elif job['status'] in ['held', 'unknown', 'leased']:
            findings.append({'job': job['id'], 'finding': 'Exact intent requires reconciliation before another effect', 'next': 'Check actual receipt first, then current independent human authority and attempt budget'})
    return {**result, 'findings': findings, 'effect_tools': [], 'human_decision_required': True,
            'next_steps': ['Configure missing source/target/key/criteria independently', 'Review exact plan before queuing', 'Verify recovered data and managed attachments before a separate human recovery decision'],
            'deployment_authority': False}
