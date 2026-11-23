from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from apps.core.evidence_access import public_evidence
from apps.identity import intake
from apps.identity.intake_models import TenantAuthority
from apps.identity.models import Grant
from tests.factory_helpers import fixture


@override_settings(ROOT_URLCONF='config.urls', PSL_DJANGO_UI=False)
class FrontendConnectionTests(TestCase):
    def test_signed_out_downloads_and_retired_forms_have_no_redirect(self):
        case = uuid4()
        downloads = (
            ('case_upload_download', (case, 1)), ('design_template_download', (case, 1)),
            ('rfp_intake_attachment', (case, 1)), ('factory_invoice_milestone_proof', (1, 1)),
            ('finance_bank_proof', (case, 1, 1, 'report')), ('design_reminder_download', (case, 1, 1, 'evidence')),
        )
        for name, args in downloads:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual((response.status_code, response.json()['code']), (401, 'unauthenticated'))
                self.assertNotIn('Location', response)
        self.assertEqual(self.client.get('/accounts/login/').json()['code'], 'page_retired')
        self.assertEqual(self.client.get('/api/v1/session').json()['next_url'], '/sign-in')

    def test_admin_signs_in_and_reads_roles_with_invites_disabled(self):
        admin = get_user_model().objects.create_superuser('frontend-admin', password='temporary-test-password')
        delegation = {'format': 'psl.tenant-access/v3', 'create_cases': True, 'manage_access': True,
            'kinds': ['project'], 'allowed_actions': ['case.read'], 'initial_actions': ['case.read'],
            'classification': 'synthetic', 'staff_lifecycle': {'allow_roster': True, 'allow_profile_edit': True}}
        applied = intake.provision(admin, admin, 'frontend-test', delegation, timezone.now() + timedelta(hours=1),
                                   True, 'Admin setup without invitations')
        case = intake.create_case(admin, applied.tenant, 'project-one', 'Lagoon Health', 'project')
        with self.assertRaisesMessage(ValidationError, 'invite_minutes'):
            intake.checked({**delegation, 'staff_lifecycle': {'allow_invite': True}})
        TenantAuthority.objects.create(user=admin, actor=admin, tenant=applied.tenant, version=2, enabled=True,
            expires_at=applied.expires_at, reason='Historical administration settings without an invitation duration',
            value={**delegation, 'staff_lifecycle': {**delegation['staff_lifecycle'], 'allow_invite': True}})
        self.assertFalse(intake.current(admin, applied.tenant, 'manage_access').value['staff_lifecycle']['allow_invite'])
        client = Client(enforce_csrf_checks=True)
        session = client.get('/api/v1/session').json()
        response = client.post('/api/v1/session', {'username': admin.username, 'password': 'temporary-test-password',
            'next_url': '/accounts/login/'}, content_type='application/json', HTTP_X_CSRFTOKEN=session['csrf_token'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['next_url'], '/my-work')
        for url in ('/api/v1/role-dashboard', '/api/v1/me'):
            response = client.get(url)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertTrue(any(row['role'] == 'admin' and row['workspace'] == case.title for row in response.json()['positions']))
        self.assertEqual(client.get('/api/v1/setup/scopes').json()['organisations'], ['frontend-test'])

    def test_tracking_intake_and_uploaded_proof_use_current_work(self):
        data = fixture(username='frontend-invoice')
        work, actor, case = data['work'], data['actor'], data['case']
        self.client.force_login(actor)
        path = f'/api/v1/work/{work.pk}'
        detail = self.client.get(path)
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()['reference'], work.request['reference'])
        tracking = self.client.get(detail.json()['tracking_url'])
        self.assertEqual(tracking.status_code, 200, tracking.content)
        self.assertFalse(tracking.json()['facts']['verified'])
        self.assertTrue(detail.json()['panels'][0]['contract_path'].startswith('/api/v1/work/{work_id}/'))
        queue = self.client.get('/api/v1/work?queue=mine&limit=15').json()
        self.assertEqual((queue['page_size'], queue['total']), (15, len(queue['items'])))
        matching = self.client.get('/api/v1/work', {'queue': 'mine', 'state': detail.json()['state']}).json()
        self.assertIn(work.pk, [row['id'] for row in matching['items']])
        self.assertEqual(self.client.get('/api/v1/work?limit=999').status_code, 422)
        line = next(line for line in self.client.get('/api/v1/lines').json()['items'] if line['key'] == work.definition)
        self.assertEqual(line['request_schema']['properties']['line']['const'], work.definition)
        self.assertIn('oneOf', line['request_schema']['properties']['intake'])
        delivery = self.client.get(f'/api/v1/projects/{case.pk}/delivery-overview')
        self.assertEqual(delivery.status_code, 200, delivery.content)
        self.assertEqual(len(delivery.json()['lines']), 6)
        proofs = detail.json()['proofs_url']
        original = BytesIO()
        pdf = PdfWriter()
        pdf.add_blank_page(width=200, height=200)
        pdf.write(original)
        with patch('adapters.case_uploads.put'), patch('adapters.case_uploads.read', return_value=original.getvalue()):
            response = self.client.post(f'/api/v1/cases/{case.pk}/files', {
                'file': SimpleUploadedFile('proof.pdf', original.getvalue(), content_type='application/pdf'),
            })
            self.assertEqual(response.status_code, 200, response.content)
            body = {'kind': 'pdf_copy', 'upload_id': response.json()['upload_id'], 'case_revision': detail.json()['case_revision']}
            for _ in range(2):
                attached = self.client.post(proofs, body, content_type='application/json')
                self.assertEqual(attached.status_code, 201, attached.content)
        saved = self.client.get(proofs).json()
        self.assertEqual([r['evidence_id'] for r in saved['items']], [attached.json()['evidence_id']])
        self.assertFalse(public_evidence(case.evidence.all()).filter(pk=attached.json()['evidence_id']).exists())
        note = {'kind': 'pmo_lead_note', 'note': 'Signed off in this workspace', 'case_revision': saved['case_revision']}
        self.assertEqual(self.client.post(proofs, note, content_type='application/json').status_code, 403)
        outsider = get_user_model().objects.create_user('frontend-unassigned')
        Grant.objects.create(user=outsider, case=case, action='case.read')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(proofs).status_code, 404)
