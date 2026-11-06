from django.test import TestCase
from apps.identity.models import Grant
from apps.finance import schedules as d
from .schedule_helpers import fixture,detail,row,review,inventory,accepted_equity

class ScheduleHumanInterfaceTests(TestCase):
 def setUp(self):
  self.f=fixture();self.url=f'/cases/{self.f["case"].pk}/finance/schedules/';self.client.force_login(self.f['reviewer'])
 def test_human_board_separates_parent_children_and_supplement(self):
  f=self.f;w=detail(f,[row(f,'a','-600'),row(f,'b','-400'),row(f,'supplement','20','additive')]);review(f,w);response=self.client.get(self.url)
  for text in ['Parent and adjustment reconciliation','Child breakdown','Separate supplements','Explained total','Current human approval','-980']:self.assertContains(response,text)
  self.assertEqual(response['Cache-Control'],'no-store')
 def test_reviewed_human_report_and_explicit_json_share_same_result(self):
  f=self.f;w=detail(f);review(f,w);url=self.url+str(w.pk)+'/report/';response=self.client.get(url);self.assertContains(response,'Reviewed income detail');self.assertContains(response,'Child breakdown');self.assertContains(response,'-1000');self.assertEqual(response['Cache-Control'],'no-store');value=self.client.get(url+'?format=json').json();self.assertEqual(value['result']['adjusted_total'],'-1000');self.assertFalse(value['ledger_posted'])
 def test_inventory_report_explains_definition_level_and_exclusions(self):
  f=self.f;w=inventory(f,accepted_equity(f));review(f,w);response=self.client.get(self.url+str(w.pk)+'/report/')
  for text in ['Reviewed schedule inventory','equity','definition','intercompany','Excluded pending evidence','undecided','Native workbook verification: unavailable']:self.assertContains(response,text)
 def test_revoked_review_and_report_grant_cannot_read_current_report(self):
  f=self.f;w=detail(f);review(f,w);review(f,w,'revoke');url=self.url+str(w.pk)+'/report/';self.assertEqual(self.client.get(url).status_code,409);response=self.client.get(self.url);self.assertContains(response,'Human review pending, held or historical');review(f,w);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.report').update(active=False);self.assertEqual(self.client.get(url).status_code,403)
