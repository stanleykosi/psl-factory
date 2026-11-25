"""Fill a fresh local database with the PSL design demo: people, clients and four projects.

Synthetic tenant only. Every record is made through the real service functions; policy values come from
the repo fixtures and are demo values, not PSL business policy.
"""
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core import client_contacts
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.finance import billing
from apps.identity import intake, role_factory_decisions, scope_moves, teams
from apps.identity.actions import ACTIONS
from apps.identity.team_models import StaffMembership
from apps.pmo import rfp
from apps.pmo.delivery import open_dossier
from apps.pmo.gates import register_candidate
from apps.pmo.issues import log_issue
from apps.pmo.meetings import record_meeting
from apps.pmo.services import complete_milestone
from apps.pmo.signatures import capture_packet
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.finance_drafts import draft_finance_policy
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.registry import components
from apps.policy.services import register_reference, save_draft, transition
from apps.workflows import factory_delivery, factory_reporting

from ._psl_demo_journey import (JOURNEY_ADA, JOURNEY_FOLAKE, JOURNEY_PM, JOURNEY_PMO_LEAD, PLACEHOLDER_ENGINEERING_LEAD,
                                TEMPLATE_RULE, JourneyMixin)

TENANT = 'psl-demo'
ROOT = 'psl-demo-root'
SETUP = 'psl-demo-setup'
DOMAIN = '@psl-demo.test'
EVIDENCE_KINDS = ['requirements', 'engineering_estimate', 'security_estimate', 'plan', 'costing', 'sow',
                  'signature', 'completion', 'policy_decision']
# Design names and amounts: frontend/mock/fixtures (E-PROJECTS, projects/money/P-0101, clients/).
PEOPLE = {
    'tunde': ('Tunde', 'Bello', 'tunde.bello'), 'chinedu': ('Chinedu', 'Okeke', 'chinedu.okeke'),
    'kemi': ('Kemi', 'Adebayo', 'kemi.adebayo'), 'ada': ('Ada', 'Okafor', 'ada.okafor'),
    'folake': ('Folake', 'Bello', 'folake.bello'), 'ngozi': ('Ngozi', 'Adeyemi', 'ngozi.adeyemi'),
    'amaka': ('Amaka', 'Obi', 'amaka.obi'),
}
PROJECTS = {
    'lagoon': {'title': 'Lagoon Health · patient app', 'client': 'Lagoon Health', 'pm': 'tunde'},
    'delta': {'title': 'Delta Foods · ordering app', 'client': 'Delta Foods', 'pm': 'chinedu'},
    'kora': {'title': 'Kora Logistics · fleet tracker', 'client': 'Kora Logistics', 'pm': 'tunde'},
    'sabi': {'title': 'Sabi Market · web store', 'client': 'Sabi Market', 'pm': None},
}
# What a project manager needs on their own projects, before any staff scope applies.
PM_ACTIONS = [
    'case.read', 'evidence.add', 'factory.read', 'factory.start', 'factory.execute', 'report.read', 'report.draft',
    'document.read', 'document.draft', 'document.request_review', 'meeting.read', 'meeting.record', 'issue.read',
    'change.read', 'delivery.read', 'rfp.read', 'engagement.read', 'engagement.capture', 'baseline.sign',
    'decision.record', 'commercial.response', 'finance.read', 'planning.read',
    'document.publish', 'meeting.participate', 'issue.manage', 'issue.own', 'issue.work', 'delivery.manage',
    'pmo.candidate',
]
LEAD_REVIEW_ACTIONS = ['case.read', 'decision.record', 'engagement.read', 'engagement.assign', 'milestone.complete',
                       'evidence.add']
FIELDS = ['executive_summary', 'scope', 'status', 'risks', 'timeline', 'dependencies', 'next_steps']
PLACEHOLDERS = f' {PLACEHOLDER_ENGINEERING_LEAD} and {TEMPLATE_RULE} apply until PSL supplies the real ones.'


