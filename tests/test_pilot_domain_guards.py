import json
from django.conf import settings
from django.test import TestCase
from django.core.exceptions import PermissionDenied
from apps.policy import pilot,pilot_bindings as d
from apps.identity.models import Grant
from adapters import pilot_guards,pilot_preflight
from tests.test_pilot_preflight import selection
from tests.helpers import rev


def bind(actor,case,operation,arguments,participant=None):
    target=participant or actor;p=selection(actor,case);p['operations']=[operation]
    if target!=actor:p['participants'].append({'user_id':target.pk,'actions':['case.read']})
    contract=pilot.configure(actor,case.pk,p)
    example=json.loads((settings.BASE_DIR/'fixtures/pilot-bindings.json').read_text(encoding='utf-8'))
    technical=pilot_preflight.technical()
    payload={'format':'psl.pilot-bindings/v1','guards':[{'operation':operation,'user_id':target.pk,'arguments':dict(arguments,expected_revision=rev(case))}],
        'deployment':dict(example['deployment'],expected={k:technical[k] for k in ['source_identity','schema_identity','database_identity']})}
    b=d.configure(actor,case.pk,contract.pk,payload)
    return contract,b,pilot.capture(actor,case.pk,contract.pk)


class FinanceGuardTests(TestCase):
    def test_issue_and_delivery_use_actual_native_review_reservation_and_receipts(self):
        from tests.settlement_helpers import fixture,draft,approve
        from apps.finance import invoices,invoice_delivery
        from apps.finance.models import InvoiceJob
        a,c,cov,prep,e=fixture();invoice=draft(a,c,prep)
        def check(operation):
            c.refresh_from_db();return pilot_guards.check(a,c,{'operation':operation,'user_id':a.pk,'arguments':{'invoice_id':invoice.pk,'role':'Finance','expected_revision':c.revision}})
        self.assertEqual(check('finance.invoice.issue')['state'],'HELD')
        approve(a,c,invoice,e)
        contract,b,pack=bind(a,c,'finance.invoice.issue',{'invoice_id':invoice.pk,'role':'Finance'})
        self.assertEqual(d.report(a,c,contract)['native_guards'][0]['state'],'READY_AT_OBSERVATION')
        self.assertEqual(InvoiceJob.objects.count(),0)
        self.assertNotIn('amount',json.dumps(pack.snapshot['bindings']));self.assertNotIn('currency',json.dumps(pack.snapshot['bindings']))
        invoices.reserve(a,c.pk,invoice.pk,'issue','Finance',rev(c));invoice_delivery.run_once()
        self.assertFalse(pilot.inspect(a,c.pk,pack.pk)['current'])
        self.assertEqual(check('finance.invoice.issue')['state'],'HELD')
        self.assertEqual(check('finance.invoice.deliver')['state'],'READY_AT_OBSERVATION')
        invoices.reserve(a,c.pk,invoice.pk,'deliver','Finance',rev(c))
        self.assertEqual(check('finance.invoice.deliver')['state'],'EXISTING_RESERVATION_SOURCE_RECOVERY')

    def test_correction_apply_and_note_delivery_preserve_native_controls(self):
        from tests.correction_helpers import fixture,note,review
        from apps.finance import corrections,invoice_delivery
        from apps.finance.models import InvoiceJob
        a,c,coverage,issue,e=fixture();invoice=issue.invoice;correction=note(a,c,issue,e);review(a,c,correction,e)
        contract,b,pack=bind(a,c,'finance.invoice.correct',{'correction_id':correction.pk,'role':'Finance'})
        before=InvoiceJob.objects.count()
        self.assertEqual(d.report(a,c,contract)['native_guards'][0]['state'],'READY_AT_OBSERVATION');self.assertEqual(InvoiceJob.objects.count(),before)
        corrections.reserve(a,c.pk,correction.pk,'adjust','Finance',rev(c));invoice_delivery.run_once()
        c.refresh_from_db()
        result=pilot_guards.check(a,c,{'operation':'finance.invoice.correction_deliver','user_id':a.pk,'arguments':{'correction_id':correction.pk,'role':'Finance','expected_revision':c.revision}})
        self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertNotIn('amount',json.dumps(result))
        corrections.reserve(a,c.pk,correction.pk,'adjust_deliver','Finance',rev(c));invoice_delivery.run_once()
        self.assertFalse(pilot.inspect(a,c.pk,pack.pk)['current'])


class PrivateBaaSGuardTests(TestCase):
    def test_private_release_reuses_current_human_authority_and_packet_guards(self):
        from tests.support_release_helpers import ready,packet
        from tests.readiness_helpers import endpoint
        from apps.baas import support_release
        with endpoint():
            f=ready('native-baas-guard');p=packet(f)
            a,c=f['actor'],f['case'];contract,b,pack=bind(a,c,'baas.response.decide',{'packet_id':p.pk,'verdict':'release'},f['reviewer'])
            result=d.report(a,c,contract)['native_guards'][0]
            self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertNotIn('payload',result);self.assertEqual(support_release.Job.objects.count(),0)
            support_release.decide(f['reviewer'],c.pk,p.pk,'release')
            self.assertFalse(pilot.inspect(a,c.pk,pack.pk)['current'])
            Grant.objects.filter(case=c,user=a,action='support.private.read').update(active=False)
            with self.assertRaises(PermissionDenied):pilot.inspect(a,c.pk,pack.pk)
