from django.test import TestCase,override_settings
from django.db import connection
from apps.workflows import readiness as d
from apps.core.services import add_evidence
from .helpers import rev

def enroll(a,c,family):
 e=add_evidence(a,c.pk,'integration_contract','Explicit synthetic readiness dependency; native business approvals remain','synthetic:integration-bridge')
 body={'kind':'adapter','family':family,'implementation':'internal_postgres_session_v1','target_key':'internal:'+family,'credential_ref':'runtime:postgres','credential_revision':'fixture-v1','principal_ref':'principal:'+connection.settings_dict['USER'],'contract_version':'psl.internal-receipts/v1','model_id':None,'capabilities':['health','receipt_lookup'],'data_scope':'public_canary_and_scoped_receipt_metadata_only'}
 r=d.capture(a,c.pk,'dependency',body,e.pk);e=add_evidence(a,c.pk,'integration_selection','Explicit synthetic enrollment before readiness evidence','synthetic:integration-bridge');d.select(a,c.pk,r.pk,e.pk);return r

class ReadinessSourceBridgeTests(TestCase):
 def test_enrolled_invoice_holds_without_issuance(self):
  from .settlement_helpers import fixture,draft,approve
  from apps.finance import invoices,invoice_delivery
  from apps.finance.models import InvoiceIssue
  a,c,cov,p,e=fixture();i=draft(a,c,p);approve(a,c,i,e);j=invoices.reserve(a,c.pk,i.pk,'issue','Finance',rev(c));enroll(a,c,'invoice');invoice_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(InvoiceIssue.objects.exists())
 def test_enrolled_publication_holds_without_delivery(self):
  from .document_helpers import publication_fixture,reserved
  from apps.documents.models import PublicationJob,PublicationReceipt
  from apps.documents.delivery import run_publication_once
  a,c,owner,source,template,recipient,recipients,storage=publication_fixture();p=reserved(a,c,template,source);j=PublicationJob.objects.get(publication=p);enroll(a,c,'publication');run_publication_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(PublicationReceipt.objects.exists())
 def test_enrolled_engineering_request_holds_without_corrective_delivery(self):
  from .reconciliation_helpers import fixture,run,request,decide
  from apps.baas import corrective,corrective_delivery
  from apps.baas.models import CorrectiveDelivery
  a,c,engineer,v,b=fixture();r=run(a,c,b);q=request(a,c,r);decide(a,c,q);j=corrective.reserve(a,c.pk,q.pk,'Finance',rev(c));enroll(a,c,'engineering');corrective_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(CorrectiveDelivery.objects.exists())
 def test_enrolled_partner_handoff_holds_without_usage_import(self):
  from .partner_helpers import fixture,report,review
  from apps.baas import partner_operations,partner_delivery
  from apps.baas.models import PartnerFinanceReceipt,PartnerBillingImport
  a,c,fin,v,cov=fixture();r=report(a,c);review(fin,c,r);j=partner_operations.reserve(a,c.pk,r.pk,'PM',rev(c));enroll(a,c,'partner');partner_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(PartnerFinanceReceipt.objects.exists());self.assertFalse(PartnerBillingImport.objects.exists())
 def test_enrolled_department_route_holds_without_receipt_or_approval(self):
  from .approval_helpers import fixture
  from apps.pmo import approval_routing
  from apps.pmo.models import ApprovalRouteReceipt
  f=fixture();j=approval_routing.reserve(f['actor'],f['case'].pk,f['request'].pk);enroll(f['actor'],f['case'],'approval');approval_routing.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertFalse(ApprovalRouteReceipt.objects.exists())
 @override_settings(OPERATOR_DRILL_DATABASE='test_psl_drill_operators')
 def test_enrolled_restore_holds_while_export_and_backup_continue(self):
  from .operator_helpers import fixture,provision_test_database,effect
  from apps.workflows import operator_delivery
  from apps.workflows.operator_models import RecoveryArtifact
  provision_test_database();f=fixture();_,e=effect(f,'export');_,b=effect(f,'backup',e.pk);j=operator_delivery.reserve(f['actor'],f['case'].pk,f['plan'].pk,'restore',b.pk);enroll(f['actor'],f['case'],'protection');operator_delivery.run_once();j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(RecoveryArtifact.objects.count(),2)
