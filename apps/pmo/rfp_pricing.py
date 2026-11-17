"""Compare prices only when both documents explicitly establish the same basis."""
import json
import re

from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.evidence_access import restricted
from apps.finance.rules import decimal


QUOTE = 'psl/rfp-commercial-terms/v1'
AWARD = 'psl/rfp-award/v1'


def read(evidence, schema):
    if evidence is None:
        return None
    try:
        value = json.loads(evidence.body)
    except ValueError:
        return None
    if not isinstance(value, dict) or value.get('schema') != schema:
        return None
    extra = 'terms' if schema == QUOTE else 'submission'
    currency = value.get('currency')
    basis = value.get('basis')
    if (set(value) != {'schema', 'amount', 'currency', 'basis', extra} or
            not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency) or
            not isinstance(basis, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', basis)):
        raise ValidationError('Structured pricing needs an exact amount, currency and declared basis.')
    if schema == QUOTE and (not isinstance(value['terms'], str) or not value['terms'].strip() or len(value['terms']) > 4000):
        raise ValidationError('Supply the actual public commercial terms.')
    if schema == AWARD and (type(value['submission']) is not int or value['submission'] < 1):
        raise ValidationError('Award proof must identify the actual submitted response.')
    return {**value, 'amount': decimal(value['amount'], nonnegative=True)}


def quote_text(evidence):
    price = read(evidence, QUOTE)
    if price is None:
        return evidence.body
    return f"{price['terms']}\nQuoted amount: {price['currency']} {price['amount']:f} ({price['basis'].replace('_', ' ')})."


def verify_award(evidence, submission, result, amount, currency):
    proof = read(evidence, AWARD)
    if proof and (result != 'won' or proof['submission'] != submission.pk or
                  (proof['amount'], proof['currency']) != (amount, currency)):
        raise ValidationError('The award amount, currency and submitted response must match the selected award proof.')


def comparison(case, outcome):
    from .rfp import public_terms_for
    from .rfp_outcomes import historical_submission

    if outcome is None or outcome.result != 'won' or outcome.award_amount is None:
        return None
    result = {'finding': 'The award and reviewed quote need an explicit comparable price basis.'}
    try:
        evidence = outcome.evidence
        if evidence is None or restricted(evidence):
            return result
        award = read(evidence, AWARD)
        if not award:
            return result
        verify_award(evidence, outcome.submission, 'won', outcome.award_amount, outcome.award_currency)
        terms = public_terms_for(outcome.submission.response)
        quote = read(terms, QUOTE)
        if not quote or restricted(terms):
            return result
        response = historical_submission(case, outcome.submission)
        if response.pk != outcome.submission.response_id:
            return result
        fields = outcome.submission.version.fields
        if not any(terms.pk in field['evidence_ids'] and field['text'].startswith(quote_text(terms) + '\nTimeline: ')
                   for field in fields.values()):
            return result
    except (ValidationError, PermissionDenied):
        return result
    result.update(quote=quote, quote_evidence=terms.pk, award_basis=award['basis'])
    if (award['currency'], award['basis']) != (quote['currency'], quote['basis']):
        result['finding'] = 'The award and reviewed quote use different currencies or price bases.'
    elif award['amount'] == quote['amount']:
        result['finding'] = 'The award matches the reviewed submitted quote.'
    else:
        result['finding'] = 'The award differs from the reviewed submitted quote. Review the difference before agreeing project pricing.'
    return result
