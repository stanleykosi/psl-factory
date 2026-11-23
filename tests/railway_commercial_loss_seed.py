"""Fresh synthetic pending bid, ready for browser-recorded loss and archive."""

import json
import os

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import rfp, rfp_portal
from apps.pmo.meetings import record_meeting
from apps.pmo.models import MeetingVersion, RFPOutcome, RFPSubmission
from apps.workflows import factory
from apps.workflows.factory_progress import set_progress
from apps.workflows.models import FactoryWork
from tests import factory_rfp_helpers
from tests.helpers import rev
from tests.railway_independent_commercial_seed import PROJECT, bind_recorder


TENANT = 'design-commercial-loss-walkthrough'
TITLE = 'SAMPLE pending bid for reviewed loss and debrief archive'
KEY = 'SAMPLE-BID-LOSS-ARCHIVE'
MAKER_USERNAME = 'sample-bid-loss-preparer'
PORTAL_REFERENCE = 'SAMPLE-PORTAL-LOSS-ARCHIVE'
DEBRIEF_REFERENCE = 'SAMPLE retrospective for this bid'
LESSON = 'Agree check-in points with the fictional customer so the next proposal addresses their delivery window.'
REASON_NAMES = ['Sample delivery timing', 'Sample service fit']
RECORDER_ACTIONS = {
    'case.read', 'factory.read', 'rfp.read', 'rfp.outcome', 'document.read', 'meeting.read',
    'policy.read', 'policy.configure', 'policy.activate',
}
SOURCES = {key: f'synthetic:commercial-loss-walkthrough-{key}' for key in ['catalog', 'debrief', 'lessons', 'loss', 'pending', 'portal']}


def prepare_pending(maker, recorder, case):
    data = factory_rfp_helpers.configured(KEY, portal=True, context=(maker, case))
    route = bind_recorder(maker, case, recorder, data)
    data['payload']['lessons'] = add_evidence(maker, case.pk, 'rfp_lessons', LESSON, SOURCES['lessons']).pk
    work = factory_rfp_helpers.start(data, key=KEY)
    _, pack = factory_rfp_helpers.reviewed_document(data, work)
    factory.run_until_wait(work.pk)

    portal = add_evidence(maker, case.pk, 'rfp_portal_receipt', json.dumps({
        'schema': rfp_portal.SCHEMA, 'version': pack.pk, 'sha256': pack.payload_sha256,
        'destination': route['destination_ref'], 'reference': PORTAL_REFERENCE,
        'received_at': timezone.now().isoformat(),
    }), SOURCES['portal'])
    submission = rfp_portal.record(maker, case.pk, pack.pk, portal.pk,
                                   'Reviewed exact fictional portal proof. No external delivery.', rev(case))
    pending = add_evidence(maker, case.pk, 'rfp_outcome', f'Fictional customer said decision on submission {submission.pk} is pending.',
                           SOURCES['pending'])
    rfp.outcome(recorder, case.pk, submission.pk, 'pending', timezone.now(), 'Client', pending.pk,
                'Synthetic customer originally said its decision was pending.', rev(case))
    add_evidence(maker, case.pk, 'rfp_outcome',
        f'Fictional customer declined exact submission {submission.pk} under reference {PORTAL_REFERENCE}. '
        'The delivery timetable was the reason given.', SOURCES['loss'])
    add_evidence(maker, case.pk, 'policy_decision',
        'The following labels were reviewed for this fictional workspace only:\n' + '\n'.join(REASON_NAMES), SOURCES['catalog'])
    notes = add_evidence(maker, case.pk, 'meeting_notes',
        f'Actual synthetic internal debrief on the fictional loss after submission {submission.pk}. {LESSON}', SOURCES['debrief'])
    record_meeting(maker, case.pk, DEBRIEF_REFERENCE, 'retrospective', timezone.now(),
                   'Review the cause of the fictional loss', LESSON, [], [], notes.pk, rev(case))
    work.refresh_from_db()
    set_progress(maker, work.pk, work.revision, True)
    return work


@transaction.atomic
def prepare(recorder):
    case, created = Case.objects.get_or_create(tenant=TENANT, kind='project', synthetic=True, title=TITLE)
    if created:
        maker = get_user_model().objects.create_user(username=MAKER_USERNAME)
        Grant.objects.bulk_create([
            *[Grant(case=case, user=maker, action=action) for action in dict.fromkeys(ACTIONS)],
            *[Grant(case=case, user=recorder, action=action) for action in sorted(RECORDER_ACTIONS)],
        ])
        work = prepare_pending(maker, recorder, case)
    else:
        work = FactoryWork.objects.get(case=case, actor__username=MAKER_USERNAME, definition='rfp-response/v1', key=KEY)
    sources = dict(case.evidence.filter(source__in=SOURCES.values()).values_list('source', 'pk'))
    source_ids = {key: sources[value] for key, value in SOURCES.items()}
    submission = RFPSubmission.objects.get(portal_receipt__evidence_id=source_ids['portal'])
    pending = RFPOutcome.objects.get(submission=submission, result='pending', evidence_id=source_ids['pending'], actor=recorder)
    debrief = MeetingVersion.objects.get(meeting__case=case, evidence_id=source_ids['debrief'])
    return {'case': str(case.pk), 'work': work.pk, 'submission': submission.pk, 'initial_pending': pending.pk,
        'debrief': debrief.pk, 'maker': work.actor_id, 'recorder': recorder.pk, 'receipt': submission.portal_receipt.pk,
        'portal_reference': PORTAL_REFERENCE, 'sources': source_ids, 'reason_names': REASON_NAMES,
        'path': reverse('factory_work_response', args=[work.pk]),
        'settings': reverse('factory_rfp_outcome_configuration', args=[case.pk]) + '#loss-reasons',
        'existing_work_preserved': not created}


def run():
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID'), os.getenv('PSL_COMMERCIAL_LOSS_FIXTURE')) != (
            'design-acceptance', PROJECT, '1'):
        raise RuntimeError('The Railway acceptance project and explicit Commercial loss fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The preview sample database must be explicitly configured.')
    recorder = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
    print('PSL_COMMERCIAL_LOSS_FIXTURE=' + json.dumps(prepare(recorder)), flush=True)
