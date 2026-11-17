"""Commands exposed by a focused screen, before its native authority and version checks."""
from django.core.exceptions import ValidationError


SCREENS = {
    'pmo-finance/v1': {
        'decision': ('claim', 'release_claim', 'decide', 'information', 'responsibility_recheck'),
        'recovery': ('reconcile', 'replace_preparation', 'resume', 'cancel', 'adopt_profile'),
    },
    'rfp-response/v1': {
        'decision': ('response', 'commercial', 'document'),
        'response': ('outcome','portal_receipt','followup_draft','followup_review','followup_send','followup_confirm','followup_lookup','followup_route'),
        'recovery': ('reconcile', 'cancel'),
    },
    'finance-accounts/v1': {
        'decision': ('claim', 'decide'),
        'recovery': ('reconcile', 'recheck', 'cancel'),
    },
    'finance-schedules/v1': {
        'decision': ('review',),
        'recovery': ('advance', 'resume', 'cancel', 'restart', 'correct', 'export', 'adopt_profile'),
    },
    'finance-ppe/v1': {
        'decision': ('review',),
        'recovery': ('advance', 'resume', 'cancel', 'restart', 'correct', 'adopt_profile'),
    },
    'finance-forecast/v1': {
        'decision': ('review', 'priority', 'group_review', 'group_rules'),
        'response': ('support', 'actual', 'verify', 'match', 'unmatch'),
        'recovery': ('advance', 'correct', 'restart', 'cancel', 'resume', 'reconcile', 'operate_delivery', 'adopt_profile'),
    },
    'finance-bu/v1': {
        'decision': ('prepare_rule', 'review'),
        'response': ('publish',),
        'recovery': ('advance', 'cancel', 'resume', 'correct', 'restart', 'receive'),
    },
    'finance-payroll/v1': {
        'decision': ('review',),
        'response': ('publish',),
        'recovery': ('advance', 'cancel', 'resume', 'correct', 'restart', 'receive', 'receive_hr', 'withdraw', 'successor'),
    },
    'finance-ledger/v1': {
        'decision': ('review',),
        'response': ('observe',),
        'recovery': ('advance', 'cancel', 'resume', 'correct', 'restart', 'recheck', 'adopt_profile'),
    },
    'pmo-emergency/v1': {
        'decision': ('review', 'preauthorization_decision', 'authorize', 'record_review', 'retrospective_decision'),
        'response': ('capture_outcome',),
        'recovery': ('reconcile', 'operate_delivery', 'reconcile_retrospective'),
    },
    'pmo-weekly-report/v1': {
        'decision': ('review',),
        'recovery': ('reconcile', 'operate_delivery'),
    },
    'pmo-minutes/v1': {
        'decision': ('review',),
        'response': ('confirm', 'add_decision', 'add_commitment', 'use_selected'),
        'recovery': ('reconcile', 'operate', 'advance', 'resume', 'cancel', 'restart', 'correct'),
    },
    'pmo-leadership-report/v1': {
        'decision': ('review',),
        'recovery': ('reconcile', 'operate_delivery'),
    },
    'pmo-escalation/v1': {
        'decision': ('decision', 'review'),
        'recovery': ('reconcile', 'operate_delivery'),
    },
    'delivery-go-live/v1': {
        'decision': ('review',),
        'response': ('accept',),
        'recovery': ('reconcile', 'operate_delivery', 'settle_stop'),
    },
    'delivery-release/v1': {
        'decision': ('delivery_decision',),
        'recovery': ('advance', 'reassess', 'resume', 'cancel', 'adopt_profile'),
    },
    'delivery-closure/v1': {
        'decision': ('review', 'decide'),
        'recovery': ('advance', 'correct', 'restart', 'cancel', 'settle_stop', 'resume', 'adopt_profile'),
    },
}


def require_action(work, focus, action):
    if focus and action not in SCREENS.get(work.definition, {}).get(focus, ()):
        raise ValidationError('Choose an available action on this page.')
