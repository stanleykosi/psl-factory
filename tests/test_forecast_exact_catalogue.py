"""Exact supplied F42 examples; synthetic clock only, real internal services.

No configured policy here is a PSL owner decision. TST represents catalogue
TEST under the native three-letter currency schema. No currency conversion.
"""
import copy
import json
from datetime import date
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from apps.finance import forecast
from apps.finance.models import ForecastScenario,ForecastRun,ForecastReview
from apps.policy.models import Configuration
from apps.policy.services import resolve
from .forecast_helpers import fixture,payload,scenario,review
from .billing_helpers import evidence
from .helpers import rev


class ForecastExactCatalogueTests(TestCase):
    def setUp(self):
        self.a,self.c,self.m=fixture()

    def initial(self,disputed=False):
        with patch('django.utils.timezone.localdate',return_value=date(2026,9,15)):
            value=payload(self.a,self.c);value['currency']='TST';value['items']=value['items'][:1]
            item=value['items'][0];item.update(key='R1',source_ref='R1',original_due='2026-09-15',expected_on='2026-09-15')
            if disputed:
                proof=evidence(self.a,self.c,'document','Synthetic R1 disputed; unresolved; no new corroborating receipt evidence')
                item['evidence_id']=proof.pk
            s=scenario(self.a,self.c,value,reference='F42-R1')
            run=forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c));review(self.a,self.c,run)
        return run

    def carry(self,parent,on,expected_on,reason):
        with patch('django.utils.timezone.localdate',return_value=on):
            value=payload(self.a,self.c);value['currency']='TST'
            value['items']=copy.deepcopy(parent.scenario.payload['items'])
            value['items'][0]['expected_on']=expected_on
            value['rollover']=[{'key':'R1','disposition':'carry','reason':reason}]
            s=scenario(self.a,self.c,value,reference='F42-R1',parent=parent)
            return forecast.prepare(self.a,self.c.pk,s.pk,rev(self.c))

    def test_literal_due_15_september_expected_10_october__F42_N01(self):
        old=self.initial();old_payload=copy.deepcopy(old.scenario.payload);old_result=copy.deepcopy(old.result)
        run=self.carry(old,date(2026,10,1),'2026-10-10','Explicit synthetic Finance expectation: receive R1 on 10 October; original due remains 15 September')
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            with self.assertRaisesMessage(ValidationError,'approval'):
                forecast.approved(run)
            proof=evidence(self.a,self.c,'forecast_review','Synthetic Finance explicitly approves R1 expected receipt 10 October, retaining unresolved due 15 September')
            approval=forecast.review(self.a,self.c.pk,run.pk,'Finance','approve',proof.pk,'Explicit October expectation, not debt settlement',rev(self.c))
            self.assertEqual(forecast.approved(run).pk,approval.pk)
        item=run.result['items'][0]
        self.assertEqual((item['key'],item['original_due'],item['expected_on']),('R1','2026-09-15','2026-10-10'))
        self.assertEqual((item['residual'],item['matched']),('50','0'))
        self.assertEqual((run.result['periods'][0]['month'],run.result['periods'][0]['expected_inflow']),('2026-10','50'))
        self.assertEqual((run.scenario.parent_id,run.scenario.root_id),(old.pk,old.scenario_id))
        self.assertEqual(item['evidence_id'],old_payload['items'][0]['evidence_id'])
        self.assertNotEqual(run.scenario.payload['openings'][0]['evidence_id'],old_payload['openings'][0]['evidence_id'])
        old.refresh_from_db();old.scenario.refresh_from_db()
        self.assertEqual(old.scenario.payload,old_payload);self.assertEqual(old.result,old_result)
        self.assertEqual(ForecastReview.objects.filter(run__in=[old,run]).count(),2)
        self.assertFalse(run.result['execution_authorized'])

    def test_unapproved_visible_horizon_not_inferred__F42_E02(self):
        a,c=self.a,self.c
        from apps.policy.services import transition,active_component
        transition(a,active_component(forecast.METHOD,c).pk,'revoked')
        narrative={'fixture_scope':'synthetic_test','visible_columns':['SEP','OCT','NOV','DEC','JAN','OTHERS'],
          'transcript_example':'Roll October items into November in its first week',
          'approved_active_horizon':None,'approved_rollover_deadline':None}
        raw=evidence(a,c,'forecast_input',json.dumps(narrative,sort_keys=True))
        counts=(ForecastScenario.objects.count(),ForecastRun.objects.count(),Configuration.objects.count())
        with self.assertRaises(ValidationError):
            forecast.capture(a,c.pk,'F42-E02-NARRATIVE',raw.pk,'Evidence only; owner horizon and deadline unresolved',rev(c))
        raw.refresh_from_db();self.assertEqual(json.loads(raw.body),narrative)
        self.assertEqual((ForecastScenario.objects.count(),ForecastRun.objects.count(),Configuration.objects.count()),counts)
        self.assertNotEqual(resolve(forecast.METHOD,c).status,'ACTIVE')
        # Even otherwise structured evidence cannot infer months from column names.
        candidate=payload(a,c);candidate['currency']='TST';candidate.pop('months')
        incomplete=evidence(a,c,'forecast_input',json.dumps(candidate))
        with self.assertRaises(ValidationError):
            forecast.capture(a,c.pk,'F42-E02-MISSING-HORIZON',incomplete.pk,'No owner-selected horizon supplied',rev(c))
        self.assertFalse(ForecastScenario.objects.exists());self.assertFalse(ForecastRun.objects.exists())
        self.assertEqual(Configuration.objects.count(),counts[2])

    def test_repeated_disputed_carry_is_not_fresh_reliable_inflow__F42_E01(self):
        old=self.initial(disputed=True)
        october=self.carry(old,date(2026,10,1),'2026-10-10','R1 remains disputed; no new item evidence; explicit carry for Finance review')
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,1)):
            review(self.a,self.c,october)
        november=self.carry(october,date(2026,11,1),'2026-11-10','R1 remains disputed; still no new item evidence; second explicit carry for Finance review')
        self.assertEqual(connection.vendor,'postgresql')
        for run in [october,november]:
            self.assertEqual(run.result['items'][0]['original_due'],'2026-09-15')
            self.assertEqual(run.result['items'][0]['evidence_id'],old.result['items'][0]['evidence_id'])
            self.assertEqual(run.scenario.root_id,old.scenario_id)
        self.assertEqual((ForecastScenario.objects.count(),ForecastReview.objects.count()),(3,2))
        self.assertNotEqual(november.result['status'],'ready',
            'F42-E01: repeated disputed carry with unchanged item evidence must stay flagged for review, not ready')
        self.assertTrue(november.result['findings'],'F42-E01 requires a visible review finding, not just preserved old dates')
