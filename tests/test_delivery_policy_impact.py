from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.db import DatabaseError,transaction
from django.core.exceptions import PermissionDenied,ValidationError
from apps.pmo import delivery_closure as native
from apps.pmo.models import DeliveryRecord
from apps.identity.models import Grant
from apps.policy.services import active_component
from apps.policy import impact
from adapters import policy_impact as adapter
from adapters.delivery_policy_impact import KEY,project
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev

class DeliveryPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture();f.setup_delivery();f.accepted();f.criteria();f.observations()
        cls.f=f
        cls.hypercare=native.evaluate_hypercare(f.actor,f.case.pk,f.d.pk,f.e['requirements'].pk,'Synthetic qualification',rev(f.case))
        cls.archive=f.archive()
        cls.policy=active_component('D11.hypercare_criteria_ref',f.case)
    def rows(self):
        from django.apps import apps
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('pmo','core','documents','workflows','finance')}
    def test_exact_component_kind_pins_and_closed_noeffect_projection(self):
        f=self.f;before=self.rows()
        for key,row in [('D11.hypercare_criteria_ref',self.hypercare),('D11.template_storage_retention_rules',self.archive)]:
            self.assertEqual(list(adapter.query(active_component(key,f.case),KEY,actor=f.actor)),[row])
            value=project(row);self.assertTrue(value['native_closure_prerequisite_current'])
            self.assertEqual(set(value),{'id','kind','record_kind','metadata_only','domain_route','dossier','snapshot_sha256','policy','head','native_closure_prerequisite_current','state','closure_authorized','deployment_authorized','debt_waived','effects_performed'})
        self.assertFalse(adapter.query(active_component('D05.role_principal_assignments',f.case),KEY,actor=f.actor).exists())
        self.assertEqual(before,self.rows())
    def test_policy_successor_retains_historical_signed_records(self):
        self.f.criteria();before=self.rows()
        self.assertFalse(project(self.hypercare)['native_closure_prerequisite_current'])
        self.assertEqual(list(adapter.query(self.policy,KEY,actor=self.f.actor)),[self.hypercare])
        self.assertEqual(before,self.rows())
        self.assertTrue(DeliveryRecord.objects.filter(dossier=self.f.d,kind='go_live').exists())
    def test_unknown_and_newer_hypercare_are_not_promoted(self):
        f=self.f;f.observations(confirmed=None)
        row=native.evaluate_hypercare(f.actor,f.case.pk,f.d.pk,f.e['requirements'].pk,'Explicit unknown',rev(f.case))
        self.assertIsNone(row.snapshot['qualified'])
        self.assertFalse(project(row)['native_closure_prerequisite_current'])
        self.assertFalse(project(self.hypercare)['native_closure_prerequisite_current'])
    def test_archive_successor_retains_old_immutable_snapshot(self):
        new=self.f.archive();before=self.rows()
        self.assertTrue(project(new)['native_closure_prerequisite_current'])
        self.assertFalse(project(self.archive)['native_closure_prerequisite_current'])
        self.assertEqual(before,self.rows())
    def test_current_observer_grants_precede_lookup(self):
        f=self.f
        for action in ('case.read','delivery.read'):
            g=Grant.objects.get(user=f.actor,case=f.case,action=action);g.active=False;g.save()
            with patch('adapters.delivery_policy_impact.DeliveryRecord.objects.filter',side_effect=AssertionError('lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(self.policy,KEY,actor=f.actor)
            g.active=True;g.save()
        f.actor.is_active=False;f.actor.save()
        with self.assertRaises(PermissionDenied):adapter.query(self.policy,KEY,actor=f.actor)
    def test_original_actor_revocation_does_not_remove_history(self):
        f=self.f;Grant.objects.filter(user=f.actor,case=f.case,action='delivery.manage').update(active=False)
        before=self.rows()
        self.assertFalse(project(self.archive)['native_closure_prerequisite_current'])
        self.assertFalse(project(self.hypercare)['native_closure_prerequisite_current'])
        self.assertEqual(list(adapter.query(self.policy,KEY,actor=f.actor)),[self.hypercare]);self.assertEqual(before,self.rows())
    def test_native_errors_generic_without_command_calls(self):
        with patch.object(native,'qualified_hypercare',side_effect=ValidationError('PRIVATE metrics')),patch.object(native,'evaluate_hypercare',side_effect=AssertionError('write')),patch.object(native,'finalize_closure',side_effect=AssertionError('close')):
            value=project(self.hypercare)
        self.assertFalse(value['native_closure_prerequisite_current']);self.assertNotIn('PRIVATE',str(value))
    def test_saved_review_agent_and_current_delivery_reader(self):
        from django.contrib.auth import get_user_model
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        from django.urls import reverse
        f=self.f;f.criteria();new=active_component('D11.hypercare_criteria_ref',f.case)
        row=impact.capture(f.actor,f.case.pk,self.policy.pk,new.pk,[KEY],f.e['policy_decision'].pk,'Historical delivery prerequisite metadata')
        reader=get_user_model().objects.create_user(username='impact797-reviewer')
        Grant.objects.bulk_create([Grant(case=f.case,user=reader,action=g.action) for g in Grant.objects.filter(case=f.case,user=f.actor)])
        impact.review(reader,f.case.pk,row.pk,'accept',f.e['policy_decision'].pk,'Independent engineering assessment')
        result=investigate(reader,f.case.pk,row.pk)
        self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        # Agent findings are fixed generic guidance, not native private findings.
        self.assertEqual(result['findings'],[
            'Observed heads match this bounded assessment',
            'Delivery prerequisite qualification is not universal closure validity. Preserve historical release and signed facts; this observation does not renew signatures, archive artifacts or authorize closure.'])
        closed={'id','kind','record_kind','metadata_only','domain_route','dossier','snapshot_sha256','policy','head','native_closure_prerequisite_current','state','closure_authorized','deployment_authorized','debt_waived','effects_performed'}
        for domains in (result['observation']['domains'],row.observation['domains']):
            self.assertEqual(set(domains),{KEY})
            self.assertEqual(len(domains[KEY]),1)
            for record in domains[KEY]:self.assertEqual(set(record),closed)
        for key in ("'inventory':","'findings':","'metrics':","'note':","'signature':"):
            self.assertNotIn(key,str(result['observation']));self.assertNotIn(key,str(row.observation))
            if key!="'findings':":self.assertNotIn(key,str(result))
        self.assertIn(KEY,dict(choices(reader,f.case)));self.assertTrue(reverse(adapter.ROUTES[KEY],args=[f.case.pk]))
        Grant.objects.filter(case=f.case,user=reader,action='delivery.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(reader,f.case.pk,row.pk)
    def clone(self,kind='hypercare',pin=None):
        snapshot=deepcopy(self.hypercare.snapshot);snapshot['policy_id']=pin
        return DeliveryRecord.objects.create(dossier=self.f.d,kind=kind,data={},snapshot=snapshot,
            evidence=self.f.e['requirements'],actor=self.f.actor)
    def test_typed_pin_and_wrong_kind_leave_guards_enabled(self):
        for pin in (str(self.policy.pk),None,True):self.clone(pin=pin)
        # This deliberately malformed wrong-kind record must not bypass native
        # progress planning prerequisites merely to populate an adapter fixture.
        before=list(DeliveryRecord.objects.order_by('pk').values())
        with self.assertRaisesMessage(DatabaseError,'Current exact UI artifact planning prerequisite required'):
            with transaction.atomic():
                self.clone(kind='progress',pin=self.policy.pk)
        self.assertEqual(list(DeliveryRecord.objects.order_by('pk').values()),before)
        self.clone(kind='archive',pin=self.policy.pk)
        self.assertEqual(list(adapter.query(self.policy,KEY,actor=self.f.actor)),[self.hypercare])
    def test_real_same_component_other_case_with_dual_grants(self):
        from tests.helpers import setup_case,prepared,activate
        from tests.test_delivery import CRITERIA
        from apps.policy.services import register_reference
        a,c=setup_case(username='impact797-other');e=prepared(a,c)
        c.tenant='impact797-other-tenant';c.save(update_fields=['tenant'])
        r=register_reference(a,c.pk,'impact797-other-criteria','schema:psl/hypercare-criteria/v1',CRITERIA,e['policy_decision'].pk)
        activate(a,c,'D11.hypercare_criteria_ref',r.ref,e['policy_decision'])
        config=active_component('D11.hypercare_criteria_ref',c)
        Grant.objects.bulk_create([Grant(case=c,user=self.f.actor,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        self.assertFalse(adapter.query(config,KEY,actor=self.f.actor).exists())
        self.assertEqual(list(adapter.query(self.policy,KEY,actor=self.f.actor)),[self.hypercare])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(self.f.actor,c,KEY,self.hypercare)
    def test_minimal_reader_has_no_manage_or_verify_authority(self):
        from django.contrib.auth import get_user_model
        reader=get_user_model().objects.create_user(username='impact797-observer')
        for action in ('case.read','delivery.read'):Grant.objects.create(user=reader,case=self.f.case,action=action)
        before=self.rows();adapter.authorize_row(reader,self.f.case,KEY,self.hypercare)
        self.assertEqual(list(adapter.query(self.policy,KEY,actor=reader)),[self.hypercare])
        self.assertTrue(project(self.hypercare)['native_closure_prerequisite_current'])
        self.assertEqual(before,self.rows())
    def test_source_successor_and_current_verifier_revocation(self):
        f=self.f;f.observations(errors=1)
        before=self.rows();self.assertFalse(project(self.hypercare)['native_closure_prerequisite_current']);self.assertEqual(before,self.rows())
        # Archive is otherwise unchanged, but its current verifier loses authority.
        Grant.objects.filter(case=f.case,user=f.actor,action='delivery.verify').update(active=False)
        before=self.rows();self.assertFalse(project(self.archive)['native_closure_prerequisite_current']);self.assertEqual(before,self.rows())
    def assessment(self):
        self.f.criteria();new=active_component('D11.hypercare_criteria_ref',self.f.case)
        f=self.f
        return impact.capture(f.actor,f.case.pk,self.policy.pk,new.pk,[KEY],f.e['policy_decision'].pk,'Scoped delivery metadata')
    def test_sql_closed_list_and_exact_budget_no_partial_capture(self):
        from apps.policy.models import ImpactAssessment
        from apps.policy.impact import digest
        from django.db import transaction,DatabaseError
        with patch.object(impact,'SNAPSHOT_LIMIT',1):row=self.assessment()
        self.assertEqual(len(row.observation['domains'][KEY]),1)
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],['pmo.delivery_prerequisites.unknown'],[KEY]*23]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=digest(['bad797',i])))
        self.clone(pin=self.policy.pk);before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):self.assessment()
        self.assertEqual(before,ImpactAssessment.objects.count())
    def test_scoped_page_limit_cursor_and_case_boundary(self):
        self.clone(pin=self.policy.pk)
        f=self.f;page=impact.page(f.actor,f.case.pk,self.policy.pk,KEY,limit=1)
        self.assertEqual(len(page['records']),1);self.assertIsNotNone(page['next_cursor'])
        next_page=impact.page(f.actor,f.case.pk,self.policy.pk,KEY,cursor=page['next_cursor'],limit=1)
        self.assertNotEqual(page['records'][0]['id'],next_page['records'][0]['id'])
        with self.assertRaises(ValidationError):impact.page(f.actor,f.case.pk,self.policy.pk,KEY,limit=0)

class DeliveryImpactClosedHistoryTests(TestCase):
    def test_actual_closed_record_and_signed_facts_survive_policy_successor(self):
        from apps.pmo.delivery_documents import draft_delivery_document
        from apps.pmo.delivery import latest
        f=DeliveryFixture();f.setup_delivery();data=f.closing()
        version=draft_delivery_document(f.actor,f.case.pk,f.d.pk,'closure',f.t.pk,data,rev(f.case))
        native.decide_closure(f.actor,f.case.pk,version.pk,'approve',f.e['requirements'].pk,'Synthetic Head of PMO closure decision',rev(f.case))
        closed=native.finalize_closure(f.actor,f.case.pk,f.d.pk,rev(f.case))
        row=latest(f.d,'hypercare');old=active_component('D11.hypercare_criteria_ref',f.case)
        f.criteria()
        from django.apps import apps
        def facts():return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('pmo','core','documents','workflows','finance')}
        historical=list(DeliveryRecord.objects.filter(dossier=f.d,kind__in=['closure','go_live']).order_by('pk').values())
        before=facts();value=project(row)
        self.assertFalse(value['native_closure_prerequisite_current']);self.assertFalse(value['closure_authorized'])
        self.assertEqual(list(adapter.query(old,KEY,actor=f.actor)),[row])
        self.assertEqual(DeliveryRecord.objects.get(dossier=f.d,kind='closure').pk,closed.pk)
        self.assertTrue(DeliveryRecord.objects.filter(dossier=f.d,kind='go_live').exists())
        self.assertEqual(historical,list(DeliveryRecord.objects.filter(dossier=f.d,kind__in=['closure','go_live']).order_by('pk').values()))
        self.assertEqual(before,facts())

