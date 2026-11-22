"""Typed supplied asset dates and explicitly configured date-to-fraction selection."""

import hashlib
import json
from collections import defaultdict
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from adapters.forecast import KEY, obj
from apps.core.evidence_access import PPE_ASSET_DATES_SOURCE
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.policy.schedule_validators import DEC, ID

from .rules import decimal


COMPONENT = 'F07.in_service_fraction_rules'
DATE_CONTRACT = 'psl/ppe-asset-dates/v1'
FACT_KIND = 'ppe_asset_date_fact'
FACT_ACTIONS = {'case.read', 'finance.read', 'ppe.read', 'ppe.capture', 'evidence.add'}
SUPPLIED = 'explicit_supplied_fraction'
DERIVED = 'reviewed_in_service_date'
DATE = {'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$'}
OPTIONAL_DATE = {'anyOf': [DATE, {'type': 'null'}]}
FACT_FIELDS = {'contract': {'const': DATE_CONTRACT}, 'delivery_date': OPTIONAL_DATE,
               'in_service_date': OPTIONAL_DATE, 'fraction_basis': {'enum': [SUPPLIED, DERIVED]},
               'support_evidence_id': ID}
ASSET_DATES = obj(dict(FACT_FIELDS, evidence_id=ID))
SOURCE_FACT = obj(dict(FACT_FIELDS, asset_id=KEY))
SUPPORT_KINDS = ('ppe_event', 'ppe_basis_explanation')
RULE_SCOPE = {'category': KEY, 'period_start': DATE, 'period_end': DATE}
RULE = obj(dict(RULE_SCOPE, in_service_from=DATE, in_service_through=DATE,
                fraction={'type': 'string'}))
ORACLE = obj(dict(RULE_SCOPE, in_service_date=OPTIONAL_DATE, expected_fraction=DEC))
POLICY = obj({'method_evidence_id': ID, 'oracle_evidence_id': ID,
              'rules': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': RULE},
              'oracles': {'type': 'array', 'minItems': 2, 'maxItems': 100, 'items': ORACLE}})
ORACLE_CONTRACT = 'psl/ppe-in-service-fraction-oracle/v1'


def calendar_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError('Enter an actual calendar date.') from None


def support(case, pk):
    from apps.pmo.services import subject

    evidence = subject(case, pk, metadata_only=True)
    if evidence.kind not in SUPPORT_KINDS:
        raise ValidationError('Select an asset event or reporting-date explanation from this engagement.')
    return evidence


def check_facts(case, facts):
    if any(calendar_day(value) > timezone.localdate() for value in
           (facts['delivery_date'], facts['in_service_date']) if value is not None):
        raise ValidationError('Record only actual delivery and in-service dates that have occurred.')
    support(case, facts['support_evidence_id'])


def checked_sources(case, assets, *, check_values=False):
    dated = [asset for asset in assets if 'dates' in asset]
    if not dated:
        return
    ids = {asset['dates']['evidence_id'] for asset in dated}
    sources = Evidence.objects.filter(case=case, kind=FACT_KIND, source=PPE_ASSET_DATES_SOURCE, pk__in=ids)
    metadata = {pk: (author, fingerprint) for pk, author, fingerprint in sources.values_list('pk', 'created_by_id', 'sha256')}
    if set(metadata) != ids:
        raise ValidationError('Select the exact recorded date evidence for each asset.')
    author_ids = {author for author, _ in metadata.values()}
    grants = defaultdict(set)
    for author, action in Grant.objects.filter(case=case, user_id__in=author_ids, user__is_active=True, active=True,
                                               action__in=FACT_ACTIONS).values_list('user_id', 'action'):
        grants[author].add(action)
    if any(grants[author] != FACT_ACTIONS for author in author_ids):
        raise PermissionDenied('The original asset date source holder needs current access.')
    if check_values:
        bodies = dict(sources.values_list('pk', 'body'))
        for asset in dated:
            values = asset['dates']
            pk = values['evidence_id']
            body = bodies[pk]
            expected = {'asset_id': asset['asset_id'], **{key: values[key] for key in FACT_FIELDS}}
            try:
                matched = json.loads(body) == expected and hashlib.sha256(body.encode()).hexdigest() == metadata[pk][1]
            except (ValueError, RecursionError):
                matched = False
            if not matched:
                raise ValidationError('The supplied dates differ from the exact recorded asset evidence.')
            check_facts(case, values)


def needs_fraction(register):
    return any(asset.get('dates', {}).get('fraction_basis') == DERIVED for asset in register['assets'])


def needs_review(register):
    return (register.payload['label_as_of'] != register.payload['period_end']
            or any('dates' in asset for asset in register.payload['assets']))


def wait_reason(result):
    findings = {code for row in result['rows'] for code in row['findings']}
    for code, reason in (
        ('in_service_date_unknown', 'Supply the missing in-service date for Finance review.'),
        ('asset_dates_review_required', 'Ask Finance to review the supplied dates.'),
        ('in_service_fraction_rule_required', 'Activate a reviewed in-service fraction rule and rebuild the schedule.'),
        ('in_service_fraction_uncovered', 'Review the rule for the selected category, reporting period and in-service date.'),
    ):
        if code in findings:
            return reason
    return ''


def lookup(config, category, period_start, period_end, in_service_date):
    if in_service_date is None:
        return None
    return next((rule['fraction'] for rule in config['rules'] if
                 (rule['category'], rule['period_start'], rule['period_end']) == (category, period_start, period_end)
                 and rule['in_service_from'] <= in_service_date <= rule['in_service_through']), None)


def check_policy(config):
    intervals = {}
    for rule in config['rules']:
        if calendar_day(rule['period_start']) > calendar_day(rule['period_end']):
            raise ValidationError('The fraction rule needs an ordered reporting period.')
        first, last = (calendar_day(rule[field]) for field in ('in_service_from', 'in_service_through'))
        scope = (rule['category'], rule['period_start'], rule['period_end'])
        group = intervals.setdefault(scope, [])
        if first > last or any(first <= end and start <= last for start, end in group):
            raise ValidationError('Supply ordered, non-overlapping in-service date ranges for each category and period.')
        group.append((first, last))
        decimal(rule['fraction'], nonnegative=True)

    seen = set()
    outcomes = set()
    for oracle in config['oracles']:
        if calendar_day(oracle['period_start']) > calendar_day(oracle['period_end']):
            raise ValidationError('The supplied reference example needs an ordered reporting period.')
        service = oracle['in_service_date']
        if service is not None:
            calendar_day(service)
        scope = (oracle['category'], oracle['period_start'], oracle['period_end'], service)
        if scope in seen:
            raise ValidationError('Supply distinct in-service reference examples.')
        seen.add(scope)
        got = lookup(config, *scope)
        expected = oracle['expected_fraction']
        if (got is None) != (expected is None) or (got is not None and decimal(got) != decimal(expected)):
            raise ValidationError('The in-service fraction does not match its independent reference example.')
        outcomes.add(got is None)
    if outcomes != {False, True}:
        raise ValidationError('Supply reference examples for both a known fraction and a held date.')
