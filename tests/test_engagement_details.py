import json
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase
from django.db import transaction,connection,DatabaseError,close_old_connections
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test.utils import CaptureQueriesContext
from pathlib import Path
from apps.core.models import ClientContactRevision
from apps.core.services import add_evidence
from apps.core import client_contacts
from apps.identity.models import Grant
from apps.policy.engagement_validators import REGISTER,REGISTER_V2,validate_reference
from apps.policy.services import active_component,reference_values
from apps.pmo import engagement as d,engagement_details as details,engagement_forms as forms,planning
from apps.workflows import factory,factory_engagement
from tests.test_engagement_intake import EngagementIntakeTests,activate
from tests.helpers import rev,setup_case


class EngagementDetailsTests(TransactionTestCase):
    def ready(self,requirements=None):
        a,c,e,p,proof,values=EngagementIntakeTests().ready()
        sample=json.loads(Path('fixtures/engagement-registration-details.json').read_text())
        rules={**sample['registration'],'required_details':requirements or sample['complete_test_requirements']}
        activate(a,c,REGISTER,rules,proof)
        return a,c,e,p,proof,rules

    def contact(self,a,c,e,name='Fictional client contact'):
        return client_contacts.save(a,c,'project',{'revision':rev(c),'evidence':e,'customer':'',
            'client_name':'Fictional client','name':name,'email':'contact@example.invalid','role':'Project sponsor'})

    def save(self,a,c,e,p,contact=None,key='facts',start='2027-01-15'):
        return details.save(a,c.pk,'SYN-DETAILS',p.pk,e.pk,key,start,contact.pk if contact else None,True)

    def register(self,a,c,e,p,saved,key='register'):
        return d.register(a,c.pk,'SYN-DETAILS','PMO Lead',e.pk,p.pk,key,saved.pk if saved else None)

    def sql_current(self,registration):
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_engagement_registration_details_current(%s)',[registration.pk])
            return cursor.fetchone()[0]

    def test_saved_facts_unknown_requirements_hold_only_registration(self):
        a,c,e,p,proof,rules=self.ready({'planned_start':None,'client_contact':None})
        saved=self.save(a,c,e,p,start=None)
        self.assertIsNone(saved.planned_start);self.assertIsNone(saved.contact_id)
        self.assertEqual(details.read(a,c,saved.pk)['planned_start'],None)
        self.assertIsNotNone(d.current_assignment(c))
        with self.assertRaisesMessage(ValidationError,'Decide whether'):self.register(a,c,e,p,saved)
        self.assertFalse(d.Identifier.objects.exists())
        self.assertEqual(details.Details.objects.count(),1)
        self.assertEqual(planning.report(a,c.pk)['project_details']['client_contact'],'unknown')

    def test_exact_binding_retry_export_and_private_planning_handoff(self):
        a,c,e,p,proof,rules=self.ready();contact=self.contact(a,c,e);saved=self.save(a,c,e,p,contact)
        self.assertEqual(self.save(a,c,e,p,contact).pk,saved.pk)
        registration=self.register(a,c,e,p,saved)
        self.assertEqual(self.register(a,c,e,p,saved).pk,registration.pk)
        self.assertTrue(self.sql_current(registration))
        self.assertEqual(d.current_registration(c).pk,registration.pk)
        summary=planning.report(a,c.pk)['project_details']
        self.assertEqual(summary['client_contact'],'recorded')
        self.assertNotIn(contact.email,json.dumps(summary));self.assertNotIn(contact.name,json.dumps(summary))
        value=details.planning_context(a,c)
        self.assertEqual(value['client_contact']['revision'],contact.pk)
        self.assertEqual(value['planned_start'],'2027-01-15')
        export=d.export_registration(a,c.pk,'public-export')
        self.assertNotIn(contact.name,export.body);self.assertNotIn(contact.email,export.body)
        self.assertNotIn('planned_start',json.loads(export.body))
        with self.assertRaises(ValidationError):self.register(a,c,e,p,None)
        for model in [details.Details,details.Binding]:
            with self.assertRaises(DatabaseError),transaction.atomic():model.objects.all().update(created_at=timezone.now())

    def test_configured_required_fields_and_foreign_billing_or_old_contacts_rejected(self):
        a,c,e,p,proof,rules=self.ready()
        unknown=self.save(a,c,e,p,start=None)
        with self.assertRaisesMessage(ValidationError,'start date'):self.register(a,c,e,p,unknown)
        dated=self.save(a,c,e,p,key='dated')
        with self.assertRaisesMessage(ValidationError,'project contact'):self.register(a,c,e,p,dated)
        contact=self.contact(a,c,e);self.contact(a,c,e,'Corrected fictional contact')
        with self.assertRaises(ValidationError):self.save(a,c,e,p,contact,key='old-contact')
        other,foreign=setup_case(username='foreign-details');foreign_e=add_evidence(other,foreign.pk,'engagement_source','Source','synthetic:foreign')
        foreign_contact=self.contact(other,foreign,foreign_e)
        with self.assertRaises(ValidationError):self.save(a,c,e,p,foreign_contact,key='foreign-contact')
        with self.assertRaises(ValidationError):details.save(a,c.pk,'SYN-DETAILS',p.pk,e.pk,'unattested',checked=False)
        with self.assertRaises(ValidationError):details.save(a,c.pk,'SYN-DETAILS',p.pk,e.pk,'bad-date','2027-02-31',checked=True)

    def test_contact_successor_and_original_owner_revocation_invalidate_read_and_sql(self):
        a,c,e,p,proof,rules=self.ready();contact=self.contact(a,c,e);saved=self.save(a,c,e,p,contact)
        registration=self.register(a,c,e,p,saved)
        self.contact(a,c,e,'New contact')
        with self.assertRaises(ValidationError):d.current_registration(c)
        with self.assertRaises(ValidationError):details.read(a,c,saved.pk)
        self.assertFalse(self.sql_current(registration))
        current=ClientContactRevision.objects.filter(case=c).latest('number')
        replacement=self.save(a,c,e,p,current,key='replacement')
        registration=self.register(a,c,e,p,replacement,key='corrected-registration')
        self.assertTrue(self.sql_current(registration))
        Grant.objects.filter(user=a,case=c,action='engagement.capture').update(active=False)
        with self.assertRaises(PermissionDenied):details.read(a,c,replacement.pk)
        self.assertFalse(self.sql_current(registration))

    def test_planning_only_reader_never_gets_contact_and_retries_cannot_change_details(self):
        a,c,e,p,proof,rules=self.ready();contact=self.contact(a,c,e);saved=self.save(a,c,e,p,contact)
        self.register(a,c,e,p,saved)
        successor=self.save(a,c,e,p,contact,key='successor',start='2027-01-16')
        with self.assertRaises(ValidationError):self.register(a,c,e,p,successor)
        user=get_user_model().objects.create_user(username='planning-only')
        Grant.objects.bulk_create([Grant(user=user,case=c,action=k) for k in ['case.read','planning.read']])
        self.assertIsNone(planning.report(user,c.pk)['project_details'])
        with self.assertRaises(PermissionDenied):details.read(user,c,saved.pk)

    def test_bounded_selectors_keep_old_selected_metadata_and_legacy_forms(self):
        a,c,e,p,proof,rules=self.ready()
        for i in range(55):add_evidence(a,c.pk,'engagement_source','Large source body '*100,'synthetic:extra-'+str(i))
        field=forms.evidence_field(c,{'evidence_id':e.pk})
        rows=list(field.queryset)
        self.assertLessEqual(len(rows),51);self.assertIn(e.pk,[r.pk for r in rows])
        self.assertTrue(all('body' in r.get_deferred_fields() for r in rows))
        self.client.force_login(a)
        page=self.client.get(reverse('engagement',args=[c.pk]))
        self.assertContains(page,'Agreed planned start date');self.assertContains(page,'Registration settings')
        response=self.client.post(reverse('engagement',args=[c.pk]),{'action':'register','revision':rev(c),'value':'SYN-DETAILS',
            'role':'PMO Lead','evidence_id':e.pk,'plan_id':p.pk,'key':'legacy-missing-details'})
        self.assertContains(response,'Save and select the project details')
        self.assertFalse(d.Identifier.objects.exists())

    def test_concurrent_saves_and_registration_converge(self):
        a,c,e,p,proof,rules=self.ready();contact=self.contact(a,c,e);barrier=Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                saved=self.save(a,c,e,p,contact)
                return self.register(a,c,e,p,saved).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(details.Details.objects.count(),1)
        self.assertEqual(details.Binding.objects.count(),1);self.assertEqual(d.Identifier.objects.count(),1)

    def test_native_factory_human_details_then_registration_and_verification(self):
        from tests.test_factory_engagement import setup,assign
        f=setup();a,c,e=f['a'],f['c'],f['e'];factory.run_until_wait(f['w'].pk);assign(f);factory.run_until_wait(f['w'].pk)
        proof=f['policy'];p=add_evidence(a,c.pk,'plan','Synthetic actual plan','synthetic:details-plan')
        rules=json.loads(Path('fixtures/engagement-intake.json').read_text())['registration']
        activate(a,c,REGISTER,{**rules,'required_details':{'planned_start':False,'client_contact':False}},proof)
        f['w'].refresh_from_db()
        saved=factory_engagement.human(a,f['w'].pk,f['w'].revision,rev(c),'details',{
            'reference':'SYN-DETAILS','plan_id':p.pk,'evidence_id':e.pk,'key':'human-details','checked':True})
        f['w'].refresh_from_db()
        factory_engagement.human(a,f['w'].pk,f['w'].revision,rev(c),'register',{
            'value':'SYN-DETAILS','role':'PMO Lead','plan_id':p.pk,'evidence_id':e.pk,'key':'human-register','details_id':saved.pk})
        factory.run_until_wait(f['w'].pk);f['w'].refresh_from_db()
        self.assertTrue(factory_engagement.verified_output(f['w'])['verified'])

    def test_v2_schema_and_plain_settings_preserve_undecided_values(self):
        from types import SimpleNamespace
        a,c,e,p,proof,rules=self.ready({'planned_start':None,'client_contact':None})
        value=validate_reference(REGISTER,SimpleNamespace(schema_ref=REGISTER_V2,content=rules),c)
        self.assertIsNone(value['required_details']['client_contact'])
        bad={**rules,'required_details':{'planned_start':'yes','client_contact':False}}
        with self.assertRaises(ValidationError):validate_reference(REGISTER,SimpleNamespace(schema_ref=REGISTER_V2,content=bad),c)
        form=forms.RegistrationRulesForm(c,{'registration_roles':['PMO Lead'],'namespace':'synthetic-v2',
            'format':'ascii_token','max_length':100,'planned_start':'','client_contact':'','evidence_id':proof.pk})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.value()['required_details'],{'planned_start':None,'client_contact':None})

    def test_won_proposal_manager_is_only_a_current_permission_checked_suggestion(self):
        from tests import test_rfp as upstream
        a,c,e,t,route=upstream.fixture()
        response=upstream.response(a,c,e);upstream.approve(a,c,e,response);submission=upstream.submit(a,c,e,t,response)
        outcome=upstream.rfp.outcome(a,c.pk,submission.pk,'won',timezone.now(),'Client',e['rfp_outcome'].pk,'Synthetic won bid',rev(c))
        disposition=upstream.rfp.dispose(a,c.pk,outcome.pk,None,rev(c))
        d.capture(a,c.pk,'A',e['rfp_outcome'].pk,'won-rfp','won-capture',disposition.pk)
        self.assertEqual(d.won_rfp_manager(a,c)['pm_id'],a.pk)
        self.assertIsNone(d.latest(c,'assignment'))
        Grant.objects.filter(user=a,case=c,action='rfp.read').update(active=False)
        with self.assertRaises(PermissionDenied):d.won_rfp_manager(a,c)
        Grant.objects.filter(user=a,case=c,action='rfp.read').update(active=True)
        Grant.objects.filter(user=a,case=c,action='engagement.read').update(active=False)
        with self.assertRaises(PermissionDenied):d.won_rfp_manager(a,c)

    def test_original_contact_owner_access_is_checked_independently(self):
        a,c,e,p,proof,rules=self.ready()
        owner=get_user_model().objects.create_user(username='source-contact-owner')
        Grant.objects.bulk_create([Grant(user=owner,case=c,action=k) for k in ['case.read','engagement.read','engagement.capture']])
        contact=self.contact(owner,c,e)
        saved=self.save(a,c,e,p,contact);registration=self.register(a,c,e,p,saved)
        Grant.objects.filter(user=owner,case=c,action='engagement.capture').update(active=False)
        with self.assertRaises(PermissionDenied):details.read(a,c,saved.pk)
        self.assertFalse(self.sql_current(registration))

    def test_database_prevents_registration_without_the_required_exact_binding(self):
        a,c,e,p,proof,rules=self.ready()
        assignment=d.current_assignment(c)
        cfg=active_component(REGISTER,c)
        data={'capture':d.current_capture(c).pk,'assignment':assignment.pk,'value':'SYN-BYPASS','plan':p.pk,
              'plan_sha256':p.sha256,'policy':cfg.pk,'role':'PMO Lead','authority':{},
              'namespace':rules['namespace'],'normalized':'syn-bypass','previous_registration':None}
        with self.assertRaises(DatabaseError),transaction.atomic():
            d.Record.objects.create(case=c,kind='registration',operation_key='bypass',data=data,evidence=e,actor=a)
            with connection.cursor() as cursor:cursor.execute('SET CONSTRAINTS psl_engagement_details_registration IMMEDIATE')
        self.assertFalse(d.Record.objects.filter(operation_key='bypass').exists())

    def test_stale_legacy_details_form_cannot_reattach_facts_to_a_successor_source(self):
        a,c,e,p,proof,rules=self.ready();capture=d.current_capture(c)
        form=forms.DetailsForm(c)
        self.assertEqual(form.initial['capture_id'],capture.pk)
        d.capture(a,c.pk,'B',e.pk,'successor-source','capture-successor')
        self.client.force_login(a)
        response=self.client.post(reverse('engagement',args=[c.pk]),{'action':'details','operation':'details','capture_id':capture.pk,
            'key':'stale-browser-save','reference':'SYN-DETAILS','plan_id':p.pk,'evidence_id':e.pk,'checked':'on'})
        self.assertContains(response,'The engagement source changed')
        self.assertFalse(details.Details.objects.exists())
        with self.assertRaises(ValidationError):details.save(a,c.pk,'SYN\nREFERENCE',p.pk,e.pk,'bad-reference',checked=True)

    def test_contact_capture_returns_to_the_exact_authorised_registration_work(self):
        from tests.test_factory_engagement import setup
        f=setup();a,c=f['a'],f['c'];self.client.force_login(a)
        url=reverse('design_client_project',args=[c.pk])+'?work='+str(f['w'].pk)
        page=self.client.get(url)
        self.assertContains(page,'Return to project registration')
        response=self.client.post(url,{'purpose':'project','revision':rev(c),'evidence':f['e'].pk,'customer':'',
            'client_name':'Fictional client','name':'Fictional registration contact','email':'contact@example.invalid','role':'Sponsor'})
        self.assertRedirects(response,url)
        self.assertEqual(ClientContactRevision.objects.get(case=c).name,'Fictional registration contact')
        Grant.objects.filter(user=a,case=c,action='factory.read').update(active=False)
        self.assertNotContains(self.client.get(url),'Return to project registration')
        self.assertNotContains(self.client.get(reverse('design_client_project',args=[c.pk])+'?work=9999999999999999999999999999999'),
                               'Return to project registration')

    def test_fact_reader_checks_metadata_without_loading_source_bodies(self):
        a,c,e,p,proof,rules=self.ready();contact=self.contact(a,c,e);saved=self.save(a,c,e,p,contact)
        with CaptureQueriesContext(connection) as queries:
            result=details.read(a,c,saved.pk)
        self.assertEqual(result['client_contact']['revision'],contact.pk)
        selected_columns=[row['sql'].split(' FROM ',1)[0] for row in queries.captured_queries]
        self.assertFalse(any('"core_evidence"."body"' in sql for sql in selected_columns))
        self.assertLess(len(queries),50)
