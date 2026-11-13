"""Run native next-step checks only on the named synthetic Railway case."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.agents.models import AgentJob
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents import validation
from apps.finance import recognition
from apps.identity.models import Grant
from apps.pmo import engagement, gates, issues, meetings, planning
from apps.pmo.models import GateVerification, IssueState, MeetingVersion
from apps.policy import role_assignments
from apps.policy.engagement_validators import ASSIGN, REGISTER
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import resolve, transition
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verify native outcomes and remaining holds in the isolated agent trial case.'

    def handle(self, *args, **options):
        case = Case.objects.filter(pk='919b157e-f212-4a3e-8cf2-2082a72128e3',
                                   tenant='psl-agent-trial', synthetic=True).first()
        actor = get_user_model().objects.filter(username='psl-agent-trial', is_active=True,
                                                 is_superuser=False).first()
        if not case or not actor:
            raise CommandError('Exact synthetic case and operator required.')
        jobs = AgentJob.objects.filter(upload__case=case, actor=actor, upload__name='acceptance.txt',
                                       status='reviewed', result__has_key='workflow_record')
        if set(jobs.values_list('role', flat=True)) != {f'A{i:02}' for i in range(1, 9)}:
            raise CommandError('All eight reviewed handoffs must exist before the trial.')
        for action in ('engagement.assign', 'issue.work', 'planning.route', 'planning.prepare',
                       'approval.request', 'approval.read', 'recognition.attest', 'action.manage',
                       'action.own', 'action.work', 'pmo.gate_verify', 'validation.review',
                       'engagement.register', 'engagement.export', 'policy.configure', 'policy.activate'):
            Grant.objects.get_or_create(case=case, user=actor, action=action)
        for job in jobs.order_by('role'):
            case.refresh_from_db()
            try:
                with transaction.atomic():
                    result = self.advance(actor, case, job)
            except (ValidationError, PermissionDenied) as exc:
                result = 'HOLD ' + str(exc)[:280]
            self.stdout.write(f'Agent outcome {job.role}: {result}')

    def advance(self, actor, case, job):
        pk = job.result['workflow_record']
        evidence = job.result['reviewed_evidence']
        key = f'hosted-agent-outcome-{job.pk}'
        role = job.role
        if role == 'A01':
            capture = engagement.Record.objects.get(pk=pk, case=case)
            if resolve(ASSIGN, case).status == 'MISSING':
                self.configure_intake(actor, case)
            engagement.assign(actor, case.pk, actor.pk, 'PMO Lead', capture.evidence_id, key)
            plan = case.evidence.filter(kind='plan', source='synthetic:agent-outcomes').first()
            if not plan:
                plan = add_evidence(actor, case.pk, 'plan', 'Synthetic pre-signature project plan.',
                                    'synthetic:agent-outcomes')
            registration = engagement.register(actor, case.pk, 'AGENT-TRIAL-1', 'PMO Lead',
                                               capture.evidence_id, plan.pk, key + '-registration')
            export = engagement.export_registration(actor, case.pk, key + '-export')
            return f'PASS project registered {registration.pk}; export evidence {export.pk}'
        if role == 'A02':
            source = validation.DiscoverySource.objects.get(pk=pk, case=case, evidence_id=evidence)
            validation.source_current(source)
            return f'PASS exact current validation source {source.pk}'
        if role == 'A03':
            initial = IssueState.objects.get(pk=pk, issue__case=case, evidence_id=evidence)
            state = initial.issue.current
            if not state.acknowledged_at:
                state = issues.update_issue(actor, case.pk, initial.issue_id, state.pk, 'acknowledge',
                                            evidence, 'Synthetic owner acknowledged the issue.', case.revision)
            return f'PASS owner acknowledgement {state.pk}; resolution and closure remain pending'
        if role == 'A04':
            requests = planning.open_requests(actor, case.pk, pk)
            if set(requests['requests']) != {'scope', 'estimates'}:
                raise CommandError('Planning did not open both department requests.')
            return f"PASS department requests {requests['requests']}; readiness awaits evidence"
        if role == 'A05':
            recognition.record(actor, case.pk, pk, 'attest', key, evidence,
                               'Synthetic progress evidence trial.', case.revision)
            return 'PM attestation recorded'
        if role == 'A06':
            meeting = MeetingVersion.objects.get(pk=pk, meeting__case=case, evidence_id=evidence)
            item = meetings.ActionItem.objects.filter(case=case, reference=key).first()
            if not item:
                item = meetings.create_action(actor, case.pk, key, 'Review the synthetic meeting summary',
                                              actor.pk, None, evidence, 'Synthetic meeting follow-up',
                                              case.revision, meeting_id=meeting.meeting_id)
                case.refresh_from_db()
            if item.current.status != 'completed':
                meetings.change_action(actor, case.pk, item.pk, 'complete', evidence,
                                       'Synthetic follow-up reviewed.', case.revision, item.current.number)
            item.refresh_from_db()
            if item.current.status != 'completed':
                raise CommandError('Meeting action did not complete.')
            return f'PASS meeting follow-up {item.pk} completed'
        if role == 'A07':
            verified = GateVerification.objects.filter(record_id=pk, record__candidate__case=case,
                                                       adapter='synthetic-gate-source-v1').first()
            verified = verified or gates.verify_gate(actor, case.pk, pk, case.revision)
            return f"PASS synthetic gate receipt {verified.pk} ({verified.result['decision']}); release remains separate"
        validation.review(actor, case.pk, pk, 'meaning', 'approve', key, evidence,
                          'Synthetic owner review trial.', case.revision)
        return 'Owner meaning review recorded'

    def configure_intake(self, actor, case):
        proof = add_evidence(actor, case.pk, 'policy_decision',
                             'Synthetic intake trial configuration only.', 'synthetic:agent-outcomes')
        now = timezone.now()
        configs = [
            role_assignments.draft(actor, case.pk, [
                {'role': 'PM', 'user_id': actor.pk}, {'role': 'PMO Lead', 'user_id': actor.pk},
            ], proof.pk, now),
            draft_operator_policy(actor, case.pk, ASSIGN, {
                'assignment_roles': ['PMO Lead'], 'allow_synthetic': True,
            }, proof.pk, now),
            draft_operator_policy(actor, case.pk, REGISTER, {
                'registration_roles': ['PMO Lead'], 'namespace': 'synthetic:agent-trial',
                'format': 'ascii_token', 'max_length': 40, 'case_sensitive': False, 'allow_synthetic': True,
            }, proof.pk, now),
        ]
        for config in configs:
            transition(actor, config.pk, 'validated')
            transition(actor, config.pk, 'active')
