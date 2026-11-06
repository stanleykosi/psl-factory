"""Read reuse cannot become command authority or survive the observation boundary."""
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.read_observation import observation_scope
from apps.identity.models import Grant
from apps.pmo.models import DeliveryRecord,Milestone
from apps.pmo.delivery_closure import closure_inputs,decide_closure,finalize_closure
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.services import complete_milestone
from adapters.delivery import LocalDeliveryAdapter
from tests.helpers import rev,setup_case,signed
from tests.test_delivery import DeliveryFixture


class DeliveryObservationTests(DeliveryFixture,TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();selected=f.closing()
        for key,value in vars(f).items():setattr(cls,key,value)
        cls.selected=selected

    def test_observation_is_read_only_and_returned_data_cannot_poison_later_reads(self):
        before=Milestone.objects.filter(case=self.case).count()
        with observation_scope():
            first=closure_inputs(self.d,self.selected);first['debt_waived']=True
            self.assertIs(closure_inputs(self.d,self.selected)['debt_waived'],False)
            with self.assertRaisesMessage(ValidationError,'Read-only observation'):
                complete_milestone(self.actor,self.case.pk,'Blocked observation effect',self.e['completion'].pk,rev(self.case))
        self.assertEqual(Milestone.objects.filter(case=self.case).count(),before)
        complete_milestone(self.actor,self.case.pk,'Fresh authorised command',self.e['completion'].pk,rev(self.case))
        self.assertEqual(Milestone.objects.filter(case=self.case).count(),before+1)
        self.assertEqual(next(c for c in LocalDeliveryAdapter().read_closure(self.d,self.selected)['checks'] if c['key']=='finance')['status'],'held')

    def test_current_authority_is_rechecked_after_observation_and_cannot_finalise_from_cached_facts(self):
        v=draft_delivery_document(self.actor,self.case.pk,self.d.pk,'closure',self.t.pk,self.selected,rev(self.case))
        decision=decide_closure(self.actor,self.case.pk,v.pk,'approve',self.e['requirements'].pk,'Actual synthetic prescribed decision before revocation',rev(self.case))
        with observation_scope():
            self.assertTrue(closure_inputs(self.d,self.selected)['finance_confirmation_id'])
            # Simulates a separate current-authority change, not a domain command.
            Grant.objects.filter(user=self.actor,case=self.case,action='delivery.finance_confirm').update(active=False)
            with self.assertRaisesMessage(ValidationError,'Read-only observation'):
                finalize_closure(self.actor,self.case.pk,self.d.pk,rev(self.case))
        with self.assertRaises(PermissionDenied):finalize_closure(self.actor,self.case.pk,self.d.pk,rev(self.case))
        self.assertTrue(DeliveryRecord.objects.filter(pk=decision.pk).exists())
        self.assertFalse(DeliveryRecord.objects.filter(dossier=self.d,kind='closure').exists())

    def test_context_failure_and_other_project_never_reuse_observed_authority(self):
        from apps.pmo.gates import register_candidate
        from apps.pmo.delivery import open_dossier
        actor,case=setup_case(username='other-observation-human');e=signed(actor,case)
        candidate=register_candidate(actor,case.pk,'Other observation candidate',e['requirements'].pk,rev(case))
        other=open_dossier(actor,case.pk,candidate.pk,e['plan'].pk,'Other project declared scope',rev(case))
        with observation_scope():
            self.assertTrue(closure_inputs(self.d,self.selected)['handover_ids'])
            with self.assertRaises(ValidationError):closure_inputs(other,self.selected)
        with self.assertRaises(ValidationError):
            with observation_scope():closure_inputs(self.d,{'retrospective_id':True,'report_evidence_id':None})
        before=Milestone.objects.filter(case=self.case).count()
        complete_milestone(self.actor,self.case.pk,'Command after failed observation',self.e['completion'].pk,rev(self.case))
        self.assertEqual(Milestone.objects.filter(case=self.case).count(),before+1)
