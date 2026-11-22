from urllib.parse import urlencode

from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.core.factory_api.intake import STARTS
from apps.core.models import Case
from apps.workflows.models import FactoryWork
from apps.workflows.native_station_contracts import PROCESSES
from apps.workflows.process_triggers import TRIGGERS
from tests import planning_helpers
from tests.helpers import setup_case
from tests.native_station_helpers import start_station
from tests.process_role_helpers import role_accounts


class TriggerNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.case = setup_case(username='trigger-navigation-owner')

    def test_directory_links_open_real_source_sections_and_filtered_tracking_for_all_63(self):
        self.client.force_login(self.owner)
        directory = self.client.get(reverse('factory_intake'), {'directory': 1})
        api = self.client.get('/api/v1/processes')
        self.assertEqual(api.status_code, 200)
        rows = api.json()['items']
        self.assertEqual(len(rows), 108)
        self.assertEqual(len(STARTS), 25)
        self.assertEqual(len(TRIGGERS), 63)
        self.assertSetEqual(set(TRIGGERS), set(PROCESSES))
        self.assertSetEqual({row['process'] for row in rows if row['guide'] is not None}, set(PROCESSES))
        self.assertContains(directory, 'id="process-directory" open')
        initial_work_count = FactoryWork.objects.count()
        sources = {}
        tracking_page = reverse('project_handoffs', args=[self.case.pk])
        for row in rows:
            guide = row['guide']
            if guide is None:
                continue
            process = row['process']
            with self.subTest(process=process):
                trigger = TRIGGERS[process]
                self.assertContains(directory, f'data-process="{process}"')
                self.assertContains(directory, guide['action'])
                self.assertContains(directory, f'href="{guide["source_url"]}"')
                self.assertContains(directory, f'href="{guide["tracking_url"]}"')
                result = self.client.get(guide['source_url'])
                expected_source = reverse(trigger.screen, args=[self.case.pk])
                self.assertRedirects(result, f'{expected_source}#{trigger.section}', fetch_redirect_response=False)
                if expected_source not in sources:
                    sources[expected_source] = self.client.get(expected_source)
                self.assertContains(sources[expected_source], f'id="{trigger.section}"')
                expected_tracking = tracking_page + '?' + urlencode({'process': process})
                self.assertRedirects(self.client.get(guide['tracking_url']), expected_tracking, fetch_redirect_response=False)
                tracking = self.client.get(expected_tracking)
                self.assertContains(tracking, row['title'])
                self.assertContains(tracking, 'No work for this process is available to you yet.')
                self.assertIn('no-store', tracking['Cache-Control'])
        self.assertEqual(FactoryWork.objects.count(), initial_work_count)
        print(f'PROCESS_NAVIGATION {len(TRIGGERS)} automatic processes, {len(sources)} source screens, {len(STARTS)} Start work types', flush=True)

    def test_project_picker_search_and_explicit_destination_preserve_record_access(self):
        from apps.identity.models import Grant

        nearby = Case.objects.create(tenant=self.case.tenant, kind='project', title='Rehearsal Budget', synthetic=True)
        other = Case.objects.create(tenant='outside-navigation', kind='project', title='Excluded Budget', synthetic=True)
        Grant.objects.bulk_create([
            Grant(case=nearby, user=self.owner, action=action)
            for action in ('case.read', 'finance.read')
        ])
        self.client.force_login(self.owner)
        source = reverse('process_destination', args=['F10', 'source'])
        listing = self.client.get(source)
        self.assertContains(listing, 'Find a project')
        self.assertContains(listing, 'Rehearsal Budget')
        self.assertNotContains(listing, 'Excluded Budget')
        search = self.client.get(source, {'q': 'Rehearsal'})
        target = reverse('finance_performance', args=[nearby.pk]) + '#action-build'
        self.assertContains(search, f'href="{target}"')
        self.assertNotContains(search, str(self.case.pk))
        self.assertRedirects(self.client.get(source, {'project': nearby.pk}), target, fetch_redirect_response=False)
        for choice in (other.pk, 'https://example.invalid', ''):
            self.assertEqual(self.client.get(source, {'project': choice}).status_code, 404)
        self.assertIn('no-store', listing['Cache-Control'])
        self.assertEqual(self.client.post(source, {'project': nearby.pk}).status_code, 405)
        self.assertEqual(Client().get(source).status_code, 302)
        self.assertEqual(self.client.get(reverse('process_destination', args=['B01', 'source'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('process_destination', args=['F10', 'elsewhere'])).status_code, 404)


class TriggerTrackingTests(TransactionTestCase):
    def test_department_filter_tracks_exact_authorised_native_work(self):
        f = planning_helpers.fixture()
        case = f['c']
        selected = start_station(self, 'P17', f['packet'])
        sibling = start_station(self, 'P18', f['packet'])
        people = role_accounts(case)
        self.client.force_login(people['pmo_member'])
        target = reverse('project_handoffs', args=[case.pk])
        scoped_url = f'{target}?process=P17'
        self.assertRedirects(self.client.get(reverse('process_destination', args=['P17', 'track']), {'project': case.pk}),
                             scoped_url, fetch_redirect_response=False)
        page = self.client.get(scoped_url)
        self.assertContains(page, f'href="{reverse("factory_detail", args=[selected.pk])}"')
        self.assertNotContains(page, f'href="{reverse("factory_detail", args=[sibling.pk])}"')
        all_work = self.client.get(target)
        self.assertContains(all_work, f'href="{reverse("factory_detail", args=[sibling.pk])}"')
        api = f'/api/v1/projects/{case.pk}/department-handoffs'
        response = self.client.get(api, {'process': 'P17'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['work_id'] for row in response.json()['items']], [selected.pk])
        self.assertEqual(self.client.get(api, {'process': 'B01'}).status_code, 422)
        self.assertEqual(self.client.get(target, {'process': 'B01'}).status_code, 404)
        self.client.force_login(people['finance_head'])
        self.assertEqual(self.client.get(scoped_url).status_code, 404)
        self.assertEqual(self.client.get(api, {'process': 'P17'}).status_code, 404)
        self.assertNotContains(self.client.get(reverse('process_destination', args=['P17', 'track'])), str(case.pk))
