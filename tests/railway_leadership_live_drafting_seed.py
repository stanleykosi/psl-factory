"""Expose one native source-cited monthly drafting claim in a separate preview case."""
import json
import os
from time import sleep
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.core.models import Audit, Case
from apps.core.services import event
from apps.documents.models import Publication
from apps.pmo import leadership_reporting as reports
from apps.workflows import factory, factory_leadership as flow
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork, HumanTask
from tests import railway_leadership_scope_seed as scoped
from tests.helpers import rev


GUARD = 'PSL_LEADERSHIP_LIVE_DRAFTING_WALKTHROUGH'
TENANT = 'design-leadership-live-drafting-walkthrough'
HOME_ID = uuid5(NAMESPACE_URL, TENANT + '/home')
SECOND_ID = uuid5(NAMESPACE_URL, TENANT + '/contributor')
TITLE = 'SAMPLE monthly leadership report live drafting'
SECOND_TITLE = 'SAMPLE authorised project for live monthly drafting'
KEY = 'SAMPLE-LEADERSHIP-LIVE-DRAFTING'
STARTER = 'sample-leadership-live-drafting-starter'
SPONSOR = 'sample-leadership-live-drafting-preparer'
REVIEWER = 'sample-leadership-live-drafting-reviewer'
PREPARED = 'sample.leadership_live_drafting_prepared'
OBSERVATION = 'sample.leadership_live_drafting_requested'
STEP = 'ACT09'
WINDOW_SECONDS = 30


def trial_reader():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
            scoped.PREVIEW_PROJECT, 'design-acceptance', '1'):
        raise RuntimeError('The exact Railway preview and live leadership drafting fixture guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('Use the explicitly configured isolated preview sample database.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def pinned(reader, work_id=None, *, lock=False):
    candidates = FactoryWork.objects.select_related('case', 'actor', 'source_head').filter(
        case_id=HOME_ID, case__tenant=TENANT, case__title=TITLE, case__kind='project', case__synthetic=True,
        actor__username=STARTER, actor__is_active=True, source_head__case_id=HOME_ID,
        key=KEY, definition=flow.DEFINITION,
    )
    if lock:
        candidates = candidates.select_for_update(of=('self',))
    work = candidates.get() if work_id is None else candidates.get(pk=work_id)
    marker = Audit.objects.get(case=work.case, action=PREPARED, actor=work.actor)
    if marker.data != {'work': work.pk, 'source': work.source_head_id, 'sha256': work.source_head.sha256, 'reader': reader.pk}:
        raise RuntimeError('Match the exact prepared monthly drafting source and separate trial reader.')
    factory.access(reader, work.case, 'factory.read', flow.DEFINITION)
    manifest = flow.source(work, reader)['manifest']['project_scope']
    if (manifest['record_counts'] != {'meetings': 2}
            or {item['case'] for item in manifest['projects']} != {str(HOME_ID), str(SECOND_ID)}):
        raise RuntimeError('Preserve the two exact authorised projects and two current meeting records.')
    return work


@transaction.atomic
def prepare():
    reader = trial_reader()
    home, created = Case.objects.get_or_create(pk=HOME_ID, defaults={
        'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True,
    })
    if created:
        Case.objects.create(pk=SECOND_ID, tenant=TENANT, title=SECOND_TITLE, kind='project', synthetic=True)
    cases = Case.objects.filter(tenant=TENANT)
    expected = {(HOME_ID, TITLE, 'project', True), (SECOND_ID, SECOND_TITLE, 'project', True)}
    if set(cases.values_list('pk', 'title', 'kind', 'synthetic')) != expected:
        raise RuntimeError('Use the two separate synthetic monthly drafting workspaces.')
    if created:
        second = cases.get(pk=SECOND_ID)
        operator = get_user_model().objects.create_user(STARTER)
        setup = scoped.create(operator, home, second, sponsor_username=SPONSOR, reviewer_username=REVIEWER)
        scoped.grant(home, reader, (*scoped.READ, 'factory.read'))
        scoped.grant(second, reader, scoped.READ)
        inputs = {
            'kind': scoped.KIND, 'audience': 'internal', 'template_id': setup.data['template'], 'content_id': None,
            'start_at': setup.data['start'], 'end_at': setup.data['end'],
            'selections': {key: [] for key in reports.DOMAINS},
            'scope': {'domains': scoped.AREAS},
        }
        work = flow.start(operator, home.pk, KEY, inputs, TITLE, rev(home))
        if not factory.run_once(work.pk) or not work.activities.filter(kind='ACT04', status='succeeded').exists():
            raise RuntimeError('The fixture must stop after its native source investigation.')
        event(operator, home, PREPARED, work=work.pk, source=work.source_head_id, sha256=work.source_head.sha256,
              reader=reader.pk)
    work = pinned(reader)
    return {'case': str(HOME_ID), 'contributor': str(SECOND_ID), 'work': work.pk, 'source': work.source_head_id,
            'step': STEP, 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created}


class ObserveDrafting(SyntheticFactoryCoordinator):
    def __init__(self, work_id):
        self.work_id = work_id

    def choose(self, context):
        if context['eligible'] != [STEP]:
            raise RuntimeError('The exact native monthly drafting step must remain eligible.')
        print(f'PSL_LEADERSHIP_LIVE_DRAFTING={self.work_id}:{STEP}', flush=True)
        sleep(WINDOW_SECONDS)
        return super().choose(context)


def observe(work_id):
    reader = trial_reader()
    if type(work_id) is not int or not 0 < work_id <= 9223372036854775807:
        raise RuntimeError('Supply the exact prepared monthly drafting work ID.')
    with transaction.atomic():
        work = pinned(reader, work_id, lock=True)
        if (work.cancel_requested or work.lease_until or (work.plan_revision, work.fence) != (1, 1)
                or Audit.objects.filter(case=work.case, action=OBSERVATION, data__work=work.pk).exists()
                or FactoryProgress.objects.filter(work=work).exists() or flow.document(work)
                or FactoryAttempt.objects.filter(activity__work=work, activity__kind=STEP).exists()):
            raise RuntimeError('Select the fresh specimen after investigation and before its first drafting claim.')
        _, profile = factory.profile(work)
        eligible, _ = flow.eligible(work, profile, *flow.snapshot(work, profile))
        if (eligible != [STEP] or profile['provider'] != 'synthetic_factory_v1'
                or profile['lease_seconds'] < 2 * WINDOW_SECONDS):
            raise RuntimeError('The exact current native drafting step and bounded local synthetic worker are required.')
        event(work.actor, work.case, OBSERVATION, work=work.pk, source=work.source_head_id, step=STEP)
    if not factory.run_once(work.pk, provider=ObserveDrafting(work.pk)):
        raise RuntimeError('The original native monthly drafting step did not settle.')
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind=STEP, phase='observed')
    report = flow.document(work)
    if (not report or attempt.result['document_version'] != report.pk or report.reviews.exists()
            or Publication.objects.filter(factory_work=work).exists()):
        raise RuntimeError('Stop at the exact source-cited native report and its unclaimed review.')
    review = HumanTask.objects.get(case=work.case, version=report, status='open', required_role='PMO Lead', claimed_by=None)
    return {'work': work.pk, 'step': STEP, 'attempt': attempt.pk, 'report': report.pk, 'review': review.pk}


def run():
    print(GUARD + '=' + json.dumps(prepare()), flush=True)
