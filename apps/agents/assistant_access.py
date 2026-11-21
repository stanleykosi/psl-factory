"""Project-owned data permissions, checked before dispatch and again on readback."""
import os

from django.core.exceptions import PermissionDenied

from apps.policy.models import Configuration
from apps.policy.services import resolve


CHAT = 'OPS.department_assistant_use'
TOTALS = 'OPS.payroll_chat_totals'
WINNING = 'OPS.winning_bid_reuse'


def permission(case, component):
    resolution = resolve(component, case)
    return resolution.configuration if resolution.status == 'ACTIVE' else None


def model_rule(case, persona):
    config = permission(case, CHAT)
    if config:
        rule = config.envelope['value']
        if persona in rule['personas'] and rule['model'] == os.getenv('OPENROUTER_MODEL'):
            return config
    return None


def admitted(cases, persona):
    candidates = Configuration.objects.filter(component=CHAT).values('case_id')
    live = cases.filter(synthetic=False, kind='project', pk__in=candidates)
    allowed = [case.pk for case in live.iterator() if model_rule(case, persona)]
    return cases.filter(synthetic=True, kind='project') | cases.filter(pk__in=allowed)


def project_sources(conversation, sources):
    from apps.identity.factory_access import PERSONA_ROLES, department_cases, role_managed

    if role_managed(conversation.actor):
        if not department_cases(conversation.actor, PERSONA_ROLES[conversation.persona]).filter(pk=conversation.case_id).exists():
            raise PermissionDenied('This project is outside your department access.')
        return sources
    if conversation.case.synthetic:
        return sources
    rule = model_rule(conversation.case, conversation.persona)
    if rule is None:
        raise PermissionDenied('Project assistant use needs a current data agreement.')
    allowed = rule.envelope['value']['sources']
    return [dict(source, permission_version=rule.pk) for source in sources
            if source.get('record', {}).get('field') in allowed]
