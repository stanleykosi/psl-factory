"""794 native definitions only; runtime separately reviewed after793 acceptance."""
import copy,json
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Evidence,Audit
from apps.core.services import add_evidence,event
from apps.identity.models import Grant
from apps.policy import impact
from apps.policy.services import active_component
from apps.pmo import planning
from apps.pmo.models import Baseline
from adapters import policy_impact as adapter,planning_comparison_impact as projection
from . import planning_helpers as h
from .helpers import rev,activate

KEY=projection.KEY

def comparison_fixture(username='impact794'):
    from apps.pmo.services import decide,sign_baseline
    from tests.signature_helpers import packet_for
    f=h.fixture(username=username);h.observe(f);a,c,e=f['a'],f['c'],f['e']
    for role in ['PM','Head of PMO','CEO','PMO Lead']:decide(a,c.pk,role,rev(c))
    packet_for(a,c,e);sign_baseline(a,c.pk,e['signature'].pk,rev(c))
    f['rules']=copy.deepcopy(f['rules']);f['rules'].update(comparison_reviewer_id=f['owners']['scope'].pk,comparison_reviewer_role='Product Owner')
    policy=h.criteria(f,f['rules']);authority=active_component(projection.AUTHORITY,c)
    proof=h.evidence(f,'planning_comparison_evidence','Private comparison source sentinel794')
    comparison=planning.compare(f['owners']['scope'],c.pk,f['packet'].pk,'no_difference',proof.pk)
    return f,policy,authority,proof,comparison

class PlanningComparisonImpactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f,cls.policy,cls.authority,cls.proof,cls.comparison=comparison_fixture()
    def page(self,policy=None):return impact.page(self.f['a'],self.f['c'].pk,(policy or self.policy).pk,KEY)
    def rows(self):return list(Evidence.objects.order_by('pk').values()),list(Audit.objects.order_by('pk').values()),list(Baseline.objects.values()),rev(self.f['c'])
    def successor(self):return h.criteria(self.f,copy.deepcopy(self.f['rules']))
    def assessment(self):
        f=self.f;new=self.successor();return impact.capture(f['a'],f['c'].pk,self.policy.pk,new.pk,[KEY],f['e']['policy_decision'].pk,'Comparison metadata only')
    def forged(self,value,provenance=True):
        f=self.f;row=add_evidence(f['a'],f['c'].pk,planning.KINDS['comparison'],json.dumps(value,sort_keys=True,separators=(',',':')),'psl:planning-v1')
        if provenance:event(f['a'],f['c'],'planning.recorded',kind='comparison',evidence_id=row.pk,sha256=row.sha256)
        return row
    def test_exact_d11_and_d05_pins_metadata_and_no_write(self):
        before=self.rows()
        for policy in [self.policy,self.authority]:
            records=self.page(policy)['records'];self.assertEqual([r['id'] for r in records],[self.comparison.pk]);self.assertTrue(records[0]['native_current'])
            self.assertFalse(records[0]['business_approval']);self.assertFalse(records[0]['contract_renewed']);self.assertFalse(records[0]['effects_performed'])
            self.assertNotIn(self.comparison.body,str(records));self.assertNotIn('Private comparison source sentinel794',str(records))
        self.assertEqual(before,self.rows())
    def test_criteria_successor_retains_old_match_and_marks_noncurrent(self):
        newer=self.successor();self.assertFalse(self.page()['records'][0]['native_current']);self.assertFalse(self.page(newer)['records'])
    def test_authority_successor_retains_historical_pin(self):
        f=self.f;refs=list(f['c'].registeredreference_set.filter(schema_ref='schema:psl/role-assignment/v1').values_list('ref',flat=True))
        activate(f['a'],f['c'],projection.AUTHORITY,refs,f['e']['policy_decision'])
        self.assertFalse(self.page(self.authority)['records'][0]['native_current'])
    def test_domain_and_signed_artifact_grants_precede_lookup(self):
        f=self.f
        for action in ['planning.read','approval.read','commercial.read','document.read']:
            Grant.objects.filter(case=f['c'],user=f['a'],action=action).update(active=False)
            with patch.object(adapter,'query',side_effect=AssertionError('No private query')):
                with self.assertRaises(PermissionDenied):self.page()
            Grant.objects.filter(case=f['c'],user=f['a'],action=action).update(active=True)
    def test_source_grant_checked_even_after_criteria_stale(self):
        f=self.f;self.successor();Grant.objects.filter(case=f['c'],user=f['a'],action='approval.source.read:synthetic-planning-estimates').update(active=False)
        with self.assertRaises(PermissionDenied):self.page()
    def test_creator_revocation_yields_historical_metadata(self):
        f=self.f;Grant.objects.filter(case=f['c'],user=f['owners']['scope'],action='planning.compare').update(active=False)
        self.assertFalse(self.page()['records'][0]['native_current'])
    def test_new_comparison_does_not_make_older_one_current(self):
        f=self.f;new=planning.compare(f['owners']['scope'],f['c'].pk,f['packet'].pk,'no_difference',self.proof.pk)
        rows={r['id']:r for r in self.page()['records']};self.assertFalse(rows[self.comparison.pk]['native_current']);self.assertTrue(rows[new.pk]['native_current'])
    def test_unresolved_difference_retained_without_new_authority(self):
        f=self.f;new=planning.compare(f['owners']['scope'],f['c'].pk,f['packet'].pk,'difference_unresolved',self.proof.pk)
        records=self.page()['records'];self.assertIn(new.pk,[r['id'] for r in records]);self.assertTrue(all(not r['native_current'] for r in records))
    def test_unscoped_unrelated_and_cross_case_are_not_matches(self):
        from .helpers import setup_case
        with self.assertRaises(PermissionDenied):adapter.query(self.policy,KEY)
        a,c=setup_case(username='impact794-foreign')
        with self.assertRaises(ValidationError):projection.parse(c,self.comparison)
        with self.assertRaises(PermissionDenied):adapter.query(self.policy,KEY,actor=a)
        from apps.policy.signature_validators import COMPONENT as SIGNATURE_COMPONENT
        other=active_component(SIGNATURE_COMPONENT,self.f['c'])
        with patch.object(projection,'parse',side_effect=AssertionError('No unrelated parse')):self.assertFalse(adapter.query(other,KEY,actor=self.f['a']).exists())
    def test_closed_numeric_shape_and_provenance_required(self):
        value=json.loads(self.comparison.body);value['policy_id']=str(self.policy.pk)
        with self.assertRaises(ValidationError):projection.parse(self.f['c'],self.forged(value))
        row=self.forged(json.loads(self.comparison.body),False)
        with self.assertRaisesMessage(ValidationError,'Native comparison provenance required'):projection.parse(self.f['c'],row)
    def test_hash_packet_and_signed_artifact_identity_holds(self):
        f=self.f;value=json.loads(self.comparison.body);value['packet_sha256']='0'*64
        with self.assertRaisesMessage(ValidationError,'Exact historical comparison packet hash required'):projection.authorize_row(f['a'],f['c'],self.forged(value))
        value=json.loads(self.comparison.body);value['sow_id']=f['packet'].pk
        with self.assertRaises(ValidationError):projection.authorize_row(f['a'],f['c'],self.forged(value))
    def test_bounded_scan_and_body_size(self):
        with patch.object(projection,'MAX_CANDIDATES',0),patch.object(projection,'parse',side_effect=AssertionError('No oversized scan')):
            with self.assertRaises(ValidationError):self.page()
        with patch.object(projection,'MAX_TOTAL_CHARACTERS',len(self.comparison.body)-1),patch.object(projection,'parse',side_effect=AssertionError('No oversized body load')):
            with self.assertRaises(ValidationError):self.page()
        with patch.object(projection,'MAX_BODY_BYTES',len(self.comparison.body.encode())-1):
            with self.assertRaises(ValidationError):projection.parse(self.f['c'],self.comparison)
    def test_assessment_review_agent_and_choices_are_scoped(self):
        from apps.agents.policy_impact import investigate
        from apps.policy.impact_views import choices
        from django.contrib.auth import get_user_model
        f=self.f;row=self.assessment();before=self.rows();user=get_user_model().objects.create_user(username='impact794-reviewer')
        Grant.objects.bulk_create([Grant(case=f['c'],user=user,action=g.action) for g in Grant.objects.filter(case=f['c'],user=f['a'])])
        impact.review(user,f['c'].pk,row.pk,'accept',f['e']['policy_decision'].pk,'Independent metadata review')
        result=investigate(user,f['c'].pk,row.pk);self.assertFalse(result['business_approval']);self.assertEqual(result['effect_tools'],[]);self.assertNotIn(self.comparison.body,str(result))
        self.assertEqual(before[0],self.rows()[0]);self.assertEqual(before[2],self.rows()[2]);self.assertIn(KEY,dict(choices(user,f['c'])))
        Grant.objects.filter(case=f['c'],user=user,action='document.read').update(active=False)
        self.assertNotIn(KEY,dict(choices(user,f['c'])))
        with self.assertRaises(PermissionDenied):investigate(user,f['c'].pk,row.pk)
    def test_sql_rejects_unregistered_variant(self):
        from django.db import DatabaseError,transaction
        from apps.policy.models import ImpactAssessment
        row=self.assessment()
        with self.assertRaises(DatabaseError),transaction.atomic():
            ImpactAssessment.objects.create(previous=row.previous,successor=row.successor,adapters=[KEY+'.unknown'],observation=row.observation,sha256=row.sha256,evidence=row.evidence,reason='Unknown variant',operation_key='f'*64,actor=row.actor)

    def test_native_packet_successor_stales_saved_assessment(self):
        f=self.f;row=self.assessment();self.assertTrue(impact.inspect(f['a'],f['c'].pk,row.pk)['current'])
        planning.capture(f['a'],f['c'].pk,copy.deepcopy(f['payload']),predecessor=f['packet'].pk)
        self.assertFalse(impact.inspect(f['a'],f['c'].pk,row.pk)['current'])
    def test_exact_byte_and_aggregate_budget_boundaries(self):
        size=len(self.comparison.body.encode());before=self.rows()
        with patch.object(projection,'MAX_BODY_BYTES',size):self.assertEqual(projection.parse(self.f['c'],self.comparison)['policy_id'],self.policy.pk)
        with patch.object(projection,'MAX_BODY_BYTES',size-1):
            with self.assertRaises(ValidationError):projection.parse(self.f['c'],self.comparison)
        chars=len(self.comparison.body)
        with patch.object(projection,'MAX_TOTAL_CHARACTERS',chars):self.assertEqual(self.page()['records'][0]['id'],self.comparison.pk)
        with patch.object(projection,'MAX_TOTAL_CHARACTERS',chars-1),patch.object(projection,'parse',side_effect=AssertionError('No over-budget parse')):
            with self.assertRaises(ValidationError):self.page()
        self.assertEqual(before,self.rows())
    def test_malformed_json_and_content_hash_mismatch(self):
        f=self.f;row=add_evidence(f['a'],f['c'].pk,planning.KINDS['comparison'],'{','psl:planning-v1')
        event(f['a'],f['c'],'planning.recorded',kind='comparison',evidence_id=row.pk,sha256=row.sha256)
        with self.assertRaisesMessage(ValidationError,'Closed historical comparison metadata required'):projection.parse(f['c'],row)
        # Unsaved tampered instance: immutable stored history is never rewritten.
        row.body='{}'
        with self.assertRaisesMessage(ValidationError,'Bounded immutable comparison content required'):projection.parse(f['c'],row)
        self.assertEqual(Evidence.objects.get(pk=row.pk).body,'{')
    def test_saved_assessment_agent_requires_current_document_and_source_grants(self):
        from apps.agents.policy_impact import investigate
        f=self.f;row=self.assessment()
        for action in ['document.read','approval.source.read:synthetic-planning-estimates']:
            Grant.objects.filter(case=f['c'],user=f['a'],action=action).update(active=False)
            for reader in [impact.inspect,investigate]:
                with self.assertRaises(PermissionDenied):reader(f['a'],f['c'].pk,row.pk)
            Grant.objects.filter(case=f['c'],user=f['a'],action=action).update(active=True)
