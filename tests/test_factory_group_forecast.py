"""Explicit group intent through existing forecast factory; synthetic sources only."""
import json
from pathlib import Path
from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.utils import timezone
from apps.workflows import factory, factory_forecast as service
from apps.workflows.factory_forecast_sources import PROTOCOL,investigation
from apps.workflows.models import FactoryWork, FactoryAttempt
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.documents.controlled import guard_reserve_publication
from apps.finance.models import ForecastBinding
from apps.finance import group_forecast
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition,reference_values,active_component
from adapters.publications import PublicationTimeoutAfterAccept
from .test_group_forecast import configured
from .billing_helpers import evidence,policy
from .helpers import rev

class GroupForecastFactoryTests(TestCase):
    def setUp(self):
        self.a,self.c,self.run,self.reader,self.t,self.g,self.expected=configured()
        s=self.run.scenario;p=s.payload
        self.selected={'protocol':PROTOCOL,'scenario_id':s.pk,'as_of':p['as_of'],'months':p['months'],
            'source_ids':sorted({s.evidence_id}|{i['evidence_id'] for i in p['items']+p['openings']}),'template_id':self.t.pk,'audience':'group'}
        proof=evidence(self.a,self.c,'policy_decision','Synthetic scoped group forecast preparation and exact human disclosure wait')
        value=json.loads(Path('fixtures/factory-forecast.json').read_text());value.pop('classification');value.update(preparer_id=self.a.pk,executor_id=self.a.pk)
        self.profile=draft_operator_policy(self.a,self.c.pk,'OPS.factory_forecast_execution',value,proof.pk,timezone.now())
        transition(self.a,self.profile.pk,'validated');transition(self.a,self.profile.pk,'active')

    def start(self):
        self.w=service.start(self.a,self.c.pk,'GROUP-1',self.selected,'Separate owner-permitted group report',rev(self.c))
        return self.w
    def advance(self):factory.run_until_wait(self.w.pk);self.w.refresh_from_db()
    def review(self):
        b=service.document(self.w)
        return service.human_action(self.a,self.w.pk,self.w.revision,rev(self.c),self.run.scenario_id,'group_review',
            {'version':b.version,'role':'Finance','verdict':'approve','reason':'Exact permitted content and recipient list reviewed'})

    def test_work_intake_scoped_investigation_human_wait_delivery_and_verification(self):
        self.start();self.advance()
        self.assertEqual(service.report(self.w,self.a)['stage'],'group_review',self.w.finding)
        self.assertFalse(Publication.objects.filter(factory_work=self.w).exists())
        self.assertEqual(service.calculation(self.w).pk,self.run.pk)
        results=list(FactoryAttempt.objects.filter(activity__work=self.w,phase='observed',result__has_key='investigation').values_list('result',flat=True))
        self.assertTrue(results)
        text=json.dumps(results)
        for secret in ['RESTRICTED_X','SECRET_X','PRIVATE_X','7391','account-1']:self.assertNotIn(secret,text)
        self.review();self.advance();self.assertEqual(self.w.status,'verified',self.w.finding)
        result=service.verify(self.w,self.a);self.assertTrue(result['verified'])
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.w).count(),1)
        self.assertEqual(group_forecast.verified(service.document(self.w).version)['recipient_count'],1)

    def test_missing_group_policy_stops_group_only_without_draft_or_investigation_leak(self):
        projection=reference_values(active_component('D10.audience_projection_rules',self.c))[0];projection.pop('group')
        policy(self.a,self.c,'D10.audience_projection_rules',projection)
        self.start();self.advance()
        self.assertEqual(service.report(self.w,self.a)['stage'],'group_policy',self.w.finding)
        self.assertFalse(ForecastBinding.objects.filter(run=self.run).exists())
        result=investigation(self.a,self.c,self.selected,self.run.pk)
        self.assertIsNone(result['projection']);self.assertNotIn('RESTRICTED_X',json.dumps(result))
        from apps.finance.forecast_documents import report_inputs
        self.assertEqual(report_inputs(self.run,'management')['audience'],'management')

    def test_group_is_explicit_separate_work_and_cannot_reuse_management_template(self):
        from .forecast_helpers import publication
        management,reader=publication(self.a,self.c)
        internal=dict(self.selected,audience='management',template_id=management.pk)
        old=service.start(self.a,self.c.pk,'INTERNAL-1',internal,'Internal report',rev(self.c))
        self.start();self.assertNotEqual(old.pk,self.w.pk)
        with self.assertRaisesMessage(ValidationError,'separate explicit work'):
            service.correct(self.a,old.pk,old.revision,rev(self.c),self.selected,'Cannot convert management work into group work')
        with self.assertRaises(ValidationError):service.start(self.a,self.c.pk,'BAD-GROUP',dict(self.selected,template_id=management.pk),'Not a group template',rev(self.c))
        old.refresh_from_db();self.assertEqual(json.loads(old.source_head.body)['audience'],'management')

    def test_primary_work_console_exact_group_review_and_readonly_get(self):
        self.start();self.advance();self.client.force_login(self.a)
        before=(FactoryAttempt.objects.count(),ForecastBinding.objects.count(),self.w.revision,rev(self.c))
        url=reverse('factory_detail',args=[self.w.pk]);response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertContains(response,'Separate group disclosure report')
        self.assertContains(response,'Decide exact group disclosure and recipients')
        self.assertContains(response,'Exact group disclosure decision');self.assertContains(response,self.reader.username)
        self.assertContains(response,service.document(self.w).version.payload_sha256)
        self.w.refresh_from_db();self.assertEqual(before,(FactoryAttempt.objects.count(),ForecastBinding.objects.count(),self.w.revision,rev(self.c)))
        b=service.document(self.w)
        response=self.client.post(url,{'action':'group_review','revision':rev(self.c),'work_revision':self.w.revision,
            'selected_scenario':self.run.scenario_id,'version':b.version_id,'role':'Finance','verdict':'approve','reason':'Exact artifact and destination reviewed'})
        self.assertEqual(response.status_code,302)
        self.advance();self.assertEqual(self.w.status,'verified',self.w.finding)
        self.client.force_login(self.reader);self.assertEqual(self.client.get(url).status_code,404)

    def test_uncertain_group_delivery_reconciles_before_correction_without_duplicate_effect(self):
        self.start();self.advance();self.review()
        for _ in range(16):
            factory.run_once(self.w.pk,adapter=PublicationTimeoutAfterAccept());self.w.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=self.w,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=self.w)
        self.assertEqual(job.status,'unknown',self.w.finding)
        with self.assertRaises(ValidationError):service.correct(self.a,self.w.pk,self.w.revision,rev(self.c),self.selected,'Cannot replace unknown delivery')
        service.reconcile(self.a,self.w.pk,self.w.revision);self.w.refresh_from_db();self.advance()
        self.assertEqual(self.w.status,'verified',self.w.finding)
        self.assertEqual(Publication.objects.filter(factory_work=self.w).count(),1)
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.w).count(),1)

    def test_returned_group_disclosure_requires_source_owned_rework_and_fresh_review(self):
        matrix=reference_values(active_component('D05.decision_action_matrix',self.c))[0]
        matrix.setdefault('rules',[]);matrix['rules'].append({'role':'Finance','actions':['return','reject']})
        policy(self.a,self.c,'D05.decision_action_matrix',matrix)
        self.start();self.advance();old=service.document(self.w)
        service.human_action(self.a,self.w.pk,self.w.revision,rev(self.c),self.run.scenario_id,'group_review',
            {'version':old.version,'role':'Finance','verdict':'return','reason':'Synthetic disclosure rework required'})
        with self.assertRaises(ValidationError):self.review()
        self.advance();self.assertEqual(service.report(self.w,self.a)['stage'],'group_review')
        service.correct(self.a,self.w.pk,self.w.revision,rev(self.c),self.selected,'Explicit new group preparation after returned disclosure')
        self.w.refresh_from_db();self.advance();new=service.document(self.w)
        self.assertNotEqual(new.version_id,old.version_id)
        self.review();self.advance();self.assertEqual(self.w.status,'verified',self.w.finding)

    def test_all_rowsets_preserved_by_preparer_and_recipient_gets(self):
        from django.db import connection
        def rows():
            result={}
            with connection.cursor() as cursor:
                for table in sorted(connection.introspection.table_names(cursor)):
                    cursor.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(table)+' t')
                    result[table]=sorted(row[0] for row in cursor.fetchall())
            return result
        self.start();self.advance();self.review();self.advance()
        self.client.force_login(self.a);before=rows()
        for url in [reverse('factory_detail',args=[self.w.pk]),reverse('finance_forecast',args=[self.c.pk]),reverse('home')]:
            self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(rows(),before)
        self.client.force_login(self.reader);before=rows()
        self.assertEqual(self.client.get(reverse('document_inbox')).status_code,200)
        self.assertEqual(self.client.get(reverse('factory_detail',args=[self.w.pk])).status_code,404)
        self.assertEqual(rows(),before)

    def test_group_audience_class_cannot_change_through_correction_restart_or_sql(self):
        from django.db import DatabaseError,transaction
        from .forecast_helpers import publication
        self.start();management,_=publication(self.a,self.c)
        value=dict(self.selected,audience='management',template_id=management.pk)
        with self.assertRaisesMessage(ValidationError,'separate explicit work'):
            service.correct(self.a,self.w.pk,self.w.revision,rev(self.c),value,'Separate group identity stays fixed')
        e=service.capture(self.a,self.c,value,'factory.forecast_source')
        with self.assertRaisesMessage(DatabaseError,'group audience'),transaction.atomic():
            FactoryWork.objects.filter(pk=self.w.pk).update(source_head=e)
        service.cancel(self.a,self.w.pk,self.w.revision);self.w.refresh_from_db()
        with self.assertRaisesMessage(ValidationError,'separate explicit work'):
            service.restart(self.a,self.w.pk,self.w.revision,rev(self.c),value,self.profile.pk,'No audience switch on restart')
