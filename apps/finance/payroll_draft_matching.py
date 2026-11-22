"""One reviewed, private way to match eligible rows from a held combination."""

from django.core.exceptions import ValidationError

from adapters.payroll import sum_values
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.payroll_validators import ACCESS, MERGE
from apps.policy.services import active_component, reference_values

from .payroll_models import PayrollInput


VERDICT = 'approve_draft_match'
MODE = 'restricted_payroll_draft_match/v1'
ROW_HOLDS = {'duplicate_source_row_or_component', 'missing_row_currency',
             'invalid_row_currency', 'row_currency_mismatch'}
SOURCE_HOLDS = ROW_HOLDS | {'source_control_unresolved'}


def source_policies(actor, combined):
    from . import payroll

    if (combined.kind != 'combine' or combined.parent_id is not None or combined.metadata['status'] != 'held'
            or set(combined.metadata['codes']) - SOURCE_HOLDS):
        raise ValidationError('Draft matching review needs the exact combination held for source rows.')
    payroll.run_access(actor, combined)
    request = combined.request
    access, rules = payroll.access(request, actor, True)
    merge = active_component(MERGE, request.case)
    treatment = reference_values(merge)[0]
    policies = {ACCESS: access.pk, MERGE: merge.pk}
    if (combined.metadata['policy_ids'] != policies or rules.get('format') != 'psl.payroll-access/v2'
            or rules.get('row_handling') != 'hold_conflicting_rows' or rules.get('currency_mode') is None
            or treatment.get('format') != 'psl.payroll-merge/v2'
            or treatment['duplicate_within_source'] != 'hold_conflicting_rows'):
        raise ValidationError('Current payroll source and combination rules must permit draft use of eligible rows.')
    return policies


def subset(combined, policies):
    from . import payroll

    request = combined.request
    inputs = [payroll.exact(request.case, PayrollInput, pk) for pk in combined.metadata['input_ids']]
    if len(inputs) != 2 or {item.provider for item in inputs} != set(request.metadata['providers']):
        raise ValidationError('Select both exact provider versions.')
    for item in inputs:
        payload = item.payload
        codes = set(item.metadata['codes'])
        if (payload['completeness'] != 'complete' or payload['control_total'] is None or codes - SOURCE_HOLDS
                or (codes and not codes.intersection(ROW_HOLDS))):
            raise ValidationError('Provide the original inventory and control for both sources before review.')

    result = combined.result
    if digest({'result': result, 'metadata': combined.metadata, 'parent': None}) != combined.sha256:
        raise ValidationError('The exact reviewed combination fingerprint no longer matches.')
    rows = result['rows']
    eligible = [index for index, row in enumerate(rows) if row['amount'] is not None and not row.get('quarantine_codes')]
    if not eligible or len(eligible) == len(rows) or len(rows) > 1000 or result['combined_total'] is not None:
        raise ValidationError('Draft matching needs both eligible rows and amounts still held as unknown.')
    pin = {'mode': MODE, 'policy_ids': policies, 'eligible_rows': len(eligible), 'held_rows': len(rows) - len(eligible),
           'subset_sha256': digest([combined.sha256, eligible]), 'publication_authorized': False}
    return pin, eligible


def scope(actor, combined):
    return subset(combined, source_policies(actor, combined))


def current(combined, review_id=None, *, read_rows=False):
    from . import payroll

    review = combined.reviews.select_related('actor').order_by('-pk').first()
    if (review is None or review.verdict != VERDICT or review.subject_sha256 != combined.sha256
            or (review_id is not None and review.pk != review_id)):
        raise ValidationError('A current review for this exact draft matching scope is required.')
    case = combined.request.case
    require(review.actor, case, 'payroll.review')
    authority = payroll.authority(review.actor, combined.request, 'combine', combined.actor_id)
    policies = source_policies(review.actor, combined)
    pin = review.authority.get('draft_match', {})
    if (pin.get('mode') != MODE or pin.get('policy_ids') != policies or pin.get('publication_authorized') is not False
            or review.authority != {**authority, 'draft_match': pin}):
        raise ValidationError('The recorded draft matching scope or reviewer authority changed.')
    eligible = []
    if read_rows:
        recomputed, eligible = subset(combined, policies)
        if recomputed != pin:
            raise ValidationError('The recorded draft subset no longer matches the exact held combination.')
    return review, eligible


def summary(combined, eligible):
    rows = combined.result['rows']
    return {'eligible_rows': len(eligible), 'held_rows': len(rows) - len(eligible),
            'known_amount': sum_values(rows[index]['amount'] for index in eligible),
            'currency': combined.request.metadata['currency']}


def match_rows(rows, eligible, hr_rows, period, semantics, rules):
    from .payroll_math import match

    matched, codes = match([rows[index] for index in eligible], hr_rows, period, semantics, rules)
    by_position = dict(zip(eligible, matched['rows'], strict=True))
    return {'rows': [by_position.get(index, {**row, 'bu': None, 'match_status': 'held_payroll_source'})
                     for index, row in enumerate(rows)], 'issues': matched['issues']}, codes
