"""Real native successors must not exhaust the agent's current-fact context."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from apps.workflows import factory,factory_hypercare
from apps.pmo import delivery,delivery_closure as closure
from apps.pmo.models import DeliveryRecord
from apps.pmo.delivery_documents import draft_delivery_document
from adapters.delivery import LocalDeliveryAdapter
from tests.test_factory_hypercare import setup
from tests.test_factory_delivery import setup as release_setup,release_sources
from tests.helpers import rev


class FactoryCurrentHeadTests(TestCase):
    def test_latest_rejected_verification_is_visible_and_cannot_fall_back_to_acceptance(self):
        from adapters.delivery import SyntheticDeliverySourceAdapter
        f=setup();source=f.source('technical_design');accepted=source.verifications.latest('pk')
        class Rejected(SyntheticDeliverySourceAdapter):
            name='synthetic-current-head-rejected'
            def read(self,row):return dict(super().read(row),decision='rejected')
        rejected=delivery.verify_source(f.actor,f.case.pk,source.pk,rev(f.case),Rejected())
        with self.assertRaisesMessage(ValidationError,'Current source-verified evidence required'):delivery.verified_source(f.d,'technical_design')
        adapter=LocalDeliveryAdapter();head=adapter.read_current(f.d)['sources'][0]
        self.assertEqual(head['verification_ids'],[rejected.pk])
        self.assertEqual(adapter.read(f.d)['sources'][0]['verification_ids'],[accepted.pk,rejected.pk])

    def history(self,f):
        return [f.source('technical_design',verify=False) for _ in range(105)]

    def test_long_lived_native_history_qualifies_current_observations_but_never_falls_back_after_successor(self):
        self.assertEqual(connection.vendor,'postgresql');f=setup();old=self.history(f)
        f.accepted();f.criteria();f.observations();adapter=LocalDeliveryAdapter()
        with self.assertRaisesMessage(ValidationError,'source/record budget'):adapter.read(f.d)
        current=adapter.read_current(f.d)
        self.assertFalse(current['coverage']['complete_history']);self.assertGreater(current['coverage']['retained_history']['sources'],100)
        self.assertLess(len(current['sources']),20);self.assertNotIn(old[-1].pk,[s['id'] for s in current['sources']])
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        original=factory_hypercare.assessed(f.work)
        successor=f.source('hypercare_infrastructure',{'observed_at':timezone.now().isoformat(),'confirmed':True,
            'metrics':{'availability':{'value':100,'unit':'percent'}}},verify=False)
        with self.assertRaises(ValidationError):factory_hypercare.verify(f.work)
        self.client.force_login(f.actor);page=self.client.get(reverse('home')+'?queue=exceptions')
        row=next(r for r in page.context['rows'] if r['work'].pk==f.work.pk)
        self.assertEqual(row['owner'],f.actor.username);self.assertTrue(row['can_reassess'])
        factory_hypercare.reassess(f.actor,f.work.pk,f.work.revision,'Review the current unverified Infrastructure successor')
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'waiting',f.work.finding)
        self.assertIsNone(factory_hypercare.assessed(f.work).snapshot['qualified'])
        delivery.verify_source(f.actor,f.case.pk,successor.pk,rev(f.case));factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(f.work.budget_limit,20000)
        self.assertTrue(DeliveryRecord.objects.filter(pk=original.pk).exists())
        self.assertEqual(f.d.sources.filter(pk__in=[s.pk for s in old]).count(),105)
        self.client.force_login(f.actor);page=self.client.get(reverse('factory_detail',args=[f.work.pk]));self.assertEqual(page.status_code,200)
        self.assertContains(page,'Earlier versions remain in delivery history.')

    def test_latest_unsent_document_does_not_hide_consumed_acceptance_sources(self):
        f=setup();f.accepted();accepted=closure.accepted_go_live(f.d)
        old_evidence=set(accepted.snapshot['evidence'].values())
        data={key:f.evidence(kind).pk for key,kind in [('checklist','deployment_checklist'),('incident_reporting','incident_reporting'),('rollback','rollback_plan')]}
        draft_delivery_document(f.actor,f.case.pk,f.d.pk,'go_live',f.t.pk,data,rev(f.case))
        current=LocalDeliveryAdapter().read_current(f.d)
        self.assertTrue(old_evidence.issubset(current['source_evidence_ids']))
        self.assertTrue(set(data.values()).issubset(current['source_evidence_ids']))
        self.assertEqual(current['coverage']['selected']['document_bindings'],2)
        self.assertEqual(closure.accepted_go_live(f.d).pk,accepted.pk)

    def test_readiness_factory_uses_current_heads_with_native_controls_after_long_history(self):
        f=release_setup();old=self.history(f);release_sources(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='release_ready').count(),1)
        self.assertEqual(f.d.sources.filter(pk__in=[s.pk for s in old]).count(),105)
