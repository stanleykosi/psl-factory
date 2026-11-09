"""P41 browser-discovered form precision and native-authority queue regressions."""
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from html.parser import HTMLParser
from django import forms
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.policy.services import active_component, reference_values, transition
from apps.policy.role_assignments import draft as draft_roles
from apps.workflows import factory_reporting as reporting
from apps.workflows.factory_reporting_views import ReportLocalDateTimeField, InputsForm
from apps.workflows.factory_views import presentation
from apps.workflows.models import FactoryWork
from apps.documents.models import Version, ControlledReview, Publication, PublicationReceipt
from apps.pmo.meetings import change_action
from tests import test_factory_reporting as base
from tests.helpers import rev
from tests.document_helpers import artifact


class Controls(HTMLParser):
    def __init__(self,html):
        super().__init__();self.fields={};self.feed(html)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='input' and attrs.get('name') in ['start_at','end_at']:
            self.fields[attrs['name']]=attrs


class LocalReportTimeTests(SimpleTestCase):
    def test_offset_strings_and_datetime_objects_render_local_seconds_and_milliseconds(self):
        class Form(forms.Form):
            value=ReportLocalDateTimeField()
        with timezone.override('Africa/Lagos'):
            for month in [1,7]:
                original=datetime(2026,month,15,22,58,47,123456,tzinfo=dt_timezone.utc)
                for value in [original,original.isoformat()]:
                    field=Form(initial={'value':value})['value']
                    rendered=str(field)
                    self.assertIn(f'value="2026-{month:02d}-15T23:58:47.123"',rendered)
                    self.assertIn('type="datetime-local"',rendered)
                    self.assertIn('step="any"',rendered)
                    self.assertNotIn('+00:00',rendered)
                    self.assertNotIn('+01:00',rendered)
        with timezone.override('UTC'):
            self.assertIn('2026-07-15T22:58:47.123',str(Form(initial={'value':original.isoformat()})['value']))

    def test_invalid_bound_value_stays_a_validation_error_without_render_crash(self):
        class Form(forms.Form):
            value=ReportLocalDateTimeField()
        form=Form({'value':'2026-13-50T99:99'})
        self.assertFalse(form.is_valid());self.assertIn('2026-13-50T99:99',str(form['value']))


