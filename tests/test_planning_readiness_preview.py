from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from apps.core.models import Evidence, Audit
from apps.identity.models import Grant
from apps.pmo import planning
from apps.policy.services import transition
from apps.workflows.models import Outbox
from adapters import pilot_guards
from adapters.planning_readiness_guard import readable
from tests.planning_helpers import fixture, observe, criteria


class PlanningReadinessPreviewTests(TestCase):
    def setUp(self):
        self.f=fixture();observe(self.f)

    def selection(self, **changes):
        f=self.f;f['c'].refresh_from_db()
        value={'operation':'planning.readiness','user_id':f['a'].pk,
            'arguments':{'expected_revision':f['c'].revision,'planning_packet_id':f['packet'].pk}}
        value['arguments'].update(changes);return value

    def check(self, **changes):
        return pilot_guards.check(self.f['a'],self.f['c'],self.selection(**changes))

    def counts(self):
        return tuple(m.objects.count() for m in [Evidence,Audit,Outbox])

    def test_ready_preview_no_effect_and_native_prepare_parity(self):
        before=self.counts();result=self.check()
        self.assertEqual(result['state'],'READY_AT_OBSERVATION');self.assertEqual(before,self.counts())
        self.assertFalse(result['business_approval']);self.assertFalse(result['native_verified'])
        row=planning.prepare(self.f['a'],self.f['c'].pk,self.f['packet'].pk)
        self.assertEqual(planning.current_readiness(self.f['c'],row.pk)['packet_id'],self.f['packet'].pk)

    def test_existing_readiness_reuses_native_record_without_preview_write(self):
        f=self.f;old=planning.prepare(f['a'],f['c'].pk,f['packet'].pk);before=self.counts()
        self.assertEqual(self.check()['state'],'READY_AT_OBSERVATION');self.assertEqual(before,self.counts())
        self.assertEqual(planning.prepare(f['a'],f['c'].pk,f['packet'].pk).pk,old.pk)

    def test_observer_denied_before_packet_lookup(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['a'],action='planning.read').update(active=False)
        with patch('adapters.planning_readiness_guard.Evidence.objects.filter',side_effect=AssertionError('must not lookup')):
            with self.assertRaises(PermissionDenied):readable(f['a'],f['c'],{'planning_packet_id':f['packet'].pk})

    def test_source_permission_revoked_before_projection(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['a'],action__startswith='approval.source.read:').update(active=False)
        with self.assertRaises(PermissionDenied):self.check()
        with self.assertRaises(PermissionDenied):planning.prepare(f['a'],f['c'].pk,f['packet'].pk)

    def test_actor_prepare_revoked_is_held_without_effect(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['a'],action='planning.prepare').update(active=False)
        before=self.counts();self.assertEqual(self.check()['state'],'HELD');self.assertEqual(before,self.counts())
        with self.assertRaises(PermissionDenied):planning.prepare(f['a'],f['c'].pk,f['packet'].pk)

    def test_stale_alignment_is_native_hold(self):
        f=self.f
        future=timezone.now()+timedelta(days=365)
        with patch('apps.pmo.planning.timezone.now',return_value=future):
            self.assertEqual(self.check()['state'],'HELD')
            with self.assertRaises(ValidationError):planning.prepare(f['a'],f['c'].pk,f['packet'].pk)

    def test_missing_criteria_is_native_hold(self):
        f=self.f;p,_=planning.criteria(f['c']);transition(f['a'],p.pk,'revoked')
        self.assertEqual(self.check()['state'],'HELD')
        with self.assertRaises(ValidationError):planning.prepare(f['a'],f['c'].pk,f['packet'].pk)

    def test_stale_revision_and_foreign_case_are_not_ready(self):
        f=self.f;self.assertEqual(self.check(expected_revision=999999)['state'],'HELD')
        other=fixture(username='preview-other')
        with self.assertRaises(PermissionDenied):self.check(planning_packet_id=other['packet'].pk)

    def test_projection_has_no_packet_body_contacts_or_notes(self):
        result=self.check()
        self.assertNotIn('payload',result['head']['planning_readiness'])
        self.assertEqual(set(result['head']['planning_readiness']),{'packet_id','packet_sha256'})
        self.assertNotIn('source_reference',str(result))

    def test_source_owner_revocation_invalidates_observation(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='approval.verify').update(active=False)
        self.assertEqual(self.check()['state'],'HELD')
        with self.assertRaises(PermissionDenied):planning.prepare(f['a'],f['c'].pk,f['packet'].pk)

    def test_successor_correlation_does_not_reuse_old_observations(self):
        f=self.f;payload=deepcopy(f['payload'])
        successor=planning.capture(f['a'],f['c'].pk,payload,f['packet'].pk)
        self.assertEqual(self.check(planning_packet_id=successor.pk)['state'],'HELD')
        with self.assertRaises(ValidationError):planning.prepare(f['a'],f['c'].pk,successor.pk)

    def test_revoked_later_source_not_hidden_by_earlier_stale_observation(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='approval.verify').update(active=False)
        keys=list(planning.SUBJECTS);last=keys[-1]
        Grant.objects.filter(case=f['c'],user=f['a'],action='approval.source.read:synthetic-planning-'+last).update(active=False)
        with self.assertRaises(PermissionDenied):self.check()

    def test_foreign_tenant_packet_denied_with_grants_on_both_cases(self):
        from apps.core.models import Case
        from apps.core.services import add_evidence
        f=self.f;c=Case.objects.create(tenant='other-synthetic-tenant',title='Other test',kind='project',synthetic=True)
        Grant.objects.bulk_create([Grant(case=c,user=f['a'],action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        e=add_evidence(f['a'],c.pk,'planning_packet','Untrusted other tenant source; not readiness','synthetic:scope-negative')
        with self.assertRaises(PermissionDenied):self.check(planning_packet_id=e.pk)

    def binding(self):
        from apps.policy import pilot
        from tests.test_pilot_preflight import selection
        from tests.test_document_guard import payload
        f=self.f;a,c=f['a'],f['c'];value=selection(a,c)
        value['operations']=['planning.readiness'];value['participants']=[{'user_id':a.pk,'actions':['planning.prepare']}]
        contract=pilot.configure(a,c.pk,value)
        selected=payload(a,c,type('Subject',(),{'pk':1})());selected['guards']=[self.selection()]
        return contract,selected

    def test_real_private_packet_binding_and_id_only_form(self):
        from apps.policy import pilot_bindings
        from apps.policy.pilot_binding_views import BindingForm
        f=self.f;contract,value=self.binding()
        row=pilot_bindings.configure(f['a'],f['c'].pk,contract.pk,value)
        self.assertEqual(set(row.payload['guards'][0]['arguments']),{'expected_revision','planning_packet_id'})
        form=BindingForm(f['a'],contract)
        self.assertIn(f['packet'].pk,list(form.fields['planning_packet_id'].queryset.values_list('pk',flat=True)))
        self.assertEqual(form.fields['planning_packet_id'].label_from_instance(f['packet']),'#'+str(f['packet'].pk))
        from apps.policy import pilot
        from apps.agents.pilot import investigate
        observation=pilot.capture(f['a'],f['c'].pk,contract.pk)
        agent=investigate(f['a'],f['c'].pk,observation.pk)
        self.assertEqual(agent['effect_tools'],[])
        self.assertNotIn('Explicit synthetic source-backed target declaration',str(agent))
        self.assertNotIn(f['packet'].body,str(agent))
        Grant.objects.filter(case=f['c'],user=f['a'],action__startswith='approval.source.read:').update(active=False)
        self.assertFalse(BindingForm(f['a'],contract).fields['planning_packet_id'].queryset.exists())

    def test_closed_binding_schema_rejects_raw_note_and_malformed_ids(self):
        from apps.policy.pilot_binding_validators import validate
        contract,value=self.binding()
        for key,item in [('note','private note must not persist'),('planning_packet_id',True),('planning_packet_id',None),('planning_packet_id',1.5)]:
            invalid=deepcopy(value);invalid['guards'][0]['arguments'][key]=item
            with self.assertRaises(ValidationError):validate(contract,invalid)
        invalid=deepcopy(value);del invalid['guards'][0]['arguments']['planning_packet_id']
        with self.assertRaises(ValidationError):validate(contract,invalid)

    def test_sql_variant_rejects_null_missing_fraction_and_foreign_packet(self):
        from django.db import transaction,DatabaseError
        from apps.policy.models import PilotBinding
        from apps.documents.contracts import digest
        from tests.helpers import setup_case
        from apps.core.services import add_evidence
        f=self.f;contract,value=self.binding();a,c=setup_case(username='sql-foreign-planning')
        other=add_evidence(a,c.pk,'planning_packet','Untrusted foreign scope test only','synthetic:sql')
        invalids=[]
        for item in [None,True,1.5,other.pk]:
            v=deepcopy(value);v['guards'][0]['arguments']['planning_packet_id']=item;invalids.append(v)
        v=deepcopy(value);del v['guards'][0]['arguments']['planning_packet_id'];invalids.append(v)
        for invalid in invalids:
            with self.assertRaises(DatabaseError),transaction.atomic():
                PilotBinding.objects.create(contract=contract,actor=f['a'],payload=invalid,sha256=digest(invalid))
        self.assertFalse(PilotBinding.objects.filter(contract=contract).exists())
