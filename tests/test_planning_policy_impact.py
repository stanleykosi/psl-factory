"""Bounded793 native cases; source candidate, native execution separately cleared."""
import copy,hashlib,json
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Evidence,Audit
from apps.core.services import add_evidence,event
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.services import active_component
from apps.pmo import planning
from adapters import policy_impact as adapter,planning_policy_impact as projection
from . import planning_helpers as h
from .helpers import rev,setup_case

KEY=projection.KEY
class PlanningPolicyImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=h.fixture(username='impact793');h.observe(cls.f)
        cls.ready=planning.prepare(cls.f['a'],cls.f['c'].pk,cls.f['packet'].pk)
        cls.policy=active_component(projection.COMPONENT,cls.f['c'])

    def page(self):return impact.page(self.f['a'],self.f['c'].pk,self.policy.pk,KEY)
    def successor(self):return h.criteria(self.f,copy.deepcopy(self.f['rules']))
    def assessment(self):
        f=self.f;new=self.successor()
        return impact.capture(f['a'],f['c'].pk,self.policy.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Bounded planning metadata reassessment')
    def rows(self):return list(Evidence.objects.order_by('pk').values()),list(Audit.objects.order_by('pk').values()),rev(self.f['c'])

    def test_exact_direct_policy_pin_and_metadata_no_writes(self):
        before=self.rows();row=self.page()['records'][0]
        self.assertEqual(row['id'],self.ready.pk);self.assertTrue(row['native_current'])
        self.assertFalse(row['business_approval']);self.assertFalse(row['native_verified']);self.assertFalse(row['effects_performed'])
        self.assertNotIn(self.ready.body,str(row));self.assertNotIn('source_correlation',str(row));self.assertNotIn('alignment_links',str(row))
        self.assertEqual(before,self.rows())
        self.assertFalse(adapter.query(self.successor(),KEY,actor=self.f['a']).exists())

    def test_policy_successor_stales_without_renewing_readiness(self):
        self.successor();before=self.rows();self.assertFalse(self.page()['records'][0]['native_current'])
        self.assertEqual(before,self.rows())

    def test_domain_permission_before_readiness_lookup(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['a'],action='planning.read').update(active=False)
        with patch.object(projection.Evidence.objects,'filter',side_effect=AssertionError('Forbidden evidence lookup')):
            with self.assertRaises(PermissionDenied):self.page()

    def test_source_permission_before_projection_of_stale_readiness(self):
        f=self.f;row=self.assessment()
        Grant.objects.filter(case=f['c'],user=f['a'],action='approval.source.read:synthetic-planning-estimates').update(active=False)
        with patch.object(planning,'current_readiness',side_effect=AssertionError('Currentness before observer access')):
            with self.assertRaises(PermissionDenied):self.page()
            with self.assertRaises(PermissionDenied):impact.inspect(f['a'],f['c'].pk,row.pk)

    def test_unscoped_query_and_foreign_case_rejected(self):
        f=self.f
        with self.assertRaises(PermissionDenied):adapter.query(self.policy,KEY)
        a,c=setup_case(username='impact793-other')
        with self.assertRaises(ValidationError):projection.parse(c,self.ready)
        with self.assertRaises(PermissionDenied):adapter.query(self.policy,KEY,actor=a)

    def test_current_creator_revocation_yields_historical_metadata(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['a'],action='planning.prepare').update(active=False)
        self.assertFalse(self.page()['records'][0]['native_current'])

    def test_native_packet_successor_stales_existing_assessment(self):
        f=self.f;row=self.assessment();self.assertTrue(impact.inspect(f['a'],f['c'].pk,row.pk)['current'])
        planning.capture(f['a'],f['c'].pk,copy.deepcopy(f['payload']),predecessor=f['packet'].pk)
        self.assertFalse(impact.inspect(f['a'],f['c'].pk,row.pk)['current'])

    def forged(self,value,provenance=True):
        f=self.f;body=json.dumps(value,sort_keys=True,separators=(',',':'))
        row=add_evidence(f['a'],f['c'].pk,planning.KINDS['ready'],body,'psl:planning-v1')
        if provenance:event(f['a'],f['c'],'planning.recorded',kind='ready',evidence_id=row.pk,sha256=row.sha256)
        return row

    def test_malformed_or_unprovenanced_candidate_is_not_silently_omitted(self):
        row=self.forged(json.loads(self.ready.body),False)
        with self.assertRaisesMessage(ValidationError,'Native readiness provenance required'):self.page()
        self.assertTrue(Evidence.objects.filter(pk=row.pk).exists())

    def test_closed_shape_and_exact_numeric_policy_pin(self):
        value=json.loads(self.ready.body);value['inputs']['policy_id']=str(self.policy.pk)
        row=self.forged(value)
        with self.assertRaisesMessage(ValidationError,'Closed historical readiness metadata required'):projection.parse(self.f['c'],row)

    def test_budget_holds_before_any_body_parsing(self):
        with patch.object(projection,'MAX_CANDIDATES',0),patch.object(projection,'parse',side_effect=AssertionError('Body parser must not run')):
            with self.assertRaisesMessage(ValidationError,'Readiness history exceeds bounded metadata budget'):self.page()

    def test_real_review_agent_and_choices_remain_domain_scoped(self):
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        f=self.f;row=self.assessment();before=Evidence.objects.filter(kind=planning.KINDS['ready']).count()
        user=get_user_model().objects.create_user(username='impact793-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=user,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        impact.review(user,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Review metadata only')
        result=investigate(user,f['c'].pk,row.pk)
        self.assertEqual(result['effect_tools'],[]);self.assertFalse(result['business_approval']);self.assertNotIn(self.ready.body,str(result))
        self.assertEqual(before,Evidence.objects.filter(kind=planning.KINDS['ready']).count())
        self.assertIn(KEY,dict(choices(user,f['c'])));self.assertTrue(reverse('planning',args=[f['c'].pk]))
        Grant.objects.filter(case=f['c'],user=user,action='planning.read').update(active=False)
        self.assertNotIn(KEY,dict(choices(user,f['c'])))
        with self.assertRaises(PermissionDenied):investigate(user,f['c'].pk,row.pk)

    def test_unrelated_policy_does_not_parse_or_match_readiness(self):
        f=self.f;other=active_component('D05.role_principal_assignments',f['c'])
        with patch.object(projection,'parse',side_effect=AssertionError('Unrelated component must not parse bodies')):
            self.assertFalse(adapter.query(other,KEY,actor=f['a']).exists())

    def test_malformed_json_or_wrong_packet_hash_stays_a_hold(self):
        f=self.f;row=add_evidence(f['a'],f['c'].pk,planning.KINDS['ready'],'{','psl:planning-v1')
        event(f['a'],f['c'],'planning.recorded',kind='ready',evidence_id=row.pk,sha256=row.sha256)
        with self.assertRaisesMessage(ValidationError,'Closed historical readiness metadata required'):projection.parse(f['c'],row)
        value=json.loads(self.ready.body);value['packet_sha256']='0'*64;wrong=self.forged(value)
        with self.assertRaisesMessage(ValidationError,'Exact historical planning packet hash required'):
            projection.authorize_row(f['a'],f['c'],wrong)

    def test_sql_does_not_accept_unregistered_variant(self):
        from django.db import DatabaseError,transaction
        from apps.policy.models import ImpactAssessment
        f=self.f;existing=self.assessment()
        with self.assertRaises(DatabaseError),transaction.atomic():
            ImpactAssessment.objects.create(previous=existing.previous,successor=existing.successor,
                adapters=['pmo.planning_readiness.unregistered'],observation=existing.observation,
                sha256=existing.sha256,evidence=existing.evidence,reason='Unknown variant rejected',
                operation_key='f'*64,actor=f['a'])

    def test_body_byte_budget_boundary_retains_original_history(self):
        size=len(self.ready.body.encode());before=self.rows()
        with patch.object(projection,'MAX_BODY_BYTES',size):
            self.assertEqual(projection.parse(self.f['c'],self.ready)['inputs']['policy_id'],self.policy.pk)
        with patch.object(projection,'MAX_BODY_BYTES',size-1):
            with self.assertRaisesMessage(ValidationError,'Bounded immutable readiness content required'):
                projection.parse(self.f['c'],self.ready)
        self.assertEqual(before,self.rows())

    def test_aggregate_character_budget_boundary_precedes_body_parse(self):
        size=len(self.ready.body);before=self.rows()
        with patch.object(projection,'MAX_TOTAL_CHARACTERS',size):
            self.assertEqual(self.page()['records'][0]['id'],self.ready.pk)
        with patch.object(projection,'MAX_TOTAL_CHARACTERS',size-1),patch.object(projection,'parse',side_effect=AssertionError('Must not parse over budget')):
            with self.assertRaisesMessage(ValidationError,'Readiness history exceeds bounded metadata budget'):self.page()
        self.assertEqual(before,self.rows())

    def test_correct_source_wrong_hash_and_wrong_kind_or_source_rejected(self):
        f=self.f
        row=Evidence.objects.create(case=f['c'],kind=planning.KINDS['ready'],source='psl:planning-v1',
            body=self.ready.body,sha256='0'*64,created_by=f['a'],version=self.ready.version+1)
        event(f['a'],f['c'],'planning.recorded',kind='ready',evidence_id=row.pk,sha256=row.sha256)
        with self.assertRaisesMessage(ValidationError,'Bounded immutable readiness content required'):projection.parse(f['c'],row)
        for kind,source in [('requirements','psl:planning-v1'),(planning.KINDS['ready'],'untrusted:not-native')]:
            wrong=add_evidence(f['a'],f['c'].pk,kind,self.ready.body,source)
            event(f['a'],f['c'],'planning.recorded',kind='ready',evidence_id=wrong.pk,sha256=wrong.sha256)
            with self.assertRaisesMessage(ValidationError,'Exact native readiness evidence required'):projection.parse(f['c'],wrong)
        self.assertTrue(Evidence.objects.filter(pk=row.pk,sha256='0'*64).exists())