class ReportingUIRegressionTests(TestCase):
    configure=base.FactoryReportingTests.configure
    start_work=base.FactoryReportingTests.start_work
    advance=base.FactoryReportingTests.advance
    finish=base.FactoryReportingTests.finish

    def setUp(self):
        base.FactoryReportingTests.setUp(self)
        self.lead=self.reader('report-pmo-lead','document.review_controlled')
        self.viewer=self.reader('report-grant-only-reviewer','document.review_controlled')
        assignments=reference_values(active_component('D05.role_principal_assignments',self.case))
        assignments=[dict(x,user_id=self.lead.pk) if x['role']=='PMO Lead' else x for x in assignments]
        cfg=draft_roles(self.actor,self.case.pk,assignments,self.owner.pk,timezone.now())
        transition(self.actor,cfg.pk,'validated');transition(self.actor,cfg.pk,'active')
        Grant.objects.get_or_create(user=self.preparer,case=self.case,action='factory.read')
        artifact(self.actor,self.case,'D05.decision_action_matrix','schema:psl/decision-actions/v1',
                 {'rules':[{'role':'PMO Lead','actions':['return']}]},self.owner)

    def reader(self,name,*extra):
        user=get_user_model().objects.create_user(name)
        for action in ['case.read','factory.read','report.read','meeting.read','issue.read','change.read',*extra]:
            Grant.objects.create(user=user,case=self.case,action=action)
        return user

    def review(self,verdict='approve'):
        self.work.refresh_from_db();v=reporting.document(self.work)
        reporting.review(self.lead,self.work.pk,self.work.revision,rev(self.case),v.pk,verdict,'Exact separate native PMO Lead decision')
        return v

    def queue_ids(self,actor,queue='needs_me'):
        self.client.force_login(actor)
        response=self.client.get(reverse('home'),{'queue':queue})
        self.assertEqual(response.status_code,200)
        return [row['work'].pk for row in response.context['rows']]

    def payload(self,controls,**extra):
        self.work.refresh_from_db()
        return {'action':'correct','revision':self.work.revision,'case_revision':rev(self.case),
                'start_at':controls['start_at']['value'],'end_at':controls['end_at']['value'],
                'template_id':self.template.pk,'content_id':self.content.pk,
                'reason':'Source owner reviews the returned report without changing its selected period',**extra}

    def exact_period(self,microsecond):
        end=(timezone.now()-timedelta(minutes=5)).replace(second=47,microsecond=microsecond)
        start=end-timedelta(days=7)
        self.inputs.update(start_at=start.isoformat(),end_at=end.isoformat())
        self.start_work();self.advance();self.review('return')
        return start,end

    def test_returned_form_post_preserves_exact_period_microseconds_and_one_work_identity(self):
        with timezone.override('Africa/Lagos'):
            start,end=self.exact_period(123456)
            self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk])
            response=self.client.get(url);controls=Controls(response.content.decode()).fields
            self.assertEqual(set(controls),{'start_at','end_at'})
            for key,original in [('start_at',start),('end_at',end)]:
                self.assertEqual(controls[key]['value'],timezone.localtime(original).replace(tzinfo=None).isoformat(timespec='milliseconds'))
                self.assertEqual(controls[key]['step'],'any')
            original_request=dict(self.work.request);identity=self.work.business_key;old_source=self.work.source_head_id
            result=self.client.post(url,self.payload(controls,original_start_at='1900-01-01T00:00:00Z'))
            self.assertEqual(result.status_code,302,result.content[:1500])
            self.work.refresh_from_db();values=reporting.source(self.work,self.actor)['inputs']
            self.assertEqual(datetime.fromisoformat(values['start_at']),start)
            self.assertEqual(datetime.fromisoformat(values['end_at']),end)
            self.assertEqual(self.work.request,original_request);self.assertEqual(self.work.business_key,identity)
            self.assertNotEqual(self.work.source_head_id,old_source)
            self.assertEqual(FactoryWork.objects.filter(case=self.case,definition=reporting.DEFINITION).count(),1)
            self.assertEqual(Version.objects.count(),1);self.assertEqual(ControlledReview.objects.count(),1)
            self.assertFalse(Publication.objects.exists())

    def test_zero_and_submillisecond_boundaries_round_trip_from_browser_normalized_values(self):
        with timezone.override('Africa/Lagos'):
            for microsecond in [0,1,999,1000,120000,999999]:
                end=(timezone.now()-timedelta(minutes=5)).replace(second=37,microsecond=microsecond)
                initial=dict(self.inputs,start_at=(end-timedelta(days=7)).isoformat(),end_at=end.isoformat())
                form=InputsForm(self.case,initial=initial,actor=self.actor)
                controls=Controls(form.as_p()).fields
                data={**initial,**{k:v['value'].rstrip('0').rstrip('.') if '.' in v['value'] else v['value'] for k,v in controls.items()}}
                posted=InputsForm(self.case,data,initial=initial,actor=self.actor)
                self.assertTrue(posted.is_valid(),posted.errors)
                self.assertEqual(posted.cleaned_data['end_at'],end)
                self.assertEqual(posted.cleaned_data['start_at'],end-timedelta(days=7))

    def test_edited_visible_boundary_is_not_restored_or_accepted_as_original_period(self):
        self.exact_period(123456);self.client.force_login(self.actor)
        url=reverse('factory_detail',args=[self.work.pk]);controls=Controls(self.client.get(url).content.decode()).fields
        old=self.work.source_head_id;count=FactoryWork.objects.count()
        changed=datetime.fromisoformat(controls['start_at']['value'])+timedelta(seconds=1)
        response=self.client.post(url,self.payload(controls,start_at=changed.isoformat(timespec='milliseconds')))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'A different reporting period requires separate work')
        self.work.refresh_from_db();self.assertEqual(self.work.source_head_id,old);self.assertEqual(FactoryWork.objects.count(),count)

    def test_stale_rendered_source_revision_cannot_overwrite_new_source(self):
        self.exact_period(654321);self.client.force_login(self.actor)
        url=reverse('factory_detail',args=[self.work.pk]);controls=Controls(self.client.get(url).content.decode()).fields
        stale=self.payload(controls)
        self.assertEqual(self.client.post(url,stale).status_code,302)
        self.work.refresh_from_db();source=self.work.source_head_id
        response=self.client.post(url,stale)
        self.assertEqual(response.status_code,200);self.assertContains(response,'Stale revision; refresh before retrying')
        self.work.refresh_from_db();self.assertEqual(self.work.source_head_id,source)
        self.assertEqual(FactoryWork.objects.filter(case=self.case,definition=reporting.DEFINITION).count(),1)

    def test_returned_and_approved_waiting_work_surface_for_eligible_publisher(self):
        self.start_work();self.advance();self.review('return');self.work.refresh_from_db()
        self.assertEqual(self.work.status,'waiting')
        self.assertTrue(presentation(self.actor,self.work)['reporting']['can_correct'])
        self.assertIn(self.work.pk,self.queue_ids(self.actor))
        self.assertNotIn(self.work.pk,self.queue_ids(self.preparer))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        reporting.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.inputs,'Explicit source-owned return correction')
        self.advance();self.review();self.work.refresh_from_db()
        row=presentation(self.actor,self.work);self.assertTrue(row['can_advance']);self.assertTrue(row['needs_me'])
        self.assertIn(self.work.pk,self.queue_ids(self.actor))
        self.assertNotIn(self.work.pk,self.queue_ids(self.lead))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))

    def test_native_pmo_lead_assignment_not_generic_review_grant_controls_queue_and_actions(self):
        self.start_work();self.advance()
        self.assertIn(self.work.pk,self.queue_ids(self.lead))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        self.assertFalse(presentation(self.viewer,self.work)['reporting']['review_verdicts'])
        self.client.force_login(self.viewer);url=reverse('factory_detail',args=[self.work.pk])
        response=self.client.get(url)
        for button in ['Approve exact report','Return exact report','Continue eligible work','Record deliberate source review','Stop report preparation']:
            self.assertNotContains(response,button)
        v=reporting.document(self.work)
        response=self.client.post(url,{'action':'review','revision':self.work.revision,'case_revision':rev(self.case),'version':v.pk,'verdict':'approve','note':'Generic grant is not role authority'})
        self.assertEqual(response.status_code,403);self.assertFalse(ControlledReview.objects.exists())
        Grant.objects.filter(user=self.lead,case=self.case,action='document.review_controlled').update(active=False)
        self.assertNotIn(self.work.pk,self.queue_ids(self.lead))

    def test_withdrawn_correction_and_execution_grants_remove_returned_work_and_management_controls(self):
        self.start_work();self.advance();self.review('return')
        Grant.objects.filter(user=self.actor,case=self.case,action__in=['factory.manage','evidence.add','factory.execute']).update(active=False)
        row=presentation(self.actor,self.work)
        self.assertFalse(row['reporting']['can_correct']);self.assertFalse(row['can_advance'])
        self.assertNotIn(self.work.pk,self.queue_ids(self.actor))
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        for button in ['Record deliberate source review','Stop report preparation','Recheck corrected prerequisites']:
            self.assertNotContains(response,button)

    def test_current_verified_work_is_quiet_and_changed_source_returns_only_to_eligible_owner(self):
        self.start_work();self.finish()
        self.assertNotIn(self.work.pk,self.queue_ids(self.actor))
        self.assertIn(self.work.pk,self.queue_ids(self.actor,'verified'))
        change_action(self.actor,self.case.pk,self.item.pk,'start',self.notes.pk,'Native currentness changed after delivery',rev(self.case),1)
        self.work.refresh_from_db();row=presentation(self.actor,self.work)
        self.assertTrue(row['readiness_changed']);self.assertFalse(row['can_advance']);self.assertTrue(row['needs_me'])
        self.assertEqual(row['owner'],self.actor.get_full_name() or self.actor.username)
        self.assertFalse(row['can_manage'])
        self.assertIn(self.work.pk,self.queue_ids(self.actor));self.assertNotIn(self.work.pk,self.queue_ids(self.actor,'verified'))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        self.assertEqual(Publication.objects.count(),1);self.assertEqual(PublicationReceipt.objects.count(),1)

    def test_queue_and_detail_get_head_leave_every_database_row_unchanged(self):
        self.start_work();self.advance();self.review('return')
        def rows():
            with connection.cursor() as cursor:
                cursor.execute("select tablename from pg_tables where schemaname='public' order by tablename")
                names=[x[0] for x in cursor.fetchall()];result={}
                for table in names:
                    cursor.execute('select count(*),md5(coalesce(string_agg(to_jsonb(t)::text,\'\' order by to_jsonb(t)::text),\'\')) from '+connection.ops.quote_name(table)+' t')
                    result[table]=cursor.fetchone()
                return result
        for actor in [self.actor,self.lead,self.preparer,self.viewer]:
            self.client.force_login(actor);before=rows()
            for method in [self.client.get,self.client.head]:
                for url in [reverse('home'),reverse('factory_detail',args=[self.work.pk])]:
                    self.assertEqual(method(url).status_code,200)
            self.assertEqual(rows(),before)

    def test_changed_source_wait_surfaces_authorized_correction(self):
        self.start_work();self.advance()
        change_action(self.actor,self.case.pk,self.item.pk,'start',self.notes.pk,'Current native source changes before publication',rev(self.case),1)
        self.advance();self.assertEqual(self.work.status,'waiting')
        row=presentation(self.actor,self.work);self.assertTrue(row['reporting']['can_correct'])
        self.assertIn(self.work.pk,self.queue_ids(self.actor))
        self.assertNotIn(self.work.pk,self.queue_ids(self.lead))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))

    def test_native_missing_template_hold_surfaces_authorized_source_correction(self):
        self.start_work(inputs=dict(self.inputs,template_id=None))
        self.advance();self.assertEqual(self.work.status,'blocked')
        self.assertIn('Select the controlled weekly client template',self.work.finding)
        row=presentation(self.actor,self.work)
        self.assertTrue(row['reporting']['can_correct']);self.assertFalse(row['can_advance'])
        self.assertIn(self.work.pk,self.queue_ids(self.actor))
        self.assertNotIn(self.work.pk,self.queue_ids(self.lead))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        self.assertFalse(Publication.objects.exists())

    def test_healthy_pending_native_review_is_only_the_current_leads_attention(self):
        self.start_work();self.advance()
        self.assertEqual(self.work.status,'waiting')
        self.assertNotEqual(self.actor.pk,self.lead.pk)
        row=presentation(self.actor,self.work)
        self.assertTrue(row['reporting']['can_correct'])  # Optional edit authority is retained.
        self.assertFalse(row['can_advance']);self.assertFalse(row['needs_me'])
        self.assertNotIn(self.work.pk,self.queue_ids(self.actor))
        self.assertIn(self.work.pk,self.queue_ids(self.lead))
        self.assertNotIn(self.work.pk,self.queue_ids(self.preparer))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        self.client.force_login(self.actor)
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        self.assertContains(response,'Record deliberate source review')
        self.assertNotContains(response,'Approve exact report')
        self.assertNotContains(response,'Continue eligible work')
        self.assertFalse(ControlledReview.objects.exists());self.assertFalse(Publication.objects.exists())

    def test_missing_coordinator_does_not_hide_independent_source_correction(self):
        self.configure(provider=None);self.start_work();self.advance()
        self.assertEqual(self.work.status,'configuration_needed')
        row=presentation(self.actor,self.work)
        self.assertTrue(row['reporting']['can_correct']);self.assertFalse(row['can_advance']);self.assertFalse(row['can_manage'])
        self.assertIn(self.work.pk,self.queue_ids(self.actor))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        self.assertFalse(Publication.objects.exists())

    def test_cancelled_settled_work_has_no_advance_correction_or_silent_resume(self):
        self.start_work();reporting.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        self.assertEqual(self.work.status,'cancelled');row=presentation(self.actor,self.work)
        self.assertFalse(row['reporting']['can_correct']);self.assertFalse(row['can_advance']);self.assertFalse(row['can_manage'])
        self.assertNotIn(self.work.pk,self.queue_ids(self.actor))
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        for label in ['Record deliberate source review','Continue eligible work','Recheck corrected prerequisites']:
            self.assertNotContains(response,label)
        self.assertFalse(Publication.objects.exists())

    def test_cancelled_uncertain_original_offers_only_authorized_receipt_reconciliation(self):
        job,receipt=base.FactoryReportingTests.uncertain_publication(self)
        reporting.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        self.assertEqual(self.work.status,'waiting_effect');row=presentation(self.actor,self.work)
        self.assertFalse(row['reporting']['can_correct']);self.assertFalse(row['can_advance']);self.assertFalse(row['can_manage'])
        self.assertTrue(row['can_reconcile']);self.assertIn(self.work.pk,self.queue_ids(self.actor))
        self.assertNotIn(self.work.pk,self.queue_ids(self.viewer))
        self.client.force_login(self.actor);response=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        self.assertContains(response,'Reconcile original report delivery')
        for label in ['Record deliberate source review','Continue eligible work','Recheck corrected prerequisites','Cancel original report delivery']:
            self.assertNotContains(response,label)
        job.refresh_from_db();self.assertEqual(job.status,'unknown')
        self.assertEqual(Publication.objects.count(),1);self.assertEqual(PublicationReceipt.objects.count(),1)
        self.assertEqual(PublicationReceipt.objects.get().pk,receipt.pk)
