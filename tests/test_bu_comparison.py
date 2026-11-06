from copy import deepcopy
from django.test import TestCase
from unittest.mock import patch
from django.urls import reverse
from apps.identity.models import Grant
from apps.finance.models import FinanceRun,BUWork,BUReport
from apps.agents.bu import investigate
from django.core.exceptions import ValidationError
from apps.finance import bu as domain,analysis
from apps.policy.bu_validators import SOURCE,MAPPING,AUTH
from apps.core.services import add_evidence
from .finance_analysis_helpers import fixture as finance_fixture,pipeline
from .bu_helpers import configure,policy,source,event,publish
from .helpers import rev,setup_case
class BUFinanceComparisonTests(TestCase):
 @classmethod
 def setUpTestData(cls):
  a,c,e,cfg,configs,s,t,recipient=finance_fixture();f={'preparer':a,'reviewer':a,'manager':recipient,'case':c,'e':e};configure(f,catalogue=False);Grant.objects.get_or_create(case=c,user=recipient,action='case.read')
  v=deepcopy(f['bu_config']['authority']);v['independent_reviewer']=False;policy(f,AUTH,v)
  v=deepcopy(f['bu_config']['source']);v.update(from_period='2026-10',to_period='2026-10',currency='NGN',company_comparison='finance_allocation_required');policy(f,SOURCE,v)
  v=deepcopy(f['bu_config']['mapping']);v.update(from_period='2026-10',to_period='2026-10');v['mappings'][0]['bu']='alpha';policy(f,MAPPING,v)
  f['bu_config']['export'].update(period='2026-10',currency='NGN',control_total='-1000',rows=[{'event_id':'E1','amount':'-1000','tags':['DIRECT-A']}]);m,b,r=pipeline(a,c,s);f['comparison']={'run_id':b.pk,'metric':'revenue'};f['finance']=b;cls.f=f
 def test_actual_finance_allocation_metric_ties_to_current_event_source(self):
  f=self.f;w=event(f,comparison=f['comparison']);self.assertTrue(w.payload['finance_company_comparison']['matches']);p=publish(f,w);self.assertEqual(domain.read_report(f['manager'],p.pk)['by_bu'],{'alpha':'-1000.00'})
 def test_mismatch_and_wrong_case_comparison_cannot_certify_rollup(self):
  f=self.f;s=source(f,control_total='999',rows=[{'event_id':'E1','amount':'999','tags':['DIRECT-A']}]);w=event(f,s=s,comparison=f['comparison']);self.assertIn('finance_company_comparison_mismatch',w.metadata['codes'])
  with self.assertRaises(ValidationError):publish(f,w)
  ref=dict(f['comparison'],run_id=999999)
  with self.assertRaises(ValidationError):event(f,key='foreign',s=s,comparison=ref)
 def test_finance_source_revision_invalidates_published_reference(self):
  f=self.f;p=publish(f,event(f,comparison=f['comparison']));s=f['finance'].source
  analysis.capture_source(f['preparer'],f['case'].pk,s.batch_id,s.entity,s.accounting_basis,s.extracted_at,s.completeness,s.control_total,s.evidence_id,rev(f['case']))
  with self.assertRaises(ValidationError):domain.read_report(f['manager'],p.pk)

 def test_comparison_metadata_board_and_agent_never_load_finance_result(self):
  f=self.f;publish(f,event(f,comparison=f['comparison']))
  def forbidden(_):raise AssertionError('Finance result values accessed on metadata-only path')
  with patch.object(FinanceRun,'result',new=property(forbidden)),patch.object(BUWork,'payload',new=property(forbidden)),patch.object(BUReport,'payload',new=property(forbidden)):
   a=investigate(f['preparer'],f['case'].pk,rev(f['case']));self.assertFalse(a.result['finance_comparison_values_read']);self.client.force_login(f['manager']);r=self.client.get(reverse('bu',args=[f['case'].pk]));self.assertEqual(r.status_code,200);self.assertContains(r,'verification runs on controlled inspection');self.assertNotContains(r,'-1000.00')
