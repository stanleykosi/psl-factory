import os
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from adapters import finance_documents
from apps.agents.department_context import registers
from apps.core.evidence_access import public_evidence
from apps.core.models import Case, Evidence
from apps.finance import document_review as service
from apps.finance.models import FinanceDocument, FinancialImport, ReviewedFinanceFigure
from apps.identity.models import Grant
from apps.identity import intake, staff, teams
from tests.finance_analysis_helpers import fixture
from tests.helpers import rev


class FinanceDocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, *_ = fixture(username='finance-reader-4', recipient_username='finance-recipient-4')
        cls.reviewer = get_user_model().objects.create_user('finance-reviewer-4')
        for actor in (cls.actor, cls.reviewer):
            for action in ('finance.read', 'finance.review', 'case.read'):
                Grant.objects.get_or_create(user=actor, case=cls.case, action=action)

    def setUp(self):
        self.proposal = {'entity': 'Sample Ltd', 'period': '2026-10', 'currency': 'NGN', 'unit': 'thousands',
            'unit_evidence': 'Page 1: NGN thousands', 'control_total': '325', 'issues': [],
            'rows': [{'account': 'Service', 'amount': '250', 'unit': 'file', 'citation': 'Page 1: Service 250'},
                     {'account': 'Other', 'amount': '75', 'unit': 'file', 'citation': 'Page 1: Other 75'}]}
        self.doc = None

    def upload(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=100)
        stream = BytesIO()
        writer.write(stream)
        self.pdf = stream.getvalue()
        with patch('adapters.case_uploads.put'):
            self.doc = service.submit(self.actor, self.case, SimpleUploadedFile('statement.pdf', self.pdf))
            self.assertEqual(self.doc.pk, service.submit(self.actor, self.case,
                SimpleUploadedFile('same-again.pdf', self.pdf)).pk)
        return self.doc

    def extract(self):
        self.upload()
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':'test', 'OPENROUTER_MODEL':'test-reader'}), \
                patch('adapters.case_uploads.read', return_value=self.pdf), \
                patch('adapters.openrouter.completion', return_value=self.proposal) as model:
            self.assertTrue(service.run_once())
            content = model.call_args.args[2]
            self.assertTrue(content[1]['file']['file_data'].startswith('data:application/pdf;base64,'))
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'review')

    def values(self, **changes):
        return {**{k: v for k, v in self.proposal.items() if k not in ('rows', 'issues')},
                'note':'Checked against page 1.', 'checked':True, 'control_unit':'file', **changes}

    def approve(self, **changes):
        return service.approve(self.reviewer, self.case, self.doc.pk, str(self.doc.attempt),
                               self.values(**changes), self.proposal['rows'])

    def test_original_to_review_to_native_accounts(self):
        self.extract()
        doc = self.doc
        self.assertFalse(ReviewedFinanceFigure.objects.exists())
        initial_count = FinancialImport.objects.count()
        with self.assertRaises(ValidationError):
            service.handoff(self.reviewer, self.case, doc.pk, 'sample', 'accrual', 'complete')
        self.assertEqual(initial_count, FinancialImport.objects.count())
        with self.assertRaises(ValidationError):
            self.approve(control_total='324')
        with self.assertRaises(ValidationError):
            self.approve(checked=False)
        approved = self.approve()
        self.approve()
        self.assertEqual(approved.approved['full_control_total'], '325000')
        self.assertEqual([r['full_amount'] for r in approved.approved['rows']], ['250000','75000'])
        group = next(g for g in registers('chidi', Case.objects.filter(pk=self.case.pk), self.reviewer) if g.key == 'finance_figure')
        self.assertEqual(group.rows.count(), 2)
        self.assertIn('250000', group.source('chidi', group.matching_entries('Service').first())['fact'])
        result = service.handoff(self.reviewer, self.case, doc.pk, 'synthetic-company', 'accrual', 'complete')
        self.assertEqual(result['status'], 'started')
        self.assertEqual(service.handoff(self.reviewer, self.case, doc.pk, 'synthetic-company', 'accrual', 'complete'), result)
        batch = FinancialImport.objects.get(pk=result['batch'])
        self.assertEqual(batch.rows[0]['amount'], '250000')
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=batch.evidence_id)).exists())

    def test_ambiguity_mixed_scales_privacy_and_recovery(self):
        self.proposal['unit'], self.proposal['issues'] = 'unknown', ['Check the heading.']
        self.extract()
        with self.assertRaises(ValidationError):
            self.approve()
        with self.assertRaises(ValidationError):
            self.approve(unit='thousands', note='')
        with self.assertRaises(ValidationError):
            service.approve(self.reviewer, self.case, self.doc.pk, 'stale', self.values(unit='units'), self.proposal['rows'])
        other = get_user_model().objects.create_user('other-department')
        self.client.force_login(other)
        for view in ('finance_document_review', 'finance_document_original'):
            self.assertEqual(self.client.get(reverse(view, args=[self.case.pk, self.doc.pk])).status_code, 404)
        with self.assertRaises(PermissionDenied):
            service.approve(other, self.case, self.doc.pk, str(self.doc.attempt), self.values(), self.proposal['rows'])
        self.proposal['rows'][0].update(amount='-1.25', unit='millions')
        self.proposal['rows'][1].update(amount='0', unit='units')
        approval = self.approve(unit='mixed', control_total='-1250', control_unit='thousands')
        self.assertEqual(approval.approved['rows'][0]['full_amount'], '-1250000.00')
        self.assertEqual(approval.approved['rows'][1]['full_amount'], '0')
        self.assertEqual(approval.draft['unit'], 'unknown')

    def test_provider_failure_never_creates_figures_and_another_reviewer_can_retry(self):
        doc = self.upload()
        with patch.dict(os.environ, {'OPENROUTER_API_KEY':''}):
            service.run_once()
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'held')
        self.assertFalse(doc.figures.exists())
        service.retry(self.reviewer, self.case, doc.pk, str(doc.attempt))
        doc.refresh_from_db()
        self.assertEqual((doc.status, doc.requested_by, doc.uploader), ('queued', self.reviewer, self.actor))
        with self.assertRaises(ValidationError):
            finance_documents.validate_draft(dict(self.proposal, rows=[{}]))

    def test_missing_check_total_needs_a_human_answer_and_empty_reading_is_held(self):
        with self.assertRaises(ValidationError):
            finance_documents.validate_draft(dict(self.proposal, rows=[]))
        self.proposal['control_total'] = ''
        self.extract()
        with self.assertRaises(ValidationError):
            self.approve()
        checked = self.approve(no_total=True)
        self.assertNotIn('full_control_total', checked.approved)
        self.assertTrue(checked.approved['no_total'])

    def test_return_preserves_the_source_without_adding_any_approved_knowledge(self):
        self.extract()
        service.return_file(self.reviewer, self.case, self.doc.pk, str(self.doc.attempt), 'Please supply page two.')
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, 'returned')
        self.assertEqual(self.doc.draft, self.proposal)
        self.assertFalse(self.doc.figures.exists())
        with self.assertRaises(ValidationError):
            self.approve()
        with self.assertRaises(DatabaseError), transaction.atomic():
            FinanceDocument.objects.filter(pk=self.doc.pk).update(status='review')
        self.assertEqual(service.full_amount('(1,250.50)', 'thousands'), '-1250500.00')

    def test_finance_lead_can_approve_and_members_stay_in_their_projects(self):
        self.extract()
        admin = get_user_model().objects.create_user('finance-team-admin')
        root = get_user_model().objects.create_superuser('finance-team-root')
        actions = ['case.read','evidence.add','action.manage','action.own','action.work']
        authority = {'format':'psl.tenant-access/v3','create_cases':True,'manage_access':True,'kinds':['project'],
            'allowed_actions':actions,'initial_actions':actions,'classification':'synthetic',
            'staff_lifecycle':{'invite_minutes':30,'allow_invite':True,'allow_deactivation':True,
                               'allow_profile_edit':True,'allow_roster':True}}
        intake.provision(root, admin, self.case.tenant, authority, timezone.now()+timedelta(days=1), True, 'Test admission')
        Grant.objects.bulk_create([Grant(user=admin, case=self.case, action=a) for a in actions])
        team = teams.create_team(admin, self.case.pk, 'finance-lead', 'Finance')
        def invite(owner, name, mode):
            _, token = staff.invite_person(owner, self.case.pk, name, name, name+'@example.test', rev(self.case),
                                          role='finance-lead', mode=mode, team_id=team.pk)
            return staff.accept(token, 'SyntheticTestFinanceAccount-23!')
        lead = invite(admin, 'f4-test-head', 'lead')
        member = invite(lead, 'f4-test-member', 'member')
        extra = Case.objects.create(tenant=self.case.tenant, kind='project', synthetic=True, title='Separate project')
        self.assertTrue(service.workspaces(lead).filter(pk=extra.pk).exists())
        self.assertFalse(service.workspaces(member).filter(pk=extra.pk).exists())
        url = reverse('finance_document_review', args=[self.case.pk, self.doc.pk])
        self.client.force_login(member)
        self.assertContains(self.client.get(url), 'Review Chidi')
        self.reviewer = lead
        self.assertEqual(self.approve().reviewer, lead)
        self.assertContains(self.client.get(url), '325,000')
