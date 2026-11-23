"""Explicit group intent through existing forecast factory; synthetic sources only."""
import json
from pathlib import Path
from unittest.mock import patch
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
    def test_api_group_disclosure_draft_requires_oracle_then_exact_group_approval(self):
        from apps.policy.services import resolve

        self.start()
        self.advance()
        self.client.force_login(self.a)
        url = f'/api/v1/work/{self.w.pk}/forecast'
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        current = page.json()
        self.assertEqual(current['stage'], 'group_review')
        base = active_component('D10.audience_projection_rules', self.c)
        draft = {'run_id': self.run.pk, 'expected_revision': current['expected_revision'],
                 'case_revision': current['case_revision'], 'base_configuration': base.pk,
                 'rows': self.g['rows'], 'fields': self.g['fields'], 'metadata': self.g['metadata'],
                 'recipients': [self.reader.pk], 'reviewer_roles': ['Finance'], 'publisher_roles': ['Finance'],
                 'allow_preparer_review': True, 'oracle': self.g['oracle_evidence_id'],
                 'decision': self.c.evidence.filter(kind='policy_decision').first().pk,
                 'effective_from': timezone.now().isoformat()}
        mismatch = evidence(self.a, self.c, 'forecast_group_oracle', '{}')
        draft['case_revision'] = rev(self.c)
        incomplete = self.client.post(url + '/disclosure', dict(draft, oracle=mismatch.pk), content_type='application/json')
        self.assertNotEqual(incomplete.status_code, 201)
        created = self.client.post(url + '/disclosure', draft, content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(resolve('D10.audience_projection_rules', self.c).configuration.pk, base.pk)
        self.assertFalse(Publication.objects.filter(factory_work=self.w).exists())
        current = self.client.get(url).json()
        command = {key: current[key] for key in ('expected_revision', 'case_revision', 'scenario_id', 'version_id')}
        decided = self.client.post(url, {**command, 'action': 'group_review', 'role': 'Finance', 'verdict': 'approve',
                                         'reason': 'Scope and the exact group recipients were reviewed.'},
                                   content_type='application/json')
        self.assertEqual(decided.status_code, 201, decided.content)
        self.advance()
        original = PublicationReceipt.objects.get(publication__factory_work=self.w)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        self.assertEqual(page.json()['jobs'][0]['receipt_ids'], [original.pk])
        self.assertEqual(page.json()['stage'], 'complete')

    def test_structured_group_rule_editor_retains_base_requires_oracle_and_saves_only_a_draft(self):
        from apps.policy.models import Configuration
        from apps.policy.services import resolve
        from apps.identity.models import Grant
        self.start();self.advance();self.client.force_login(self.a)
        url=reverse('factory_invoice_decision',args=[self.w.pk])
        self.assertContains(self.client.get(url),'Save group rules for review')
        base=active_component('D10.audience_projection_rules',self.c)
        previous=reference_values(base)[0]
        values={'action':'group_rules','work_revision':self.w.revision,'case_revision':rev(self.c),
            'base_configuration':base.pk,'rows':self.g['rows'],'fields':self.g['fields'],
            'metadata':self.g['metadata'],'recipients':[self.reader.pk],'reviewer_roles':['Finance'],
            'publisher_roles':['Finance'],'allow_preparer_review':'yes','oracle':self.g['oracle_evidence_id'],
            'decision':self.c.evidence.filter(kind='policy_decision').first().pk,
            'effective_from':timezone.now().isoformat()}
        before=Configuration.objects.filter(case=self.c).count()
        self.assertContains(self.client.post(url,{**values,'base_configuration':0}),'disclosure rules changed')
        invalid=self.client.post(url,{**values,'metadata':['as_of']})
        self.assertContains(invalid,'currency, accounting basis')
        self.assertNotContains(invalid,'__all__')
        wrong=evidence(self.a,self.c,'forecast_group_oracle','{}')
        values['case_revision']=rev(self.c)
        self.assertContains(self.client.post(url,{**values,'oracle':wrong.pk}),'independent expected report differs')
        self.assertEqual(Configuration.objects.filter(case=self.c).count(),before)
        self.assertRedirects(self.client.post(url,values),url)
        successor=Configuration.objects.filter(case=self.c,component='D10.audience_projection_rules').latest('pk')
        self.assertNotEqual(successor.pk,base.pk)
        self.assertEqual(resolve('D10.audience_projection_rules',self.c).configuration.pk,base.pk)
        result=reference_values(successor)[0]
        self.assertEqual(result['forecast'],previous['forecast'])
        self.assertEqual(result['group']['run_hash'],self.run.sha256)
        self.assertFalse(Publication.objects.filter(factory_work=self.w).exists())
        from apps.finance.group_disclosure_forms import GroupDisclosureForm
        from django.core.exceptions import PermissionDenied
        Grant.objects.filter(case=self.c,user=self.a,action='finance.read').update(active=False)
        with self.assertRaises(PermissionDenied):
            GroupDisclosureForm(self.a,self.c,self.run,base)
        self.assertEqual(self.client.post(url,values).status_code,404)
        Grant.objects.filter(case=self.c,user=self.a,action='finance.read').update(active=True)
        Grant.objects.filter(case=self.c,user=self.a,action='policy.configure').update(active=False)
        values['case_revision']=rev(self.c)
        self.assertEqual(self.client.post(url,values).status_code,403)

    def setUp(self):
        # A long acceptance run can cross midnight during one review journey.
        # Keep the test on its starting business date while worker leases use real time.
        business_date = timezone.localdate()
        self.enterContext(patch.object(timezone, 'localdate', return_value=business_date))
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

    def test_group_queue_presentation_reuses_verified_report_and_rechecks_revocation(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.core.read_observation import observation_scope
        from apps.identity.models import Grant
        from apps.workflows.factory_views import presentation

        self.start();self.advance();self.review();self.advance()
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertEqual(self.w.status, 'verified')
        receipt = PublicationReceipt.objects.get(publication__factory_work=self.w)
        with observation_scope():
            with (patch.object(service, 'report', wraps=service.report) as reports,
                  patch.object(service, 'verify', wraps=service.verify) as verification,
                  CaptureQueriesContext(connection) as scoped_queries):
                row = presentation(self.a, self.w)
            reports.assert_called_once()
            verification.assert_called_once()
            self.assertEqual(row['forecast']['status']['stage'], 'complete')
            self.assertFalse(row['readiness_changed'])
            with CaptureQueriesContext(connection) as duplicate_queries:
                self.assertEqual(service.report(self.w, self.a)['stage'], 'complete')
                self.assertEqual(service.verify(self.w, self.a)['receipt_ids'], [receipt.pk])
        print(f'Group Forecast queue presentation statements: {len(scoped_queries)}; '
              f'additional statements in the former duplicate checks: {len(duplicate_queries)}')
        self.assertLess(len(scoped_queries), 1400)
        self.assertGreater(len(duplicate_queries), 0)

        recipient = Grant.objects.filter(case=self.c, user=self.reader, action='document.receive:group')
        self.assertEqual(recipient.filter(active=True).count(), 1)
        recipient.update(active=False)
        with patch.object(service, 'verify', wraps=service.verify) as verification:
            held = presentation(self.a, self.w)
        verification.assert_called_once()
        self.assertTrue(held['readiness_changed'])
        self.assertNotEqual(held['forecast']['status']['stage'], 'complete')
        recipient.update(active=True)
        self.assertFalse(presentation(self.a, self.w)['readiness_changed'])

        disclosure = active_component('D10.audience_projection_rules', self.c)
        transition(self.a, disclosure.pk, 'revoked')
        stale = presentation(self.a, self.w)
        self.assertTrue(stale['readiness_changed'])
        self.assertNotEqual(stale['forecast']['status']['stage'], 'complete')
        self.assertTrue(PublicationReceipt.objects.filter(pk=receipt.pk, recipient=self.reader).exists())

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
        url=reverse('factory_invoice_decision',args=[self.w.pk]);response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertContains(response,'Separate group disclosure report')
        self.assertContains(response,'Decide exact group disclosure and recipients')
        self.assertContains(response,'Exact group disclosure decision');self.assertContains(response,self.reader.username)
        self.assertContains(response,'Selected forecast rows')
        self.assertContains(response,'<td>50</td>',html=True)
        self.assertNotContains(response,'7391')
        self.assertContains(response,service.document(self.w).version.payload_sha256)
        actuals=self.client.get(reverse('factory_work_response',args=[self.w.pk]))
        self.assertNotContains(actuals,'Exact group disclosure decision')
        self.assertNotContains(actuals,self.reader.username)
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
