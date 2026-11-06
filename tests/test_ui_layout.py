"""Staff presentation preserves native permissions, source facts, forms and read-only browsing."""
from pathlib import Path
from django.conf import settings
from django.test import TestCase,Client
from django.template.loader import get_template
from django.urls import reverse
from apps.core.models import Case,Evidence,Audit
from apps.identity.models import Grant
from apps.core.templatetags.studio_ui import workspace_name,workspace_sections
from tests.helpers import setup_case,rev
from django.core.exceptions import ValidationError
from apps.core import workbench


class StudioLayoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):cls.a,cls.c=setup_case(username='layout-reviewer')

    def client_for(self,csrf=False):
        client=Client(enforce_csrf_checks=csrf);client.force_login(self.a);return client

    def test_every_template_compiles_after_shared_shell_and_copy_changes(self):
        for path in sorted((settings.BASE_DIR/'templates').rglob('*.html')):
            with self.subTest(template=path.name):get_template(path.relative_to(settings.BASE_DIR/'templates').as_posix())

    def test_overview_preserves_actual_names_escaping_search_and_no_development_badges(self):
        self.c.title='Client <script>alert(1)</script>';self.c.save(update_fields=['title'])
        client=self.client_for();response=client.get(reverse('workspace_overview'),{'q':'Client'})
        self.assertContains(response,'Overview');self.assertContains(response,'Search workspaces')
        self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>alert(1)</script>')
        for text in ['Synthetic demonstration','Revision ','UUID','Process coverage','Evidence to owned action']:self.assertNotContains(response,text)
        self.assertEqual(response['Cache-Control'],'no-store')
        self.assertNotContains(client.get(reverse('workspace_overview'),{'q':'missing-title'}),'Client &lt;script&gt;')

    def test_friendly_sample_names_do_not_change_original_records_or_real_workspace_titles(self):
        self.c.title='Synthetic F01 duplicate decisions and corrected references';self.c.save(update_fields=['title'])
        response=self.client_for().get(reverse('workspace_overview'),{'q':'Transaction corrections'})
        self.assertContains(response,'Transaction corrections');self.assertContains(response,'Sample data')
        self.assertNotContains(response,'Synthetic F01');self.c.refresh_from_db()
        self.assertEqual(self.c.title,'Synthetic F01 duplicate decisions and corrected references')
        self.c.synthetic=False;self.c.save(update_fields=['synthetic'])
        self.assertEqual(workspace_name(self.c),self.c.title)
        self.assertEqual(workspace_name({'title':'AF13 synthetic evidence and owner validation','synthetic':True}),'Operational readiness')

    def test_grouped_case_navigation_is_permission_based_and_all_links_use_the_case(self):
        groups=workspace_sections(self.c,{'case.read','meeting.read','finance.read','policy.read'})
        names={g['title'] for g in groups};self.assertEqual(names,{'Projects','Finance','Workspace settings'})
        for group in groups:
            for link in group['links']:self.assertIn(str(self.c.pk),link['url'])
        self.assertFalse(workspace_sections(self.c,{'case.read'}))
        client=self.client_for();response=client.get(reverse('case',args=[self.c.pk]))
        self.assertContains(response,'area-grid');self.assertContains(response,'Meetings and actions')
        Grant.objects.filter(user=self.a,case=self.c,action__in=['finance.read','policy.read','meeting.read','ledger.agent.read','payment.read','d03.read','hrfinance.read','payroll.read','bu.read','schedules.read','ppe.read','recognition.read']).update(active=False)
        response=client.get(reverse('case',args=[self.c.pk]))
        self.assertNotContains(response,'href="'+reverse('finance_settlement',args=[self.c.pk])+'"')
        self.assertNotContains(response,'href="'+reverse('policy',args=[self.c.pk])+'"')

    def test_restyled_document_capture_keeps_csrf_native_revision_and_exact_source(self):
        client=self.client_for(True);url=reverse('case',args=[self.c.pk]);client.get(url)
        value={'action':'evidence','revision':rev(self.c),'kind':'document','body':'Exact client brief <script>private()</script>','source':'internal:layout-review'}
        self.assertEqual(client.post(url,value).status_code,403)
        response=client.post(url,dict(value,csrfmiddlewaretoken=client.cookies['csrftoken'].value))
        self.assertEqual(response.status_code,302)
        row=Evidence.objects.get(case=self.c);self.assertEqual(row.body,value['body']);self.assertEqual(row.source,value['source'])
        self.assertContains(client.get(url),'&lt;script&gt;private()&lt;/script&gt;')

    def test_browsing_does_not_create_business_records_or_expose_revoked_workspace(self):
        client=self.client_for();before=(Case.objects.count(),Evidence.objects.count(),Audit.objects.count(),Grant.objects.count())
        for url in [reverse('home'),reverse('work_inbox'),reverse('case',args=[self.c.pk]),reverse('document_inbox'),reverse('project_views')]:
            self.assertEqual(client.get(url).status_code,200)
        self.assertEqual(before,(Case.objects.count(),Evidence.objects.count(),Audit.objects.count(),Grant.objects.count()))
        Grant.objects.filter(user=self.a,case=self.c,action='case.read').update(active=False)
        self.assertEqual(client.get(reverse('case',args=[self.c.pk])).status_code,404)
        self.assertNotContains(client.get(reverse('home')),str(self.c.pk))

    def test_finance_navigation_filters_before_pagination_and_rechecks_current_access(self):
        other=Case.objects.create(title='Restricted account',tenant=self.c.tenant,kind='project',synthetic=True)
        Grant.objects.create(user=self.a,case=other,action='case.read')
        client=self.client_for();response=client.get(reverse('home'),{'area':'finance'})
        self.assertContains(response,str(self.c.pk));self.assertNotContains(response,str(other.pk))
        Grant.objects.create(user=self.a,case=other,action='finance.read')
        result=workbench.discover(self.a,area='finance',page_size=1)
        self.assertIsNotNone(result['next_cursor'])
        with self.assertRaises(ValidationError):workbench.discover(self.a,page_size=1,cursor=result['next_cursor'])
        Grant.objects.filter(user=self.a,case=self.c,action='finance.read').update(active=False)
        self.assertNotContains(client.get(reverse('home'),{'area':'finance'}),str(self.c.pk))
        self.assertContains(client.get(reverse('home'),{'area':'invalid'}),'Select a valid choice')
