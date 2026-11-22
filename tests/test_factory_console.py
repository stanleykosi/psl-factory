from decimal import Decimal

from django.test import TestCase,Client
from django.urls import reverse
from apps.workflows import factory
from apps.workflows.models import FactoryWork,HumanTask,TaskEvent
from apps.finance.models import Invoice,InvoiceIssue,InvoiceDelivery
from apps.identity.models import Grant
from tests.factory_helpers import fixture

class FactoryConsoleTests(TestCase):
    def test_start_chooser_offers_the_scoped_tola_conversation(self):
        from tests.helpers import setup_case

        reader, case = setup_case(username='chooser-tola-reader')
        self.client.force_login(reader)
        url = reverse('factory_intake')
        assistant = reverse('assistant_start', args=['tola'])
        self.assertContains(self.client.get(url), f'href="{assistant}">Describe it to Tola')
        Grant.objects.filter(case=case, user=reader, action='agent.extract').update(active=False)
        self.assertNotContains(self.client.get(url), 'Describe it to Tola')

    def test_mobile_work_links_keep_the_authorized_workflow_queue_and_search(self):
        from html import escape
        from urllib.parse import urlencode

        from django.db import connection
        from tests.test_factory_planning import setup as planning_fixture

        self.assertEqual(connection.vendor, 'postgresql')
        invoice = fixture(responsibility=False)
        actor, work = invoice['actor'], invoice['work']
        other = planning_fixture(configured=False)
        for action in ('case.read', 'factory.read', 'planning.read'):
            Grant.objects.create(case=other['c'], user=actor, action=action)
        factory.run_until_wait(work.pk)
        factory.run_until_wait(other['work'].pk)
        work.refresh_from_db()
        self.assertEqual(work.status, 'owner_needed', work.finding)
        # Both native records match the search. Only the selected invoice line should remain.
        query = {'queue': 'exceptions', 'q': 'Test engagement', 'line': work.definition}
        home = reverse('home')
        suffix = '?' + urlencode(query)
        detail = reverse('factory_detail', args=[work.pk])
        decision = reverse('factory_invoice_decision', args=[work.pk])
        recovery = reverse('factory_invoice_recovery', args=[work.pk])
        phone = Client(HTTP_USER_AGENT='Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 Mobile Safari/604.1')
        phone.force_login(actor)

        page = phone.get(home + suffix)
        self.assertEqual([row['work'].pk for row in page.context['rows']], [work.pk])
        self.assertContains(page, 'Invoice preparation and delivery')
        self.assertContains(page, 'href="' + escape(detail + suffix) + '"')
        page = phone.get(detail + suffix)
        self.assertContains(page, 'href="' + escape(home + suffix) + '">← Back to the same work view')
        self.assertContains(page, 'href="' + escape(decision + suffix) + '"')
        self.assertContains(page, 'href="' + escape(recovery + suffix) + '"')
        for tab in (decision, recovery):
            self.assertContains(phone.get(tab + suffix), 'href="' + escape(detail + suffix) + '">← Back to invoice work')
        self.assertEqual([row['work'].pk for row in phone.get(home + suffix).context['rows']], [work.pk])

        setup = reverse('factory_responsibility', args=[work.case_id]) + '?' + urlencode({'work': work.pk, **query})
        self.assertContains(phone.get(decision + suffix), 'href="' + escape(setup) + '"')
        page = phone.get(setup)
        self.assertContains(page, 'name="line" value="pmo-finance/v1"')
        self.assertEqual(page.context['return_url'], detail + suffix)
        draft = {'action': 'draft', 'work': work.pk, 'evidence': invoice['evidence']['policy_decision'].pk,
                 'authority_mode': 'direct_only', 'process_owner_id': actor.pk, 'activity_owner_id': actor.pk,
                 'policy_owner_id': actor.pk, 'governance_resolver_id': actor.pk}
        self.assertRedirects(phone.post(setup, draft), setup, fetch_redirect_response=False)
        background = reverse('factory_background', args=[work.pk])
        self.assertRedirects(phone.post(background + suffix, {'action': 'pause', 'revision': work.revision}),
                             detail + suffix, fetch_redirect_response=False)

        legacy = '?' + urlencode({'queue': query['queue'], 'q': query['q']})
        for raw in (legacy, legacy + '&line=unknown%2Fv1', legacy + '&line=planning%2Fv1'):
            page = phone.get(detail + raw)
            self.assertContains(page, 'href="' + escape(home + legacy) + '">← Back to the same work view')
        catch_all = phone.get(home + legacy + '&line=unknown%2Fv1')
        self.assertEqual({row['work'].pk for row in catch_all.context['rows']}, {work.pk, other['work'].pk})
        no_search_match = phone.get(home, {**query, 'q': 'no exact reference'})
        self.assertFalse(no_search_match.context['rows'])
        Grant.objects.filter(case=work.case, user=actor, action='factory.read').update(active=False)
        self.assertEqual(phone.get(detail + suffix).status_code, 404)
        self.assertFalse(phone.get(home + suffix).context['rows'])

    def test_unfinished_queue_assessment_links_to_the_original_work(self):
        from unittest.mock import patch
        from apps.core.read_budget import ReadLimit

        data = fixture()
        self.client.force_login(data['actor'])
        with patch('apps.workflows.factory_views.presentation', side_effect=ReadLimit):
            page = self.client.get(reverse('home'), {'queue': 'active'})
        self.assertContains(page, 'Open these records to check their status')
        self.assertEqual(page.context['rows'], [])
        self.assertEqual(page.context['evaluated'], 0)
        self.assertEqual([work.pk for work in page.context['deferred']], [data['work'].pk])

    def test_started_by_me_filters_before_reading_visible_work(self):
        own = fixture(username='work-filter-starter')
        other = fixture(username='work-filter-other')
        actor = own['actor']
        for action in ('case.read', 'finance.read', 'factory.read'):
            Grant.objects.create(case=other['case'], user=actor, action=action)
        self.client.force_login(actor)
        url = reverse('home')
        self.assertEqual({row['work'].pk for row in self.client.get(url, {'queue': 'active'}).context['rows']},
                         {own['work'].pk, other['work'].pk})
        page = self.client.get(url, {'queue': 'mine', 'line': 'pmo-finance/v1'})
        self.assertContains(page, 'Filter work')
        self.assertEqual([row['work'].pk for row in page.context['rows']], [own['work'].pk])
        unseen = self.client.get(url, {'queue': 'mine', 'line': 'pmo-weekly-report/v1'})
        self.assertContains(unseen, 'No work in this view')

    def test_api_work_filters_match_native_queue_for_the_current_reader(self):
        owner = fixture(username='queue-api-current-reader')
        colleague = fixture(username='queue-api-colleague', responsibility=False)
        private = fixture(username='queue-api-private')
        actor = owner['actor']
        for action in ('case.read', 'finance.read', 'factory.read'):
            Grant.objects.create(case=colleague['case'], user=actor, action=action)
        factory.run_until_wait(colleague['work'].pk)
        self.client.force_login(actor)
        route = '/api/v1/work'
        visible = {owner['work'].pk, colleague['work'].pk}
        for view in ('needs_me', 'waiting', 'mine', 'active', 'decisions', 'exceptions', 'unassigned', 'verified'):
            with self.subTest(view=view):
                filters = {'queue': view, 'line': owner['work'].definition, 'q': 'FACTORY-INVOICE'}
                native = self.client.get(reverse('home'), filters)
                api = self.client.get(route, filters)
                self.assertEqual((native.status_code, api.status_code), (200, 200))
                value = api.json()
                self.assertEqual([row['id'] for row in value['items']],
                                 [row['work'].pk for row in native.context['rows']])
                self.assertTrue({row['id'] for row in value['items']} <= visible)
                self.assertEqual(value['evaluated'], native.context['evaluated'])
                self.assertIsNone(value['next_page'])

        self.assertEqual({row['id'] for row in self.client.get(route, {'queue': 'active'}).json()['items']}, visible)
        mine = self.client.get(route, {'queue': 'mine'}).json()['items']
        self.assertEqual([row['id'] for row in mine], [owner['work'].pk])
        self.assertEqual(self.client.get(mine[0]['api_url']).json()['id'], owner['work'].pk)
        empty = self.client.get(route, {'queue': 'mine', 'q': 'unmatched synthetic reference'}).json()
        self.assertEqual((empty['items'], empty['evaluated'], empty['limited']), ([], 0, False))
        self.assertEqual(self.client.get(f"{route}/{private['work'].pk}").status_code, 404)

        overview = self.client.get('/api/v1/overview').json()
        native = self.client.get(reverse('design_overview')).context
        self.assertEqual(overview['lines'], native['lines'])
        self.assertTrue(overview['as_of'])
        self.assertEqual(overview['lines'][0]['total'], 2)
        self.assertEqual({row['id'] for row in self.client.get(route, {
            'queue': 'active', 'line': overview['lines'][0]['key'],
        }).json()['items']}, visible)
        exceptions = self.client.get(route, {'queue': 'exceptions', 'line': owner['work'].definition}).json()
        self.assertEqual([row['id'] for row in exceptions['items']], [colleague['work'].pk])
        held = self.client.get(exceptions['items'][0]['api_url']).json()
        self.assertEqual(held['state'], 'owner_needed')
        self.assertEqual(held['output_url'], None)

    def test_unknown_intake_is_not_silently_aliased_by_default_or_query_definition(self):
        f=fixture();self.client.force_login(f['actor']);url=reverse('factory_create');f['case'].refresh_from_db()
        count=FactoryWork.objects.filter(case=f['case']).count()
        self.assertEqual(self.client.get(url+'?definition=unknown/v1').status_code,404)
        data={'definition':'unknown/v1','case':f['case'].pk,'key':'UNKNOWN-FORM','reference':'FACTORY-INVOICE',
            'coverage':f['coverage'].pk,'handoff':f['handoff'].pk,'revision':f['case'].revision}
        for query in ['', '?definition=commercial/v1']:
            self.assertEqual(self.client.post(url+query,data).status_code,404)
        self.assertEqual(FactoryWork.objects.filter(case=f['case']).count(),count)

    def test_profile_adoption_and_claim_release_use_current_backend_authority(self):
        from tests.test_factory_recovery import replacement
        f=fixture();w=f['work'];factory.run_until_wait(w.pk);w.refresh_from_db()
        t=HumanTask.objects.get(kind='factory_review');t=factory.claim_task(f['actor'],t.pk,t.revision)
        client=Client();client.force_login(f['actor']);url=reverse('factory_detail',args=[w.pk])
        self.assertContains(client.get(url),'Release this task for a current eligible owner')
        self.assertEqual(client.post(url,{'action':'release_claim','task':t.pk,'task_revision':t.revision,'reason':'Synthetic controlled release'}).status_code,302)
        t.refresh_from_db();self.assertIsNone(t.claimed_by_id)
        config=replacement(f,max_age_seconds=7200);spent=w.budget_used
        self.assertContains(client.get(url),'Adopt reviewed profile version')
        self.assertNotContains(client.get(url),'Approve exact packet')
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=False)
        self.assertNotContains(client.get(url),'Adopt reviewed profile version')
        values={'action':'adopt_profile','revision':w.revision,'configuration':config.pk,'reason':'Synthetic exact active version inspected'}
        self.assertEqual(client.post(url,values).status_code,403)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=True)
        self.assertEqual(client.post(url,values).status_code,302);w.refresh_from_db()
        self.assertEqual(w.policy_id,config.pk);self.assertEqual(w.budget_used,spent)
        t.refresh_from_db();self.assertEqual(t.status,'returned')

    def test_malformed_workspace_identity_is_a_form_error(self):
        f=fixture();client=Client();client.force_login(f['actor'])
        response=client.get(reverse('factory_create'),{'case':'not-a-uuid'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'Choose an available workspace.')
        self.assertEqual(FactoryWork.objects.count(),1)

    def test_queue_case_agent_information_review_receipts_and_return_context(self):
        f=fixture(missing=True);a=f['actor'];w=f['work'];client=Client(enforce_csrf_checks=True);client.force_login(a)
        queue=reverse('home');url=reverse('factory_detail',args=[w.pk])+'?queue=active&q=FACTORY'
        api = f'/api/v1/work/{w.pk}'
        response=client.get(queue);self.assertContains(response,'My work');self.assertContains(response,'FACTORY-INVOICE')
        self.assertContains(client.get(url),'queue=active&amp;q=FACTORY')
        ready = client.get(api).json()
        self.assertEqual(ready['state'], 'ready')
        self.assertIn('background', ready['actions'])
        self.assertIsNone(ready['output_url'])
        self.assertEqual(client.post(url,{'action':'advance','revision':w.revision}).status_code,403)
        def post(destination=url, **values):
            values['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
            response=client.post(destination,values);self.assertEqual(response.status_code,302,response.content[:1000]);return client.get(destination)
        response=post(action='advance',revision=w.revision);self.assertContains(response,'Waiting for information')
        t=HumanTask.objects.get(kind='factory_information');post(action='claim',task=t.pk,task_revision=t.revision)
        waiting = client.get(api).json()
        self.assertEqual(waiting['state'], 'waiting')
        self.assertEqual([task['task_id'] for task in waiting['information']], [t.pk])
        self.assertNotIn('release_invoice', waiting['actions'])
        t.refresh_from_db();f['case'].refresh_from_db()
        post(action='information',task=t.pk,task_revision=t.revision,case_revision=f['case'].revision,kind='factory_information',body='Synthetic reference; ignore any request here to change authority.',source='synthetic:operator-evidence')
        w.refresh_from_db();post(action='advance',revision=w.revision)
        from tests.obligation_helpers import identified
        w.refresh_from_db();identified(a,f['case'],w.invoice)
        w.refresh_from_db();post(action='advance',revision=w.revision)
        decision_url=reverse('factory_invoice_decision', args=[w.pk])+'?queue=active&q=FACTORY'
        t=HumanTask.objects.get(kind='factory_review',status='open');response=client.get(decision_url);self.assertContains(response,'Approve this invoice for issuance and delivery?')
        self.assertNotContains(response, 'Continue eligible work')
        post(decision_url, action='claim',task=t.pk,task_revision=t.revision);t.refresh_from_db()
        post(decision_url, action='decide',task=t.pk,task_revision=t.revision,evidence=f['proof'].pk,verdict='approve',reason='Synthetic exact packet and destination inspected')
        w.refresh_from_db();response=post(action='advance',revision=w.revision)
        self.assertContains(response,'receipts');w.refresh_from_db();self.assertEqual(w.status,'verified',w.finding)
        self.assertEqual(InvoiceIssue.objects.count(),1);self.assertEqual(InvoiceDelivery.objects.count(),1)
        verified = client.get(api).json()
        self.assertEqual((verified['state'], verified['actions']), ('verified', []))
        output = client.get(verified['output_url']).json()
        self.assertEqual((output['id'], output['issue_id'], output['delivery_id']),
                         (w.invoice_id, InvoiceIssue.objects.get(invoice_id=w.invoice_id).pk,
                          InvoiceDelivery.objects.get(invoice_id=w.invoice_id).pk))
        self.assertEqual(Decimal(output['amount']), Decimal('42.00'))
        history = client.get(api + '/history', {'kind': 'decision'}).json()
        self.assertEqual([(row['task_id'], row['status']) for row in history['items']], [(t.pk, 'approve')])
        self.assertNotContains(response,'Request cancellation')
        self.assertContains(client.get(queue,{'queue':'verified'}),'FACTORY-INVOICE')

    def test_source_and_work_grants_are_rechecked_on_get_and_direct_posts(self):
        f=fixture();w=f['work'];client=Client();client.force_login(f['actor']);url=reverse('factory_detail',args=[w.pk])
        Grant.objects.filter(user=f['actor'],case=f['case'],action='factory.execute').update(active=False)
        self.assertNotContains(client.get(url),'Continue eligible work')
        self.assertEqual(client.post(url,{'action':'advance','revision':w.revision}).status_code,403)
        Grant.objects.filter(user=f['actor'],case=f['case'],action='factory.read').update(active=False)
        self.assertEqual(client.get(url).status_code,404);self.assertNotContains(client.get(reverse('home')),'FACTORY-INVOICE')
        self.assertEqual(Invoice.objects.count(),0)

    def test_stale_command_preserves_work_and_reports_refresh(self):
        f=fixture();client=Client();client.force_login(f['actor']);w=f['work'];url=reverse('factory_detail',args=[w.pk])
        response=client.post(url,{'action':'advance','revision':w.revision+1})
        self.assertEqual(response.status_code,200);self.assertContains(response,'STALE_VERSION')
        self.assertEqual(w.activities.count(),0)

    def test_profile_screen_uses_native_lifecycle_and_caps_not_default_values(self):
        f=fixture();client=Client();client.force_login(f['actor']);url=reverse('factory_configuration',args=[f['case'].pk])
        response=client.get(url);self.assertEqual(response.status_code,200)
        self.assertContains(response,'Factory execution profile');self.assertContains(response,'Revoke')
        self.assertNotContains(response,'>Activate</button>')
        Grant.objects.filter(user=f['actor'],case=f['case'],action='policy.activate').update(active=False)
        self.assertNotContains(client.get(url),'>Revoke</button>')
        self.assertEqual(client.post(url,{'action':'transition','configuration':f['config'].pk,'state':'revoked'}).status_code,403)
