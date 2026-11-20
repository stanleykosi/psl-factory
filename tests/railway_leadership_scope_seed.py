"""Prepare the guarded two-project leadership setup for the native browser."""

import json
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.core.services import add_evidence, event
from apps.documents.controlled import register_template
from apps.documents.models import Document, Publication, Template
from apps.identity.models import Grant
from apps.pmo import leadership_project_scope as coverage
from apps.pmo import leadership_reporting as reports
from apps.pmo.meetings import record_meeting
from apps.pmo.models import MeetingVersion
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.role_assignments import draft as draft_roles
from apps.policy.services import transition
from apps.workflows import factory_leadership as flow
from apps.workflows.models import FactoryWork, HumanTask
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.railway_batch_walkthrough_seed import PREVIEW_PROJECT


GUARD = 'PSL_LEADERSHIP_SCOPE_WALKTHROUGH'
TENANT = 'design-leadership-scope-walkthrough'
HOME_TITLE = 'SAMPLE leadership report workspace'
SECOND_TITLE = 'SAMPLE project contributing to the leadership report'
HOME_ID = uuid5(NAMESPACE_URL, TENANT + '/home')
SECOND_ID = uuid5(NAMESPACE_URL, TENANT + '/contributor')
MARKER = 'sample.leadership_scope_prepared'
TEMPLATE = 'SAMPLE monthly leadership report'
REFERENCE = 'SAMPLE leadership report across two authorised projects'
KIND = 'monthly_executive'
AREAS = ['meetings']
SPONSOR = 'sample-leadership-scope-preparer'
REVIEWER = 'sample-leadership-scope-reviewer'

READ = ('case.read', 'report.read', 'meeting.read')
SOURCE = ('meeting.record', 'meeting.participate', 'evidence.add')
START = ('factory.read', 'factory.start', 'factory.execute', 'evidence.add')
PREPARE = ('policy.configure', 'policy.activate', 'factory.execute', 'report.draft',
           'document.template', 'document.draft', 'document.request_review', 'document.publish')


def current_operator():
    if (os.getenv('RAILWAY_PROJECT_ID'), os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv(GUARD)) != (
        PREVIEW_PROJECT, 'design-acceptance', '1',
    ):
        raise RuntimeError('The exact Railway acceptance environment and leadership sample guard are required.')
    database = os.getenv('PGDATABASE', '')
    if not database or database.startswith('test_'):
        raise RuntimeError('The isolated preview database must be explicitly configured.')
    return get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)


def grant(case, actor, actions):
    Grant.objects.bulk_create([Grant(case=case, user=actor, action=action) for action in dict.fromkeys(actions)])


def activate(actor, configuration):
    transition(actor, configuration.pk, 'validated')
    transition(actor, configuration.pk, 'active')
    return configuration


def create(operator, home, second):
    users = get_user_model().objects
    sponsor = users.create_user(SPONSOR, first_name='Sample report preparer')
    reviewer = users.create_user(REVIEWER, first_name='Sample PMO reviewer')
    grant(home, sponsor, (*READ, *SOURCE, *PREPARE))
    grant(second, sponsor, (*READ, *SOURCE))
    grant(home, operator, (*READ, *START))
    grant(second, operator, READ)
    grant(home, reviewer, (*READ, 'factory.read', 'document.review_controlled'))
    grant(second, reviewer, READ)

    end = timezone.localtime().replace(second=0, microsecond=0)
    start = end - timedelta(days=7)
    proof = add_evidence(sponsor, home.pk, 'policy_decision',
                         'Fictional approval for this two-project leadership sample only.',
                         'synthetic:leadership-walkthrough-coverage')
    scope = activate(sponsor, draft_operator_policy(
        sponsor, home.pk, coverage.COMPONENT, {'enabled': True}, proof.pk, timezone.now(),
    ))
    activate(sponsor, draft_roles(sponsor, home.pk, [{'role': 'PMO Lead', 'user_id': reviewer.pk}],
                                  proof.pk, timezone.now()))
    activate(sponsor, draft_operator_policy(sponsor, home.pk, reports.REVIEW_COMPONENT, {'role': 'PMO Lead'},
                                            proof.pk, timezone.now()))
    fields = ['executive_summary', *reports.THEMES[KIND]]
    template = register_template(sponsor, home.pk, TEMPLATE, {
        'document_type': 'status_report', 'required_fields': fields, 'internal_review_required': True,
        'audience_fields': {'internal': fields},
    }, proof.pk, rev(home))
    artifact(sponsor, home, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1',
             {'template_ids': [template.pk], 'repository': 'internal-versioned', 'retention_days': 30}, proof)
    profile = json.loads(Path('fixtures/factory-leadership.json').read_text())
    profile.pop('classification')
    profile.update(preparer_id=sponsor.pk, executor_id=sponsor.pk)
    activate(sponsor, draft_operator_policy(sponsor, home.pk, 'OPS.factory_leadership_execution', profile,
                                            proof.pk, timezone.now()))

    observations = []
    for project, reference, when in ((home, 'SAMPLE-LEADERSHIP-HOME', end - timedelta(hours=2)),
                                     (second, 'SAMPLE-LEADERSHIP-CONTRIBUTOR', end - timedelta(hours=1))):
        source = add_evidence(sponsor, project.pk, 'meeting_notes', 'Fictional progress meeting with separate follow-up.',
                              'synthetic:scoped-leadership-meeting')
        meeting = record_meeting(sponsor, project.pk, reference, 'status', when, 'Review fictional progress',
                                 'The sample team identified follow-up and kept wider outcomes unknown.',
                                 [sponsor.pk], [], source.pk, rev(project))
        observations.append({'case': str(project.pk), 'meeting': meeting.meeting_id,
                             'version': meeting.pk, 'evidence': source.pk})
    if (FactoryWork.objects.filter(case=home).exists() or Document.objects.filter(case=home).exists()
            or HumanTask.objects.filter(case=home).exists() or Publication.objects.filter(version__document__case=home).exists()):
        raise RuntimeError('The leadership walkthrough must stop before work, report, review or delivery.')
    return event(sponsor, home, MARKER, operator=operator.pk, reviewer=reviewer.pk, configuration=scope.pk,
                 proof=proof.pk, template=template.pk, start=start.isoformat(), end=end.isoformat(),
                 observations=observations)


