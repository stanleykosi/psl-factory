"""Payment assessment and independent release controls for an authorised workspace."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.shortcuts import get_object_or_404

from adapters.payment_release import LocalPaymentReleaseControls
from apps.agents.payments import investigate
from apps.core.evidence_access import public_evidence
from apps.core.services import lock_case
from apps.core.views import accessible_case
from apps.finance import payments
from apps.finance.models import BillingCoverage, PaymentAssessment, PaymentDecision, PaymentException, PaymentReleaseReservation
from apps.identity.services import active_case_grants, require
from apps.pmo.models import DeliveryDossier
from apps.policy.payment_drafts import draft_payment_policy
from apps.policy.payment_validators import PEOPLE, SCHEMAS
from apps.policy.services import resolve

from .delivery import NOTE, PIN, PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .work import PAGE, page_number


GRANTS = {'assess': 'payment.assess', 'request': 'payment.exception.request',
          'reserve': 'payment.release.reserve', 'check': 'payment.release.reserve',
          'investigate': 'agent.payments', 'draft_rule': 'policy.configure'}
KEY = {**TEXT, 'maxLength': 100}
VERDICTS = ('approve', 'reject', 'return', 'revoke', 'withdraw')
STATE = choice('UNKNOWN', 'MEETS_EXPECTATION', 'BELOW_EXPECTATION')
ASSESSMENT = obj({'id': ID, 'dossier_id': ID, 'coverage_id': ID, 'status': STATE, 'created_at': DATETIME})
ASSESSMENT_RESULT = obj({'status': STATE, 'denominator': nullable(TEXT), 'qualifying_funds': nullable(TEXT),
    'percentage': nullable(TEXT), 'expectation_percent': TEXT, 'currency': TEXT, 'amount_basis': nullable(TEXT),
    'findings': array(TEXT), 'debt_waived': BOOLEAN, 'deployment_authorized': BOOLEAN, 'scope': TEXT,
    'open_debt': nullable(TEXT)}, optional=('open_debt',))
EXCEPTION = obj({'id': ID, 'assessment_id': ID, 'latest_verdict': nullable(choice(*VERDICTS)),
                 'valid_from': DATETIME, 'valid_until': DATETIME})
RESERVATION = obj({'id': ID, 'assessment_id': ID, 'decision_id': nullable(ID), 'sha256': PIN})
DECISION = obj({'id': ID, 'verdict': choice(*VERDICTS), 'evidence_id': ID, 'reason': TEXT, 'created_at': DATETIME})
CONTROLS = obj({'reservation': ID, 'sha256': PIN, 'controls_current': BOOLEAN,
                'deployment_dispatched': BOOLEAN, 'debt_waived': BOOLEAN})
COMMANDS = {
    'assess': {'dossier_id': ID, 'coverage_id': ID},
    'request': {'assessment_id': ID, 'operation_key': KEY, 'reason': NOTE, 'evidence_id': ID,
                'valid_from': DATETIME, 'valid_until': DATETIME},
    'decide': {'request_id': ID, 'verdict': choice(*VERDICTS), 'reason': NOTE, 'evidence_id': ID},
    'reserve': {'assessment_id': ID, 'operation_key': KEY, 'request_id': nullable(ID)},
    'check': {'reservation_id': ID},
    'investigate': {},
}
DRAFTS = [obj({'action': {'const': 'draft_rule'}, 'revision': REVISION, 'component': {'const': component},
               'effective_from': DATETIME, 'evidence_id': ID, 'value': array(schema, limit=100) if component == PEOPLE else schema})
          for component, (_, schema) in SCHEMAS.items()]


def scope(actor, case_id):
    case = accessible_case(actor, case_id)
    for grant in ('payment.read', 'finance.read', 'delivery.read'):
        require(actor, case, grant)
    return case


def verbs(actor, case, grants):
    allowed = ['withdraw'] if 'payment.exception.withdraw' in grants else []
    if 'payment.exception.decide' in grants:
        try:
            payments.authority(actor, case)
        except (PermissionDenied, ValidationError):
            pass
        else:
            allowed.extend(VERDICTS[:-1])
    return allowed


@endpoint(response=obj({'revision': REVISION, 'actions': array(choice(*GRANTS)), 'verdicts': array(choice(*VERDICTS)),
    'dossiers': array(obj({'id': ID, 'candidate': TEXT}), limit=20),
    'coverage': array(obj({'id': ID, 'reference': TEXT, 'version': REVISION, 'completeness': TEXT}), limit=20),
    'assessments': array(ASSESSMENT, limit=20), 'requests': array(EXCEPTION, limit=20),
    'reservations': array(RESERVATION, limit=20), 'evidence': array(PROOF, limit=40),
    'rules': array(obj({'component': choice(*SCHEMAS), 'status': TEXT})), 'next_page': nullable(PAGE)}),
    query={'page': PAGE}, summary='List bounded assessment, human exception and release control references')
def options(request, case_id):
    actor = request.user
    case = scope(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    actions = [action for action, grant in GRANTS.items() if grant in grants]
    number = page_number(request)
    offset = (number - 1) * 20
    bounds = slice(offset, offset + 21)
    assessments = list(PaymentAssessment.objects.filter(case=case).only('dossier_id', 'coverage_id', 'created_at').annotate(
        effect_status=KeyTextTransform('status', 'result')
    ).order_by('-pk')[bounds])
    latest = PaymentDecision.objects.filter(request_id=OuterRef('pk')).order_by('-pk').values('verdict')[:1]
    requests = list(PaymentException.objects.filter(assessment__case=case).only('assessment_id', 'valid_from', 'valid_until').annotate(
        latest=Subquery(latest)).order_by('-pk')[bounds])
    reservations = list(PaymentReleaseReservation.objects.filter(assessment__case=case).order_by('-pk').values(
        'id', 'assessment_id', 'decision_id', 'sha256')[bounds])
    dossiers, coverage = [], []
    if 'assess' in actions:
        dossiers = list(DeliveryDossier.objects.filter(case=case).order_by('-pk').values_list('pk', 'candidate__reference')[bounds])
        coverage = list(BillingCoverage.objects.filter(case=case).order_by('-pk').values(
            'id', 'reference', 'version', 'completeness')[bounds])
    proofs = public_evidence(case.evidence.all()).only('id', 'kind', 'version').order_by('-pk')[:40]
    more = max(map(len, (assessments, requests, reservations, dossiers, coverage))) > 20
    return {'revision': case.revision, 'actions': actions, 'verdicts': verbs(actor, case, grants),
            'dossiers': [{'id': pk, 'candidate': reference} for pk, reference in dossiers[:20]],
            'coverage': coverage[:20], 'evidence': proof_rows(proofs),
            'assessments': [{'id': row.pk, 'dossier_id': row.dossier_id, 'coverage_id': row.coverage_id,
                             'status': row.effect_status, 'created_at': row.created_at} for row in assessments[:20]],
            'requests': [{'id': row.pk, 'assessment_id': row.assessment_id, 'latest_verdict': row.latest,
                          'valid_from': row.valid_from, 'valid_until': row.valid_until} for row in requests[:20]],
            'reservations': reservations[:20], 'rules': [{'component': key, 'status': resolve(key, case).status} for key in SCHEMAS],
            'next_page': number + 1 if more and number < PAGE['maximum'] else None}


@endpoint(response=obj({'id': ID, 'revision': REVISION, 'result': ASSESSMENT_RESULT, 'sha256': PIN,
                       'dossier_id': ID, 'coverage_id': ID}),
          summary='Read the historical result of one exact payment assessment')
def assessment(request, case_id, assessment_id):
    case = scope(request.user, case_id)
    row = get_object_or_404(PaymentAssessment.objects, case=case, pk=assessment_id)
    return {'id': row.pk, 'revision': case.revision, 'result': row.result, 'sha256': row.sha256,
            'dossier_id': row.dossier_id, 'coverage_id': row.coverage_id}


@endpoint(response=obj({'id': ID, 'revision': REVISION, 'assessment_id': ID, 'reason': TEXT,
    'requested_by_me': BOOLEAN, 'evidence_id': ID, 'valid_from': DATETIME, 'valid_until': DATETIME,
    'decisions': array(DECISION, limit=20)}), summary='Read one exception request and its recorded human decisions')
def exception(request, case_id, request_id):
    case = scope(request.user, case_id)
    row = get_object_or_404(PaymentException.objects, assessment__case=case, pk=request_id)
    decisions = list(row.decisions.order_by('-pk').values('id', 'verdict', 'evidence_id', 'reason', 'created_at')[:20])
    return {'id': row.pk, 'revision': case.revision, 'assessment_id': row.assessment_id, 'reason': row.reason,
            'requested_by_me': row.actor_id == request.user.pk, 'evidence_id': row.evidence_id,
            'valid_from': row.valid_from, 'valid_until': row.valid_until, 'decisions': decisions}


@endpoint(method='POST', request={'oneOf': [obj({'action': {'const': action}, 'revision': REVISION, **fields})
    for action, fields in COMMANDS.items()] + DRAFTS},
    response=obj({'id': ID, 'revision': REVISION, 'controls': nullable(CONTROLS)}), status=201,
    summary='Assess payment, request and decide an exception, and reserve or revalidate independent controls')
def command(request, case_id, *, body):
    actor = request.user
    case = scope(actor, case_id)
    action = body['action']
    rev = body['revision']
    args = (actor, case.pk)
    controls = None
    if 'evidence_id' in body and not public_evidence(case.evidence.filter(pk=body['evidence_id'])).exists():
        raise ValidationError('Choose evidence in this workspace that is available for payment review.')
    if action == 'assess':
        row = payments.assess(*args, body['dossier_id'], body['coverage_id'], rev)
    elif action == 'request':
        row = payments.request_exception(*args, body['assessment_id'], body['operation_key'], body['reason'],
            body['evidence_id'], body['valid_from'], body['valid_until'], rev)
    elif action == 'decide':
        row = payments.decide(*args, body['request_id'], body['verdict'], body['evidence_id'], body['reason'], rev)
    elif action == 'reserve':
        row = payments.reserve(*args, body['assessment_id'], body['operation_key'], rev, body['request_id'])
    elif action == 'check':
        with transaction.atomic():
            lock_case(*args, GRANTS['check'], rev)
            controls = LocalPaymentReleaseControls().check_for_use(*args, body['reservation_id'])
        row_id = controls['reservation']
    elif action == 'investigate':
        row = investigate(*args, rev)
    else:
        with transaction.atomic():
            lock_case(*args, GRANTS['draft_rule'], rev)
            row = draft_payment_policy(*args, body['component'], body['value'], body['evidence_id'], body['effective_from'])
    if controls is None:
        row_id = row.pk
    case.refresh_from_db(fields=['revision'])
    return {'id': row_id, 'revision': case.revision, 'controls': controls}
