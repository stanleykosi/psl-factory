import json
from django.test import TestCase
from django.conf import settings
from django.core.exceptions import PermissionDenied,ValidationError
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.operator_validators import OPERATOR
from apps.workflows.operator_recovery import recover
from apps.workflows.operator_inventory import jobs
from .operator_helpers import policy
from .helpers import rev

def attach(a,c,role):
 v=json.loads((settings.BASE_DIR/'fixtures/operator-recovery.json').read_text(encoding='utf-8'))['operator'];v.update(operators=[{'user_id':a.pk,'role':role,'purposes':['recover','review']}],reviewer_id=a.pk,reviewer_role=role,independent_review=False)
 e=add_evidence(a,c.pk,'policy_decision','Explicit synthetic operator routes only; existing source roles unchanged','synthetic:operator-bridge')
 policy({'actor':a,'case':c,'sources':{'policy_decision':e}},OPERATOR,v)

def cancel(test,a,c,family,j,read,operate):
 test.assertTrue(any(r['family']==family and r['id']==j.pk for r in jobs(a,c)[0]))
 Grant.objects.filter(case=c,user=a,action=operate).update(active=False)
 with test.assertRaises(PermissionDenied):recover(a,c.pk,family,j.pk,'cancel','Missing source action cannot be bypassed')
 Grant.objects.filter(case=c,user=a,action=operate).update(active=True)
 recover(a,c.pk,family,j.pk,'cancel','Known pending intent; no effect committed');j.refresh_from_db();test.assertEqual(j.status,'cancelled')

class OperatorRemainingBridgesTests(TestCase):
 def test_invoice_recovery_retains_finance_review_and_no_issuance(self):
  from .settlement_helpers import fixture,draft,approve
  from apps.finance import invoices
  from apps.finance.models import InvoiceIssue
  a,c,cov,p,e=fixture();attach(a,c,'Finance');i=draft(a,c,p);approve(a,c,i,e);j=invoices.reserve(a,c.pk,i.pk,'issue','Finance',rev(c));cancel(self,a,c,'invoice',j,'finance.read','finance.invoice.operate');self.assertFalse(InvoiceIssue.objects.exists())
 def test_controlled_publication_recovery_retains_review_and_no_receipt(self):
  from .document_helpers import publication_fixture,reserved
  from apps.documents.models import PublicationJob,PublicationReceipt
  a,c,owner,source,template,recipient,recipients,storage=publication_fixture();attach(a,c,'PM');p=reserved(a,c,template,source);j=PublicationJob.objects.get(publication=p);cancel(self,a,c,'publication',j,'document.read','document.operate');self.assertFalse(PublicationReceipt.objects.exists())
 def test_engineering_handoff_recovery_cannot_apply_credit(self):
  from .reconciliation_helpers import fixture,run,request,decide
  from apps.baas import corrective
  from apps.baas.models import CorrectiveDelivery
  a,c,engineer,v,b=fixture();attach(a,c,'Finance');r=run(a,c,b);q=request(a,c,r);decide(a,c,q);j=corrective.reserve(a,c.pk,q.pk,'Finance',rev(c));cancel(self,a,c,'engineering',j,'baas.read','baas.corrective.operate');self.assertFalse(CorrectiveDelivery.objects.exists())
 def test_partner_handoff_recovery_cannot_import_usage(self):
  from .partner_helpers import fixture,report,review
  from apps.baas import partner_operations
  from apps.baas.models import PartnerFinanceReceipt,PartnerBillingImport
  a,c,fin,v,cov=fixture();attach(a,c,'PM');r=report(a,c);review(fin,c,r);j=partner_operations.reserve(a,c.pk,r.pk,'PM',rev(c));cancel(self,a,c,'partner',j,'partner.read','partner.finance.operate');self.assertFalse(PartnerFinanceReceipt.objects.exists());self.assertFalse(PartnerBillingImport.objects.exists())
