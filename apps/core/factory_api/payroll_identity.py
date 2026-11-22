"""Same-ID payroll name checks using separate source holders."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.views.decorators.debug import sensitive_variables

from adapters.forecast import KEY
from apps.core.views import accessible_case
from apps.finance import payroll_identity as native
from apps.finance.hrfinance_models import HRReadSnapshot
from apps.finance.payroll_models import PayrollInput
from apps.identity.services import active_case_grants

from .http import BOOLEAN, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj


SIDE = choice(*native.CAPTURE_ACTIONS)
RESULT = choice('awaiting_source', 'same', 'different')
COMPARISON = obj({'id': ID, 'result': RESULT,
                  'followup': nullable(ID), 'review': nullable(choice('response', 'correction_return', 'correction_reject'))})


def workspace(actor, case_id):
    case = accessible_case(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    if not grants.intersection({'payroll.read', 'hrfinance.read'}):
        raise PermissionDenied
    return case, grants


@endpoint(response=obj({'revision': REVISION, 'configured': BOOLEAN, 'can_compare': BOOLEAN,
                        'can_route_difference': BOOLEAN, 'attestation_sides': array(SIDE, limit=2)}),
          summary='Read which private payroll and HR name-check actions apply to the current user')
def options(request, case_id):
    actor = request.user
    case, grants = workspace(actor, case_id)
    try:
        _, rules = native.rule(case)
    except ValidationError:
        rules = None
    sides = []
    compare = False
    if rules:
        compare = actor.pk in rules['reader_ids'] and {'payroll.read', 'payroll.private.read'} <= grants
        if {'evidence.add', 'payroll.read', 'payroll.capture'} <= grants and PayrollInput.objects.filter(
                request__case=case, actor=actor, metadata__accepted=True).exists():
            sides.append('payroll')
        if {'evidence.add', 'hrfinance.read', 'hrfinance.capture'} <= grants and HRReadSnapshot.objects.filter(
                contract__need__case=case, contract__payload__purpose='payroll_matching', actor=actor, status='accepted').exists():
            sides.append('hr')
    return {'revision': case.revision, 'configured': rules is not None, 'attestation_sides': sides,
            'can_compare': compare, 'can_route_difference': compare and 'payroll.hr_correction' in grants}


@endpoint(method='POST', request=obj({'revision': REVISION, 'side': SIDE, 'record_id': ID, 'row_key': KEY,
    'name': {**TEXT, 'maxLength': 160}, 'source_reference': {**TEXT, 'maxLength': 160}}),
    response=obj({'attestation_id': ID, 'revision': REVISION}), status=201,
    summary='Record a private name exactly as held by the authorised owner of that payroll or HR source')
@sensitive_variables('body')
def attest(request, case_id, *, body):
    case, _ = workspace(request.user, case_id)
    row = native.capture(request.user, case.pk, body['side'], body['record_id'], body['row_key'], body['name'],
                         body['source_reference'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'attestation_id': row.pk, 'revision': case.revision}


@endpoint(method='POST', request=obj({'revision': REVISION, 'run_id': ID, 'input_id': ID, 'row_key': KEY}),
    response=obj({'id': ID, 'result': RESULT}), status=201,
    summary='Compare the two owner-attested names for one exact matched staff ID')
def compare(request, case_id, *, body):
    case, _ = workspace(request.user, case_id)
    row = native.check(request.user, case.pk, body['run_id'], body['input_id'], body['row_key'], body['revision'])
    return {'id': row.pk, 'result': row.data['result']}


@endpoint(response=COMPARISON, summary='Read the authorised name comparison and HR correction status')
def detail(request, case_id, comparison_id):
    case, _ = workspace(request.user, case_id)
    return native.readback(request.user, case.pk, comparison_id)


@endpoint(method='POST', request=obj({'revision': REVISION}),
    response=obj({'followup_id': ID, 'request_id': ID, 'revision': REVISION}),
    summary='Send the recorded name difference to HR through the existing correction workflow')
def route(request, case_id, comparison_id, *, body):
    case, _ = workspace(request.user, case_id)
    followup = native.route(request.user, case.pk, comparison_id, body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'followup_id': followup.pk, 'request_id': followup.record_id, 'revision': case.revision}
