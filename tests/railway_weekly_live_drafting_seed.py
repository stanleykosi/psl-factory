"""Observe an isolated, source-cited weekly drafting claim through native settlement."""
import json
import os
from datetime import timedelta
from time import sleep
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.agents.factory_catalogue import SyntheticFactoryCoordinator
from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.controlled import register_template
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.pmo.models import MinutesReportBinding
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from apps.workflows import factory, factory_reporting as weekly
from apps.workflows.models import FactoryAttempt, FactoryProgress, FactoryWork, HumanTask
from tests import railway_weekly_return_walkthrough_seed as prior
from tests.document_helpers import artifact
from tests.helpers import rev


GUARD = 'PSL_WEEKLY_LIVE_DRAFTING_WALKTHROUGH'
TENANT = 'design-weekly-live-drafting-walkthrough'
TITLE = 'SAMPLE weekly report with a live assembly step'
CASE_ID = uuid5(NAMESPACE_URL, f'psl-factory:{TENANT}')
KEY = 'SAMPLE-WEEKLY-LIVE-DRAFTING'
TEMPLATE = 'Sample weekly assembly template'
MAKER = 'sample-weekly-live-drafting-maker'
REVIEWER = 'sample-weekly-live-drafting-reviewer'
SPONSOR = 'sample-weekly-live-drafting-sponsor'
PREPARED = 'sample.weekly_live_drafting_prepared'
OBSERVATION = 'sample.weekly_live_drafting_requested'
STEP = 'ACT09'
WINDOW = 50