def person_name(key):
    first, last, _ = PEOPLE[key]
    return f'{first} {last}'


def username(key):
    return PEOPLE[key][2] + DOMAIN


class Command(JourneyMixin, BaseCommand):
    help = ('Seed the PSL design demo (people, clients, four projects) in its own synthetic tenant. '
            'Writes sign-in names and passwords to --credentials-file only.')

    def add_arguments(self, parser):
        parser.add_argument('--credentials-file', required=True)

    def handle(self, *args, **options):
        path = Path(options['credentials_file'])
        user_model = get_user_model()
        if (Case.objects.filter(tenant=TENANT).exists() or user_model.objects.filter(username__in=[ROOT, SETUP]).exists()
                or user_model.objects.filter(username__in=[username(key) for key in PEOPLE]).exists()):
            raise CommandError('PSL demo records already exist; this command never overwrites')
        if path.exists():
            raise CommandError('The credentials file already exists; choose a new path')
        self.passwords = {key: secrets.token_urlsafe(18) for key in PEOPLE}
        self.cases = {}
        self.e = {}
        self.projects = PROJECTS
        self.templates, self.recipients, self.engagement_work, self.commercial_work = {}, {}, {}, {}
        self.report_definition = {'document_type': 'status_report', 'required_fields': FIELDS,
                                  'audience_fields': {'client': FIELDS}}
        self.work_ids = []
        self.write_credentials(path)
        try:
            self.build()
        except BaseException:
            path.unlink()
            raise
        # Workers run after the records commit, as in the other demos.
        for command in ('work_factory', 'work_reports', 'work_factory', 'work_outbox', 'work_publications'):
            if command == 'work_factory':
                call_command(command, *[f'--work={pk}' for pk in self.work_ids], '--until-wait', stdout=self.stdout)
            else:
                call_command(command, stdout=self.stdout)
        self.place_people()
        self.stdout.write('PSL demo seeded: ' + ', '.join(project['title'] for project in PROJECTS.values()))

    # -- people and workspaces -------------------------------------------------------------------------

    def write_credentials(self, path):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            for key in PEOPLE:
                handle.write(f'{username(key)} {self.passwords[key]}\n')

    @transaction.atomic
    def build(self):
        user_model = get_user_model()
        root = user_model.objects.create_superuser(ROOT)
        root.set_unusable_password()
        root.save()
        self.admin = user_model.objects.create_user(SETUP, first_name='PSL demo setup')
        self.admin.set_unusable_password()
        self.admin.save()
        intake.provision(root, self.admin, TENANT, {
            'format': 'psl.tenant-access/v3', 'create_cases': True, 'manage_access': True, 'kinds': ['project'],
            'allowed_actions': sorted(set(ACTIONS)), 'initial_actions': sorted(set(ACTIONS)),
            'classification': 'synthetic',
            'staff_lifecycle': {'invite_minutes': 60, 'allow_invite': True, 'allow_deactivation': True,
                                'allow_profile_edit': True, 'allow_roster': True},
        }, timezone.now() + timedelta(days=180), True, 'Synthetic PSL demo set-up; not operational access.')
        root.is_active = False
        root.save()
        self.users = {}
        for key, (first, last, _) in PEOPLE.items():
            self.users[key] = user_model.objects.create_user(
                username(key), email=username(key), password=self.passwords[key], first_name=first, last_name=last)
        for key, project in PROJECTS.items():
            case = intake.create_case(self.admin, TENANT, 'PSL-DEMO-' + key.upper(), project['title'], 'project')
            self.cases[key] = case
        self.users['placeholder_eng'] = self.technical_person('psl-demo-placeholder-engineering-lead',
                                                              PLACEHOLDER_ENGINEERING_LEAD)
        for key in PROJECTS:
            self.start_project(key)
        # Each project's history runs the real journey; Kora stops at its costing approval, Delta and Lagoon are signed.
        for key, approvals in (('kora', ['PM']), ('delta', ['PM', 'Head of PMO', 'CEO', 'PMO Lead']),
                               ('lagoon', ['PM', 'Head of PMO', 'CEO', 'PMO Lead'])):
            self.documents_setup(key)
            self.rfp_history(key)
            self.engagement_history(key)
            work, revision = self.costing_history(key, approvals)
            if len(approvals) == 4:
                self.sign_sow(key, revision)
        self.rfp_received('sabi')
        self.lagoon_money_and_milestones()
        self.open_issue('lagoon')
        self.release_work('lagoon')
        self.release_work('delta')
        # The report reads the inventory as it stands when it starts, so it starts after the other records.
        self.weekly_report('lagoon')

    @transaction.atomic
    def place_people(self):
        self.staff_roles()
        self.assign_report_review()

    def grant(self, case, key, actions):
        self.grant_user(case, self.users[key], actions)

    def grant_user(self, case, user, actions):
        for action in actions:
            intake.change_access(self.admin, case.pk, user.pk, action, True, 'Synthetic PSL demo access')

    def evidence(self, case, kind, text):
        return add_evidence(self.admin, case.pk, kind, text, 'synthetic:psl-demo')

    def activate(self, case, owner, component, value):
        config = save_draft(self.admin, case.pk, {
            'slot_id': components()[component]['parent_decision_id'], 'component_id': component,
            'component_schema_ref': components()[component]['schema_ref'], 'schema_version': '1',
            'subject_scope': {'kind': 'project', 'ref': str(case.pk)}, 'policy_revision': 1, 'lifecycle': 'draft',
            'effective_from': (timezone.now() - timedelta(minutes=1)).isoformat(), 'effective_until': None,
            'evidence_refs': [f'evidence:{owner.pk}'], 'human_decision_ref': f'evidence:{owner.pk}',
            'implementation_id': 'psl.reference-validation', 'implementation_version': '1',
            'reviewed_implementation_ref': 'code:apps/policy/services.py#reference-validation-v1',
            'fixture_scope': 'synthetic_test', 'value': value})
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        return config

    def artifact(self, case, owner, component, schema, content):
        reference = register_reference(self.admin, case.pk, 'psl-demo:' + str(uuid4()), schema, content, owner.pk)
        return self.activate(case, owner, component, {
            'artifact_ref': reference.ref, 'artifact_version': reference.version, 'sha256': reference.sha256,
            'schema_ref': reference.schema_ref})

    def roles(self, case, owner, pm):
        assigned = [('PM', pm)] if pm else [('PM', 'tunde'), ('PM', 'chinedu')]
        assigned += [('Head of PMO', 'kemi'), ('CEO', 'folake'), ('PMO Lead', 'kemi')]
        if pm:
            # D-214: the PM logs engineering decisions for the placeholder engineering lead. The template costing rule
            # is owned by the PMO and tested by Finance; the client answers through the PM (staff-recorded).
            assigned += [('Engineering Lead', 'placeholder_eng'), ('Engineering Lead', pm), ('Client', pm),
                         ('PMO', 'kemi'), ('Finance', 'ada')]
        refs = []
        for index, (role, key) in enumerate(assigned):
            ref = f'psl-demo:role:{index}'
            register_reference(self.admin, case.pk, ref, 'schema:psl/role-assignment/v1',
                               {'role': role, 'user_id': self.users[key].pk}, owner.pk)
            refs.append(ref)
        return self.activate(case, owner, 'D05.role_principal_assignments', refs)

    def start_project(self, key):
        """Access, evidence, the people behind each role and the client for one project."""
        project, case = PROJECTS[key], self.cases[key]
        pm = project['pm']
        if pm:
            self.grant(case, pm, PM_ACTIONS + JOURNEY_PM)
            self.grant(case, 'ada', ['case.read'] + JOURNEY_ADA)
        else:
            # Both PMs are nominated for Sabi, so the PMO Lead has someone to choose; neither is assigned.
            for nominee in ('tunde', 'chinedu'):
                self.grant(case, nominee, ['case.read', 'rfp.read', 'rfp.prepare'])
        self.grant(case, 'kemi', LEAD_REVIEW_ACTIONS + (JOURNEY_PMO_LEAD if pm else []))
        self.grant(case, 'folake', ['case.read', 'decision.record'] + (JOURNEY_FOLAKE if pm else []))
        e = {kind: self.evidence(case, kind, f'{project["title"]}: {kind.replace("_", " ")} (demo record).' + (PLACEHOLDERS if kind == 'policy_decision' else ''))
             for kind in EVIDENCE_KINDS}
        self.e[key] = e
        self.roles(case, e['policy_decision'], pm)
        # D-212: the PMO Lead assigns the accountable PM. The rest is the repo fixture's synthetic matrix.
        matrix = json.loads(Path(settings.BASE_DIR, 'fixtures/rfp.json').read_text())['decision_matrix']
        matrix['rfp']['assignment_roles'] = ['PMO Lead']
        config = draft_standard_policy(self.admin, case.pk, 'D05.decision_action_matrix', matrix,
                                       e['policy_decision'].pk, timezone.now() - timedelta(minutes=1))
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        proof = self.evidence(case, 'engagement_source', f'{project["client"]} engagement source (demo record).')
        client_contacts.save(self.users[pm] if pm else self.admin, case, 'project', {
            'customer': '', 'client_name': project['client'], 'name': f'{project["client"]} project contact',
            'email': '', 'role': '', 'evidence': proof, 'revision': self.rev(case)})

    def rfp_received(self, key):
        case = self.cases[key]
        source = self.evidence(case, 'rfp_intake', f'{PROJECTS[key]["client"]} request for proposal, as received.')
        rfp.intake(self.admin, case.pk, 'PSL-DEMO-RFP-SABI', source.pk, timezone.now() - timedelta(hours=2),
                   'not_stated', None, None, 'The received document states no deadline', self.rev(case))

    def open_issue(self, key):
        case, pm = self.cases[key], self.users[PROJECTS[key]['pm']]
        incident = self.evidence(case, 'incident', 'Login fails on older Android phones (demo record).')
        log_issue(pm, case.pk, 'ISS-0233', 'Login fails on older Android phones', 'Defect', pm.pk,
                  'Reproduce on an older Android phone and confirm the fix', incident.pk,
                  'Raised during UAT with the client', self.rev(case), 'High')

    def signature_packet(self, case, e, pm, revision):
        identity = self.evidence(case, 'client_identity', 'Demo client representative (synthetic).')
        self.artifact(case, e['policy_decision'], 'D11.client_signature_contract',
                      'schema:psl/client-signature-contract/v1', {
            'parties': [{'party_ref': 'synthetic-client', 'display_name': 'Demo client representative',
                         'identity_evidence_id': identity.pk, 'documents': ['sow', 'prd']}],
            'methods': ['synthetic-reviewed-file'], 'assurance': 'human_verified_reference_only',
            'unchanged_prd_signature_reuse': 'unconfigured', 'applicability': 'client_project',
            'signature_requirement': 'required', 'scope_evidence_id': None, 'allow_synthetic': True})
        prd = self.evidence(case, 'prd', 'Product requirements document (demo record).')
        prd_signature = self.evidence(case, 'signature', 'Separate PRD signature reference (demo record).')
        signatures = {kind: {'evidence_id': source.pk, 'party_ref': 'synthetic-client',
                             'method': 'synthetic-reviewed-file', 'locator': kind + ':signature',
                             'human_verified': True}
                      for kind, source in [('sow', e['signature']), ('prd', prd_signature)]}
        capture_packet(pm, case.pk, prd.pk, signatures, 'Demo human-verified signature references',
                       str(uuid4()), self.rev(case), revision.pk, None)

    def lagoon_money_and_milestones(self):
        case, e = self.cases['lagoon'], self.e['lagoon']
        coverage_proof = self.evidence(case, 'billing_coverage', 'Lagoon Health patient app contract coverage (demo).')
        cover = billing.register_coverage(
            self.admin, case.pk, 'lagoon-patient-app', 'lagoon-health', 'patient-app', 'sow-lagoon-v1', 'NGN',
            'net_exclusive', '2026-10', '2027-09', 'partial', coverage_proof.pk, self.rev(case))
        signature = e['signature']

        def policy(component, content):
            owner = self.evidence(case, 'policy_decision', 'Demo billing terms from the design fixtures; not PSL policy.')
            config = draft_finance_policy(self.admin, case.pk, component, content, owner.pk, timezone.now())
            transition(self.admin, config.pk, 'validated')
            transition(self.admin, config.pk, 'active')

        policy('D12.contract_version_ref', {'coverage_id': cover.pk, 'signed_evidence_id': signature.pk,
                                            'signed_sha256': signature.sha256})
        policy('D12.currency_amount_basis', {'coverage_id': cover.pk, 'currency': 'NGN',
                                             'amount_basis': 'net_exclusive', 'contract_value': None,
                                             'decimal_places': 2})
        policy('D12.stage_terms', [
            {'coverage_id': cover.pk, 'stage': 'signed_sow', 'amount': '3000000.00', 'due_date': '2026-10-30'},
            {'coverage_id': cover.pk, 'stage': 'uat', 'amount': '4250000.00', 'due_date': '2026-11-10'},
            {'coverage_id': cover.pk, 'stage': 'completion', 'amount': None, 'due_date': '2026-12-12'}])
        policy('D12.uat_billing_predicate_ref', {'coverage_id': cover.pk, 'stage': 'uat',
                                                 'milestone_name': 'UAT sign-off'})
        policy('D12.completion_billing_predicate_ref', {'coverage_id': cover.pk, 'stage': 'completion',
                                                        'milestone_name': 'Go-live'})
        kemi = self.users['kemi']
        complete_milestone(kemi, case.pk, 'Kick-off', e['completion'].pk, self.rev(case))
        uat = self.evidence(case, 'completion', 'UAT sign-off recorded with the client (demo record).')
        complete_milestone(kemi, case.pk, 'UAT sign-off', uat.pk, self.rev(case))

    def technical_user(self, name, full_name, actions):
        user = get_user_model().objects.create_user(name, first_name=full_name)
        user.set_unusable_password()
        user.save()
        self.users[name] = user
        self.grant(self.cases['lagoon'], name, actions)
        return user

    def weekly_report(self, key):
        """A client weekly report that waits for the PMO Lead, as seed_factory_demo builds it."""
        case, project, pm = self.cases[key], PROJECTS[key], self.users[PROJECTS[key]['pm']]
        owner = self.e[key]['policy_decision']
        preparer = self.technical_user('psl-demo-report-preparer', 'Report preparer (automated)', [
            'case.read', 'report.read', 'factory.execute', 'report.draft', 'document.draft',
            'document.request_review', 'evidence.add', 'meeting.read', 'issue.read', 'change.read',
            'delivery.read', 'rfp.read'])
        template = self.templates[key]['report']
        profile = json.loads(Path(settings.BASE_DIR, 'fixtures/factory-reporting.json').read_text())
        profile.pop('classification')
        profile.update(preparer_id=preparer.pk, executor_id=pm.pk)
        config = draft_operator_policy(self.admin, case.pk, 'OPS.factory_reporting_execution', profile,
                                       owner.pk, timezone.now() - timedelta(minutes=1))
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        now = timezone.now()
        notes = add_evidence(pm, case.pk, 'meeting_notes',
                             'Weekly delivery review with the client: UAT progress and next steps were discussed.',
                             'synthetic:weekly-report-meeting')
        record_meeting(pm, case.pk, 'PSL-DEMO-WEEKLY-001', 'status', now - timedelta(hours=1),
                       'Weekly delivery review', 'The team reviewed UAT progress and next steps with the client.',
                       [pm.pk], [{'text': 'UAT progress was reviewed.', 'evidence_id': notes.pk}],
                       notes.pk, self.rev(case))
        sections = {
            'status': 'UAT with the client is under way and on the agreed plan.',
            'risks': 'No client-facing risk has been confirmed this week.',
            'timeline': 'Milestone dates are unchanged by this review.',
            'next_steps': 'The project manager confirms the next review with the client.',
        }
        content = add_evidence(pm, case.pk, 'agent_private_report_content', json.dumps({
            'protocol': 'pmo-weekly-client-content/v1',
            'sections': {topic: {'text': text, 'evidence_ids': [notes.pk]} for topic, text in sections.items()}}),
            'synthetic:human-authored-client-report')
        work = factory_reporting.start(
            pm, case_id=case.pk, key='PSL-DEMO-WEEKLY-REPORT', expected=self.rev(case),
            reference=f'Weekly client report: {project["title"]}',
            inputs={'template_id': template.pk, 'content_id': content.pk,
                    'start_at': (now - timedelta(days=7)).isoformat(), 'end_at': now.isoformat()})
        self.work_ids.append(work.pk)
        self.report_work = work.pk

    def staff_roles(self):
        """Move the named people into their staff roles; the PMs keep their per-project access."""
        case = self.cases['lagoon']
        pmo = teams.create_team(self.admin, case.pk, 'pmo-lead', 'Project management')
        finance = teams.create_team(self.admin, case.pk, 'finance-lead', 'Finance')
        hr = teams.create_team(self.admin, case.pk, 'hr', 'Human resources')
        self.grant(case, 'ada', ['case.read'])
        self.grant(case, 'ngozi', ['case.read'])
        self.grant(case, 'amaka', ['case.read'])
        for key, role, mode, team in [('kemi', 'pmo-lead', 'lead', pmo), ('ada', 'finance-lead', 'lead', finance),
                                      ('folake', 'ceo', 'standalone', None), ('ngozi', 'hr', 'lead', hr),
                                      ('amaka', 'hr', 'member', hr)]:
            team_id = team.pk if team else None
            case.refresh_from_db()
            preview = scope_moves.prepare(self.admin, case, self.users[key].pk, role, mode, team_id)
            scope_moves.apply(self.admin, case.pk, self.users[key].pk, role, mode, team_id, preview['fingerprint'],
                              str(uuid4()), f'{person_name(key)} joins as {role} ({mode}) in the PSL demo')

    def assign_report_review(self):
        """The set-up administrator hands the report review to the PMO Lead, who is its PMO Lead principal."""
        case = self.cases['lagoon']
        member = StaffMembership.objects.get(case=case, user=self.users['kemi'], active=True)
        role_factory_decisions.assign(self.admin, case.pk, member.pk, self.report_work, 'document', None, None,
                                      self.rev(case))

    def release_work(self, key):
        """Open the release dossier and start the release line, so the project shows its release station."""
        case, e, pm = self.cases[key], self.e[key], self.users[PROJECTS[key]['pm']]
        candidate = register_candidate(pm, case.pk, 'delivery-build', e['requirements'].pk, self.rev(case))
        dossier = open_dossier(pm, case.pk, candidate.pk, e['plan'].pk,
                               'PM scope attestation for this requirements and plan', self.rev(case))
        profile = json.loads(Path(settings.BASE_DIR, 'fixtures/factory-delivery.json').read_text())
        profile.pop('classification')
        config = draft_operator_policy(self.admin, case.pk, 'OPS.factory_delivery_execution', profile,
                                       e['policy_decision'].pk, timezone.now() - timedelta(minutes=1))
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        work = factory_delivery.start(pm, case.pk, 'PSL-DEMO-RELEASE', dossier.pk,
                                      f'Release: {PROJECTS[key]["title"]}', self.rev(case))
        self.work_ids.append(work.pk)
