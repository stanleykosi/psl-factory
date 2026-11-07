"""Synthetic F38-N01 boundary evidence, not authenticated bank reconciliation."""
import copy,json
from datetime import date
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.finance import forecast
from .forecast_helpers import fixture,payload,run,scenario
from .billing_helpers import evidence

class ForecastOpeningBoundaryTests(TestCase):
    def setUp(self):
        self.clock=patch('django.utils.timezone.localdate',return_value=date(2026,10,1));self.clock.start();self.addCleanup(self.clock.stop)
        self.a,self.c,self.m=fixture()

    def boundary(self,status='reconciled',observed_on='2026-09-30'):
        v=payload(self.a,self.c)
        close={'entity':'synthetic-company','currency':'NGN','basis':'gross_cash','account':'account-1','amount':'100','observed_on':observed_on,'cutoff':'end_of_day',
               'source':'synthetic-bank','source_version':'statement-2026-09-v1','boundary_at':'2026-10-01T00:00:00+01:00'}
        e=evidence(self.a,self.c,'forecast_opening',json.dumps(close))
        boundary={'as_of':'2026-10-01','opening_at':'2026-10-01T00:00:00+01:00','status':status}
        declaration=dict(boundary,snapshot_evidence_id=e.pk,snapshot_sha256=e.sha256,**close)
        b=evidence(self.a,self.c,'forecast_opening',json.dumps(declaration))
        v['openings']=[dict(close,contract='forecast-opening-boundary/v1',evidence_id=e.pk,boundary=dict(boundary,evidence_id=b.pk))]
        return v

    def test_f38_n01_supplied_close_boundary_preserves_original_date_and_version(self):
        v=self.boundary();r=run(self.a,self.c,v)
        self.assertEqual(r.result['periods'][0]['opening'],'100')
        self.assertEqual(r.scenario.payload['openings'],v['openings'])
        self.assertEqual(r.result['opening_provenance'][0]['observed_on'],'2026-09-30')
        self.assertEqual(r.result['opening_provenance'][0]['source_version'],'statement-2026-09-v1')

    def test_unreconciled_boundary_remains_unknown_not_zero(self):
        r=run(self.a,self.c,self.boundary(status='unreconciled'))
        self.assertIsNone(r.result['periods'][0]['opening']);self.assertIsNone(r.result['periods'][0]['closing'])

    def test_noncontiguous_close_is_not_automatically_carried(self):
        r=run(self.a,self.c,self.boundary(observed_on='2026-09-29'))
        self.assertIsNone(r.result['periods'][0]['opening']);self.assertIsNone(r.result['periods'][0]['closing'])

    def embedded(self,**changes):
        v=self.boundary();o=v['openings'][0];o['boundary'].pop('evidence_id');o.update(changes)
        body={k:x for k,x in o.items() if k!='evidence_id'}
        e=evidence(self.a,self.c,'forecast_opening',json.dumps(body));o['evidence_id']=e.pk
        return v

    def test_single_supplied_artifact_needs_no_extra_approval_or_artifact(self):
        r=run(self.a,self.c,self.embedded())
        p=r.result['opening_provenance'][0]
        self.assertEqual(p['snapshot_sha256'],p['boundary_sha256'])
        self.assertEqual(r.result['periods'][0]['opening'],'100')
        self.assertIn('freshness',' '.join(r.result['findings']))
        self.assertEqual(r.result['implementation'],'forecast/v2-continuation')

    def test_unknown_snapshot_amount_is_not_zero(self):
        r=run(self.a,self.c,self.embedded(amount=None))
        self.assertIsNone(r.result['periods'][0]['opening'])

    def test_supplied_mismatched_boundary_labels_remain_unknown(self):
        for changes in [{'boundary_at':'2026-10-01T00:00:00+00:00'},
                        {'observed_on':'2026-08-31'}]:
            with self.subTest(changes=changes):
                r=run(self.a,self.c,self.embedded(**changes))
                self.assertIsNone(r.result['periods'][0]['opening'])

    def test_unbound_tampering_and_cross_case_source_rejected(self):
        v=self.boundary();v['openings'][0]['source_version']='changed'
        with self.assertRaises(ValidationError):scenario(self.a,self.c,v)
        v=self.boundary();v['openings'][0]['boundary']['opening_at']='2026-10-01T00:00:00+00:00'
        with self.assertRaises(ValidationError):scenario(self.a,self.c,v)
        from apps.core.models import Case
        from apps.core.models import Evidence
        other=Case.objects.create(tenant='other',title='Other',synthetic=True)
        e=Evidence.objects.create(case=other,kind='forecast_opening',version=1,source='synthetic',body='{}',sha256='a'*64,created_by=self.a)
        v=self.boundary();v['openings'][0]['boundary']['evidence_id']=e.pk
        with self.assertRaises(ValidationError):scenario(self.a,self.c,v)

    def test_native_guard_rejects_forged_provenance_and_known_unknown(self):
        from django.db import transaction,DatabaseError
        from apps.finance.models import ForecastRun
        for status in ['reconciled','unreconciled']:
            r=run(self.a,self.c,self.boundary(status=status))
            for kind in ['provenance','opening']:
                result=copy.deepcopy(r.result)
                if kind=='provenance':result['opening_provenance'][0]['source_version']='forged'
                else:result['periods'][0]['opening']='999'
                with self.subTest(status=status,kind=kind),self.assertRaises(DatabaseError),transaction.atomic():
                    ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=result,sha256='f'*64,actor=self.a)

    def test_native_scenario_rejects_unbound_source_versions(self):
        from django.db import transaction,DatabaseError
        from apps.finance.models import ForecastScenario
        s=scenario(self.a,self.c,self.boundary());v=copy.deepcopy(s.payload)
        v['openings'][0]['source_version']='forged'
        with self.assertRaises(DatabaseError),transaction.atomic():
            ForecastScenario.objects.create(case=self.c,reference='FORGED',number=1,evidence=s.evidence,payload=v,reason='Synthetic forged source',actor=self.a)

    def test_review_currentness_legacy_shape_and_private_ui_citations(self):
        from .forecast_helpers import review
        from .helpers import rev
        from apps.agents.forecast import investigate
        legacy=run(self.a,self.c)
        self.assertNotIn('opening_provenance',legacy.result)
        self.assertNotIn('opening_contract',legacy.manifest)
        v=self.boundary();r=run(self.a,self.c,v);decision=review(self.a,self.c,r)
        self.assertEqual(forecast.approved(r).pk,decision.pk)
        agent=investigate(self.a,self.c.pk,r.pk,rev(self.c))
        self.assertIn(v['openings'][0]['boundary']['evidence_id'],[e['id'] for e in agent.result['citations']])
        self.client.force_login(self.a)
        response=self.client.get(f'/cases/{self.c.pk}/finance/forecast/')
        self.assertContains(response,'statement-2026-09-v1');self.assertContains(response,'Supplied opening snapshot boundaries')
        scenario(self.a,self.c,self.embedded(source_version='statement-2026-09-v2'))
        with self.assertRaisesMessage(ValidationError,'newer'):forecast.ensure_current(r)
        r.refresh_from_db();decision.refresh_from_db()
        self.assertEqual(r.result['opening_provenance'][0]['source_version'],'statement-2026-09-v1')
        self.assertEqual(decision.snapshot['run_hash'],r.sha256)

    def test_source_scope_and_timestamp_must_be_explicit(self):
        for changes in [{'currency':'USD'},{'entity':'other-company'},{'boundary_at':'2026-10-01T00:00:00'},
                        {'boundary_at':'2026-10-01T00:00:00+01:99'}]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                scenario(self.a,self.c,self.embedded(**changes))

    def test_native_unknown_boundary_cannot_forge_later_known_closing(self):
        from django.db import transaction,DatabaseError
        from apps.finance.models import ForecastRun
        r=run(self.a,self.c,self.boundary(status='unreconciled'));result=copy.deepcopy(r.result)
        result['periods'][1]['closing']='999'
        with self.assertRaises(DatabaseError),transaction.atomic():
            ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=result,sha256='f'*64,actor=self.a)

    def test_native_source_date_freshness_cannot_be_relabelled_ready(self):
        from django.db import transaction,DatabaseError
        from apps.finance.models import ForecastRun
        r=run(self.a,self.c,self.boundary());result=copy.deepcopy(r.result)
        self.assertIn('freshness',' '.join(result['findings']))
        result.update(status='ready',findings=[])
        with self.assertRaises(DatabaseError),transaction.atomic():
            ForecastRun.objects.create(case=self.c,scenario=r.scenario,manifest=r.manifest,result=result,sha256='f'*64,actor=self.a)