def trial_reader():
    actual = os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)
    database = os.getenv('PGDATABASE', '')
    if actual != (prior.PREVIEW_PROJECT, 'design-acceptance', '1') or not database or database.startswith('test_'):
        raise RuntimeError('The isolated Railway preview and weekly live drafting fixture guard are required.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def pinned(reader, *, work_id=None, lock=False):
    candidates = FactoryWork.objects.select_related('case', 'actor', 'source_head').filter(
        case_id=CASE_ID, case__tenant=TENANT, case__title=TITLE, case__kind='project', case__synthetic=True,
        actor__username=MAKER, actor__is_active=True, source_head__case_id=CASE_ID, key=KEY, definition=weekly.DEFINITION,
    )
    if lock:
        candidates = candidates.select_for_update(of=('self',))
    work = candidates.get() if work_id is None else candidates.get(pk=work_id)
    marker = Audit.objects.get(case=work.case, actor=work.actor, action=PREPARED)
    if any(marker.data[key] != value for key, value in {
        'work': work.pk, 'source': work.source_head_id, 'sha256': work.source_head.sha256, 'reader': reader.pk,
    }.items()):
        raise RuntimeError('Match the original weekly source, work and independent Trial reader.')
    factory.access(reader, work.case, 'factory.read', weekly.DEFINITION)
    data = weekly.source(work, reader)
    if (data['inputs'] != marker.data['inputs'] or len(data['manifest']['meetings']) != 4
            or any(data['manifest'][area] for area in ('actions', 'milestones', 'issues', 'changes'))):
        raise RuntimeError('Preserve the selected week, template and its four exact same-case source records.')
    return work, marker


@transaction.atomic
def prepare():
    reader = trial_reader()
    case, created = Case.objects.get_or_create(pk=CASE_ID, defaults={'tenant': TENANT, 'title': TITLE, 'kind': 'project', 'synthetic': True})
    if (case.tenant, case.title, case.kind, case.synthetic) != (TENANT, TITLE, 'project', True):
        raise RuntimeError('Preserve the unrelated workspace occupying the weekly drafting specimen.')
    if created:
        users = get_user_model().objects
        sponsor = users.create_user(SPONSOR)
        maker = users.create_user(MAKER)
        reviewer = users.create_user(REVIEWER)
        Grant.objects.bulk_create([Grant(case=case, user=user, action=action) for user, actions in (
            (sponsor, prior.SPONSOR), (maker, prior.MAKER), (reviewer, prior.REVIEWER), (reader, prior.READ),
        ) for action in actions])
        rule_proof = add_evidence(sponsor, case.pk, 'policy_decision',
            'Fictional template and separate human reviewer for weekly draft observation only.', 'synthetic:weekly-live-drafting')
        role = draft_roles(sponsor, case.pk, [{'role': 'PMO Lead', 'user_id': reviewer.pk}], rule_proof.pk, timezone.now())
        transition(sponsor, role.pk, 'validated')
        transition(sponsor, role.pk, 'active')
        fields = ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']
        template = register_template(sponsor, case.pk, TEMPLATE, {
            'document_type': 'status_report', 'required_fields': fields, 'audience_fields': {'client': fields},
        }, rule_proof.pk, rev(case))
        artifact(sponsor, case, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
                 {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, rule_proof)
        profile = json.loads((settings.BASE_DIR / 'fixtures/factory-reporting.json').read_text(encoding='utf-8'))
        profile.pop('classification')
        profile.update(preparer_id=maker.pk, executor_id=None)
        config = draft_operator_policy(sponsor, case.pk, 'OPS.factory_reporting_execution', profile, rule_proof.pk, timezone.now())
        transition(sponsor, config.pk, 'validated')
        transition(sponsor, config.pk, 'active')
        end = timezone.now().replace(microsecond=0)
        start = end - timedelta(days=7)
        sections = {key: {'text': text, 'evidence_ids': [
            prior._meeting_source(sponsor, case, f'assembly-{key}', text, end - timedelta(hours=2)).pk,
        ]} for key, text in prior.INITIAL.items()}
        content = add_evidence(maker, case.pk, 'agent_private_report_content',
            json.dumps({'protocol': 'pmo-weekly-client-content/v1', 'sections': sections}, sort_keys=True),
            'synthetic:weekly-live-drafting-human-narrative')
        inputs = {'start_at': start.isoformat(), 'end_at': end.isoformat(), 'template_id': template.pk, 'content_id': content.pk}
        work = weekly.start(maker, case.pk, KEY, inputs, TITLE, rev(case))
        if not factory.run_once(work.pk) or not work.activities.filter(kind='ACT04', status='succeeded').exists():
            raise RuntimeError('Stop after the current native source investigation, before drafting.')
        event(maker, case, PREPARED, work=work.pk, source=work.source_head_id, sha256=work.source_head.sha256,
              reader=reader.pk, reviewer=reviewer.pk, inputs=inputs, sections=sections)
    work, marker = pinned(reader)
    return {**marker.data, 'case': str(case.pk), 'path': reverse('factory_detail', args=[work.pk]), 'preserved': not created}


class ObserveAssembly(SyntheticFactoryCoordinator):
    def __init__(self, work_id):
        self.work_id = work_id

    def choose(self, context):
        if context['eligible'] != [STEP]:
            raise RuntimeError('The current exact weekly drafting step must remain eligible.')
        print(f'{GUARD}_CLAIM={self.work_id}:{STEP}', flush=True)
        sleep(WINDOW)
        return super().choose(context)


def observe(work_id):
    reader = trial_reader()
    if type(work_id) is not int or not 0 < work_id <= 9223372036854775807:
        raise RuntimeError('Supply the exact weekly drafting work ID.')
    with transaction.atomic():
        work, marker = pinned(reader, work_id=work_id, lock=True)
        if (work.cancel_requested or work.lease_until or (work.plan_revision, work.fence) != (1, 1)
                or weekly.document(work) or FactoryProgress.objects.filter(work=work).exists()
                or FactoryAttempt.objects.filter(activity__work=work, activity__kind=STEP).exists()
                or Audit.objects.filter(case=work.case, action=OBSERVATION, data__work=work.pk).exists()):
            raise RuntimeError('Choose the fresh weekly specimen after its investigation and before its first drafting claim.')
        _, profile = factory.profile(work)
        eligible, _ = weekly.eligible(work, profile, *weekly.snapshot(work, profile))
        if (eligible != [STEP] or profile['provider'] != 'synthetic_factory_v1' or profile['lease_seconds'] < 2 * WINDOW
                or profile['preparer_id'] != work.actor_id or profile['executor_id'] is not None):
            raise RuntimeError('A bounded synthetic drafting claim with no publisher is required.')
        event(work.actor, work.case, OBSERVATION, work=work.pk, source=work.source_head_id, step=STEP)
    if not factory.run_once(work.pk, provider=ObserveAssembly(work.pk)):
        raise RuntimeError('The current native weekly drafting claim did not settle.')
    attempt = FactoryAttempt.objects.get(activity__work=work, activity__kind=STEP, phase='observed')
    report = weekly.document(work)
    if (not report or attempt.result['document_version'] != report.pk or report.reviews.exists()
            or Publication.objects.filter(factory_work=work).exists()
            or PublicationReceipt.objects.filter(publication__factory_work=work).exists()):
        raise RuntimeError('Stop at the exact native weekly draft awaiting separate human review.')
    binding = MinutesReportBinding.objects.get(version=report)
    if (binding.manifest != weekly.source(work, reader)['manifest']
            or any(report.fields[key]['text'] != part['text'] for key, part in marker.data['sections'].items())):
        raise RuntimeError('The draft must retain the four selected statements and their source inventory.')
    review = HumanTask.objects.get(case=work.case, version=report, status='open', required_role='PMO Lead', claimed_by=None)
    return {'work': work.pk, 'step': STEP, 'attempt': attempt.pk, 'report': report.pk, 'review': review.pk}


def run():
    print(GUARD + '=' + json.dumps(prepare(), sort_keys=True), flush=True)


def run_observation(work_id):
    print(GUARD + '_SETTLED=' + json.dumps(observe(work_id), sort_keys=True), flush=True)
