from copy import deepcopy
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.finance.payroll_models import PayrollInput, PayrollPublication, PayrollReview, PayrollRun
from apps.identity.models import Grant
from apps.policy.payroll_validators import ACCESS
from tests.helpers import rev
from tests.payroll_helpers import policy
from tests.test_design_payroll_sources import COLUMNS, CSV, worksheet
from tests.test_payroll_working_progress import configured


class PayrollApiCutoverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = configured()

    def test_multipart_sources_are_nominee_scoped_and_held_rows_stay_private(self):
        f, case = self.f, self.f['case']
        self.client.force_login(f['owner'])
        root = f'/api/v1/projects/{case.pk}/payroll'
        native = f['request']
        listed = self.client.get(root + '/requests')
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual([item['id'] for item in listed.json()['items']], [native.pk])
        created = self.client.post(root + '/requests', {'revision': rev(case), 'reference': 'SAMPLE-API-PAYROLL',
            'metadata': native.metadata, 'evidence_id': native.evidence_id}, content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        rules = deepcopy(f['config']['access'])
        rules['providers'][1]['spreadsheet_layouts'] = [{'format': 'csv', 'delimiter': ',', 'columns': COLUMNS},
                                                       {'format': 'xlsx', 'sheet': 'Payroll', 'columns': COLUMNS}]
        policy(f, ACCESS, rules)
        path = f'{root}/requests/{native.pk}/inputs'
        prepared = self.client.get(path)
        self.assertEqual(prepared.status_code, 200, prepared.content)
        choices = {row['provider']: row['formats'] for row in prepared.json()['provider_options']}
        self.assertEqual(choices['PAY-B'], ['json', 'csv', 'xlsx'])

        def upload(name, content, key, provider='PAY-B', *, total='150', **fields):
            return self.client.post(path, {'revision': rev(case), 'provider': provider, 'operation_key': key,
                'source_version': key, 'extracted_at': (timezone.now() - timedelta(seconds=1)).isoformat(),
                'completeness': 'complete', 'control_total': total, 'file': SimpleUploadedFile(name, content), **fields})

        for name, data in [('sample.csv', CSV), ('sample.xlsx', worksheet())]:
            imported = upload(name, data, 'import-' + name)
            self.assertEqual(imported.status_code, 201, imported.content)
            self.assertTrue(imported.json()['input']['accepted'])
            self.assertNotIn('E002', imported.content.decode())
        malformed = upload('unsupported.csv', b'Unsupported,Columns\na,b\n', 'unsupported-shape')
        self.assertEqual(malformed.status_code, 201, malformed.content)
        rejected = malformed.json()['input']
        self.assertFalse(rejected['accepted'])
        self.assertNotIn('a,b', malformed.content.decode())
        corrected = upload('corrected-shape.csv', CSV, 'corrected-shape')
        self.assertEqual(corrected.status_code, 201, corrected.content)
        self.assertTrue(corrected.json()['input']['accepted'])
        self.assertNotEqual(corrected.json()['input']['id'], rejected['id'])
        unknown = upload('needs-review.csv', b'Ref,Staff ID,Pay code,Total\nB1,E002,BASIC,\n', 'unknown-amount', total='')
        self.assertEqual(unknown.status_code, 201, unknown.content)
        source = unknown.json()['input']
        self.assertEqual(source['status'], 'held')
        self.assertTrue(source['accepted'])
        rows_path = f"{root}/input/{source['id']}/working-rows"
        self.client.force_login(f['manager'])
        self.assertEqual(self.client.get(rows_path).status_code, 403)
        self.assertEqual(upload('sample.csv', CSV, 'forbidden-import').status_code, 403)
        self.client.force_login(f['preparer'])
        page = self.client.get(rows_path, {'status': 'held'})
        self.assertEqual(page.status_code, 200, page.content)
        self.assertEqual((page.json()['rows'][0]['employee'], page.json()['rows'][0]['amount']), ('E002', None))
        self.assertEqual(page.json()['held'], 1)
        self.client.force_login(f['owner'])
        self.assertEqual(upload('corrected.csv', CSV, 'stale-predecessor', replaces_input_id=1).status_code, 409)
        replacement = upload('corrected.csv', CSV, 'current-predecessor', replaces_input_id=source['id'])
        self.assertEqual(replacement.status_code, 201, replacement.content)
        self.assertEqual(replacement.json()['input']['replaces_input_id'], source['id'])
        history = self.client.get(path).json()['inputs']
        self.assertEqual(history[0]['replaces_input_id'], source['id'])
        self.assertIn(source['id'], {item['id'] for item in history})
        self.client.force_login(f['preparer'])
        self.assertEqual(self.client.get(rows_path).status_code, 422)
        Grant.objects.filter(user=f['preparer'], case=case, action='payroll.private.read').update(active=False)
        self.assertEqual(self.client.get(rows_path).status_code, 403)
        self.assertFalse(PayrollInput.objects.get(pk=source['id']).reviews.exists())

    def test_private_working_operations_do_not_release_held_amounts(self):
        f, case, work = self.f, self.f['case'], self.f['work']
        self.client.force_login(f['preparer'])
        url = f'/api/v1/work/{work.pk}/payroll-operations'

        def operate(action, **fields):
            work.refresh_from_db()
            return self.client.post(url, {'action': action, 'expected_revision': work.revision,
                'case_revision': rev(case), **fields}, content_type='application/json')

        for stage in ('combine', 'match', 'aggregate'):
            result = operate('working', stage=stage)
            self.assertEqual(result.status_code, 200, result.content)
            row = PayrollRun.objects.get(pk=result.json()['record_id'])
            self.assertEqual(row.metadata['status'], 'held')
        self.assertEqual(operate('publish').status_code, 422)
        self.assertFalse(PayrollReview.objects.exists())
        self.assertFalse(PayrollPublication.objects.exists())