class DeliveryImpactBaselineReplacementTests(TestCase):
    def test_native_signed_baseline_successor_stales_original_dossier_without_effects(self):
        from tests.delivery_impact797_helpers import ReplacementDeliveryFixture,replace_baseline
        from apps.pmo.delivery import dossier_for
        from apps.pmo.signatures import assert_current_signed_baseline
        from apps.documents import delivery as publication_worker
        from adapters.publications import InternalPublicationAdapter
        from apps.pmo.models import RFPCase
        from django.apps import apps
        # No external adapter substitution before any local fixture publication.
        import inspect
        self.assertEqual(InternalPublicationAdapter.deliver.__module__,'adapters.publications')
        self.assertIn('adapter=adapter or InternalPublicationAdapter()',inspect.getsource(publication_worker.run_publication_once))
        f=ReplacementDeliveryFixture();f.setup_delivery();f.accepted();f.criteria();f.observations()
        row=native.evaluate_hypercare(f.actor,f.case.pk,f.d.pk,f.e['requirements'].pk,'Original exact qualification',rev(f.case))
        config=active_component('D11.hypercare_criteria_ref',f.case)
        self.assertFalse(RFPCase.objects.filter(case=f.case).exists())
        self.assertEqual(dossier_for(f.case,f.d.pk).pk,f.d.pk)
        self.assertTrue(project(row)['native_closure_prerequisite_current'])
        adoption,packet=replace_baseline(f)
        self.assertEqual({k:v for k,v in adoption.before.items() if k!='signed_id'},f.d.baseline)
        self.assertNotEqual(adoption.before['plan_id'],adoption.after['plan_id'])
        self.assertEqual(assert_current_signed_baseline(f.case).pk,packet.pk)
        with self.assertRaisesMessage(ValidationError,'Delivery baseline changed'):dossier_for(f.case,f.d.pk)
        def facts():return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('pmo','core','documents','workflows','finance')}
        before=facts();self.assertFalse(project(row)['native_closure_prerequisite_current'])
        self.assertEqual(list(adapter.query(config,KEY,actor=f.actor)),[row])
        self.assertEqual(before,facts())