def checked_scope(operator, home, marker):
    data = marker.data
    if data['operator'] != operator.pk or marker.actor.username != SPONSOR:
        raise RuntimeError('Preserve the original isolated leadership sample.')
    if coverage.current_rule(home).pk != data['configuration']:
        raise RuntimeError('The exact reviewed synthetic leadership coverage changed.')
    if not Template.objects.filter(case=home, pk=data['template'], name=TEMPLATE, evidence_id=data['proof'],
                                   created_by=marker.actor, definition__internal_review_required=True).exists():
        raise RuntimeError('The exact retained monthly template is required.')
    for row in data['observations']:
        if not MeetingVersion.objects.filter(pk=row['version'], meeting_id=row['meeting'], meeting__case_id=row['case'],
                                             meeting__current_id=row['version'], evidence_id=row['evidence']).exists():
            raise RuntimeError('The checked native sample meeting changed.')
    inputs = {'kind': KIND, 'audience': 'internal', 'template_id': data['template'], 'content_id': None,
              'start_at': data['start'], 'end_at': data['end'], 'selections': {key: [] for key in reports.DOMAINS},
              'scope': {'mode': coverage.MODE, 'domains': AREAS, 'configuration': data['configuration'], 'actor': operator.pk}}
    manifest = coverage.snapshot(home, inputs)
    coverage.access(operator, home, manifest)
    actual = {project['case']: project['inventory']['meetings'] for project in manifest['project_scope']['projects']}
    exact = {row['case']: [[row['meeting'], row['version'], row['evidence']]] for row in data['observations']}
    if actual != exact or set(exact) != {str(HOME_ID), str(SECOND_ID)}:
        raise RuntimeError('The fixture must retain exactly two native authorized projects and their source versions.')


@transaction.atomic
def prepare():
    operator = current_operator()
    home, created = Case.objects.get_or_create(pk=HOME_ID, defaults={
        'tenant': TENANT, 'title': HOME_TITLE, 'kind': 'project', 'synthetic': True,
    })
    if created:
        if Case.objects.filter(tenant=TENANT).exclude(pk=home.pk).exists():
            raise RuntimeError('The isolated leadership sample tenant already contains other records.')
        Case.objects.create(pk=SECOND_ID, tenant=TENANT, title=SECOND_TITLE, kind='project', synthetic=True)
    expected = {(HOME_ID, HOME_TITLE), (SECOND_ID, SECOND_TITLE)}
    subjects = Case.objects.filter(tenant=TENANT, kind='project', synthetic=True)
    if set(subjects.values_list('pk', 'title')) != expected or Case.objects.filter(tenant=TENANT).count() != 2:
        raise RuntimeError('The exact two synthetic sample projects are required.')
    marker = create(operator, home, subjects.get(pk=SECOND_ID)) if created else Audit.objects.get(case=home, action=MARKER)
    checked_scope(operator, home, marker)
    work = FactoryWork.objects.filter(case=home, actor=operator, definition=flow.DEFINITION,
                                      request__reference=REFERENCE).values_list('pk', flat=True).first()
    path = reverse('factory_create') + '?' + urlencode({'definition': flow.DEFINITION, 'kind': KIND,
        'case': HOME_ID, 'scope': coverage.MODE})
    return {**marker.data, 'home': str(HOME_ID), 'contributor': str(SECOND_ID), 'template_name': TEMPLATE,
            'reference': REFERENCE, 'areas': AREAS, 'path': path, 'existing_work': work, 'preserved': not created}


def run():
    print(GUARD + '=' + json.dumps(prepare()), flush=True)
