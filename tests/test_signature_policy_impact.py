from copy import deepcopy,copy
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied,ValidationError
from django.apps import apps
from apps.identity.models import Grant
from apps.policy.services import active_component
from apps.policy.signature_validators import COMPONENT
from apps.policy import impact
from apps.pmo import signatures
from apps.pmo.models import CommercialSignaturePacket,CommercialSignatureUse,CommercialSignatureReaffirmation,BaselineAdoption,RFPCase
from adapters import policy_impact as adapter
from adapters.signature_policy_impact import KEY,AUTHORITY,project
from tests.helpers import setup_case,prepared,signed,activate
from tests.signature_helpers import packet_for,contract

class SignaturePolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a,cls.c=setup_case(username='impact799');cls.e=prepared(cls.a,cls.c)
        cls.packet=packet_for(cls.a,cls.c,cls.e);cls.config=active_component(COMPONENT,cls.c)
        if (CommercialSignatureUse.objects.filter(packet__case=cls.c).exists()
            or CommercialSignatureReaffirmation.objects.filter(packet__case=cls.c).exists()
            or BaselineAdoption.objects.filter(revision__dossier__case=cls.c).exists()
            or RFPCase.objects.filter(case=cls.c).exists()):
            raise AssertionError('Fresh packet fixture must not consume/adopt/reaffirm/convert')
    def facts(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()
            if m._meta.app_label in ('pmo','core','documents','finance','workflows')}
    def successor(self):
        contract(self.a,self.c,self.e['policy_decision']);return active_component(COMPONENT,self.c)
    def capture(self):
        new=self.successor()
        return impact.capture(self.a,self.c.pk,self.config.pk,new.pk,[KEY],self.e['policy_decision'].pk,'Original packet policy metadata')
    def test_exact_direct_fks_closed_projection_no_effects(self):
        before=self.facts()
        for component in (COMPONENT,AUTHORITY):
            self.assertEqual(list(adapter.query(active_component(component,self.c),KEY,actor=self.a)),[self.packet])
        value=project(self.packet);self.assertTrue(value['packet_policy_valid_now'])
        self.assertEqual(set(value),{'id','kind','metadata_only','domain_route','revision','policy','authority','packet_sha256','packet_policy_valid_now','state','signature_authenticity_verified','signing_authorized','effects_performed'})
        self.assertFalse(value['signing_authorized']);self.assertFalse(value['signature_authenticity_verified'])
        self.assertEqual(before,self.facts())
    def test_null_contract_preparation_matches_only_authority(self):
        a,c=setup_case(username='impact799-missing');e=prepared(a,c);row=packet_for(a,c,e,configure=False)
        self.assertIsNone(row.policy_id);self.assertFalse(project(row)['packet_policy_valid_now'])
        self.assertEqual(list(adapter.query(active_component(AUTHORITY,c),KEY,actor=a)),[row])
        contract(a,c,e['policy_decision']);config=active_component(COMPONENT,c)
        self.assertFalse(adapter.query(config,KEY,actor=a).exists());self.assertFalse(project(row)['packet_policy_valid_now'])
    def test_same_component_cross_case_dual_grants_and_wrong_component(self):
        a,c=setup_case(username='impact799-other');e=prepared(a,c);row=packet_for(a,c,e)
        Grant.objects.bulk_create([Grant(case=c,user=self.a,action=g.action) for g in Grant.objects.filter(case=c,user=a)])
        self.assertEqual(list(adapter.query(active_component(COMPONENT,c),KEY,actor=self.a)),[row])
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.a)),[self.packet])
        with self.assertRaises(PermissionDenied):adapter.authorize_row(self.a,c,KEY,self.packet)
        unrelated=copy(self.config);unrelated.component='D11.hypercare_criteria_ref'
        self.assertFalse(adapter.query(unrelated,KEY,actor=self.a).exists())
    def test_minimal_observer_not_signing_principal(self):
        from django.contrib.auth import get_user_model
        reader=get_user_model().objects.create_user(username='impact799-reader')
        for action in ('case.read','commercial.read'):Grant.objects.create(case=self.c,user=reader,action=action)
        before=self.facts();adapter.authorize_row(reader,self.c,KEY,self.packet)
        self.assertEqual(list(adapter.query(self.config,KEY,actor=reader)),[self.packet])
        self.assertTrue(project(self.packet)['packet_policy_valid_now']);self.assertEqual(before,self.facts())
    def test_missing_inactive_observer_denied_before_lookup(self):
        for action in ('case.read','commercial.read'):
            grant=Grant.objects.get(user=self.a,case=self.c,action=action);grant.active=False;grant.save()
            with patch('adapters.signature_policy_impact.CommercialSignaturePacket.objects.filter',side_effect=AssertionError('lookup')):
                with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY,actor=self.a)
            grant.active=True;grant.save()
        self.a.is_active=False;self.a.save()
        with patch('adapters.signature_policy_impact.CommercialSignaturePacket.objects.filter',side_effect=AssertionError('lookup')):
            with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY,actor=self.a)
            with self.assertRaises(PermissionDenied):adapter.query(self.config,KEY)
    def test_original_recorder_grants_revoked_history_remains(self):
        for action in ('commercial.response','baseline.sign'):
            grant=Grant.objects.get(user=self.a,case=self.c,action=action);grant.active=False;grant.save()
            before=self.facts();self.assertFalse(project(self.packet)['packet_policy_valid_now'])
            self.assertEqual(list(adapter.query(self.config,KEY,actor=self.a)),[self.packet]);self.assertEqual(before,self.facts())
            grant.active=True;grant.save()
    def test_authority_successor_invalidates_selected_original_packet(self):
        authority=active_component(AUTHORITY,self.c);activate(self.a,self.c,AUTHORITY,active_component(AUTHORITY,self.c).envelope['value'],self.e['policy_decision'])
        before=self.facts();self.assertFalse(project(self.packet)['packet_policy_valid_now'])
        self.assertEqual(list(adapter.query(authority,KEY,actor=self.a)),[self.packet]);self.assertEqual(before,self.facts())
    def test_contract_successor_invalidates_but_preserves_old_pin(self):
        new=self.successor();before=self.facts()
        self.assertFalse(project(self.packet)['packet_policy_valid_now']);self.assertFalse(adapter.query(new,KEY,actor=self.a).exists())
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.a)),[self.packet]);self.assertEqual(before,self.facts())
    def test_consumed_packet_policy_validity_is_not_fresh_signing(self):
        a,c=setup_case(username='impact799-consumed');signed(a,c)
        use=CommercialSignatureUse.objects.get(packet__case=c);row=use.packet
        self.assertFalse(CommercialSignatureReaffirmation.objects.filter(packet__case=c).exists())
        self.assertFalse(BaselineAdoption.objects.filter(revision__dossier__case=c).exists())
        self.assertFalse(RFPCase.objects.filter(case=c).exists())
        before=self.facts();value=project(row)
        self.assertTrue(value['packet_policy_valid_now']);self.assertFalse(value['signing_authorized'])
        self.assertEqual(list(adapter.query(row.policy,KEY,actor=a)),[row]);self.assertEqual(before,self.facts())
    def test_latest_packet_and_changed_unsigned_source_do_not_relabel_policy_validity(self):
        from apps.core.services import add_evidence
        add_evidence(self.a,self.c.pk,'prd','New synthetic unsigned PRD','synthetic:impact799')
        newer=packet_for(self.a,self.c,self.e)
        self.assertEqual(newer.predecessor_id,self.packet.pk)
        before=self.facts();self.assertTrue(project(self.packet)['packet_policy_valid_now'])
        self.assertTrue(project(newer)['packet_policy_valid_now'])
        self.assertEqual(list(adapter.query(self.config,KEY,actor=self.a)),[self.packet,newer]);self.assertEqual(before,self.facts())
    def test_unverified_native_packet_and_detached_malformed_metadata_are_generic(self):
        refs=deepcopy(self.packet.signatures)
        for v in refs.values():v['human_verified']=False
        row=packet_for(self.a,self.c,self.e,signatures=refs)
        self.assertFalse(project(row)['packet_policy_valid_now'])
        detached=copy(row);detached.signatures={'PRIVATE':'not typed'}
        before=self.facts();value=project(detached);self.assertFalse(value['packet_policy_valid_now'])
        self.assertNotIn('PRIVATE',str(value));self.assertEqual(before,self.facts())
    def test_projection_never_uses_latest_consumption_or_effect_commands(self):
        with patch.object(signatures,'current_packet',side_effect=AssertionError('latest/consumption')),patch.object(signatures,'record_use',side_effect=AssertionError('write')),patch.object(signatures,'reaffirm_baseline',side_effect=AssertionError('reaffirm')),patch.object(signatures,'validate_packet_policy',side_effect=ValidationError('PRIVATE details')):
            value=project(self.packet)
        self.assertFalse(value['packet_policy_valid_now']);self.assertNotIn('PRIVATE',str(value))
    def test_capture_review_agent_privacy_and_saved_reader_revocation(self):
        from django.contrib.auth import get_user_model
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        from scripts.impact795_upgrade_lifecycle import unchanged_except_capture_audit
        new=self.successor();before=self.facts()
        row=impact.capture(self.a,self.c.pk,self.config.pk,new.pk,[KEY],self.e['policy_decision'].pk,'Exact selected packet metadata')
        unchanged_except_capture_audit(before,self.facts(),actor=self.a.pk,case=self.c.pk,assessment=row.pk,previous=self.config.pk,successor=new.pk)
        reader=get_user_model().objects.create_user(username='impact799-reviewer')
        Grant.objects.bulk_create([Grant(case=self.c,user=reader,action=g.action) for g in Grant.objects.filter(case=self.c,user=self.a)])
        before_review=self.facts()
        review=impact.review(reader,self.c.pk,row.pk,'accept',self.e['policy_decision'].pk,'Independent engineering metadata review')
        result=investigate(reader,self.c.pk,row.pk);self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[])
        after_review=self.facts();old_ids={r['id'] for r in before_review['core.Audit']}
        self.assertEqual([r for r in after_review['core.Audit'] if r['id'] in old_ids],before_review['core.Audit'])
        added=[r for r in after_review['core.Audit'] if r['id'] not in old_ids];self.assertEqual(len(added),1)
        self.assertEqual((added[0]['actor_id'],added[0]['case_id'],added[0]['action'],added[0]['data']),
            (reader.pk,self.c.pk,'policy.impact.reviewed',{'assessment':row.pk,'review':review.pk,'verdict':'accept'}))
        expected=dict(before_review);expected['core.Audit']=after_review['core.Audit'];self.assertEqual(expected,after_review)
        for body in (str(row.observation),str(result)):
            for key in ("'sources':","'signatures':","'party_ref':","'locator':","'actor':","'note':","'operation_key':"):
                self.assertNotIn(key,body)
        self.assertIn(KEY,dict(choices(reader,self.c)))
        Grant.objects.filter(case=self.c,user=reader,action='commercial.read').update(active=False)
        for call in (impact.inspect,investigate):
            with self.assertRaises(PermissionDenied):call(reader,self.c.pk,row.pk)
    def test_sql_registry_and_exact_budget_no_partial_capture(self):
        from apps.policy.models import ImpactAssessment
        from apps.policy.impact import digest
        from django.db import transaction,DatabaseError
        with patch.object(impact,'SNAPSHOT_LIMIT',1):row=self.capture()
        self.assertEqual(len(row.observation['domains'][KEY]),1)
        base={k:v for k,v in ImpactAssessment.objects.values().get(pk=row.pk).items() if k not in ('id','created_at')}
        for i,keys in enumerate([[],[KEY,KEY],['pmo.signature_packets.unknown'],[KEY]*25]):
            with self.assertRaises(DatabaseError),transaction.atomic():ImpactAssessment.objects.create(**dict(base,adapters=keys,operation_key=digest(['bad799',i])))
        packet_for(self.a,self.c,self.e)
        # Match the original authority which both packets retain, independent of contract successor.
        old=active_component(AUTHORITY,self.c);activate(self.a,self.c,AUTHORITY,active_component(AUTHORITY,self.c).envelope['value'],self.e['policy_decision']);new=active_component(AUTHORITY,self.c)
        before=ImpactAssessment.objects.count()
        with patch.object(impact,'SNAPSHOT_LIMIT',1),self.assertRaisesMessage(ValidationError,'snapshot exceeds'):
            impact.capture(self.a,self.c.pk,old.pk,new.pk,[KEY],self.e['policy_decision'].pk,'Exact packet budget')
        self.assertEqual(before,ImpactAssessment.objects.count())
