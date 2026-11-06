"""Connected forecast tests against the actual accepted predecessor migration graph."""
import json
from pathlib import Path
from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, DatabaseError, transaction
from django.urls import reverse
from django.utils import timezone
from apps.workflows import factory, factory_forecast as service
from apps.workflows.factory_forecast_sources import PROTOCOL
from apps.workflows.models import FactoryWork
from apps.finance.models import ForecastReview, ForecastActualVerification, ForecastMatch
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.identity.models import Grant
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from tests.forecast_helpers import fixture,scenario,publication,review,actual
from tests.billing_helpers import evidence
from tests.helpers import rev

class ForecastFactoryTests(TestCase):
    def setUp(self):
        self.actor,self.case,self.method=fixture()
        self.scenario=scenario(self.actor,self.case)
        self.template,self.reader=publication(self.actor,self.case)
        p=self.scenario.payload
        self.selected={'protocol':PROTOCOL,'scenario_id':self.scenario.pk,'as_of':p['as_of'],'months':p['months'],'source_ids':sorted({self.scenario.evidence_id}|{i['evidence_id'] for i in p['items']+p['openings']}),'template_id':self.template.pk,'audience':'management'}
        proof=evidence(self.actor,self.case,'policy_decision','Synthetic scoped forecast factory preparation and delivery')
        value=json.loads(Path('fixtures/factory-forecast.json').read_text());value.pop('classification');value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk)
        self.profile=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_forecast_execution',value,proof.pk,timezone.now())
        transition(self.actor,self.profile.pk,'validated');transition(self.actor,self.profile.pk,'active')

    def start(self):
        self.work=service.start(self.actor,self.case.pk,'FORECAST-1',self.selected,'Reviewed cash forecast',rev(self.case))
        return self.work

    def advance(self):
        factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work

    def test_complete_native_review_and_aggregate_receipt_chain(self):
        self.start();self.advance()
        r=service.calculation(self.work,self.actor)
        self.assertIsNotNone(r,self.work.finding)
        self.assertEqual(service.report(self.work,self.actor)['stage'],'review',self.work.finding)
        self.assertFalse(ForecastReview.objects.exists())
        review(self.actor,self.case,r)
        self.advance()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        result=service.verify(self.work,self.actor)
        self.assertFalse(result['execution_authorized']);self.assertFalse(result['cash_mutated'])
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),1)
        self.assertFalse(ForecastActualVerification.objects.exists());self.assertFalse(ForecastMatch.objects.exists())
        payload=json.dumps(PublicationReceipt.objects.get(publication__factory_work=self.work).payload)
        self.assertNotIn('account-1',payload);self.assertNotIn('expected-1',payload)

    def test_intake_idempotency_and_database_terminal_guard(self):
        self.start()
        self.assertEqual(service.start(self.actor,self.case.pk,'OTHER',self.selected,'Same native forecast').pk,self.work.pk)
        with self.assertRaises(ValidationError):service.start(self.actor,self.case.pk,'FORECAST-1',self.selected,'Changed intent')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_native_actual_change_recalculates_without_verification_or_match(self):
        self.start();self.advance();old=service.calculation(self.work,self.actor)
        a=actual(self.actor,self.case,verified=False)
        self.advance();self.assertEqual(service.calculation(self.work,self.actor).pk,old.pk)
        self.assertEqual(service.report(self.work,self.actor)['stage'],'rework')
        service.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,'Explicitly recalculate after native actual inventory changed')
        self.advance();new=service.calculation(self.work,self.actor)
        self.assertNotEqual(new.pk,old.pk)
        self.assertIn(a.pk,[x[0] for x in new.manifest['actuals']])
        self.assertFalse(ForecastActualVerification.objects.exists());self.assertFalse(ForecastMatch.objects.exists())
        self.assertEqual(self.work.source_head.body,json.dumps(self.selected,sort_keys=True))

    def test_revoked_native_source_authority_stops_work(self):
        self.start();Grant.objects.filter(case=self.case,user=self.actor,action='finance.forecast.capture').update(active=False)
        with self.assertRaises(PermissionDenied):service.source(self.work,self.actor)
        self.advance();self.assertNotEqual(self.work.status,'verified');self.assertFalse(Publication.objects.filter(factory_work=self.work).exists())

    def test_new_scenario_requires_explicit_source_owned_selection(self):
        self.start();self.advance();spent=self.work.budget_used;head=self.work.source_head_id
        s=scenario(self.actor,self.case);p=s.payload
        with self.assertRaises(ValidationError):service.source(self.work,self.actor)
        value=dict(self.selected,scenario_id=s.pk,source_ids=sorted({s.evidence_id}|{i['evidence_id'] for i in p['items']+p['openings']}))
        service.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),value,'Explicit native revision selected')
        self.work.refresh_from_db();self.assertNotEqual(self.work.source_head_id,head);self.assertEqual(self.work.budget_used,spent)
        self.advance();self.assertEqual(service.calculation(self.work,self.actor).scenario_id,s.pk)

    def test_work_console_get_is_read_only_and_separates_selection_and_pin(self):
        self.start();self.advance();self.client.force_login(self.actor)
        before=self.work.revision;case_before=rev(self.case)
        response=self.client.get(reverse('factory_detail',args=[self.work.pk]))
        self.assertContains(response,'Selected sources');self.assertContains(response,'Calculation pin');self.assertContains(response,'Human Finance decisions')
        self.work.refresh_from_db();self.assertEqual(self.work.revision,before);self.assertEqual(rev(self.case),case_before)

    def test_lost_delivery_reconciles_original_before_source_correction(self):
        from adapters.publications import PublicationTimeoutAfterAccept
        self.start();self.advance();review(self.actor,self.case,service.calculation(self.work,self.actor))
        for _ in range(16):
            factory.run_once(self.work.pk,adapter=PublicationTimeoutAfterAccept());self.work.refresh_from_db()
            if PublicationJob.objects.filter(publication__factory_work=self.work,status='unknown').exists():break
        job=PublicationJob.objects.get(publication__factory_work=self.work)
        self.assertEqual(job.status,'unknown',self.work.finding)
        with self.assertRaises(ValidationError):service.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,'Cannot replace unresolved original effect')
        service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        service.reconcile(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db();job.refresh_from_db()
        self.assertEqual(job.status,'confirmed');self.assertEqual(self.work.status,'followup_needed')
        self.assertEqual(Publication.objects.filter(factory_work=self.work).count(),1)

    def test_unconfigured_preparer_holds_without_granting_authority(self):
        self.start();Grant.objects.filter(case=self.case,user=self.actor,action='finance.forecast.calculate').update(active=False)
        self.advance();self.assertEqual(self.work.status,'owner_needed',self.work.finding)

    def test_unselected_actual_invalidates_delivered_review_until_deliberate_rework(self):
        self.start();self.advance();old=service.calculation(self.work,self.actor)
        review(self.actor,self.case,old);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        receipt=PublicationReceipt.objects.get(publication__factory_work=self.work)
        a=actual(self.actor,self.case,verified=False)
        with self.assertRaises(ValidationError):service.forecast.approved(old)
        with self.assertRaises(ValidationError):service.verify(self.work,self.actor)
        self.assertTrue(service.projection(self.actor,self.work)['readiness_changed'])
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('home')+'?queue=exceptions'),self.work.request['reference'])
        self.assertNotIn(a.evidence_id,self.selected['source_ids'])
        self.assertEqual(service.calculation(self.work,self.actor).pk,old.pk)
        spent=self.work.budget_used
        service.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,'Human requests same-selection recalculation after actual capture')
        self.advance();new=service.calculation(self.work,self.actor)
        self.assertNotEqual(old.pk,new.pk);self.assertEqual(service.report(self.work,self.actor)['stage'],'review')
        self.assertGreaterEqual(self.work.budget_used,spent)
        self.assertEqual(PublicationReceipt.objects.get(pk=receipt.pk).publication_id,receipt.publication_id)
        self.assertIsNone(service.document(self.work))
        self.assertEqual(Publication.objects.filter(factory_work=self.work).count(),1)

    def test_human_wrapper_requires_exact_pin_and_current_human_authority(self):
        self.start();self.advance();r=service.calculation(self.work,self.actor)
        proof=evidence(self.actor,self.case,'forecast_review','Exact human approval proof')
        data={'run':r,'role':'Finance','verdict':'approve','evidence':proof,'reason':'Human approved selected current calculation'}
        with self.assertRaises(ValidationError):service.human_action(self.actor,self.work.pk,self.work.revision,rev(self.case),self.scenario.pk+999,'review',data)
        Grant.objects.filter(case=self.case,user=self.actor,action='finance.forecast.review').update(active=False)
        with self.assertRaises(PermissionDenied):service.human_action(self.actor,self.work.pk,self.work.revision,rev(self.case),self.scenario.pk,'review',data)
        self.assertFalse(ForecastReview.objects.exists())

    def test_operating_configuration_and_intake_pages_render(self):
        self.client.force_login(self.actor)
        response=self.client.get(reverse('factory_configuration',args=[self.case.pk])+'?definition=finance-forecast/v1')
        self.assertContains(response,'Existing native forecast preparer')
        response=self.client.get(reverse('factory_create')+'?definition=finance-forecast/v1&case='+str(self.case.pk))
        self.assertContains(response,'Exact ordered month horizon')

    def rowsets(self):
        """Exact all-table observation fingerprint, including audit, tasks and sessions."""
        result={}
        with connection.cursor() as cursor:
            for table in sorted(connection.introspection.table_names(cursor)):
                cursor.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(table)+' t')
                result[table]=sorted(row[0] for row in cursor.fetchall())
        return result

    def test_all_rowsets_unchanged_by_detail_queue_and_configuration_gets(self):
        self.start();self.advance();self.client.force_login(self.actor)
        before=self.rowsets()
        for url in [reverse('factory_detail',args=[self.work.pk]),reverse('home'),reverse('factory_configuration',args=[self.case.pk])+'?definition=finance-forecast/v1']:
            response=self.client.get(url);self.assertEqual(response.status_code,200,url)
        self.assertEqual(self.rowsets(),before)

    def held_publication(self):
        from adapters.publications import InternalPublicationAdapter
        class RefusedTransport(InternalPublicationAdapter):
            def deliver(self,job_id,fence):raise ValidationError('Synthetic external refusal before acceptance')
        self.start();self.advance();review(self.actor,self.case,service.calculation(self.work,self.actor))
        for _ in range(16):
            factory.run_once(self.work.pk,adapter=RefusedTransport());self.work.refresh_from_db()
            job=PublicationJob.objects.filter(publication__factory_work=self.work,status='held').first()
            if job:return job
        self.fail('Expected held original publication: '+self.work.finding)

    def test_cancelled_work_cannot_retry_held_publication_via_api_or_post(self):
        job=self.held_publication();service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        with self.assertRaisesMessage(ValidationError,'stopped'):
            service.operate(self.actor,self.work.pk,self.work.revision,rev(self.case),job.pk,'retry','Attempt retry after stop')
        self.client.force_login(self.actor)
        response=self.client.post(reverse('factory_detail',args=[self.work.pk]),{'action':'operate_delivery','revision':self.work.revision,'case_revision':rev(self.case),'job':job.pk,'operation':'retry','reason':'Attempt retry after stop'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'stopped')
        job.refresh_from_db();self.assertEqual(job.status,'held');self.assertFalse(PublicationReceipt.objects.filter(publication=job.publication).exists())

    def test_http_native_human_review_uses_exact_work_pin(self):
        self.start();self.advance();r=service.calculation(self.work,self.actor)
        proof=evidence(self.actor,self.case,'forecast_review','Human checked exact native calculation')
        self.client.force_login(self.actor)
        response=self.client.post(reverse('factory_detail',args=[self.work.pk]),{'action':'review','work_revision':self.work.revision,'selected_scenario':self.scenario.pk,'revision':rev(self.case),'run':r.pk,'role':'Finance','verdict':'approve','evidence':proof.pk,'reason':'Actual configured human approval'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(ForecastReview.objects.get(run=r).actor_id,self.actor.pk)
        self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)

    def test_database_rejects_audited_but_inexact_source_inventory(self):
        from apps.core.services import add_evidence,event
        self.start()
        for value in [dict(self.selected,source_ids=self.selected['source_ids'][:-1]),dict(self.selected,source_ids=self.selected['source_ids']+[self.selected['source_ids'][0]]),dict(self.selected,audience='client'),dict(self.selected,inferred_approval=True)]:
            e=add_evidence(self.actor,self.case.pk,service.KIND,json.dumps(value,sort_keys=True),'synthetic:invalid-selection')
            event(self.actor,self.case,'factory.forecast_source',evidence_id=e.pk,sha256=e.sha256)
            with self.assertRaises(DatabaseError),transaction.atomic():
                FactoryWork.objects.filter(pk=self.work.pk).update(source_head=e)
        self.work.refresh_from_db();self.assertEqual(json.loads(self.work.source_head.body),self.selected)

    def test_missing_publish_grant_holds_only_document_preparation(self):
        self.start();Grant.objects.filter(case=self.case,user=self.actor,action='finance.publish').update(active=False)
        self.advance();r=service.calculation(self.work,self.actor)
        self.assertIsNotNone(r,self.work.finding)
        review(self.actor,self.case,r);self.advance()
        self.assertEqual(self.work.status,'owner_needed',self.work.finding)
        self.assertIsNone(service.document(self.work))

    def test_explicit_native_rollover_preserves_prior_receipt_due_dates_and_new_review(self):
        from copy import deepcopy
        from datetime import date
        from unittest.mock import patch
        from tests.forecast_helpers import payload,month
        self.start();self.advance();old=service.calculation(self.work,self.actor)
        review(self.actor,self.case,old);self.advance();old_receipt=PublicationReceipt.objects.get(publication__factory_work=self.work)
        next_date=date.fromisoformat(month(1)+'-01')
        with patch('django.utils.timezone.localdate',return_value=next_date):
            v=payload(self.actor,self.case)
            v['items']=deepcopy(old.scenario.payload['items'])
            for item in v['items']:item['expected_on']=v['as_of']
            v['rollover']=[{'key':item['key'],'disposition':'carry','reason':'Human explicitly retains unresolved assumption at revised date'} for item in v['items']]
            successor=scenario(self.actor,self.case,v,parent=old)
            selected=dict(self.selected,scenario_id=successor.pk,as_of=v['as_of'],months=v['months'],source_ids=sorted({successor.evidence_id}|{i['evidence_id'] for i in v['items']+v['openings']}))
            service.correct(self.actor,self.work.pk,self.work.revision,rev(self.case),selected,'Human selected exact rollover and fresh opening proof')
            self.advance();r=service.calculation(self.work,self.actor)
            self.assertEqual(successor.parent_id,old.pk);self.assertEqual(successor.root_id,old.scenario_id)
            self.assertFalse(ForecastReview.objects.filter(run=r).exists())
            self.assertEqual(r.result['items'][0]['original_due'],old.result['items'][0]['original_due'])
            investigation=service.sources.investigation(self.actor,self.case,selected,r.pk)
            self.assertEqual(investigation['rollover']['parent_run'],old.pk)
            self.assertGreater(investigation['aging'][0]['days_past_original_due'],0)
            review(self.actor,self.case,r);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
            self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),2)
            self.assertEqual(PublicationReceipt.objects.get(pk=old_receipt.pk).payload,old_receipt.payload)

    def test_group_audience_is_not_inferred_from_management_permission(self):
        with self.assertRaisesMessage(ValidationError,'audience'):
            service.start(self.actor,self.case.pk,'GROUP',dict(self.selected,audience='group'),'Group request',rev(self.case))
        self.assertFalse(FactoryWork.objects.exists())

    def restart_post(self):
        return dict(self.selected,action='restart',revision=self.work.revision,case_revision=rev(self.case),configuration=self.profile.pk,reason='Explicit fresh preparation instruction',months=json.dumps(self.selected['months']))

    def test_settled_restart_preserves_identity_history_and_allowance_via_service_and_http(self):
        self.start();self.advance();spent=self.work.budget_used;limit=self.work.budget_limit;head=self.work.source_head_id;history=self.work.activities.count()
        service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'Explicit fresh instruction after clean stop')
        self.work.refresh_from_db();self.assertFalse(self.work.cancel_requested);self.assertNotEqual(self.work.source_head_id,head)
        self.assertEqual(self.work.budget_used,spent);self.assertEqual(self.work.budget_limit,limit);self.assertEqual(self.work.activities.count(),history)
        self.assertEqual(FactoryWork.objects.count(),1)
        self.advance();service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        self.client.force_login(self.actor);url=reverse('factory_detail',args=[self.work.pk]);self.assertContains(self.client.get(url),'Fresh preparation instruction')
        before=self.work.source_head_id;spent=self.work.budget_used
        response=self.client.post(url,self.restart_post());self.assertEqual(response.status_code,302)
        self.work.refresh_from_db();self.assertEqual(self.work.status,'ready');self.assertNotEqual(self.work.source_head_id,before);self.assertEqual(self.work.budget_used,spent)

    def test_restart_refuses_wrong_policy_revision_and_unsettled_or_delivered_work(self):
        self.start();self.advance();service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        with self.assertRaisesMessage(ValidationError,'policy'):
            service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk+999,'Wrong exact policy selection')
        self.client.force_login(self.actor);data=self.restart_post();data['revision']=self.work.revision-1
        response=self.client.post(reverse('factory_detail',args=[self.work.pk]),data);self.assertEqual(response.status_code,200)
        self.work.refresh_from_db();self.assertTrue(self.work.cancel_requested)
        service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'Fresh exact instruction')
        self.advance();review(self.actor,self.case,service.calculation(self.work,self.actor));self.advance();self.assertEqual(self.work.status,'verified')
        with self.assertRaises(ValidationError):
            service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'Cannot restart delivered work')
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=self.work).count(),1)

    def test_restart_refuses_unresolved_effect_then_accepts_explicit_operator_settlement(self):
        job=self.held_publication();service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        with self.assertRaises(ValidationError):
            service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'Cannot restart held original effect')
        self.client.force_login(self.actor)
        response=self.client.post(reverse('factory_detail',args=[self.work.pk]),self.restart_post());self.assertEqual(response.status_code,200)
        self.assertFalse(PublicationReceipt.objects.filter(publication__factory_work=self.work).exists())
        service.operate(self.actor,self.work.pk,self.work.revision,rev(self.case),job.pk,'cancel','Human settles undispatched original effect');self.work.refresh_from_db()
        spent=self.work.budget_used
        service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'Fresh instruction after original cancellation')
        self.work.refresh_from_db();job.refresh_from_db();self.assertEqual(job.status,'cancelled');self.assertEqual(self.work.budget_used,spent)

    def test_restart_requires_current_source_and_native_permissions(self):
        self.start();self.advance();service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        scenario(self.actor,self.case)
        with self.assertRaises(ValidationError):
            service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'Cannot implicitly select newest scenario')
        Grant.objects.filter(case=self.case,user=self.actor,action='factory.manage').update(active=False)
        with self.assertRaises(PermissionDenied):
            service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,self.profile.pk,'No current restart permission')

    def test_restart_explicit_changed_policy_needs_activation_authority_and_preserves_cap(self):
        self.start();self.advance();service.cancel(self.actor,self.work.pk,self.work.revision);self.work.refresh_from_db()
        limit=self.work.budget_limit;spent=self.work.budget_used
        proof=evidence(self.actor,self.case,'policy_decision','Human reviewed revised synthetic operating allowance')
        value=json.loads(Path('fixtures/factory-forecast.json').read_text());value.pop('classification');value.update(preparer_id=self.actor.pk,executor_id=self.actor.pk,max_tokens=30000)
        config=draft_operator_policy(self.actor,self.case.pk,'OPS.factory_forecast_execution',value,proof.pk,timezone.now())
        transition(self.actor,config.pk,'validated');transition(self.actor,config.pk,'active')
        Grant.objects.filter(case=self.case,user=self.actor,action='policy.activate').update(active=False)
        with self.assertRaises(PermissionDenied):
            service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,config.pk,'Explicitly selected changed policy but no adoption authority')
        Grant.objects.filter(case=self.case,user=self.actor,action='policy.activate').update(active=True)
        service.restart(self.actor,self.work.pk,self.work.revision,rev(self.case),self.selected,config.pk,'Explicit fresh instruction adopts exact reviewed current policy')
        self.work.refresh_from_db();self.assertEqual(self.work.policy_id,config.pk);self.assertEqual(self.work.budget_limit,limit);self.assertEqual(self.work.budget_used,spent)
