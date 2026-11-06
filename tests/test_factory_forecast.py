"""Final suite requires accepted forecast migrations; provisional subclass is separate."""
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
