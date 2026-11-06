from html.parser import HTMLParser
from urllib.parse import urlencode,urlsplit,parse_qs
from django.test import TestCase,Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.identity.models import Grant
from apps.policy.factory_routing_validators import COMPONENT
from apps.policy.models import Configuration
from apps.policy.services import save_draft
from apps.finance.models import InvoiceReview,InvoiceJob
from apps.workflows import factory
from tests.factory_helpers import fixture
from tests.test_factory_routing import configure
from tests.helpers import setup_case

class Links(HTMLParser):
    def __init__(self,body):super().__init__();self.hrefs=[];self.feed(body.decode())
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.hrefs.extend(v for k,v in attrs if k=='href')

class ResponsibilityReviewTests(TestCase):
    def client_for(self,user,csrf=False):
        client=Client(enforce_csrf_checks=csrf);client.force_login(user);return client

    def test_http_draft_validate_activate_preserves_work_and_filters_with_named_versions(self):
        f=fixture();a=f['actor'];a.first_name='Synthetic';a.last_name='Accountable Owner';a.save()
        w=f['work'];client=self.client_for(a);q='Needs & review'
        base=reverse('factory_responsibility',args=[f['case'].pk]);context={'work':w.pk,'queue':'exceptions','q':q}
        url=base+'?'+urlencode(context);returned=reverse('factory_detail',args=[w.pk])+'?'+urlencode({'queue':'exceptions','q':q})
        response=client.get(url);self.assertContains(response,'Synthetic Accountable Owner')
        self.assertEqual(response.context['return_url'],returned);self.assertEqual(len(response.context['current_names']),4)
        self.assertTrue(all(row['status']=='Current workspace access' for row in response.context['current_names']))
        data={**context,'action':'draft','process_owner_id':a.pk,'activity_owner_id':a.pk,'policy_owner_id':'','governance_resolver_id':a.pk,'evidence':f['evidence']['policy_decision'].pk}
        self.assertEqual(client.post(url,data)['Location'],url)
        config=Configuration.objects.filter(case=f['case'],component=COMPONENT).latest('pk')
        response=client.get(url);self.assertContains(response,'Revision 2 · Draft')
        self.assertEqual(response.context['configurations'][0].nominees[2]['name'],'Not assigned')
        for state in ['validated','active']:
            self.assertEqual(client.post(url,{**context,'action':'transition','configuration':config.pk,'state':state})['Location'],url)
        response=client.get(url);self.assertContains(response,'Revision 2 · Active');self.assertContains(response,'Revision 1 · Superseded')
        self.assertEqual(response.context['current_names'][2]['status'],'Unknown')
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())
        w.refresh_from_db();self.assertEqual(w.budget_used,0)
        self.assertEqual(client.post(url,{**context,'action':'transition','configuration':config.pk,'state':'revoked'})['Location'],url)
        self.assertContains(client.get(url),'Revision 2 · Revoked')

    def test_visible_foreign_work_and_tampered_context_cannot_select_another_workspace(self):
        f=fixture();other=fixture(username='other-factory-owner');a=f['actor'];client=self.client_for(a)
        for action in ['case.read','finance.read','factory.read']:Grant.objects.create(case=other['case'],user=a,action=action)
        base=reverse('factory_responsibility',args=[f['case'].pk])
        self.assertEqual(client.get(base,{'work':other['work'].pk}).status_code,404)
        url=base+'?'+urlencode({'work':f['work'].pk,'queue':'decisions','q':'keep'})
        count=Configuration.objects.filter(case=f['case']).count()
        response=client.post(url,{'work':other['work'].pk,'action':'draft'})
        self.assertEqual(response.status_code,404);self.assertEqual(Configuration.objects.filter(case=f['case']).count(),count)
        for key in ['True','0','-1','99999999999999999999999999999','9223372036854775808']:
            with self.subTest(key=key):self.assertEqual(client.get(base,{'work':key}).status_code,404)

    def test_return_destination_is_native_and_foreign_urls_are_ignored(self):
        f=fixture();client=self.client_for(f['actor']);w=f['work']
        base=reverse('factory_responsibility',args=[f['case'].pk])
        response=client.get(base,{'work':w.pk,'queue':'https://untrusted.invalid','q':'x'*200,'next':'https://untrusted.invalid','return_url':'//untrusted.invalid'})
        destination=response.context['return_url'];parsed=urlsplit(destination)
        self.assertEqual(parsed.netloc,'');self.assertEqual(parsed.path,reverse('factory_detail',args=[w.pk]))
        self.assertEqual(parse_qs(parsed.query),{'queue':['needs_me'],'q':['x'*120]})
        self.assertNotContains(response,'href="https://untrusted.invalid')

    def test_revoked_nominee_access_stays_visible_without_granting_invoice_authority(self):
        f=fixture();owner=get_user_model().objects.create_user(username='nominated-only',first_name='Named',last_name='Owner')
        for action in ['case.read','finance.read','factory.read']:Grant.objects.create(case=f['case'],user=owner,action=action)
        configure(f,process_owner_id=owner.pk,activity_owner_id=owner.pk,policy_owner_id=owner.pk)
        url=reverse('factory_responsibility',args=[f['case'].pk]);client=self.client_for(f['actor'])
        self.assertContains(client.get(url),'Named Owner')
        Grant.objects.filter(case=f['case'],user=owner,action='finance.read').update(active=False)
        response=client.get(url);self.assertContains(response,'Named Owner')
        self.assertEqual([row['status'] for row in response.context['current_names'][:3]],['Access needs review']*3)
        self.assertFalse(Grant.objects.filter(user=owner,action='finance.invoice.review').exists())
        self.assertFalse(InvoiceReview.objects.exists());self.assertFalse(InvoiceJob.objects.exists())

    def test_historical_nomination_does_not_disclose_account_after_it_leaves_workspace(self):
        f=fixture();owner,foreign=setup_case(username='foreign-secret');owner.first_name='Other Workspace Secret';owner.save()
        for action in ['case.read','finance.read','factory.read']:Grant.objects.create(case=f['case'],user=owner,action=action)
        configure(f,process_owner_id=owner.pk)
        Grant.objects.filter(case=f['case'],user=owner).delete()
        response=self.client_for(f['actor']).get(reverse('factory_responsibility',args=[f['case'].pk]))
        self.assertContains(response,'Account unavailable in this workspace');self.assertNotContains(response,'Other Workspace Secret')
        self.assertNotContains(response,'foreign-secret')

    def test_unknown_null_draft_is_readable_and_standalone_configuration_remains_available(self):
        f=fixture(responsibility=False)
        save_draft(f['actor'],f['case'].pk,{'component_id':COMPONENT,'value':None})
        response=self.client_for(f['actor']).get(reverse('factory_responsibility',args=[f['case'].pk]))
        self.assertContains(response,'Current assignments need review');self.assertContains(response,'Revision 1 · Draft')
        self.assertIsNone(response.context['return_url']);self.assertTrue(all(row['name']=='Not assigned' for row in response.context['current_names']))

    def test_configuration_and_context_do_not_bypass_current_permission_or_csrf(self):
        f=fixture();a=f['actor'];url=reverse('factory_responsibility',args=[f['case'].pk])+'?'+urlencode({'work':f['work'].pk})
        response=self.client_for(a,csrf=True).post(url,{'action':'draft','work':f['work'].pk})
        self.assertEqual(response.status_code,403)
        Grant.objects.filter(case=f['case'],user=a,action='policy.configure').update(active=False)
        self.assertEqual(self.client_for(a).get(url).status_code,403)

    def test_work_detail_link_preserves_selected_decision_search_and_shows_named_owners(self):
        f=fixture();factory.run_until_wait(f['work'].pk);q='Needs & review'
        url=reverse('factory_detail',args=[f['work'].pk])+'?'+urlencode({'queue':'decisions','q':q})
        response=self.client_for(f['actor']).get(url);self.assertContains(response,'Invoice process owner')
        hrefs=[href for href in Links(response.content).hrefs if '/factory/responsibility/' in href]
        self.assertEqual(len(hrefs),1)
        self.assertEqual(parse_qs(urlsplit(hrefs[0]).query),{'work':[str(f['work'].pk)],'queue':['decisions'],'q':[q]})