class ForecastOpeningGroupTests(TestCase):
    def test_new_boundary_private_lineage_never_enters_real_group_receipt(self):
        from datetime import timedelta
        from django.utils import timezone
        from .test_group_forecast import configured
        from .forecast_helpers import review
        from .billing_helpers import policy
        from .helpers import rev
        from apps.finance import group_forecast
        from apps.policy.services import active_component,reference_values
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        a,c,old,reader,t,g,expected=configured();today=timezone.localdate()
        value=copy.deepcopy(old.scenario.payload)
        # Literal current-date fixture, no patched wall clock or database session timezone.
        stamp=today.isoformat()+'T00:00:00+01:00'
        opening={'contract':'forecast-opening-boundary/v1','entity':value['entity'],'currency':value['currency'],'basis':value['basis'],
                 'account':'account-1','amount':'100','observed_on':(today-timedelta(days=1)).isoformat(),'cutoff':'end_of_day',
                 'source':'PRIVATE_BANK','source_version':'PRIVATE_VERSION','boundary_at':stamp,
                 'boundary':{'as_of':today.isoformat(),'opening_at':stamp,'status':'reconciled'}}
        e=evidence(a,c,'forecast_opening',json.dumps(opening));value['openings']=[dict(opening,evidence_id=e.pk)]
        r=run(a,c,value);review(a,c,r)
        projection=copy.deepcopy(reference_values(active_component('D10.audience_projection_rules',c))[0])
        projection['group'].update(run_id=r.pk,run_hash=r.sha256);policy(a,c,'D10.audience_projection_rules',projection)
        v=group_forecast.draft(a,c.pk,r.pk,t.pk,rev(c));self.assertEqual(group_forecast.check_content(v.forecastbinding),expected)
        group_forecast.review(a,c.pk,v.pk,'Finance','approve','Synthetic exact public selected rows',rev(c))
        p=reserve_publication(a,c.pk,v.pk,rev(c));run_publication_once(case_id=c.pk)
        text=json.dumps(PublicationReceipt.objects.get(publication=p).payload)
        for private in ['PRIVATE_BANK','PRIVATE_VERSION','boundary_at','opening_provenance','account-1','snapshot_sha256']:
            self.assertNotIn(private,text)
        self.client.force_login(reader)
        self.assertEqual(self.client.get(f'/cases/{c.pk}/finance/forecast/').status_code,404)
