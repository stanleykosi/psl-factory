from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services import add_evidence
from apps.finance import hrfinance, payroll
from apps.finance.models import PayrollInput
from apps.policy.payroll_validators import ACCESS
from tests.helpers import rev
from tests.payroll_helpers import approve, combined, fixture, policy

COLUMNS = {'row_ref': 'Ref', 'employee_id': 'Staff ID', 'component': 'Pay code', 'amount': 'Total'}
CSV = b'Ref,Staff ID,Pay code,Total\nB1,E002,BASIC,150\n'


def worksheet(formula=False):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package = 'http://schemas.openxmlformats.org/package/2006/relationships'
    cells = ''.join(f'<c r="{col}1" t="inlineStr"><is><t>{header}</t></is></c>'
                    for col, header in zip('ABCD', COLUMNS.values()))
    cells2 = ''.join(f'<c r="{col}2" t="inlineStr"><is><t>{value}</t></is></c>'
                    for col, value in zip('ABC', ['B1', 'E002', 'BASIC']))
    value = '<f>100+50</f><v>150</v>' if formula else '<v>150</v>'
    buf = BytesIO()
    with ZipFile(buf, 'w') as archive:
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
                         '<sheet name="Payroll" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="{package}">'
                         f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet2.xml', f'<worksheet xmlns="{ns}"><sheetData>'
                         f'<row r="1">{cells}</row><row r="2">{cells2}<c r="D2">{value}</c></row></sheetData></worksheet>')
    return buf.getvalue()


class PayrollSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = fixture()

    def test_plain_export_fields_use_native_csv_and_excel_capture_without_approval(self):
        f=self.f;case=f['case'];rules=deepcopy(f['config']['access'])
        rules['providers'][1]['spreadsheet_layouts']=[{'format':'csv','delimiter':',','columns':COLUMNS},
                                                    {'format':'xlsx','sheet':'Payroll','columns':COLUMNS}]
        policy(f,ACCESS,rules);self.client.force_login(f['owner'])
        url=reverse('design_payroll_inputs',args=[case.pk]);page=self.client.get(url)
        self.assertContains(page,'Source export version');self.assertContains(page,'Export prepared at')
        for format_,content in [('csv',CSV),('xlsx',worksheet())]:
            data={'action':'capture','revision':rev(case),'request_record':f['request'].pk,'provider':'PAY-B',
                  'operation_key':'plain-'+format_,'source_version':'plain-'+format_,
                  'extracted_at':(timezone.now()-timedelta(seconds=1)).isoformat(),
                  'completeness':'complete','control_total':'150',
                  'file':SimpleUploadedFile('source.'+format_,content)}
            self.assertContains(self.client.post(url,data,follow=True),'Payroll history updated')
            row=PayrollInput.objects.get(request=f['request'],operation_key='plain-'+format_)
            self.assertEqual(row.source_sha256,sha256(content).hexdigest())
            self.assertEqual(row.payload['rows'][0]['amount'],'150')
            self.assertFalse(row.reviews.exists())
        unknown=b'Ref,Staff ID,Pay code,Total\nB1,E002,BASIC,\n'
        data.update(revision=rev(case),operation_key='plain-unknown',source_version='plain-unknown',control_total='',
                    file=SimpleUploadedFile('unknown.csv',unknown))
        self.assertContains(self.client.post(url,data,follow=True),'Payroll history updated')
        row=PayrollInput.objects.get(request=f['request'],operation_key='plain-unknown')
        self.assertIsNone(row.payload['control_total']);self.assertIsNone(row.payload['rows'][0]['amount'])
        self.assertEqual(row.metadata['status'],'held');self.assertFalse(row.reviews.exists())

    def test_plain_export_fields_refuse_conflicting_missing_or_nonspreadsheet_details(self):
        f=self.f;self.client.force_login(f['owner']);url=reverse('design_payroll_inputs',args=[f['case'].pk])
        base={'action':'capture','request_record':f['request'].pk,'provider':'PAY-B','operation_key':'ambiguous-file',
              'source_version':'plain-v2','extracted_at':(timezone.now()-timedelta(seconds=1)).isoformat(),
              'completeness':'complete','control_total':'150'}
        for changes in [{'extraction':json.dumps({key:base[key] for key in ['source_version','extracted_at','completeness','control_total']})},
                        {'source_version':''},{'extracted_at':'not-a-time'},{'control_total':'9'*101}]:
            data={**base,**changes,'revision':rev(f['case']),'file':SimpleUploadedFile('source.csv',CSV)}
            self.assertContains(self.client.post(url,data,follow=True),'The upload could not be accepted')
        data={**base,'revision':rev(f['case']),'file':SimpleUploadedFile('source.json',b'{}')}
        self.assertContains(self.client.post(url,data,follow=True),'The upload could not be accepted')
        self.assertEqual(PayrollInput.objects.filter(request=f['request']).count(),2)

    def test_spreadsheet_upload_requires_configured_layout_and_preserves_bytes(self):
        f = self.f
        case = f['case']
        self.client.force_login(f['owner'])
        url = reverse('design_payroll_inputs', args=[case.pk])
        details = {'source_version': 'v2', 'extracted_at': (timezone.now()-timedelta(seconds=1)).isoformat(),
                   'completeness': 'complete', 'control_total': '150'}

        def post(format_, content, key, **changes):
            return self.client.post(url, {'action': 'capture', 'revision': rev(case), 'request_record': f['request'].pk,
                                         'provider': 'PAY-B', 'operation_key': key,
                                         'extraction': json.dumps({**details, **changes}),
                                         'file': SimpleUploadedFile(f'payroll.{format_}', content)}, follow=True)

        self.assertContains(post('csv', CSV, 'no-layout'), 'The upload could not be accepted')
        rules = deepcopy(f['config']['access'])
        rules['providers'][1]['spreadsheet_layouts'] = [
            {'format': 'csv', 'delimiter': ',', 'columns': COLUMNS},
            {'format': 'xlsx', 'sheet': 'Payroll', 'columns': COLUMNS},
        ]
        policy(f, ACCESS, rules)
        for format_, content in [('csv', CSV), ('xlsx', worksheet())]:
            name = f'exact-{format_}'
            self.assertContains(post(format_, content, name), 'Payroll history updated')
            self.assertContains(post(format_, content, name), 'Payroll history updated')
            row = PayrollInput.objects.get(request=f['request'], operation_key=name)
            self.assertEqual(row.source_sha256, sha256(content).hexdigest())
            self.assertEqual(row.payload['rows'][0]['employee_id'], 'E002')
            self.assertEqual(row.metadata['status'], 'complete')
            self.assertContains(post(format_, content, name, control_total='151'), 'The upload could not be accepted')
        self.assertContains(post('xlsx', worksheet(formula=True), 'formula'), 'remove formulas')
        extra = b'Ref,Staff ID,Pay code,Total,private\nB1,E002,BASIC,150,PRIVATE-SENTINEL\n'
        self.assertNotContains(post('csv', extra, 'extra'), 'PRIVATE-SENTINEL')
        self.assertEqual(PayrollInput.objects.get(operation_key='extra').payload, {})

    def test_exact_hr_decision_is_private_and_approval_requires_successor_receipt(self):
        f = self.f
        case = f['case']
        run = combined(f)
        approve(f, run)
        matching = payroll.match(f['preparer'], case.pk, run.pk, f['hr'].pk, 'match-for-hr-desk', rev(case))
        links = [payroll.hr_correction(f['preparer'], case.pk, matching.pk, key, f['e']['hr_correction_request'].pk, rev(case))
                 for key in ['to-return', 'to-approve']]
        evidence = add_evidence(f['owner'], case.pk, 'hr_correction_response', 'Synthetic decision evidence', 'synthetic:payroll')
        routes = [reverse('design_hr_payroll_correction', args=[case.pk, link.pk]) for link in links]
        self.client.force_login(f['preparer'])
        self.assertEqual(self.client.get(routes[0]).status_code, 403)
        self.client.force_login(f['owner'])
        self.assertNotContains(self.client.get(routes[0]), 'E002')
        values = {'verdict': 'return', 'revision': rev(case), 'evidence': evidence.pk, 'operation_key': uuid4()}
        self.assertContains(self.client.post(routes[0], values, follow=True), 'Returned for clarification')

        replacement = deepcopy(f['hr_config']['export'])
        replacement['extracted_at'] = timezone.now().isoformat()
        successor = hrfinance.capture(f['owner'], case.pk, f['hr_contract'].pk, 'corrected-hr', json.dumps(replacement), rev(case))
        values.update(verdict='approve', successor=successor.pk, revision=rev(case), operation_key=uuid4())
        self.assertContains(self.client.post(routes[1], values, follow=True), 'Finance must confirm receipt')
        held = payroll.match(f['preparer'], case.pk, run.pk, successor.pk, 'held-without-receipt', rev(case))
        self.assertIn('hr_receipt_missing', held.metadata['codes'])
        for user in [f['preparer'], f['reviewer']]:
            hrfinance.receive(user, case.pk, successor.pk, f'finance-receipt-{user.pk}', f['e']['hr_disclosure_decision'].pk, rev(case))
        rerun = payroll.match(f['preparer'], case.pk, run.pk, successor.pk, 'approved-with-receipt', rev(case))
        self.assertEqual(rerun.metadata['status'], 'complete')
