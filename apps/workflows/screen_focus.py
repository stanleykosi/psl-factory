"""Commands exposed by a focused screen, before its native authority and version checks."""
from django.core.exceptions import ValidationError


SCREENS = {
    'pmo-finance/v1': {
        'decision': ('claim', 'release_claim', 'decide', 'information', 'responsibility_recheck'),
        'recovery': ('reconcile', 'replace_preparation', 'resume', 'cancel', 'adopt_profile'),
    },
    'rfp-response/v1': {
        'decision': ('response', 'commercial', 'document'),
        'response': ('outcome',),
        'recovery': ('reconcile', 'cancel'),
    },
    'finance-accounts/v1': {
        'decision': ('claim', 'decide'),
        'recovery': ('reconcile', 'recheck', 'cancel'),
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
        'response': ('confirm', 'add_decision', 'add_commitment'),
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
