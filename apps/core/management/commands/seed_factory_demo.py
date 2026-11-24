import json
from datetime import timedelta
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import register_template
from apps.documents.models import Template
from apps.identity.models import Grant
from apps.pmo.meetings import record_meeting
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.registry import components
from apps.policy.services import register_reference, resolve, save_draft, transition
from apps.workflows import factory_reporting
from apps.workflows.models import FactoryWork
from .seed_demo import ACTIONS

TEMPLATE = 'Synthetic client weekly report'
KEY = 'SYNTHETIC-WEEKLY-REPORT-1'
PREPARER = 'studio-demo-report-preparer'
PREPARER_ACTIONS = ['case.read', 'report.read', 'factory.execute', 'report.draft', 'document.draft',
                    'document.request_review', 'evidence.add', 'meeting.read', 'issue.read', 'change.read',
                    'delivery.read', 'rfp.read']
FIELDS = ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']


class Command(BaseCommand):
    help = ('Add a synthetic weekly client report that waits at PMO Lead review. Synthetic project only; '
            'values are fixtures, not business policy.')

    def add_arguments(self, parser):
        parser.add_argument('--username', default='studio-demo')

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(username=options['username'])
        case = Case.objects.get(tenant='synthetic-demo', synthetic=True, kind='project',
                                grant__user=actor, grant__action='case.read')
        if not case.synthetic or case.tenant != 'synthetic-demo':
            raise CommandError('This fixture runs only on a synthetic demo project')
        if (Template.objects.filter(case=case, name=TEMPLATE).exists() or get_user_model().objects.filter(username=PREPARER).exists()
                or FactoryWork.objects.filter(case=case, key=KEY).exists()):
            raise CommandError('Factory demo exists; its history is preserved')
        work_id = self.prepare(actor, case)
        # Workers run after the fixture commits, as in the other demos.
        call_command('work_factory', work=[work_id], until_wait=True, stdout=self.stdout)
        call_command('work_reports', stdout=self.stdout)
        work = FactoryWork.objects.get(pk=work_id)
        self.stdout.write(f'Case {case.pk}; weekly report work {work.pk}: {work.status}')

    @transaction.atomic
    def prepare(self, actor, case):
        for action in ACTIONS:
            Grant.objects.get_or_create(case=case, user=actor, action=action)
        preparer = get_user_model().objects.create_user(PREPARER)
        for action in PREPARER_ACTIONS:
            Grant.objects.create(case=case, user=preparer, action=action)

        def revision():
            case.refresh_from_db()
            return case.revision

        def activate(component, value):
            config = save_draft(actor, case.pk, {
                'slot_id': components()[component]['parent_decision_id'], 'component_id': component,
                'component_schema_ref': components()[component]['schema_ref'], 'schema_version': '1',
                'subject_scope': {'kind': 'project', 'ref': str(case.pk)}, 'policy_revision': 1, 'lifecycle': 'draft',
                'effective_from': (timezone.now() - timedelta(minutes=1)).isoformat(), 'effective_until': None,
                'evidence_refs': [f'evidence:{owner.pk}'], 'human_decision_ref': f'evidence:{owner.pk}',
                'implementation_id': 'psl.reference-validation', 'implementation_version': '1',
                'reviewed_implementation_ref': 'code:apps/policy/services.py#reference-validation-v1',
                'fixture_scope': 'synthetic_test', 'value': value})
            transition(actor, config.pk, 'validated')
            transition(actor, config.pk, 'active')

        owner = add_evidence(actor, case.pk, 'policy_decision',
                             'Synthetic weekly report configuration fixture. These values are not operational business policy.',
                             'synthetic:weekly-report-owner')
        if resolve('D05.role_principal_assignments', case).status != 'ACTIVE':
            refs = []
            for index, role in enumerate(['PM', 'Head of PMO', 'CEO', 'PMO Lead']):
                ref = f'factory-demo:role:{index}'
                register_reference(actor, case.pk, ref, 'schema:psl/role-assignment/v1',
                                   {'role': role, 'user_id': actor.pk}, owner.pk)
                refs.append(ref)
            activate('D05.role_principal_assignments', refs)
        if resolve('D11.recipient_grant_refs', case).status != 'ACTIVE':
            recipient = register_reference(actor, case.pk, 'factory-demo:recipient', 'schema:psl/document-recipient/v1',
                                           {'audience': 'client', 'user_id': actor.pk}, owner.pk)
            activate('D11.recipient_grant_refs', [recipient.ref])
        template = register_template(actor, case.pk, TEMPLATE, {
            'document_type': 'status_report', 'required_fields': FIELDS, 'audience_fields': {'client': FIELDS}},
            owner.pk, revision())
        storage = register_reference(actor, case.pk, 'factory-demo:storage', 'schema:psl/document-storage/v1', {
            'template_ids': list(Template.objects.filter(case=case).values_list('pk', flat=True)),
            'repository': 'internal-versioned', 'retention_days': 30}, owner.pk)
        activate('D11.template_storage_retention_rules', {
            'artifact_ref': storage.ref, 'artifact_version': storage.version, 'sha256': storage.sha256,
            'schema_ref': storage.schema_ref})
        profile = json.loads(Path('fixtures/factory-reporting.json').read_text())
        profile.pop('classification')
        profile.update(preparer_id=preparer.pk, executor_id=actor.pk)
        config = draft_operator_policy(actor, case.pk, 'OPS.factory_reporting_execution', profile,
                                       owner.pk, timezone.now() - timedelta(minutes=1))
        transition(actor, config.pk, 'validated')
        transition(actor, config.pk, 'active')
        now = timezone.now()
        notes = add_evidence(actor, case.pk, 'meeting_notes',
                             'Synthetic delivery status review. Progress and next steps were discussed.',
                             'synthetic:weekly-report-meeting')
        record_meeting(actor, case.pk, 'SYNTHETIC-WEEKLY-001', 'status', now - timedelta(hours=1),
                       'Review delivery progress', 'The synthetic team reviewed progress and next steps.',
                       [actor.pk], [{'text': 'Delivery progress was reviewed.', 'evidence_id': notes.pk}],
                       notes.pk, revision())
        sections = {
            'status': 'Synthetic delivery status is progressing as discussed in the review.',
            'risks': 'Synthetic example: no client-facing risk has been confirmed.',
            'timeline': 'Synthetic example: milestone dates are unchanged by this review.',
            'next_steps': 'Synthetic example: the project owner confirms the next review.',
        }
        content = add_evidence(actor, case.pk, 'agent_private_report_content', json.dumps({
            'protocol': 'pmo-weekly-client-content/v1',
            'sections': {topic: {'text': text, 'evidence_ids': [notes.pk]} for topic, text in sections.items()}}),
            'synthetic:human-authored-client-report')
        work = factory_reporting.start(
            actor, case_id=case.pk, key=KEY, expected=revision(), reference='Synthetic weekly client report',
            inputs={'template_id': template.pk, 'content_id': content.pk,
                    'start_at': (now - timedelta(days=7)).isoformat(), 'end_at': now.isoformat()})
        return work.pk
